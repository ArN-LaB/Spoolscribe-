"""Validated, atomic storage shared by the application and standalone workers.

No import of core, application settings, or network access here.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from contextlib import contextmanager, ExitStack, redirect_stdout, redirect_stderr
from typing import Callable


class DatabaseError(ValueError):
    """The original file must be preserved and the error shown to the user."""


class SourceUnavailable(RuntimeError):
    """A source could not be checked; this is not a successful refresh."""


class PartialUpdate(RuntimeError):
    """Some work succeeded, but at least one source or item failed."""


def requires_manual_color(entry: dict) -> bool:
    """Leave intentionally non-solid unknown colors for an explicit user choice.

    This only prevents automatic filling; it never assigns alpha or colors.
    """
    name = entry.get("color_name", "")
    return bool(entry.get("additional_color_hexes") or "alpha" in entry or re.search(
        r"\b(transparent|translucent|clear|rainbow|gradient|dual|multicolor|multicolour)\b", name, re.I))


_DARK_NAMES = re.compile(r"black|noir|schwarz|negro|nero|dark|carbon|charcoal|onyx|obsidian|midnight|graphite|"
                         r"jet|ebony|coal|raven|ink|shadow|espresso|galaxy|space|night|anthracite|cf\b|fiber|fibre|"
                         r"matte|matt\b|shadow|smoke|grey|gray|gris|slate|steel|iron|titan|military|army|camo|licorice",
                         re.I)
_LIGHT_NAMES = re.compile(r"white|blanc|weiss|weiß|bianco|blanco|clear|natural|naturel|ivory|cream|snow|milk|pearl|"
                          r"light|pastel|lemon|yellow|jaune|gelb|cyan|pink|rose", re.I)


def _field_is_source_owned(entry: dict, key: str) -> bool:
    """True when the value still comes from a source (never corrected by the user).

    Historical entries without a ``source`` are user-owned by precaution; an
    explicit correction removes the field from ``_field_sources``.
    """
    if not entry.get("source") and "_field_sources" not in entry:
        return False
    provenance = entry.get("_field_sources")
    return provenance is None or key in provenance


def implausible_color(entry: dict) -> str | None:
    """A source HEX that contradicts the color name must be confirmed, not exported.

    Only a flagrant contradiction is reported (black HEX for a light name, or a
    white HEX for a dark name). The HEX is kept; nothing is replaced.
    """
    hx = str(entry.get("hex") or "").upper().removeprefix("#")
    name = str(entry.get("color_name") or "")
    if hx not in ("000000", "FFFFFF") or not name or not _field_is_source_owned(entry, "hex"):
        return None
    if hx == "000000" and _LIGHT_NAMES.search(name) and not _DARK_NAMES.search(name):
        return f"HEX noir pour « {name} »"
    if hx == "FFFFFF" and _DARK_NAMES.search(name) and not _LIGHT_NAMES.search(name):
        return f"HEX blanc pour « {name} »"
    return None


PHYSICAL_PLAUSIBILITY = {"min_temp": (120, 500), "max_temp": (120, 500), "bed_min_temp": (0, 200),
                         "bed_max_temp": (1, 200), "density": (0.5, 4.0), "diameter": (1.0, 3.2)}


def implausible_physical(product: dict) -> list[str]:
    """Source values outside printable ranges; user corrections are trusted."""
    issues = []
    labels = {"min_temp": "buse", "max_temp": "buse", "bed_min_temp": "plateau", "bed_max_temp": "plateau",
              "density": "densité", "diameter": "diamètre"}
    for key, (low, high) in PHYSICAL_PLAUSIBILITY.items():
        value = product.get(key)
        if value is None or type(value) not in (int, float) or not _field_is_source_owned(product, key):
            continue
        if not low <= value <= high:
            detail = "non renseigné (0)" if key == "bed_max_temp" and value == 0 else f"{value} hors plage {low}–{high}"
            issues.append(f"{labels[key]} : {detail}")
    return issues


def default_db_path() -> str:
    """The user's writable database, shared with the application (never the repository)."""
    home = os.environ.get("SPOOLSCRIBE_DATA_HOME")
    if not home:
        if sys.platform.startswith("win"):
            base = os.environ.get("APPDATA") or os.path.expanduser("~")
        elif sys.platform == "darwin":
            base = os.path.expanduser("~/Library/Application Support")
        else:
            base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        home = os.path.join(base, "SpoolScribe")
    return os.path.join(home, "data", "polymaker_db.json")


def check_source_shrink(db: dict, snapshot_key: str, incoming_count: int, label: str) -> None:
    """Refuse a refresh that would silently lose most of a source's references."""
    previous = (db.get("_source_snapshots") or {}).get(snapshot_key) or {}
    before = previous.get("references")
    if isinstance(before, int) and before >= 20 and incoming_count < before * 0.5:
        raise SourceUnavailable(f"{label} : {incoming_count} références reçues contre {before} auparavant ; "
                                "mise à jour refusée par précaution, données locales conservées.")


class Database(dict):
    """A JSON dict with an out-of-band revision to detect stale writers."""
    revision: str | None = None
    source_path: str | None = None


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _constant(value: str):
    raise DatabaseError(f"Nombre JSON non fini : {value}")


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DatabaseError(f"Clé JSON dupliquée : {key}")
        result[key] = value
    return result


def parse_json(data: bytes | str):
    try:
        return json.loads(data, parse_constant=_constant, object_pairs_hook=_object)
    except (ValueError, UnicodeError) as exc:
        raise DatabaseError(f"JSON invalide : {exc}") from exc


def validate_db(db: dict) -> None:
    if not isinstance(db, dict):
        raise DatabaseError("La base doit être un objet JSON.")
    for section in ("_products", "_skus", "_brands"):
        entries = db.get(section, {})
        if not isinstance(entries, dict):
            raise DatabaseError(f"{section} doit être un objet JSON.")
        for key, entry in entries.items():
            if not isinstance(key, str) or not key.strip() or not isinstance(entry, dict):
                raise DatabaseError(f"Entrée invalide dans {section} : {key!r}")
    for sku, entry in db.get("_skus", {}).items():
        if not isinstance(entry.get("product"), str) or not entry["product"].strip():
            raise DatabaseError(f"{sku} : nom de produit absent.")
        if not isinstance(entry.get("color_name", ""), str):
            raise DatabaseError(f"{sku} : nom de couleur invalide.")
        hx = entry.get("hex")
        if hx is not None and (not isinstance(hx, str) or not re.fullmatch(r"#?[0-9a-fA-F]{6}", hx)):
            raise DatabaseError(f"{sku} : HEX invalide ({hx!r}).")
        if "alpha" in entry and (not isinstance(entry["alpha"], str)
                                or not re.fullmatch(r"[0-9a-fA-F]{2}", entry["alpha"])):
            raise DatabaseError(f"{sku} : transparence alpha invalide.")
    for name, product in db.get("_products", {}).items():
        for key in ("min_temp", "max_temp", "bed_min_temp", "bed_max_temp", "diameter", "density"):
            value = product.get(key)
            if value is None:
                continue  # Incomplete products remain visible, but cannot be exported.
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise DatabaseError(f"{name} : {key} invalide ({value!r}).")
            if key in ("diameter", "density") and value == 0:
                raise DatabaseError(f"{name} : {key} doit être positif.")
        for low, high in (("min_temp", "max_temp"), ("bed_min_temp", "bed_max_temp")):
            if product.get(low) is not None and product.get(high) is not None and product[low] > product[high]:
                raise DatabaseError(f"{name} : plage {low}/{high} inversée.")


def load_db(path: str | Path, *, missing_ok: bool = False) -> Database:
    path = Path(path)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        if not missing_ok:
            raise DatabaseError(f"Base absente : {path}") from None
        raw = None
        data = {}
    except OSError as exc:
        raise DatabaseError(f"Lecture impossible : {path} : {exc}") from exc
    else:
        try:
            data = parse_json(raw)
        except DatabaseError as exc:
            raise DatabaseError(f"{path} : {exc}. Sauvegarde éventuelle : {path}.bak") from exc
    validate_db(data)
    db = Database(data)
    for key in ("_products", "_skus", "_brands"):
        db.setdefault(key, {})
    db.revision = _digest(raw) if raw is not None else None
    db.source_path = str(path.resolve())
    return db


def atomic_write(path: str | Path, data: bytes, *, before_replace: Callable[[], None] | None = None) -> None:
    """Write in the destination directory, flush, then replace in one operation."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if before_replace is not None:
            before_replace()
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


STALE_LOCK_SECONDS = 15 * 60


def _lock_is_stale(lock: Path) -> bool:
    """A lock left by a dead or interrupted writer must not block the user forever.

    POSIX checks the recorded PID; elsewhere (Windows has no harmless signal 0)
    only an old lock is considered abandoned.
    """
    try:
        age = time.time() - lock.stat().st_mtime
        pid = int(lock.read_text(encoding="ascii").strip() or 0)
    except (OSError, ValueError):
        return False
    if os.name == "posix" and pid > 0 and pid != os.getpid():
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        return age > STALE_LOCK_SECONDS
    return age > STALE_LOCK_SECONDS


@contextmanager
def _writer_lock(path: Path):
    lock = path.with_name(path.name + ".lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        if _lock_is_stale(lock):
            try:
                lock.unlink()
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except OSError:
                raise DatabaseError(f"Écriture déjà en cours : {lock}. Si un processus a été interrompu, "
                                    "vérifiez qu'il est arrêté avant de retirer ce verrou.") from None
        else:
            raise DatabaseError(f"Écriture déjà en cours : {lock}. Si un processus a été interrompu, "
                                "vérifiez qu'il est arrêté avant de retirer ce verrou.") from None
    identity = os.fstat(fd)
    try:
        os.write(fd, str(os.getpid()).encode("ascii"))
        yield
    finally:
        os.close(fd)
        try:
            current = lock.stat()
            if (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
                lock.unlink()
        except FileNotFoundError:
            pass


def _concurrent_change(path: Path, current: bytes | None) -> None:
    """Retain the detected version, even if it is an unfinished external edit."""
    preserved = None
    if current is not None:
        fd, preserved = tempfile.mkstemp(prefix=path.name + ".concurrent-", dir=path.parent)
        with os.fdopen(fd, "wb") as stream:
            stream.write(current)
            stream.flush()
            os.fsync(stream.fileno())
    detail = f" Copie concurrente conservée : {preserved}." if preserved else " Le fichier a été supprimé."
    raise DatabaseError("La base a changé depuis sa lecture. Rechargez-la avant de sauvegarder." + detail)


def save_db(db: dict, path: str | Path) -> bool:
    """Preserve the last valid revision, reject stale saves, and publish atomically."""
    validate_db(db)
    try:
        raw = json.dumps(db, indent=2, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise DatabaseError(f"Base non sérialisable : {exc}") from exc
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _writer_lock(path):
        old = path.read_bytes() if path.exists() else None
        if isinstance(db, Database) and db.source_path == str(path.resolve()):
            if db.revision != (_digest(old) if old is not None else None):
                _concurrent_change(path, old)
        if old is not None:
            previous = parse_json(old)
            validate_db(previous)  # Never overwrite a corrupt original.
            for section in ("_skus", "_products", "_brands"):
                removed = set(previous.get(section, {})) - set(db.get(section, {}))
                if removed:
                    raise DatabaseError(f"Suppression de données locales refusée dans {section} : "
                                        + ", ".join(sorted(removed)))
            def unresolved(data):
                return {sku for sku, entry in data.get("_skus", {}).items()
                        if entry["product"] not in data.get("_products", {})}
            introduced = unresolved(db) - unresolved(previous)
            if introduced:
                raise DatabaseError("Nouvelles références sans produit : " + ", ".join(sorted(introduced)))
        if old == raw:
            return False
        if old is not None:
            atomic_write(str(path) + ".bak", old)

        def check_revision():
            current = path.read_bytes() if path.exists() else None
            if current != old:
                _concurrent_change(path, current)

        # Recheck after staging/fsync, immediately before replace. An external
        # writer ignoring our lock can still race the check and os.replace.
        atomic_write(path, raw, before_replace=check_revision)
        if isinstance(db, Database):
            db.revision = _digest(raw)
            db.source_path = str(path.resolve())
    return True


def backup_db(path: str | Path) -> Path:
    """Keep the state before the whole update, separate from per-step backups."""
    path = Path(path)
    raw = path.read_bytes()
    validate_db(parse_json(raw))
    destination = Path(str(path) + ".pre-update.bak")
    atomic_write(destination, raw)
    return destination


def restore_db(path: str | Path, backup: str | Path | None = None) -> None:
    """Explicit restoration; retain the replaced bytes, including a corrupt file."""
    path = Path(path)
    source = Path(backup) if backup is not None else Path(str(path) + ".bak")
    raw = source.read_bytes()
    validate_db(parse_json(raw))
    with _writer_lock(path):
        if path.exists():
            fd, preserved = tempfile.mkstemp(prefix=path.name + ".before-restore-", dir=path.parent)
            with os.fdopen(fd, "wb") as stream:
                stream.write(path.read_bytes())
                stream.flush()
                os.fsync(stream.fileno())
        atomic_write(path, raw)


def merge_bundled_db(local: dict, bundled: dict) -> tuple[dict, list[str]]:
    """Add missing keys only. Existing nulls and user values are intentional."""
    validate_db(local)
    validate_db(bundled)
    merged = copy.deepcopy(local)
    conflicts = []

    def add_missing(target, source, prefix):
        for key, value in source.items():
            label = f"{prefix}.{key}"
            if key not in target:
                target[key] = copy.deepcopy(value)
            elif isinstance(target[key], dict) and isinstance(value, dict):
                add_missing(target[key], value, label)
            elif target[key] != value:
                conflicts.append(label)

    for section in ("_products", "_skus", "_brands"):
        add_missing(merged.setdefault(section, {}), bundled.get(section, {}), section)
    # Historical orphan entries stay visible, but a bundle must not add new ones.
    for sku in list(merged["_skus"]):
        if sku not in local.get("_skus", {}) and merged["_skus"][sku]["product"] not in merged["_products"]:
            del merged["_skus"][sku]
            conflicts.append(f"_skus.{sku} (produit absent, ajout ignoré)")
    return merged, conflicts


def orca_values(profile: dict) -> dict:
    """Read Orca array fields without fabricating nozzle or physical values."""
    if not isinstance(profile, dict):
        raise DatabaseError("Profil Orca : objet JSON requis.")

    def number(key, default=None, *, integer=False):
        if key not in profile and default is not None:
            return default
        items = profile.get(key)
        if not isinstance(items, list) or not items or isinstance(items[0], bool):
            raise DatabaseError(f"Profil Orca : {key} doit être une liste numérique non vide.")
        try:
            value = float(items[0])
        except (ValueError, TypeError) as exc:
            raise DatabaseError(f"Profil Orca : {key} invalide.") from exc
        if not math.isfinite(value) or value < 0 or (integer and int(value) != value):
            raise DatabaseError(f"Profil Orca : {key} hors plage ou non fini.")
        return int(value) if integer else value

    plates = [number(key, 0, integer=True) for key in
              ("cool_plate_temp", "eng_plate_temp", "hot_plate_temp", "textured_plate_temp")]
    nonzero = [temp for temp in plates if temp > 0]
    # A profile without any plate temperature has an unknown bed, not 0 °C.
    result = {
        "min_temp": number("nozzle_temperature_range_low", integer=True),
        "max_temp": number("nozzle_temperature_range_high", integer=True),
        "bed_min_temp": min(nonzero) if nonzero else None,
        "bed_max_temp": max(nonzero) if nonzero else None,
        "density": number("filament_density"),
        "diameter": number("filament_diameter"),
    }
    if result["min_temp"] > result["max_temp"] or result["density"] <= 0 or result["diameter"] <= 0:
        raise DatabaseError("Profil Orca : plage de buse inversée ou valeur physique non positive.")
    return result


STEP_PREFIX = "SPOOLSCRIBE_STEP_RESULT="


def _execute_step(main: Callable, db_path: str | None):
    status, code, message = "unchanged", 0, ""
    try:
        before = Path(db_path).read_bytes() if db_path and Path(db_path).exists() else None
        result = main()
        after = Path(db_path).read_bytes() if db_path and Path(db_path).exists() else None
        if before != after or result == "changed":
            status = "changed"
        if isinstance(result, int) and result != 0:
            status, code, message = "error", result, "Le script a échoué."
    except SourceUnavailable as exc:
        status, code, message = "unavailable", 2, str(exc)
    except PartialUpdate as exc:
        status, code, message = "partial", 3, str(exc)
    except Exception as exc:
        status, code, message = "error", 1, str(exc)
    return {"status": status, "message": message}, code


def run_step(main: Callable, db_path: str | None = None) -> None:
    """Report through a private result file even in a windowed Windows exe."""
    with ExitStack() as streams:
        if sys.stdout is None:
            streams.enter_context(redirect_stdout(streams.enter_context(open(os.devnull, "w", encoding="utf-8"))))
        if sys.stderr is None:
            streams.enter_context(redirect_stderr(streams.enter_context(open(os.devnull, "w", encoding="utf-8"))))
        record, code = _execute_step(main, db_path)
        raw = json.dumps(record, ensure_ascii=False)
        destination = os.environ.get("SPOOLSCRIBE_STEP_RESULT_PATH")
        if destination:
            atomic_write(destination, raw.encode("utf-8"))
        if record["message"]:
            print(record["message"], file=sys.stderr)
        print(STEP_PREFIX + raw, flush=True)
    raise SystemExit(code)

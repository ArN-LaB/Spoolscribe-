"""Sauvegarder / restaurer mes données : archive ZIP vérifiée, restauration journalisée.

Aucune dépendance Qt ni réseau ; bibliothèque standard et validateurs existants.

* **Format** : ZIP **non chiffré** (``.zip`` lisible par tout outil), avec un
  ``manifest.json`` strict (voir :func:`_validate_manifest`). Le manifeste ne
  contient ni nom d'utilisateur, ni chemin absolu, ni identifiant de machine,
  ni consentement réseau.
* **Contenu** : catalogue complet (identifiants, copies ``_personal``,
  ``_field_sources``, ``null`` volontaires : octets exacts), registre de
  mesures et presets d'appareil quand présents, profils Orca locaux, copie
  utilisateur ``printers.json`` quand présente et valide, préférences filtrées
  si demandé (sans consentement ni état machine ; disposition et dossier
  d'export seulement sur option ; réglages OpenTag3D inclus), exports
  ``output/`` seulement sur option. Les caches, audits, logos, sources brutes,
  sauvegardes internes et fichiers techniques sont annoncés comme exclus ; un
  fichier inconnu est signalé, jamais inclus ni supprimé.
* **Restauration** : instantané exact des éléments présents dans l'archive (pas
  de fusion), absence dans l'archive = fichier local conservé. Contenu actuel
  conservé d'abord à l'identique (absence comprise), journal durable, puis
  publications atomiques par fichier ; retour arrière vérifié en cas d'erreur
  ou au prochain démarrage (voir :mod:`spoolscribe.recovery`, qui détaille
  aussi ce qui **n'est pas** garanti : transaction logique pour les programmes
  coopérants, pas transaction globale du système de fichiers).

Préconditions d'appel de :func:`restore_backup` (responsabilité de
l'interface) : tenir le verrou d'instance de l'application, avoir arrêté le
worker d'actualisation et traité les brouillons ; recharger ensuite vues,
chemins et révisions de façon coordonnée.
"""
from __future__ import annotations

import copy
import datetime as _dt
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import unicodedata
import zipfile
import zlib
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path

from scripts import db_io

from . import colour_measurements as cm
from . import device_profiles
from . import recovery
from .recovery import MESSAGES, BackupError, RecoveryResult

FORMAT = "spoolscribe-backup"
VERSION = 1
MANIFEST_NAME = "manifest.json"
PREFERENCES_FORMAT = "spoolscribe-settings"   # envelope of config/preferences.json (same as the preferences export)

CATALOGUE, REGISTRY, PRESETS, PRINTERS, CONFIG, ORCA, EXPORT = (
    "catalogue", "registry", "presets", "printers", "config", "orca", "export")
TYPES = (CATALOGUE, REGISTRY, PRESETS, PRINTERS, CONFIG, ORCA, EXPORT)
FIXED_MEMBERS = {CATALOGUE: "data/polymaker_db.json", REGISTRY: "data/colour_measurements.json",
                 PRESETS: "data/colour_device_profiles.json", PRINTERS: "data/printers.json",
                 CONFIG: "config/preferences.json"}
ABSENT_TYPES = (REGISTRY, PRESETS, PRINTERS, CONFIG, ORCA, EXPORT)
# Categories announced as not included (manifest ``excluded`` and plan).
EXCLUDED_CATEGORIES = ("internal_backups", "sources", "audits", "resources", "technical", "restore_snapshots",
                       "external_exports", "unknown", PRINTERS, CONFIG, EXPORT, ORCA)
CATEGORY_LABELS = {
    CATALOGUE: "Catalogue (copies personnelles, corrections et provenances comprises)",
    REGISTRY: "Registre des mesures de couleur",
    PRESETS: "Réglages d'appareil de mesure",
    PRINTERS: "Liste d'imprimantes mise à jour",
    CONFIG: "Préférences (dont réglages OpenTag3D)",
    ORCA: "Profils Orca locaux",
    EXPORT: "Exports générés (dossier output)",
    "internal_backups": "Sauvegardes internes de l'application (.bak, avant restauration…)",
    "sources": "Caches et sources brutes retéléchargeables",
    "audits": "Rapports d'audit des sources",
    "resources": "Logos et ressources embarquées",
    "technical": "Fichiers techniques (verrous, temporaires, système)",
    "restore_snapshots": "Instantanés locaux d'avant restauration",
    "external_exports": "Dossier d'export choisi hors du dossier de données",
    "unknown": "Fichiers non reconnus",
}
REASON_LABELS = {
    "option_off": "Non inclus selon les options choisies.",
    "cache": "Recréé ou retéléchargé par l'application.",
    "internal_backup": "Sauvegarde interne, recréée par l'application.",
    "resource": "Ressource fournie avec l'application.",
    "technical": "Fichier technique sans donnée utilisateur.",
    "restore_snapshot": "Conservé localement pour annuler une restauration.",
    "external": "Jamais suivi automatiquement.",
    "invalid": "Fichier invalide, ignoré par l'application.",
    "unportable_name": "Nom de fichier non portable entre systèmes.",
    "link": "Lien symbolique non suivi.",
    "too_large": "Fichier au-delà de la limite par fichier.",
    "unknown": "Fichier non reconnu : ni inclus ni supprimé.",
}

MiB = 1024 * 1024
# Software protection bounds. Finer existing limits are kept (registry, presets,
# printer list, preferences file: 128 KiB like core.SETTINGS_FILE_LIMIT).
LIMITS = {
    "members": 4096,
    "total_bytes": 512 * MiB,
    "archive_bytes": 512 * MiB + 16 * MiB,
    "manifest": 4 * MiB,
    CATALOGUE: 128 * MiB,
    REGISTRY: cm.LIMITS["registry_bytes"],
    PRESETS: 64 * 1024,
    PRINTERS: 512 * 1024,          # printer_profiles.MAX_CATALOGUE_BYTES
    CONFIG: 128 * 1024,            # core.SETTINGS_FILE_LIMIT
    ORCA: 8 * MiB,
    EXPORT: 64 * MiB,
}
_PUBLISH_ORDER = {PRINTERS: 0, PRESETS: 1, REGISTRY: 2, ORCA: 3, EXPORT: 4, CONFIG: 5, CATALOGUE: 6}
_CHUNK = 1024 * 1024

# Test hook: called with a label at each publication boundary of restore_backup.
_FAULT_HOOK = None


def _fault(label: str) -> None:
    if _FAULT_HOOK is not None:
        _FAULT_HOOK(label)


# ── Public data types ─────────────────────────────────────────────────────
@dataclass(frozen=True)
class Paths:
    """Effective data paths (``config_path`` may be on another volume)."""
    data_home: str
    db_path: str
    registry_path: str
    presets_path: str
    orca_dir: str
    printers_user_path: str
    config_path: str
    output_dir: str

    @classmethod
    def current(cls) -> "Paths":
        """Resolved from ``core`` at call time, so patched/isolated paths are honoured."""
        from . import core, printer_profiles
        db = Path(core.DB_PATH)
        printers = printer_profiles.user_path() or Path(core.DATA_HOME) / "data" / "printers.json"
        return cls(str(core.DATA_HOME), str(db), str(db.with_name("colour_measurements.json")),
                   str(db.with_name("colour_device_profiles.json")), str(core.ORCA_DIR), str(printers),
                   str(core.CONFIG_PATH), str(core.OUTPUT_DIR))

    @classmethod
    def for_home(cls, data_home, config_path=None) -> "Paths":
        """Standard layout of a data folder (``config_path`` defaults to ``<home>/config.json``)."""
        home = Path(data_home)
        data = home / "data"
        return cls(str(home), str(data / "polymaker_db.json"), str(data / "colour_measurements.json"),
                   str(data / "colour_device_profiles.json"), str(home / "orca_profiles"),
                   str(data / "printers.json"), str(config_path or home / "config.json"), str(home / "output"))


@dataclass
class Options:
    include_config: bool = True
    include_layout: bool = False
    include_export_path: bool = False
    include_exports: bool = False

    def as_dict(self) -> dict:
        return {"include_config": self.include_config, "include_layout": self.include_layout,
                "include_export_path": self.include_export_path, "include_exports": self.include_exports}


@dataclass
class PlanItem:
    """One data element: ``state`` is ``included``, ``absent``, ``excluded`` or ``invalid``.

    ``source`` is the local absolute path (for local display only, never written
    to the manifest); ``reason`` a key of :data:`REASON_LABELS`; ``error`` the
    blocking :class:`BackupError` when the element prevents the backup.
    """
    type: str
    member: str | None
    source: str
    state: str
    bytes: int = 0
    reason: str | None = None
    error: BackupError | None = None
    revision: str | None = None
    data: bytes | None = field(default=None, repr=False)


@dataclass
class Plan:
    """Inventory before creating a backup; nothing is written.

    ``categories``: category → ``{"state", "count", "bytes", "reason"}`` for every
    category of :data:`CATEGORY_LABELS` that was found or decided; ``unknown``:
    paths relative to the data folder (POSIX form) of unrecognised files;
    ``blocking``: errors that prevent the backup (also raised by
    :func:`create_backup`).
    """
    paths: Paths
    options: Options
    items: list
    categories: dict
    unknown: list
    counts: dict
    blocking: list
    member_count: int
    total_bytes: int

    @property
    def included(self) -> list:
        return [item for item in self.items if item.state == "included"]

    @property
    def ok(self) -> bool:
        return not self.blocking


@dataclass
class Analysis:
    """Fully validated archive and preview of its restoration; nothing was written.

    ``entries``: one dict per member (``type``, ``member``, ``bytes``, ``sha256``,
    ``target``, ``action`` = ``replace``/``create``/``unchanged``, ``current`` and
    ``after`` digests). ``replaced``/``created``/``unchanged`` are views of it;
    ``kept``: local data not in the archive, left as is; ``ignored``:
    categories the archive declares excluded; ``absent``: types declared absent
    at creation (their local files are kept). ``revisions``: target → digest seen
    (``None`` = absent), re-checked under lock by :func:`restore_backup`.
    """
    archive: str
    archive_sha256: str
    archive_bytes: int
    paths: Paths
    manifest: dict
    app_version: str
    created_utc: str
    options: dict
    entries: list
    kept: list
    ignored: list
    absent: list
    counts: dict
    config: dict | None
    revisions: dict

    @property
    def replaced(self) -> list:
        return [e for e in self.entries if e["action"] == "replace"]

    @property
    def created(self) -> list:
        return [e for e in self.entries if e["action"] == "create"]

    @property
    def unchanged(self) -> list:
        return [e for e in self.entries if e["action"] == "unchanged"]


@dataclass
class RestoreResult:
    """Committed restoration. ``snapshot_dir`` keeps the exact pre-restore state (see :func:`revert_restore`)."""
    txid: str
    published: list
    unchanged: list
    snapshot_dir: str
    sources_changed: bool
    reload: list


# ── Member names ──────────────────────────────────────────────────────────
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
_FORBIDDEN = set('<>:"|?*\\')


def _display(name) -> str:
    text = name if isinstance(name, str) else repr(name)
    text = "".join(c if c.isprintable() else "\\x%02x" % ord(c) if ord(c) < 256 else "\\u%04x" % ord(c) for c in text)
    return text if len(text) <= 200 else text[:197] + "…"


def _component_ok(part: str) -> bool:
    if not part or part in (".", "..") or len(part.encode("utf-8")) > 255:
        return False
    if any(ord(c) < 32 or ord(c) == 127 or c in _FORBIDDEN for c in part):
        return False
    if part[-1] in ". " or part[0] == " ":
        return False
    return part.split(".")[0].upper() not in _RESERVED


def check_member_name(name) -> tuple:
    """Components of an allowed relative member name, else ``BackupError('unsafe_path')``.

    Refused: absolute paths, ``..``/``.``, empty components, backslashes, drive
    letters/``:``, control characters, Windows-reserved or trailing-dot names,
    names not in Unicode NFC, over-long names.
    """
    if (not isinstance(name, str) or not name or len(name.encode("utf-8", "surrogatepass")) > 1024
            or name.startswith("/") or "\\" in name or "\x00" in name
            or unicodedata.normalize("NFC", name) != name):
        raise BackupError("unsafe_path", v0=_display(name))
    parts = tuple(name.split("/"))
    if not all(_component_ok(part) for part in parts):
        raise BackupError("unsafe_path", v0=_display(name))
    return parts


def member_type(name: str) -> str | None:
    for kind, member in FIXED_MEMBERS.items():
        if name == member:
            return kind
    parts = name.split("/")
    if len(parts) == 2 and parts[0] == "orca_profiles" and parts[1].endswith(".json") and len(parts[1]) > 5:
        return ORCA
    if len(parts) >= 2 and parts[0] == "output":
        return EXPORT
    return None


def _collision_key(name: str) -> str:
    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", name).casefold())


# ── Content validation (shared by creation and analysis) ──────────────────
def _portable_keys() -> tuple:
    from . import core
    return tuple(core.PORTABLE_SETTINGS_KEYS)


def exportable_preferences(cfg: dict, options: Options) -> dict:
    """Filtered preferences (``core.exportable_settings``): never consent, revision or refresh dates/statuses."""
    from . import core
    prefs = core.exportable_settings(cfg, include_layout=options.include_layout,
                                     include_export_path=options.include_export_path)
    return {k: v for k, v in prefs.items() if k not in core.MACHINE_STATE_KEYS}


def _validate_preferences(prefs: dict, printer_doc: dict | None = None) -> None:
    """``core.validate_settings`` (the import rule, without writing) on the defaults overlaid with ``prefs``.

    The printer list carried by the backup is accepted as the source of printer ids.
    """
    from . import core, printer_profiles
    if "update_interval_days" in prefs and not core.valid_update_interval(prefs["update_interval_days"]):
        raise ValueError("Cadence d’actualisation invalide")
    profiles = {}
    for printer in (printer_doc or {}).get("printers", []):
        profiles[printer["id"]] = printer
    profiles.update(printer_profiles.PROFILES)
    cfg = copy.deepcopy(core.DEFAULT_CONFIG)
    cfg.update(copy.deepcopy(prefs))
    core.validate_settings(cfg, profiles=profiles)


def _catalogue_counts(db: dict) -> dict:
    skus = db.get("_skus", {})
    user_fields = 0
    for section in ("_products", "_skus"):
        for entry in db.get(section, {}).values():
            user_fields += sum(1 for info in (entry.get("_field_sources") or {}).values()
                               if isinstance(info, dict) and info.get("source") == db_io.USER_SOURCE)
    return {"products": len(db.get("_products", {})), "skus": len(skus), "brands": len(db.get("_brands", {})),
            "personal": sum(1 for entry in skus.values() if entry.get("_personal")), "user_fields": user_fields}


def _validate_content(kind: str, raw: bytes, *, options: Options | None = None, printer_doc: dict | None = None):
    """Parse and validate one element; returns ``(counts, document)``. Raises ValueError/RecursionError."""
    if kind == CATALOGUE:
        db = db_io.parse_json(raw)
        db_io.validate_db(db)
        return _catalogue_counts(db), None
    if kind == REGISTRY:
        document = cm.validate_registry(db_io.parse_json(raw))
        measurements = document["measurements"].values()
        return {"measurements": len(document["measurements"]),
                "linked": sum(1 for m in measurements if m.get("association"))}, None
    if kind == PRESETS:
        document = device_profiles.validate(db_io.parse_json(raw))
        return {"presets": len(document["profiles"])}, None
    if kind == PRINTERS:
        from . import printer_profiles
        document = printer_profiles.parse_catalogue_bytes(raw)
        return {"printers": len(document.get("printers", []))}, document
    if kind == ORCA:
        document = db_io.parse_json(raw)
        if not isinstance(document, dict):
            raise ValueError("Profil Orca : objet JSON requis.")
        return {}, None
    if kind == CONFIG:
        return _validate_preferences_member(raw, options or Options(), printer_doc)
    return {}, None


def _validate_preferences_member(raw: bytes, options: Options, printer_doc):
    document = db_io.parse_json(raw)
    if not isinstance(document, dict) or set(document) != {"format", "version", "settings"} \
            or document["format"] != PREFERENCES_FORMAT:
        raise ValueError("Format de réglages inconnu")
    if type(document["version"]) is not int or document["version"] != 1:
        raise ValueError("Version de réglages non prise en charge")
    prefs = document["settings"]
    if not isinstance(prefs, dict):
        raise ValueError("Réglages invalides")
    allowed = set(_portable_keys()) | ({"ui"} if options.include_layout else set()) \
        | ({"export_directory"} if options.include_export_path else set())
    extra = sorted(set(prefs) - allowed)
    optional = [k for k in extra if k in ("ui", "export_directory")]
    if optional:
        raise BackupError("options_mismatch", v0=", ".join(optional))
    if extra:
        raise ValueError("Clés non prises en charge : " + ", ".join(_display(k) for k in extra))
    _validate_preferences(prefs, printer_doc)
    return {"keys": len(prefs), "opentag3d": len(prefs.get("opentag3d_settings") or {}),
            "favorite_filaments": len(prefs.get("favorite_filaments") or [])}, prefs


# ── Inventory ─────────────────────────────────────────────────────────────
_SYSTEM_FILES = {".DS_Store", "Thumbs.db", "desktop.ini", ".localized"}


def _data_category(name: str) -> tuple:
    """(category, reason) of a file found in the data folder that is not a backed-up element."""
    if name in _SYSTEM_FILES or name.endswith((".lock", ".tmp")) or name.startswith("."):
        return "technical", "technical"
    if ".before-restore-" in name or ".concurrent-" in name or name.endswith(".bak"):
        return "internal_backups", "internal_backup"
    if name.endswith("_audit.json"):
        return "audits", "cache"
    if re.fullmatch(r"catalogue_[a-z0-9_]+\.json|wholesale_raw\.json|.+\.jsonl(\.gz)?", name):
        return "sources", "cache"
    if name.endswith((".svg", ".png", ".ico", ".icns", ".jpg", ".jpeg", ".webp")) or name.endswith("LICENSE.txt"):
        return "resources", "resource"
    return "unknown", "unknown"


def _add_category(categories: dict, name: str, state: str, size: int = 0, reason: str | None = None) -> None:
    entry = categories.setdefault(name, {"state": state, "count": 0, "bytes": 0, "reason": reason})
    entry["count"] += 1
    entry["bytes"] += size


def _read_source(path: Path, limit: int, member: str) -> bytes | None:
    """Bytes of a source file, checked on the inode first and again while reading."""
    try:
        with open(path, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise BackupError("source_unreadable", v0=path.name, v1="fichier non régulier")
            if info.st_size > limit:
                raise BackupError("source_too_large", v0=path.name, v1=info.st_size, v2=limit)
            data = stream.read(limit + 1)
    except FileNotFoundError:
        return None
    except IsADirectoryError:
        raise BackupError("source_unreadable", v0=path.name, v1="dossier") from None
    except OSError as exc:
        raise BackupError("source_unreadable", v0=path.name, v1=exc.strerror or exc) from exc
    if len(data) > limit:
        raise BackupError("source_too_large", v0=path.name, v1=len(data), v2=limit)
    return data


def _fixed_item(kind: str, path: str, *, keep: bool, options: Options, printer_doc=None, counts=None):
    """PlanItem of a single-file element (data kept in memory when ``keep``)."""
    member, source = FIXED_MEMBERS[kind], Path(path)
    try:
        raw = _read_source(source, LIMITS[kind], member)
    except BackupError as exc:
        if kind == PRINTERS:   # the application itself ignores an unusable user list
            return PlanItem(kind, member, str(source), "excluded", reason="invalid"), None
        return PlanItem(kind, member, str(source), "invalid", error=exc), None
    if raw is None:
        return PlanItem(kind, member, str(source), "absent"), None
    try:
        found, document = _validate_content(kind, raw, options=options, printer_doc=printer_doc)
    except (ValueError, RecursionError) as exc:
        if kind == PRINTERS:   # the application itself ignores an invalid user list
            return PlanItem(kind, member, str(source), "excluded", len(raw), reason="invalid"), None
        return PlanItem(kind, member, str(source), "invalid", len(raw),
                        error=BackupError("source_invalid", v0=source.name, v1=exc)), None
    if counts is not None:
        counts.update(found)
    return PlanItem(kind, member, str(source), "included", len(raw), revision=hashlib.sha256(raw).hexdigest(),
                    data=raw if keep else None), document


def _config_item(paths: Paths, options: Options, *, keep: bool, printer_doc, counts: dict, categories: dict):
    source = Path(paths.config_path)
    member = FIXED_MEMBERS[CONFIG]
    try:
        raw = _read_source(source, 4 * MiB, member)
    except BackupError as exc:
        if not options.include_config:
            return None, None
        return PlanItem(CONFIG, member, str(source), "invalid", error=exc), None
    cfg = None
    if raw is not None:
        try:
            cfg = db_io.parse_json(raw)
        except db_io.DatabaseError:
            cfg = None
    directory = cfg.get("export_directory") if isinstance(cfg, dict) else None
    if isinstance(directory, str) and os.path.isabs(directory):
        try:
            inside = Path(directory).resolve().is_relative_to(Path(paths.output_dir).resolve())
        except (OSError, ValueError):
            inside = False
        if not inside:
            categories["external_exports"] = {"state": "excluded", "count": 1, "bytes": 0, "reason": "external"}
    if not options.include_config:
        if raw is not None:
            categories[CONFIG] = {"state": "excluded", "count": 1, "bytes": len(raw), "reason": "option_off"}
        return None, None
    if raw is None:
        return PlanItem(CONFIG, member, str(source), "absent"), None
    if not isinstance(cfg, dict):
        return PlanItem(CONFIG, member, str(source), "invalid", len(raw),
                        error=BackupError("source_invalid", v0=source.name, v1="objet JSON attendu")), None
    try:
        prefs = exportable_preferences(cfg, options)
        payload = json.dumps({"format": PREFERENCES_FORMAT, "version": 1, "settings": prefs},
                             indent=2, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(payload) > LIMITS[CONFIG]:
            raise BackupError("source_too_large", v0=source.name, v1=len(payload), v2=LIMITS[CONFIG])
        found, _ = _validate_preferences_member(payload, options, printer_doc)
    except BackupError as exc:
        return PlanItem(CONFIG, member, str(source), "invalid", len(raw), error=exc), None
    except (ValueError, TypeError, RecursionError) as exc:
        return PlanItem(CONFIG, member, str(source), "invalid", len(raw),
                        error=BackupError("source_invalid", v0=source.name, v1=exc)), None
    counts.update({"config_" + k: v for k, v in found.items()})
    item = PlanItem(CONFIG, member, str(source), "included", len(payload), revision=hashlib.sha256(raw).hexdigest(),
                    data=payload if keep else None)
    return item, prefs


def _walk_files(root: Path, limit: int):
    """Regular files and links below ``root`` (links never followed), at most ``limit`` + 1 entries."""
    found = 0
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in sorted(dirnames):
            if (base / name).is_symlink():
                yield base / name, True
                found += 1
        for name in sorted(filenames):
            yield base / name, (base / name).is_symlink()
            found += 1
            if found > limit:
                return
        dirnames[:] = sorted(d for d in dirnames if not (base / d).is_symlink())


def _relative(paths: Paths, path: Path) -> str:
    try:
        return Path(os.path.relpath(path, paths.data_home)).as_posix()
    except ValueError:
        return path.name


def _scan(paths: Paths, options: Options, *, keep: bool) -> Plan:
    items, categories, unknown, counts, blocking = [], {}, [], {}, []
    printer_doc = None
    for kind, path in ((CATALOGUE, paths.db_path), (REGISTRY, paths.registry_path), (PRESETS, paths.presets_path),
                       (PRINTERS, paths.printers_user_path)):
        item, document = _fixed_item(kind, path, keep=keep, options=options, counts=counts)
        if kind == PRINTERS and document is not None:
            printer_doc = document
        items.append(item)
    config_item, _ = _config_item(paths, options, keep=keep, printer_doc=printer_doc, counts=counts,
                                  categories=categories)
    if config_item is not None:
        items.append(config_item)
    if items[0].state == "absent":
        blocking.append(BackupError("catalogue_missing"))

    # Local Orca profiles: regular *.json files directly in the folder.
    orca_dir, seen = Path(paths.orca_dir), set()
    try:
        names = sorted(os.listdir(orca_dir))
    except OSError:
        names = None
    orca_count = 0
    for name in names or []:
        path = orca_dir / name
        if path.is_symlink():
            _add_category(categories, ORCA, "excluded", 0, "link")
            continue
        if not path.is_file():
            unknown.append(_relative(paths, path) + "/")
            continue
        if not name.endswith(".json"):
            category, reason = _data_category(name)
            if category == "unknown":
                unknown.append(_relative(paths, path))
            else:
                _add_category(categories, category, "excluded", path.stat().st_size, reason)
            continue
        member = "orca_profiles/" + unicodedata.normalize("NFC", name)
        try:
            check_member_name(member)
            if _collision_key(member) in seen:
                raise BackupError("duplicate_member", v0=_display(member))
        except BackupError:
            _add_category(categories, ORCA, "excluded", 0, "unportable_name")
            continue
        seen.add(_collision_key(member))
        try:
            raw = _read_source(path, LIMITS[ORCA], member)
            if raw is None:
                continue
            _validate_content(ORCA, raw)
        except BackupError as exc:
            _add_category(categories, ORCA, "excluded", 0, "too_large" if exc.code == "source_too_large" else "invalid")
            continue
        except (ValueError, RecursionError):
            _add_category(categories, ORCA, "excluded", len(raw), "invalid")
            continue
        items.append(PlanItem(ORCA, member, str(path), "included", len(raw),
                              revision=hashlib.sha256(raw).hexdigest(), data=raw if keep else None))
        orca_count += 1
    if orca_count == 0:
        items.append(PlanItem(ORCA, None, str(orca_dir), "absent"))
    counts["orca_profiles"] = orca_count

    # Generated exports: only on option; an external export folder is never followed.
    output, export_count = Path(paths.output_dir), 0
    if output.is_dir() and not output.is_symlink():
        for path, is_link in _walk_files(output, LIMITS["members"]):
            if is_link:
                _add_category(categories, EXPORT, "excluded", 0, "link")
                continue
            size = path.stat().st_size
            if not options.include_exports:
                _add_category(categories, EXPORT, "excluded", size, "option_off")
                continue
            member = "output/" + unicodedata.normalize("NFC", path.relative_to(output).as_posix())
            try:
                check_member_name(member)
                if _collision_key(member) in seen:
                    raise BackupError("duplicate_member", v0=_display(member))
            except BackupError:
                _add_category(categories, EXPORT, "excluded", size, "unportable_name")
                continue
            if size > LIMITS[EXPORT]:
                _add_category(categories, EXPORT, "excluded", size, "too_large")
                continue
            seen.add(_collision_key(member))
            items.append(PlanItem(EXPORT, member, str(path), "included", size))
            export_count += 1
    if options.include_exports and export_count == 0:
        items.append(PlanItem(EXPORT, None, str(output), "absent"))
    counts["exports"] = export_count

    # Everything else in the data folder: announced by category, unknown files reported.
    data_dir = Path(paths.db_path).parent
    included_names = {Path(p).name for p in (paths.db_path, paths.registry_path, paths.presets_path,
                                             paths.printers_user_path) if Path(p).parent == data_dir}
    try:
        data_names = sorted(os.listdir(data_dir))
    except OSError:
        data_names = []
    for name in data_names:
        path = data_dir / name
        if name in included_names:
            continue
        if path.is_dir() and not path.is_symlink():
            unknown.append(_relative(paths, path) + "/")
            continue
        category, reason = _data_category(name)
        try:
            size = path.lstat().st_size
        except OSError:
            size = 0
        if category == "unknown":
            unknown.append(_relative(paths, path))
        else:
            _add_category(categories, category, "excluded", size, reason)
    home = Path(paths.data_home)
    known_top = {"data", "orca_profiles", "output", recovery.TX_ROOT_NAME, "spoolscribe.instance.lock",
                 Path(paths.config_path).name if Path(paths.config_path).parent == home else "config.json"}
    try:
        top_names = sorted(os.listdir(home))
    except OSError:
        top_names = []
    for name in top_names:
        path = home / name
        if name == recovery.TX_ROOT_NAME:
            kept = len(recovery.committed_restores(home))
            if kept:
                categories["restore_snapshots"] = {"state": "excluded", "count": kept, "bytes": 0,
                                                   "reason": "restore_snapshot"}
            continue
        if name == "diagnostics" and path.is_dir() and not path.is_symlink():
            # Opt-in local diagnostic sessions (diagnostics.FOLDER_NAME): never backed up nor restored.
            _add_category(categories, "technical", "excluded", 0, "technical")
            continue
        if name in known_top or name in _SYSTEM_FILES or name.endswith((".lock", ".tmp", recovery.POINTER_SUFFIX)):
            if name.endswith(".lock") or name in _SYSTEM_FILES:
                _add_category(categories, "technical", "excluded", 0, "technical")
            continue
        unknown.append(name + ("/" if path.is_dir() else ""))
    if unknown:
        categories["unknown"] = {"state": "excluded", "count": len(unknown), "bytes": 0, "reason": "unknown"}

    for item in items:
        if item.state == "invalid" and item.error is not None:
            blocking.append(item.error)
        if item.state in ("included", "absent") and item.type not in (ORCA, EXPORT):
            categories[item.type] = {"state": item.state, "count": int(item.state == "included"),
                                     "bytes": item.bytes, "reason": None}
        elif item.state in ("excluded", "invalid") and item.type not in (ORCA, EXPORT):
            categories[item.type] = {"state": item.state, "count": 1, "bytes": item.bytes, "reason": item.reason}
    if orca_count:
        categories.setdefault(ORCA, {"state": "included", "count": 0, "bytes": 0, "reason": None})
        categories[ORCA].update(state="included", count=orca_count,
                                bytes=sum(i.bytes for i in items if i.type == ORCA and i.state == "included"))
    elif ORCA not in categories:
        categories[ORCA] = {"state": "absent", "count": 0, "bytes": 0, "reason": None}
    if export_count:
        categories[EXPORT] = {"state": "included", "count": export_count,
                              "bytes": sum(i.bytes for i in items if i.type == EXPORT and i.state == "included"),
                              "reason": None}
    elif options.include_exports and EXPORT not in categories:
        categories[EXPORT] = {"state": "absent", "count": 0, "bytes": 0, "reason": None}
    included = [i for i in items if i.state == "included"]
    member_count = len(included) + 1
    total = sum(i.bytes for i in included)
    if member_count > LIMITS["members"]:
        blocking.append(BackupError("backup_too_large", v0=f"{member_count} fichiers", v1=LIMITS["members"]))
    if total > LIMITS["total_bytes"]:
        blocking.append(BackupError("backup_too_large", v0=f"{total} octets", v1=LIMITS["total_bytes"]))
    return Plan(paths, options, items, categories, sorted(unknown), counts, blocking, member_count, total)


def plan_backup(paths: Paths | None = None, options: Options | None = None) -> Plan:
    """Inventory of what a backup would contain (present/absent/excluded, unknown files); writes nothing."""
    return _scan(paths or Paths.current(), options or Options(), keep=False)


# ── Creation ──────────────────────────────────────────────────────────────
def _check_cancel(cancel) -> None:
    if cancel is not None and cancel():
        raise BackupError("cancelled")


def _writer_locks(stack: ExitStack, targets) -> None:
    """Hold the per-file writer locks of ``scripts.db_io`` (shared with every cooperating writer)."""
    for target in dict.fromkeys(Path(t) for t in targets):
        if not target.parent.is_dir():
            continue
        try:
            stack.enter_context(db_io._writer_lock(target))
        except db_io.DatabaseError as exc:
            raise BackupError("writer_busy", v0=target.name) from exc
        except OSError as exc:
            raise BackupError("writer_busy", v0=target.name) from exc


def _zipinfo(name: str, when: tuple) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=when)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o600) << 16
    return info


def _app_version() -> str:
    from . import core
    return str(core.APP_VERSION)


def create_backup(destination, paths: Paths | None = None, options: Options | None = None, *,
                  overwrite: bool = False, cancel=None) -> dict:
    """Write a NEW verified archive at ``destination`` and return its manifest.

    Sources are read under their writer locks, checked again after staging
    (no mix of generations), the archive is re-verified in full, then
    published atomically (temporary file + fsync + link/replace). An existing
    file is refused unless ``overwrite=True``. ``cancel()`` returning true stops
    before publication; nothing is written then.
    """
    paths = paths or Paths.current()
    options = options or Options()
    dest = Path(destination)
    if not dest.name or dest.is_dir() or not dest.parent.is_dir():
        raise BackupError("destination_invalid", v0=_display(str(dest)))
    resolved = dest.resolve()
    sources = [paths.db_path, paths.registry_path, paths.presets_path, paths.printers_user_path, paths.config_path]
    if any(resolved == Path(p).resolve() for p in sources) or \
            recovery.tx_root(paths.data_home).resolve() in resolved.parents:
        raise BackupError("destination_invalid", v0=_display(dest.name))
    if os.path.lexists(dest) and not overwrite:
        raise BackupError("destination_exists", v0=_display(dest.name))
    with ExitStack() as stack:
        _writer_locks(stack, sources)
        plan = _scan(paths, options, keep=True)
        if plan.blocking:
            raise plan.blocking[0]
        _check_cancel(cancel)
        now = _dt.datetime.now(_dt.timezone.utc)
        when = now.timetuple()[:6]
        try:
            fd, temporary = tempfile.mkstemp(prefix=f".{dest.name}.", suffix=".tmp", dir=dest.parent)
        except OSError as exc:
            raise BackupError("write_failed", v0=exc.strerror or exc) from exc
        try:
            entries = []
            with os.fdopen(fd, "w+b") as stream:
                with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
                    for item in plan.included:
                        _check_cancel(cancel)
                        digest, size = hashlib.sha256(), 0
                        with archive.open(_zipinfo(item.member, when), "w") as out:
                            if item.data is not None:
                                out.write(item.data)
                                digest.update(item.data)
                                size = len(item.data)
                            else:
                                with open(item.source, "rb") as source:
                                    for chunk in iter(lambda: source.read(_CHUNK), b""):
                                        size += len(chunk)
                                        if size > LIMITS[item.type]:
                                            raise BackupError("source_changed", v0=_display(item.member))
                                        digest.update(chunk)
                                        out.write(chunk)
                                        _check_cancel(cancel)
                                item.revision = digest.hexdigest()
                        entries.append({"path": item.member, "type": item.type, "bytes": size,
                                        "sha256": digest.hexdigest()})
                    # Same generation: every source still holds the bytes that were archived.
                    for item in plan.included:
                        check = item.source if item.type != CONFIG else paths.config_path
                        if recovery.file_digest(check) != item.revision:
                            raise BackupError("source_changed", v0=_display(Path(check).name))
                    present = {item.type for item in plan.included}
                    absent = sorted({i.type for i in plan.items if i.state == "absent"} - present)
                    excluded = sorted(c for c, info in plan.categories.items()
                                      if info["state"] == "excluded" and c in EXCLUDED_CATEGORIES and c not in present)
                    manifest = {"format": FORMAT, "version": VERSION,
                                "app": {"name": recovery.APP_NAME, "version": _app_version()},
                                "created_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                "options": options.as_dict(), "entries": entries,
                                "absent": absent, "excluded": excluded}
                    archive.writestr(_zipinfo(MANIFEST_NAME, when),
                                     json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False).encode("utf-8"))
                stream.flush()
                os.fsync(stream.fileno())
            _check_cancel(cancel)
            verified = _open_verified(Path(temporary))       # never publish an archive we would refuse
            if verified["manifest"] != manifest:
                raise BackupError("write_failed", v0="vérification de l'archive")
            _check_cancel(cancel)
            _publish(Path(temporary), dest, overwrite)
        except OSError as exc:
            raise BackupError("write_failed", v0=exc.strerror or exc) from exc
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return manifest


def _publish(temporary: Path, dest: Path, overwrite: bool) -> None:
    if overwrite:
        os.replace(temporary, dest)
    else:
        try:
            os.link(temporary, dest)          # atomic "create only if absent"
        except FileExistsError:
            raise BackupError("destination_exists", v0=_display(dest.name)) from None
        except OSError:
            # Hard links unsupported here (some network/FAT volumes): last check, then replace.
            if os.path.lexists(dest):
                raise BackupError("destination_exists", v0=_display(dest.name)) from None
            os.replace(temporary, dest)
    recovery.fsync_dir(dest.parent)


# ── Verification of an archive ────────────────────────────────────────────
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_HEX64 = re.compile(r"[0-9a-f]{64}")


def _invalid(detail: str) -> BackupError:
    return BackupError("manifest_invalid", v0=detail)


def _validate_manifest(document) -> dict:
    """Strict v1 manifest; format is checked first, then the exact integer version."""
    if not isinstance(document, dict) or document.get("format") != FORMAT:
        raise BackupError("not_a_backup")
    version = document.get("version")
    if type(version) is not int or version != VERSION:
        raise BackupError("unsupported_version", v0=_display(repr(version)))
    expected = {"format", "version", "app", "created_utc", "options", "entries", "absent", "excluded"}
    if set(document) != expected:
        raise _invalid("clés " + ", ".join(sorted(_display(k) for k in set(document) ^ expected)))
    app = document["app"]
    if not isinstance(app, dict) or set(app) != {"name", "version"} or app["name"] != recovery.APP_NAME \
            or not isinstance(app["version"], str) or not 0 < len(app["version"]) <= 64:
        raise _invalid("application")
    if not isinstance(document["created_utc"], str) or not _UTC.fullmatch(document["created_utc"]):
        raise _invalid("date de création")
    options = document["options"]
    if not isinstance(options, dict) or set(options) != set(Options().as_dict()) \
            or any(type(v) is not bool for v in options.values()):
        raise _invalid("options")
    entries = document["entries"]
    if not isinstance(entries, list) or len(entries) > LIMITS["members"]:
        raise _invalid("entrées")
    keys = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "type", "bytes", "sha256"}:
            raise _invalid("entrée")
        check_member_name(entry["path"])
        if entry["type"] not in TYPES or member_type(entry["path"]) != entry["type"]:
            raise _invalid("type de " + _display(entry["path"]))
        if type(entry["bytes"]) is not int or entry["bytes"] < 0 or not isinstance(entry["sha256"], str) \
                or not _HEX64.fullmatch(entry["sha256"]):
            raise _invalid("taille ou empreinte de " + _display(entry["path"]))
        key = _collision_key(entry["path"])
        if key in keys:
            raise BackupError("duplicate_member", v0=_display(entry["path"]))
        keys.add(key)
    types = [e["type"] for e in entries]
    if types.count(CATALOGUE) != 1:
        raise _invalid("catalogue absent")
    for name, allowed in (("absent", ABSENT_TYPES), ("excluded", EXCLUDED_CATEGORIES)):
        value = document[name]
        if not isinstance(value, list) or len(set(map(str, value))) != len(value) \
                or any(not isinstance(v, str) or v not in allowed for v in value):
            raise _invalid(name)
    if set(document["absent"]) & set(types):
        raise _invalid("élément à la fois présent et absent")
    # Content must match the announced options: no hidden partial restoration.
    if CONFIG in types and not options["include_config"]:
        raise BackupError("options_mismatch", v0="préférences présentes sans l'option")
    if options["include_config"] and CONFIG not in types and CONFIG not in document["absent"]:
        raise BackupError("options_mismatch", v0="préférences annoncées mais absentes")
    if not options["include_config"] and (options["include_layout"] or options["include_export_path"]):
        raise BackupError("options_mismatch", v0="options de préférences sans préférences")
    if EXPORT in types and not options["include_exports"]:
        raise BackupError("options_mismatch", v0="exports présents sans l'option")
    if options["include_exports"] and EXPORT not in types and EXPORT not in document["absent"]:
        raise BackupError("options_mismatch", v0="exports annoncés mais absents")
    for kind in (REGISTRY, PRESETS, PRINTERS, ORCA):
        if kind not in types and kind not in document["absent"] and kind not in document["excluded"]:
            raise _invalid("élément non déclaré : " + kind)
    return document


def _stream_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo, limit: int, sink=None) -> str:
    """Digest of a member read in bounded chunks (stops at limit + 1, whatever the headers claim)."""
    name = _display(info.orig_filename)
    if info.file_size > limit:
        raise BackupError("member_too_large", v0=name, v1=info.file_size, v2=limit)
    digest, total = hashlib.sha256(), 0
    try:
        with archive.open(info) as stream:
            while True:
                chunk = stream.read(min(_CHUNK, limit + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > limit:
                    raise BackupError("member_too_large", v0=name, v1=total, v2=limit)
                digest.update(chunk)
                if sink is not None:
                    sink(chunk)
    except BackupError:
        raise
    except (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError, RuntimeError, ValueError, OSError) as exc:
        raise BackupError("member_corrupt", v0=name, v1=_display(str(exc))) from exc
    if total != info.file_size:
        raise BackupError("size_mismatch", v0=name)
    return digest.hexdigest()


def _read_member(archive, info, limit, expected_sha: str) -> bytes:
    parts = []
    digest = _stream_member(archive, info, limit, parts.append)
    if digest != expected_sha:
        raise BackupError("digest_mismatch", v0=_display(info.orig_filename))
    return b"".join(parts)


def _member_infos(archive: zipfile.ZipFile) -> dict:
    """Central-directory checks before any read: names, types, flags, counts and declared sizes."""
    infos = archive.infolist()
    if len(infos) > LIMITS["members"]:
        raise BackupError("too_many_members", v0=len(infos), v1=LIMITS["members"])
    manifests = [i for i in infos if i.orig_filename == MANIFEST_NAME]
    if len(manifests) > 1:
        raise BackupError("manifest_duplicate")
    if not manifests:
        raise BackupError("manifest_missing")
    by_name, keys, total = {}, set(), 0
    for info in infos:
        name = info.orig_filename
        kind = stat.S_IFMT(info.external_attr >> 16)
        if kind == stat.S_IFLNK:
            raise BackupError("link_member", v0=_display(name))
        if name.endswith("/") or info.is_dir() or kind not in (0, stat.S_IFREG):
            raise BackupError("not_regular", v0=_display(name))
        check_member_name(name)
        key = _collision_key(name)
        if key in keys:
            raise BackupError("duplicate_member", v0=_display(name))
        keys.add(key)
        if info.flag_bits & 0x1 or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise BackupError("encrypted_member", v0=_display(name))
        total += info.file_size
        if total > LIMITS["total_bytes"]:
            raise BackupError("total_too_large", v0=total, v1=LIMITS["total_bytes"])
        by_name[name] = info
    return by_name


def _open_verified(path: Path) -> dict:
    """Complete validation of an archive, independent of the destination; writes nothing."""
    try:
        info = os.stat(path)
    except OSError as exc:
        raise BackupError("archive_unreadable", v0=exc.strerror or exc) from exc
    if not stat.S_ISREG(info.st_mode):
        raise BackupError("archive_unreadable", v0="fichier non régulier")
    if info.st_size > LIMITS["archive_bytes"]:
        raise BackupError("archive_too_large", v0=info.st_size, v1=LIMITS["archive_bytes"])
    archive_sha = recovery.file_digest(path)
    try:
        handle = open(path, "rb")
    except OSError as exc:
        raise BackupError("archive_unreadable", v0=exc.strerror or exc) from exc
    with handle:
        try:
            archive = zipfile.ZipFile(handle)
        except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, ValueError, EOFError, NotImplementedError) as exc:
            raise BackupError("not_a_backup") from exc
        with archive:
            by_name = _member_infos(archive)
            raw = _read_member_unchecked(archive, by_name[MANIFEST_NAME], LIMITS["manifest"])
            try:
                document = db_io.parse_json(raw)
            except db_io.DatabaseError as exc:
                raise BackupError("not_a_backup") from exc
            manifest = _validate_manifest(document)
            options = Options(**manifest["options"])
            entries = {e["path"]: e for e in manifest["entries"]}
            members = set(by_name) - {MANIFEST_NAME}
            for missing in sorted(set(entries) - members):
                raise BackupError("missing_member", v0=_display(missing))
            for extra in sorted(members - set(entries)):
                raise BackupError("unexpected_member", v0=_display(extra))
            for entry in manifest["entries"]:
                zinfo = by_name[entry["path"]]
                if zinfo.file_size != entry["bytes"]:
                    raise BackupError("size_mismatch", v0=_display(entry["path"]))
                if entry["bytes"] > LIMITS[entry["type"]]:
                    raise BackupError("member_too_large", v0=_display(entry["path"]), v1=entry["bytes"],
                                      v2=LIMITS[entry["type"]])
            counts, prefs, printer_doc = {}, None, None
            ordered = sorted(manifest["entries"], key=lambda e: (e["type"] == CONFIG, _PUBLISH_ORDER[e["type"]]))
            for entry in ordered:
                zinfo, kind = by_name[entry["path"]], entry["type"]
                if kind == EXPORT:
                    if _stream_member(archive, zinfo, LIMITS[EXPORT]) != entry["sha256"]:
                        raise BackupError("digest_mismatch", v0=_display(entry["path"]))
                    counts["exports"] = counts.get("exports", 0) + 1
                    continue
                data = _read_member(archive, zinfo, LIMITS[kind], entry["sha256"])
                try:
                    found, document = _validate_content(kind, data, options=options, printer_doc=printer_doc)
                except BackupError:
                    raise
                except (ValueError, RecursionError) as exc:
                    raise BackupError("member_invalid", v0=_display(entry["path"]), v1=exc) from exc
                if kind == PRINTERS:
                    printer_doc = document
                elif kind == CONFIG:
                    prefs = document
                    found = {"config_" + k: v for k, v in found.items()}
                elif kind == ORCA:
                    found = {"orca_profiles": counts.get("orca_profiles", 0) + 1}
                counts.update(found)
    return {"manifest": manifest, "options": options, "counts": counts, "prefs": prefs, "printer_doc": printer_doc,
            "archive_sha256": archive_sha, "archive_bytes": info.st_size}


def _read_member_unchecked(archive, info, limit) -> bytes:
    parts = []
    _stream_member(archive, info, limit, parts.append)
    return b"".join(parts)


# ── Analysis (preview) ────────────────────────────────────────────────────
def _target(paths: Paths, entry: dict) -> Path:
    kind, parts = entry["type"], entry["path"].split("/")
    if kind == CATALOGUE:
        return Path(paths.db_path)
    if kind == REGISTRY:
        return Path(paths.registry_path)
    if kind == PRESETS:
        return Path(paths.presets_path)
    if kind == PRINTERS:
        return Path(paths.printers_user_path)
    if kind == CONFIG:
        return Path(paths.config_path)
    root = Path(paths.orca_dir if kind == ORCA else paths.output_dir)
    return root.joinpath(*parts[1:])


def _check_target(paths: Paths, entry: dict, target: Path) -> None:
    """Never write through a link, onto a folder, or outside the chosen data folders."""
    if os.path.islink(target) or target.is_dir():
        raise BackupError("unsafe_target", v0=_display(entry["path"]))
    if entry["type"] in (ORCA, EXPORT):
        root = Path(paths.orca_dir if entry["type"] == ORCA else paths.output_dir)
        if os.path.islink(root):
            raise BackupError("unsafe_target", v0=_display(entry["path"]))
        try:
            inside = target.resolve().is_relative_to(root.resolve())
        except (OSError, ValueError):
            inside = False
        if not inside:
            raise BackupError("unsafe_target", v0=_display(entry["path"]))


def _merged_config(current: bytes | None, prefs: dict) -> tuple:
    """Local configuration with the archived preferences: machine state, consent and omitted keys stay local.

    As for a preferences import, a change of sources resets the network
    authorisation revision (consent must be asked again); consent is never granted.
    Returns ``(bytes, sources_changed, local_was_invalid)``.
    """
    from . import core
    local, invalid = {}, False
    if current is not None:
        try:
            parsed = db_io.parse_json(current)
        except db_io.DatabaseError:
            parsed = None
        if isinstance(parsed, dict):
            local = parsed
        else:
            invalid = True
    effective = dict(core.DEFAULT_CONFIG)
    effective.update(local)
    merged = copy.deepcopy(local)
    merged.update(copy.deepcopy(prefs))
    changed = "selected_sources" in prefs and prefs["selected_sources"] != effective.get("selected_sources")
    if changed:
        merged["network_sources_revision"] = 0
    return json.dumps(merged, indent=2, ensure_ascii=False, allow_nan=False).encode("utf-8"), changed, invalid


def _config_preview(current: bytes | None, prefs: dict, options: Options) -> dict:
    from . import core
    local = {}
    if current is not None:
        try:
            parsed = db_io.parse_json(current)
            local = parsed if isinstance(parsed, dict) else {}
        except db_io.DatabaseError:
            local = {}
    effective = dict(core.DEFAULT_CONFIG)
    effective.update(local)
    categories = getattr(core, "SETTINGS_CATEGORIES", ())
    replaced = [name for name, keys in categories if any(k in prefs for k in keys)]
    kept = [name for name, keys in categories if not any(k in prefs for k in keys)]
    _, sources_changed, invalid = _merged_config(current, prefs)
    return {"keys": sorted(prefs), "changed": sorted(k for k in prefs if prefs[k] != effective.get(k)),
            "replaced_categories": replaced, "kept_categories": kept, "layout": "ui" in prefs,
            "export_directory": prefs.get("export_directory") if "export_directory" in prefs else None,
            "machine_state_kept": list(core.MACHINE_STATE_KEYS), "sources_change": sources_changed,
            "local_invalid": invalid, "opentag3d": len(prefs.get("opentag3d_settings") or {}),
            "include_layout": options.include_layout, "include_export_path": options.include_export_path}


def _read_current(path: Path, limit: int = 4 * MiB) -> bytes | None:
    try:
        with open(path, "rb") as stream:
            return stream.read(limit + 1)
    except FileNotFoundError:
        return None


def analyze_backup(archive, paths: Paths | None = None) -> Analysis:
    """Validate the whole archive and preview its restoration; never writes to active data."""
    paths = paths or Paths.current()
    archive = Path(archive)
    verified = _open_verified(archive)
    manifest, options, prefs = verified["manifest"], verified["options"], verified["prefs"]
    entries, revisions = [], {}
    config_preview = None
    for entry in sorted(manifest["entries"], key=lambda e: (_PUBLISH_ORDER[e["type"]], e["path"])):
        target = _target(paths, entry)
        _check_target(paths, entry, target)
        try:
            current = recovery.file_digest(target)
        except OSError as exc:
            raise BackupError("unsafe_target", v0=_display(entry["path"])) from exc
        after = entry["sha256"]
        if entry["type"] == CONFIG:
            raw = _read_current(target)
            if raw is not None and len(raw) > 4 * MiB:
                raise BackupError("unsafe_target", v0=_display(entry["path"]))
            merged, _, _ = _merged_config(raw, prefs)
            after = hashlib.sha256(merged).hexdigest()
            config_preview = _config_preview(raw, prefs, options)
        action = "unchanged" if current == after else "create" if current is None else "replace"
        entries.append({"type": entry["type"], "member": entry["path"], "bytes": entry["bytes"],
                        "sha256": entry["sha256"], "target": str(target), "action": action,
                        "current": current, "after": after})
        revisions[str(target)] = current
    present = {e["type"] for e in entries}
    kept = []
    for kind, path in ((REGISTRY, paths.registry_path), (PRESETS, paths.presets_path),
                       (PRINTERS, paths.printers_user_path), (CONFIG, paths.config_path)):
        if kind not in present and Path(path).exists():
            kept.append({"type": kind, "target": path, "count": 1})
    archived = {_collision_key(e["member"]) for e in entries}
    for kind, root in ((ORCA, Path(paths.orca_dir)), (EXPORT, Path(paths.output_dir))):
        if not root.is_dir():
            continue
        if kind == ORCA:
            local = [root / n for n in os.listdir(root) if n.endswith(".json") and (root / n).is_file()]
            prefix = "orca_profiles/"
        else:
            local = [p for p, link in _walk_files(root, LIMITS["members"]) if not link]
            prefix = "output/"
        extra = [p for p in local
                 if _collision_key(prefix + unicodedata.normalize("NFC", p.relative_to(root).as_posix())) not in archived]
        if extra:
            kept.append({"type": kind, "target": str(root), "count": len(extra)})
    ignored = [{"category": c, "label": CATEGORY_LABELS.get(c, c)} for c in manifest["excluded"]]
    return Analysis(str(archive), verified["archive_sha256"], verified["archive_bytes"], paths, manifest,
                    manifest["app"]["version"], manifest["created_utc"], dict(manifest["options"]), entries, kept,
                    ignored, list(manifest["absent"]), verified["counts"], config_preview, revisions)


# ── Restoration ───────────────────────────────────────────────────────────
_ConcurrentChange = recovery.ConcurrentChange


def restore_backup(analysis: Analysis, paths: Paths | None = None, *, cancel=None) -> RestoreResult:
    """Restore the analysed archive as one journaled logical transaction.

    Under the restore lock and the writer locks of the fixed files: the
    archive and every target must still be exactly as seen by the analysis
    (else ``changed_since_analysis``: re-analyse; nothing written). Members are
    re-read, re-verified and staged privately; the current content and identity
    of every target are recorded (absence recorded); the journal is made durable;
    then, for each item, a durable proof of the exact object about to be
    published is written, and the file is published without ever replacing an
    object that is not the expected one (``recovery.publish_new`` /
    ``publish_replace``). Any error after the first publication rolls back only
    what this transaction provably published (``restore_failed``); an object of
    ambiguous ownership, or a rollback that cannot finish, keeps journal and
    snapshots for :func:`recover` (``restore_recoverable``).
    ``cancel()`` is honoured until the journal is written, not after.
    """
    paths = paths or analysis.paths
    if paths != analysis.paths:
        raise BackupError("paths_changed")
    home = Path(paths.data_home)
    work = [e for e in analysis.entries if e["action"] != "unchanged"]
    with recovery.restore_lock(home):
        pending = recovery.pending_recovery(home, paths.config_path)
        if pending is not None:
            if all(t["phase"] == "staging" for t in pending["transactions"]):
                for t in pending["transactions"]:
                    recovery._remove_tree(Path(t["dir"]))
            else:
                raise BackupError("recovery_pending", details=pending)
        with ExitStack() as stack:
            _writer_locks(stack, [paths.db_path, paths.registry_path, paths.presets_path,
                                  paths.printers_user_path, paths.config_path])
            if recovery.file_digest(analysis.archive) != analysis.archive_sha256:
                raise BackupError("archive_changed")
            for entry in analysis.entries:
                target = Path(entry["target"])
                _check_target(paths, {"type": entry["type"], "path": entry["member"]}, target)
                if recovery.file_digest(target) != analysis.revisions[entry["target"]]:
                    raise BackupError("changed_since_analysis", v0=_display(target.name))
            _check_cancel(cancel)
            # A target to create needs the no-replace primitive of its folder; refused before anything is written.
            for folder in sorted({str(Path(e["target"]).parent) for e in work if e["current"] is None}):
                if not recovery.link_supported(folder):
                    raise BackupError("staging_failed", v0=_display(
                        "création sans remplacement non prise en charge par le système de fichiers de "
                        + Path(folder).name))
            txid, txdir = recovery.new_transaction(home)
            try:
                items, sources_changed = _stage(analysis, paths, work, txdir, cancel)
                _fault("staged")
                _check_cancel(cancel)
            except BackupError:
                recovery._remove_tree(txdir)
                raise
            except BaseException as exc:
                recovery._remove_tree(txdir)
                if isinstance(exc, (OSError, ValueError)):
                    raise BackupError("staging_failed", v0=_display(str(exc))) from exc
                raise
            pointer = None
            if not Path(paths.config_path).resolve().is_relative_to(home.resolve()) and \
                    any(item["type"] == CONFIG for item in items):
                pointer = paths.config_path
            journal = {"format": recovery.JOURNAL_FORMAT, "version": recovery.JOURNAL_VERSION, "txid": txid,
                       "phase": "publishing", "created_utc": recovery.now_utc(), "pid": os.getpid(),
                       "data_home": str(home), "config_pointer": pointer,
                       "archive_sha256": analysis.archive_sha256, "items": items}
            try:
                recovery.write_journal(txdir, journal)
                if pointer:
                    recovery.write_pointer(pointer, txdir)
            except OSError as exc:
                recovery.remove_pointer(pointer, txdir)
                recovery._remove_tree(txdir)
                raise BackupError("staging_failed", v0=_display(exc.strerror or str(exc))) from exc
            completed = set()
            try:
                _fault("journal")
                for position, item in enumerate(items):
                    data = (txdir / item["staged"]).read_bytes()
                    if hashlib.sha256(data).hexdigest() != item["after"]:
                        raise BackupError("staging_failed", v0=_display(item["member"]))
                    target = Path(item["target"])

                    def proof(identity, index=item["index"], after=item["after"], position=position):
                        # Durable before the publication: the exact object we are about to publish.
                        recovery.write_proof(txdir, index, after, identity)
                        _fault(f"proof:{position}")

                    try:
                        if item["before"] is None:
                            recovery.publish_new(target, data, before_publish=proof)
                        else:
                            recovery.publish_replace(target, data, before_publish=proof, expected={
                                "identity": item["before_identity"], "digest": item["before"]})
                    except FileExistsError as exc:        # an object appeared meanwhile: never replaced
                        raise _ConcurrentChange(target.name) from exc
                    completed.add(item["index"])
                    _fault(f"published:{position}")
                _fault("before_commit")
                journal["phase"] = "committed"
                journal["committed_utc"] = recovery.now_utc()
                recovery.write_journal(txdir, journal)
            except BaseException as exc:
                reason = _failure_text(exc)
                if isinstance(exc, recovery.StagingConflict):   # kept and reported until resolved, never "complete"
                    journal.setdefault("residues", []).append(exc.residue)
                outcome = recovery.rollback_items(txdir, journal, completed=completed)
                try:
                    recovery.finish_rollback(txdir, journal, outcome)
                except OSError:
                    outcome["complete"] = False
                if not isinstance(exc, Exception):
                    raise
                code = "restore_failed" if outcome["complete"] else "restore_recoverable"
                raise BackupError(code, v0=reason, details={"txid": txid, "dir": str(txdir), **outcome}) from exc
            # Committed: the exact pre-restore snapshot stays available for an explicit undo.
            _fault("committed")
            import shutil
            shutil.rmtree(txdir / "new", ignore_errors=True)
            recovery.remove_pointer(pointer, txdir)
            recovery.prune_kept(home)
    _mark_restored(paths, items)
    published = [{"type": i["type"], "member": i["member"], "target": i["target"],
                  "action": "create" if i["before"] is None else "replace"} for i in items]
    unchanged = [{"type": e["type"], "member": e["member"], "target": e["target"]}
                 for e in analysis.entries if e["action"] == "unchanged"]
    return RestoreResult(txid, published, unchanged, str(txdir / "snapshot"), sources_changed,
                         sorted({i["type"] for i in items}))


def _failure_text(exc: BaseException) -> str:
    if isinstance(exc, _ConcurrentChange):
        return MESSAGES["concurrent_change"].format(v0=_display(str(exc)))
    if isinstance(exc, OSError):
        return _display(exc.strerror or str(exc))
    return _display(str(exc) or type(exc).__name__)


def _stage(analysis: Analysis, paths: Paths, work: list, txdir: Path, cancel) -> tuple:
    """Re-read and re-verify members into ``new/``, copy current targets into ``snapshot/``."""
    verified_options = Options(**analysis.options)
    items, sources_changed = [], False
    printer_doc = None
    with open(analysis.archive, "rb") as handle, zipfile.ZipFile(handle) as archive:
        infos = _member_infos(archive)
        manifest_entries = {e["path"]: e for e in analysis.manifest["entries"]}
        if set(infos) - {MANIFEST_NAME} != set(manifest_entries):
            raise BackupError("archive_changed")
        if any(e["type"] == PRINTERS for e in manifest_entries.values()) and any(e["type"] == CONFIG for e in work):
            entry = next(e for e in manifest_entries.values() if e["type"] == PRINTERS)
            data = _read_member(archive, infos[entry["path"]], LIMITS[PRINTERS], entry["sha256"])
            from . import printer_profiles
            printer_doc = printer_profiles.parse_catalogue_bytes(data)
        for index, entry in enumerate(work):
            _check_cancel(cancel)
            info, kind = infos[entry["member"]], entry["type"]
            staged = txdir / "new" / str(index)
            if kind == EXPORT:
                fd = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
                with os.fdopen(fd, "wb") as out:
                    digest = _stream_member(archive, info, LIMITS[EXPORT], out.write)
                    out.flush()
                    os.fsync(out.fileno())
                if digest != entry["sha256"]:
                    raise BackupError("digest_mismatch", v0=_display(entry["member"]))
                after = digest
            else:
                data = _read_member(archive, info, LIMITS[kind], entry["sha256"])
                try:
                    _, document = _validate_content(kind, data, options=verified_options, printer_doc=printer_doc)
                except BackupError:
                    raise
                except (ValueError, RecursionError) as exc:
                    raise BackupError("member_invalid", v0=_display(entry["member"]), v1=exc) from exc
                if kind == CONFIG:
                    data, sources_changed, _ = _merged_config(_read_current(Path(entry["target"])), document)
                after = hashlib.sha256(data).hexdigest()
                if after != entry["after"]:
                    raise BackupError("changed_since_analysis", v0=_display(Path(entry["target"]).name))
                recovery.write_private(staged, data)
            snapshot, before_identity = None, None
            if entry["current"] is not None:
                snapshot = f"snapshot/{index}"
                target = Path(entry["target"])
                before_identity = recovery.file_identity(target)
                if before_identity is None or _copy_exact(target, txdir / snapshot) != entry["current"] \
                        or not recovery.same_identity(recovery.file_identity(target), before_identity):
                    raise BackupError("changed_since_analysis", v0=_display(target.name))
            items.append({"index": index, "type": kind, "member": entry["member"], "target": entry["target"],
                          "before": entry["current"], "after": after, "snapshot": snapshot,
                          "staged": f"new/{index}", "before_identity": before_identity})
    recovery.fsync_dir(txdir / "new")
    recovery.fsync_dir(txdir / "snapshot")
    return items, sources_changed


def _copy_exact(source: Path, destination: Path) -> str:
    digest = hashlib.sha256()
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(fd, "wb") as out, open(source, "rb") as stream:
        for chunk in iter(lambda: stream.read(_CHUNK), b""):
            digest.update(chunk)
            out.write(chunk)
        out.flush()
        os.fsync(out.fileno())
    return digest.hexdigest()


def _mark_restored(paths: Paths, items: list) -> None:
    """In this process, a restored catalogue is not merged with bundled data on its next load (as core.restore_db)."""
    core = sys.modules.get("spoolscribe.core")
    if core is None or not any(i["type"] == CATALOGUE for i in items):
        return
    marks = getattr(core, "_RESTORED_DB_PATHS", None)
    if isinstance(marks, set):
        marks.add(str(Path(paths.db_path).resolve()))


# ── Recovery (delegated to the stdlib-only module) ────────────────────────
def pending_recovery(data_home, config_path) -> dict | None:
    """Unfinished transaction for these folders, or ``None`` (see :func:`recovery.pending_recovery`)."""
    return recovery.pending_recovery(data_home, config_path)


def recover(data_home, config_path) -> RecoveryResult:
    """Roll back an interrupted transaction (see :func:`recovery.recover`)."""
    return recovery.recover(data_home, config_path)


def revert_restore(data_home, txid: str, config_path=None) -> RecoveryResult:
    """Explicit undo of a committed restoration from its exact snapshot (see :func:`recovery.revert_restore`)."""
    return recovery.revert_restore(data_home, txid, config_path)


def dismiss_recovery(data_home, txid: str) -> RecoveryResult:
    """Accept the current files after an incomplete rollback (see :func:`recovery.dismiss_recovery`)."""
    return recovery.dismiss_recovery(data_home, txid)


def committed_restores(data_home) -> list:
    """Kept pre-restore snapshots, newest first."""
    return recovery.committed_restores(data_home)

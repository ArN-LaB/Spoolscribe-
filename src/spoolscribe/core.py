#!/usr/bin/env python3
"""
core.py — Logique métier pure, sans aucune I/O terminal (print/input).

Ce module est le cœur partagé par :
  - le CLI  (convert_profile.py)
  - la GUI  (app_gui.py)

Aucune fonction ici n'imprime ni ne demande d'entrée utilisateur.
Tout est testable et appelable sans effet de bord visuel.
"""
from __future__ import annotations

import copy
import json
import hashlib
import math
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional
from pathlib import Path

from scripts import db_io, catalogue_sources, resource_paths
from . import printer_profiles

DatabaseError = db_io.DatabaseError

# ─── Identité de l'application ────────────────────────────────────────────
# APP_VERSION est la référence de version. spoolscribe.spec la lit ici ;
# la CI vérifie que la version déclarée dans pyproject.toml reste alignée.
APP_NAME = "SpoolScribe"
APP_VERSION = "0.7.0"
APP_AUTHOR = "ArN-LaB"
APP_URL = "https://github.com/ArN-LaB/Spoolscribe-"

EMPTY_DB = {"_products": {}, "_skus": {}, "_brands": {}}

_FROZEN = bool(getattr(sys, "frozen", False))


# ─── Chemins ──────────────────────────────────────────────────────────────
def _resource_dir() -> str:
    """
    Ressources **en lecture seule** (embarquées dans le bundle / le repo).

    - Mode normal : dossier de ce fichier.
    - Mode gelé (PyInstaller) : sys._MEIPASS (onefile : dossier temporaire
      d'extraction ; onedir : dossier _internal).
    """
    if _FROZEN:
        return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    return str(Path(__file__).resolve().parents[2])


def user_data_dir() -> str:
    """Dossier inscriptible propre à l'utilisateur, par OS."""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, APP_NAME)


RESOURCE_DIR = _resource_dir()                     # lecture seule (bundle)
SCRIPTS_DIR  = os.path.join(RESOURCE_DIR, "scripts")
SCRIPT_DIR   = RESOURCE_DIR                         # alias rétro-compatible

# Données inscriptibles : repo en dev, dossier utilisateur en .exe (onefile :
# sinon tout irait dans le dossier temporaire _MEIPASS et serait perdu).
DATA_HOME   = os.environ.get("SPOOLSCRIBE_DATA_HOME") or user_data_dir()
DATA_DIR    = os.path.join(DATA_HOME, "data")
DB_PATH     = os.path.join(DATA_DIR, "polymaker_db.json")
ORCA_DIR    = os.path.join(DATA_HOME, "orca_profiles")
OUTPUT_DIR  = os.path.join(DATA_HOME, "output")
CONFIG_PATH = os.environ.get("SPOOLSCRIBE_CONFIG_PATH") or os.path.join(user_data_dir(), "config.json")

# Les scrapers (process séparés, lancés via runpy) ne peuvent pas importer
# core ; on leur transmet le dossier inscriptible via l'environnement.
os.environ.setdefault("SPOOLSCRIBE_DATA_HOME", DATA_HOME)
os.environ.setdefault("SPOOLSCRIBE_RESOURCE_DIR", RESOURCE_DIR)
# The printer list was loaded at import time, before these paths were known:
# reload it so a newer user copy in DATA_HOME is taken into account.
printer_profiles.reload()


def _seed_writable_data() -> None:
    """
    Au premier lancement en .exe, recopie les ressources embarquées (DB,
    profils Orca, logo) vers le dossier inscriptible pour que l'app
    fonctionne hors-ligne et que les mises à jour persistent.
    """
    if not _FROZEN:
        return
    bundled_path = Path(RESOURCE_DIR) / "data" / "polymaker_db.json"
    if not bundled_path.is_file():
        if not Path(DB_PATH).exists():
            db_io.save_db(EMPTY_DB.copy(), DB_PATH)
        return
    bundled = db_io.load_db(bundled_path)
    extension_bytes = b""
    for filename in ("catalogue_ofd.json", "catalogue_spoolman.json"):
        extension_path = bundled_path.with_name(filename)
        if extension_path.is_file():
            extension_bytes += extension_path.read_bytes()
            bundled.update(db_io.merge_bundled_db(bundled, db_io.load_db(extension_path))[0])
    digest = hashlib.sha256(bundled_path.read_bytes() + extension_bytes).hexdigest()
    if os.path.exists(DB_PATH):
        local = db_io.load_db(DB_PATH)
        if local.get("_bundled_digest") != digest:
            merged, conflicts = db_io.merge_bundled_db(local, bundled)
            local.update(merged)
            local["_bundled_digest"] = digest
            local["_bundle_conflicts"] = conflicts
            db_io.save_db(local, DB_PATH)
    else:
        bundled["_bundled_digest"] = digest
        db_io.save_db(bundled, DB_PATH)
    for sub, dst in (("data", DATA_DIR), ("orca_profiles", ORCA_DIR)):
        src = os.path.join(RESOURCE_DIR, sub)
        os.makedirs(dst, exist_ok=True)
        if os.path.isdir(src):
            for name in os.listdir(src):
                if name == "polymaker_db.json":
                    continue
                s = os.path.join(src, name)
                d = os.path.join(dst, name)
                if os.path.isfile(s) and not os.path.exists(d):
                    # Exclusive creation: never replace a user's resource.
                    with open(d, "xb") as stream:
                        stream.write(Path(s).read_bytes())

# Pipeline de mise à jour : (fichier_script, libellé, timeout_s)
UPDATE_PIPELINE: list[tuple[str, str, int]] = [
    ("sync_universal_catalogue.py",    "Catalogue multi-fabricants OFD", 900),
    ("sync_spoolman_catalogue.py",     "Fabricants complémentaires SpoolmanDB", 300),
    ("scrape_wholesale.py",            "Scrape wholesale",          120),
    ("scrape_wiki_hex.py",             "Scrape hex wiki",            60),
    ("scrape_spoolman_hex.py",         "Scrape hex SpoolmanDB",      60),
    ("scrape_thefilamentdb_hex.py",    "Scrape hex TheFilamentDB",   60),
    ("scrape_internal_exact_hex.py",   "Scrape hex internal exact",  30),
    ("sync_polymaker_brand_assets.py", "Sync Polymaker brand assets",60),
    ("sync_multibrand_assets.py",      "Sync Prusament/ROSA3D assets",60),
    ("seed_prusament.py",               "Seed Prusament (table interne)",30),
    ("seed_rosa3d.py",                   "Seed ROSA3D (table interne)",   30),
    ("scrape_spoolman_multibrand_hex.py",    "Scrape hex SpoolmanDB (Prusament/ROSA3D)",   60),
    ("scrape_thefilamentdb_multibrand_hex.py","Scrape hex TheFilamentDB (Prusament/ROSA3D)",60),
    ("download_orca_profiles.py",      "Download profils Orca",     120),
    ("import_orca_profiles.py",        "Import profils Orca",        60),
]

# ─── Transparence réseau ──────────────────────────────────────────────────
# NETWORK_SOURCES (liste exhaustive des hôtes contactés, affichée avant tout
# accès réseau) est dérivée de SOURCE_GROUPS en fin de module.

# Cadence de l'actualisation automatique au lancement (update_interval_days) :
# 0 = à chaque lancement, n > 0 = au plus une fois tous les n jours,
# -1 = jamais (manuelle uniquement). Le consentement réseau reste requis.
UPDATE_INTERVAL_CHOICES = ((0, "À chaque lancement"), (1, "Une fois par jour"),
                           (7, "Une fois par semaine"), (-1, "Manuellement seulement"))

DEFAULT_CONFIG = {
    "language": "auto",
    "network_consent": None,    # None = jamais demandé ; True/False = choix explicite
    "auto_update": False,       # conservé pour les anciens réglages ; la cadence fait foi
    "update_interval_days": 1,
    "last_update": None,
    "last_update_attempt": None,   # dernière tentative (succès ou non), hors base de données
    "last_update_status": None,
    "orca_overrides": False,   # Explicit choice before replacing local values at export.
    "network_sources_revision": 0,
    "nfc_tag_type": "NTAG216",
    "nfc_profile": "auto",
    "nfc_format": "openspool",
    "opentag3d_output": "nfctools-mobile",
    "opentag3d_settings": {},
    "printer_profile": "u1",
    "printer_firmware": None,
    "selected_sources": ["polymaker", "ofd", "spoolman", "bambu", "sunlu"],
    "ui": {},
    "favorite_brands": [],
    "favorite_filaments": [],
    "colour_delta_max": 10.0,  # Screen-colour search scope, not a printing tolerance.
    "preferred_weight_g": 1000,
    "preferred_packaging": "any",
    "export_directory": "",
    "show_extra_fields": False,
    "nfc_reserved_bytes": 0,
    "qr_label": {},            # QR paper profile only (spoolscribe.qr_layout.validate_settings).
}
NETWORK_SOURCES_REVISION = 2


def load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        merged = dict(DEFAULT_CONFIG)
        merged.update(cfg)
        return merged
    except Exception:
        return dict(DEFAULT_CONFIG)


def valid_colour_delta_limit(value):
    import math
    return value is None or (type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 200)


def colour_delta_limit(cfg=None):
    value = (load_config() if cfg is None else cfg).get("colour_delta_max", 10.0)
    return value if valid_colour_delta_limit(value) else 10.0


def save_config(cfg: dict) -> None:
    db_io.atomic_write(CONFIG_PATH, json.dumps(cfg, indent=2, ensure_ascii=False,
                                             allow_nan=False).encode("utf-8"))


def export_directory(cfg=None) -> str:
    value=(cfg if cfg is not None else load_config()).get('export_directory')
    return value if isinstance(value,str) and value and os.path.isabs(value) and '\x00' not in value else OUTPUT_DIR


def has_network_consent() -> bool:
    """True uniquement si l'utilisateur a explicitement accepté l'accès réseau."""
    cfg = load_config()
    return cfg.get("network_consent") is True and cfg.get("network_sources_revision") == NETWORK_SOURCES_REVISION


def consent_was_asked() -> bool:
    cfg = load_config()
    return cfg.get("network_consent") is False or has_network_consent()


def set_network_consent(value: bool, auto_update: "bool | None" = None) -> None:
    cfg = load_config()
    cfg["network_consent"] = bool(value)
    cfg["network_sources_revision"] = NETWORK_SOURCES_REVISION
    if auto_update is not None:
        cfg["auto_update"] = bool(auto_update)
    save_config(cfg)


def mark_updated() -> None:
    cfg = load_config()
    cfg["last_update"] = datetime.now().isoformat()
    save_config(cfg)


def update_due(cfg: Optional[dict] = None, now: Optional[datetime] = None) -> bool:
    """Whether the launch refresh should run, according to the configured cadence.

    A manual update (button/CLI) ignores this and always runs after consent.
    """
    cfg = cfg if cfg is not None else load_config()
    interval = cfg.get("update_interval_days")
    if type(interval) is not int:
        interval = DEFAULT_CONFIG["update_interval_days"]
    if interval < 0:
        return False
    if interval == 0:
        return True
    last = cfg.get("last_update_attempt")
    if not isinstance(last, str) or not last:
        return True
    try:
        elapsed = ((now or datetime.now()) - datetime.fromisoformat(last)).total_seconds()
    except ValueError:
        return True
    return elapsed >= interval * 86400


# ─── Environnement Python ─────────────────────────────────────────────────
def is_frozen() -> bool:
    """True si on tourne dans un bundle PyInstaller (.exe / .app)."""
    return bool(getattr(sys, "frozen", False))


def venv_python() -> str:
    """Retourne le Python du venv local s'il existe, sinon sys.executable."""
    for candidate in (
        os.path.join(SCRIPT_DIR, ".venv", "Scripts", "python.exe"),  # Windows
        os.path.join(SCRIPT_DIR, ".venv", "bin", "python"),           # Unix
    ):
        if os.path.isfile(candidate):
            return candidate
    return sys.executable


RUN_SCRIPT_FLAG = "--run-script"


def _script_command(python: str, script_path: str) -> list[str]:
    """
    Commande pour exécuter un script scraper.

    - En mode normal : [python, script_path]
    - En mode gelé (PyInstaller) : on relance l'exécutable lui-même avec
      RUN_SCRIPT_FLAG, car aucun interpréteur Python externe n'est garanti.
    """
    if is_frozen():
        return [sys.executable, RUN_SCRIPT_FLAG, script_path]
    return [python, script_path]


def maybe_run_as_script_worker(argv: list[str]) -> bool:
    """
    À appeler en tout début de main(). Si argv contient RUN_SCRIPT_FLAG,
    exécute le script demandé puis termine le process. Retourne True si
    on a agi comme worker (l'appelant doit alors retourner immédiatement).
    """
    if RUN_SCRIPT_FLAG in argv:
        idx = argv.index(RUN_SCRIPT_FLAG)
        if idx + 1 < len(argv):
            script_path = argv[idx + 1]
            if os.path.basename(script_path) == script_path:
                script_path = os.path.join(SCRIPTS_DIR, script_path)
            # The packaged application only runs its own bundled workers. CI
            # probes opt in explicitly through the environment.
            inside = Path(script_path).resolve()
            allowed_roots = [Path(SCRIPTS_DIR).resolve()]
            if os.environ.get("SPOOLSCRIBE_RUN_SCRIPT_ALLOW"):
                allowed_roots.append(Path(os.environ["SPOOLSCRIBE_RUN_SCRIPT_ALLOW"]).resolve())
            if not any(root == inside or root in inside.parents for root in allowed_roots) or not inside.is_file():
                print(f"Script refusé : {script_path} (seuls les workers embarqués sont autorisés)", file=sys.stderr)
                raise SystemExit(2)
            # Les scripts impriment des caractères Unicode (—, ─…). Dans un exe
            # gelé sous Windows, stdout/stderr utilisent cp1252 par défaut, ce
            # qui provoque un UnicodeEncodeError. On force l'UTF-8.
            for _stream in (sys.stdout, sys.stderr):
                try:
                    _stream.reconfigure(encoding="utf-8", errors="replace")
                except Exception:
                    pass
            import runpy
            # Standalone scripts import the same helper in source and frozen mode.
            if RESOURCE_DIR not in sys.path:
                sys.path.insert(0, RESOURCE_DIR)
            sys.argv = [script_path]
            runpy.run_path(script_path, run_name="__main__")
        return True
    return False


# ─── DB : lecture / écriture ──────────────────────────────────────────────
_RESTORED_DB_PATHS: set[str] = set()


def db_restored_this_session(path: Optional[str] = None) -> bool:
    """A successful restore inhibits automatic changes for this process only."""
    return str(Path(path or DB_PATH).resolve()) in _RESTORED_DB_PATHS


def load_db(path: Optional[str] = None) -> dict:
    """Corrupt files are reported, never silently replaced with an empty DB."""
    default_path = path is None
    path = path or DB_PATH
    if default_path and not Path(path).exists():
        db_io.save_db(EMPTY_DB.copy(), path)
    if _FROZEN and os.path.abspath(path) == os.path.abspath(DB_PATH) and not db_restored_this_session(path):
        _seed_writable_data()
    db = db_io.load_db(path)
    # Older installations and some sources list product lines as brands.
    catalogue_sources.normalize_brand_lines(db)
    # Development also uses the separately audited offline extension. Preserve
    # revision metadata and never write just because the catalogue was opened.
    if not _FROZEN and not db_restored_this_session(path):
        for filename, source_name in (("catalogue_ofd.json", "Open Filament Database"),
                                      ("catalogue_spoolman.json", "SpoolmanDB")):
            extension = Path(path).with_name(filename)
            if extension.is_file():
                merged, conflicts = db_io.merge_bundled_db(db, db_io.load_db(extension))
                # Snapshot records keep their source provenance: should they be
                # saved, a later refresh can still update them (they are not user edits).
                for section in ("_products", "_skus"):
                    for key, item in merged.get(section, {}).items():
                        if key not in db.get(section, {}) and "_field_sources" not in item:
                            item["_field_sources"] = {k: dict(source=item.get("source", source_name), rank=20, value=copy.deepcopy(v))
                                                      for k, v in item.items() if not k.startswith("_")}
                db.update(merged)
                if conflicts:
                    db.setdefault("_bundle_conflicts", []).extend(conflicts)
    return db


def save_db(db: dict, path: Optional[str] = None) -> None:
    db_io.save_db(db, path or DB_PATH)


def restore_db(path: Optional[str] = None, backup: Optional[str] = None) -> None:
    path = path or DB_PATH
    db_io.restore_db(path, backup)
    _RESTORED_DB_PATHS.add(str(Path(path).resolve()))


def db_stats(db: dict) -> dict:
    """Statistiques rapides pour les en-têtes d'UI."""
    skus = db.get("_skus", {})
    return {
        "skus": len(skus),
        "products": len(db.get("_products", {})),
        "missing_hex": sum(1 for v in skus.values() if not v.get("hex")),
        "last_updated": db.get("_last_updated"),
    }


def db_age_days(db: dict) -> Optional[float]:
    """Âge de la DB en jours, ou None si inconnu."""
    last = db.get("_last_updated")
    if isinstance(last, str) and last:
        try:
            return (datetime.now() - datetime.fromisoformat(last)).total_seconds() / 86400
        except Exception:
            return None
    return None


def db_needs_update(db: dict, max_age_days: int = 7) -> bool:
    age = db_age_days(db)
    return age is None or age >= max_age_days


# ─── Validation / utilitaires ─────────────────────────────────────────────
def validate_hex(h: str) -> Optional[str]:
    """Retourne le HEX normalisé en MAJUSCULES (6 chars) ou None si invalide."""
    if not isinstance(h, str):
        return None
    h = h.strip().removeprefix("#")
    return h.upper() if re.fullmatch(r"[0-9A-Fa-f]{6}", h) else None


def slugify(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", name or "")


# ─── Profils Orca ─────────────────────────────────────────────────────────
def find_orca_profile(product_name: str) -> Optional[str]:
    """Chemin du profil Orca pour ce produit, ou None."""
    if not os.path.isdir(ORCA_DIR):
        return None
    # Universal material/product names can contain '/' (e.g. PA6/66). They
    # cannot name one of our flat legacy presets, so no override is applicable.
    if "/" in product_name or "\\" in product_name or len(product_name.encode("utf-8")) > 190:
        return None
    path = os.path.join(ORCA_DIR, f"{product_name} @Snapmaker U1 - OrcaSlicer.json")
    if Path(path).resolve().parent != Path(ORCA_DIR).resolve():
        raise ExportValidationError("Le profil Orca doit rester dans son dossier de ressources.")
    return path if os.path.isfile(path) else None


def load_orca_temps(path: str) -> dict:
    """Validate all physical values before applying an Orca override."""
    try:
        return db_io.orca_values(db_io.parse_json(Path(path).read_bytes()))
    except (DatabaseError, OSError) as exc:
        raise ExportValidationError(f"Profil Orca inutilisable ({path}) : {exc}") from exc


def _apply_orca(src: dict, path: str, use_orca_overrides: bool) -> tuple[dict, set]:
    """The single Orca policy of both encoders: fill unknowns, or override on request.

    Mutates ``src`` and returns the profile values and the keys actually applied.
    Callers keep their own error wording; this helper only centralises the rule.
    """
    values = load_orca_temps(path)
    applied = set()
    for key, value in values.items():
        if value is not None and (use_orca_overrides or src.get(key) is None):
            src[key] = value
            applied.add(key)
    return values, applied


# ─── Logo SVG ─────────────────────────────────────────────────────────────
def app_logo_abs_path() -> Optional[str]:
    """Chemin absolu du logo de l'application SpoolScribe, ou None."""
    rel = "data/app/spoolscribe_logo.svg"
    for base in (DATA_HOME, RESOURCE_DIR):
        root = Path(base).resolve()
        # PyInstaller macOS places data in Resources and links Frameworks/data
        # to it. Compare resolved paths on both sides, keeping escape checks.
        for relative in resource_paths.resource_candidates(rel):
            candidate = (root / relative).resolve()
            if candidate.is_relative_to((root / "data").resolve()) and candidate.is_file():
                return str(candidate)
    return None


def app_icon_abs_path() -> Optional[str]:
    """Chemin absolu de l'icône binaire (.png) de l'application, ou None."""
    for name in ("app.png", "app.ico"):
        for base in (DATA_HOME, RESOURCE_DIR):
            for relative in resource_paths.resource_candidates("data/app/" + name):
                abs_p = os.path.join(base, relative)
                if os.path.exists(abs_p):
                    return abs_p
    return None


_LOGO_MANIFEST: Optional[dict] = None


def logo_manifest() -> dict:
    """Logos revus embarqués, indexés par clé de marque (lus une fois).

    Prend le pas sur le ``logo_path`` mémorisé dans une base : un logo
    remplacé dans une version suivante s'affiche sans resynchroniser.
    """
    global _LOGO_MANIFEST
    if _LOGO_MANIFEST is None:
        index = {}
        for base in (RESOURCE_DIR, DATA_HOME):
            # Read older user manifests without rewriting or migrating their files.
            for relative in ("data/brand_logos/manifest.json", "data/brands/manifest.json"):
                path = Path(base) / relative
                try:
                    for entry in db_io.parse_json(path.read_bytes()).values():
                        if isinstance(entry, dict) and entry.get("name") and entry.get("path"):
                            index[catalogue_sources.brand_key(entry["name"])] = entry["path"]
                except (OSError, DatabaseError):
                    continue
        _LOGO_MANIFEST = index
    return _LOGO_MANIFEST


def logo_abs_path(db: dict, brand: str = "Polymaker") -> Optional[str]:
    """Chemin absolu du logo de marque, ou None."""
    meta = db.get("_brands", {}).get(brand, {})
    logo_path = logo_manifest().get(catalogue_sources.brand_key(brand or "")) or meta.get("logo_path", "")
    if not logo_path:
        # Repli : nom de fichier nu dans `logo` → cherché sous data/.
        logo = (meta.get("logo") or "").strip()
        if logo:
            logo_path = logo if ("/" in logo or os.sep in logo) else f"data/{logo}"
    # Historical artwork is shipped independently of the downloaded metadata.
    legacy = {'polymaker':'data/polymaker_logo.svg','prusament':'data/prusament_logo.png','rosa3d':'data/rosa3d_logo.png'}.get(catalogue_sources.brand_key(brand or ''))
    for path in dict.fromkeys(p for p in (logo_path, legacy) if p):
        rel = path.replace("/", os.sep)
        # Données inscriptibles (mises à jour) d'abord, puis bundle en repli.
        for base in (DATA_HOME, RESOURCE_DIR):
            root = Path(base).resolve()
            for relative in resource_paths.resource_candidates(rel):
                candidate = (root / relative).resolve()
                if candidate.is_relative_to((root / "data").resolve()) and candidate.is_file():
                    return str(candidate)
    return None


def logo_signature(abs_path: Optional[str]) -> str:
    """Signature factuelle courte du SVG (viewBox / fill)."""
    if not abs_path or not os.path.exists(abs_path):
        return "(absent)"
    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            svg = f.read()
        m_view = re.search(r'viewBox="([^"]+)"', svg)
        m_fill = re.search(r'fill="([^"]+)"', svg)
        return (f"{os.path.basename(abs_path)} | "
                f"viewBox {m_view.group(1) if m_view else '?'} | "
                f"fill {m_fill.group(1) if m_fill else '?'}")
    except Exception:
        return os.path.basename(abs_path)


# ─── Lookup / fiche produit ───────────────────────────────────────────────
@dataclass
class SkuView:
    """Vue agrégée d'un SKU prête à afficher (CLI ou GUI)."""
    sku: str
    product: str
    color_name: str
    hex: Optional[str]
    product_data: dict
    brand_meta: Optional[dict] = None

    @property
    def display_product(self) -> str:
        return self.product_data.get("display_name") or self.product

    @property
    def type_str(self) -> str:
        t = self.product_data.get("type", "")
        st = self.product_data.get("subtype")
        return f"{t} [{st}]" if st else t

    @property
    def nozzle_str(self) -> str:
        lo, hi = self.product_data.get("min_temp"), self.product_data.get("max_temp")
        return "Non renseigné" if lo is None or hi is None else f"{lo}–{hi} °C"

    @property
    def bed_str(self) -> str:
        lo = self.product_data.get("bed_min_temp")
        hi = self.product_data.get("bed_max_temp")
        if lo is None or hi is None:
            return "Non renseigné"
        return f"{lo} °C" if lo == hi else f"{lo}–{hi} °C"

    @property
    def density_str(self) -> str:
        value = self.product_data.get("density")
        return f"{value} g/cm³" if value is not None else "Non renseignée"

    @property
    def diameter_str(self) -> str:
        d = self.product_data.get("diameter")
        return f"{d} mm" if d is not None else "—"


def get_sku_view(db: dict, sku: str) -> Optional[SkuView]:
    """Construit une SkuView, ou None si SKU ou produit introuvable."""
    entry = db.get("_skus", {}).get(sku)
    if not entry:
        return None
    product_name = entry.get("product", "")
    product_data = db.get("_products", {}).get(product_name)
    if not product_data:
        return None
    # Métadonnées de marque résolues dynamiquement (multi-marques :
    # Polymaker, Prusament, …) à partir du champ `brand` du produit.
    brand = product_data.get("brand")
    brand_meta = db.get("_brands", {}).get(brand) if brand else None
    return SkuView(
        sku=sku,
        product=product_name,
        color_name=entry.get("color_name", ""),
        hex=entry.get("hex"),
        product_data=product_data,
        brand_meta=brand_meta,
    )


def list_skus(db: dict) -> list[dict]:
    """Liste triée des SKUs sous forme de dicts simples (pour table GUI/CLI)."""
    skus = db.get("_skus", {})
    out = []
    for sku in sorted(skus):
        e = skus[sku]
        p = db.get("_products", {}).get(e.get("product"), {})
        issues = []
        if not p:
            issues.append("Produit absent")
        if not validate_hex(e.get("hex")):
            issues.append("Couleur à renseigner")
        source_colors = e.get("source_colors", [])
        if source_colors and (len(source_colors) > 5 or any(len(c) != 6 for c in source_colors)):
            issues.append("Couleurs multiples incompatibles avec OpenSpool")
        try:
            _validate_physical(p)
        except ExportValidationError:
            issues.append("Caractéristiques à compléter")
        # Source values that contradict themselves are kept visible but need a
        # confirmation before they can reach a tag.
        suspect_color = db_io.implausible_color(e)
        if suspect_color:
            issues.append(f"Couleur à vérifier ({suspect_color})")
        suspect_physical = db_io.implausible_physical(p)
        if suspect_physical:
            issues.append("Caractéristiques à vérifier (" + " ; ".join(suspect_physical) + ")")
        if not p.get("brand") or not p.get("type"):
            issues.append("Marque ou matière absente")
        family, variant = material_family(p.get("type", ""))
        hex_info = (e.get("_field_sources") or {}).get("hex") or {}
        row = {
            "sku": sku,
            # Human-readable reference: the manufacturer article when known,
            # otherwise the internal identifier (OFD-…/SMDB-… are not SKUs).
            "reference": e.get("manufacturer_sku") or sku,
            "product": p.get("display_name") or e.get("product", ""),
            "color_name": e.get("color_name", ""),
            "hex": e.get("hex"),
            "brand": p.get("brand", ""),
            "material": p.get("type", ""),
            "family": family,
            "variant": variant,
            "line": p.get("line", ""),
            "diameter": p.get("diameter"),
            "weight": e.get("weight"),
            "density": p.get("density"),
            "ready": not issues,
            "quality": " ; ".join(issues) or "Export possible",
            "source_id": e.get("source_id", ""),
            "manufacturer_sku": e.get("manufacturer_sku", ""),
            "alpha": e.get("alpha"),
            "source_colors": e.get("source_colors", []),
            # Display/search projection only: lets the proximity search exclude
            # multicolour references; exports keep reading the stored entry.
            "additional_color_hexes": list(e.get("additional_color_hexes") or []),
            "source_traits": e.get("source_traits", {}),
            "spool_refill": e.get("spool_refill"),
            "_hex_rank": hex_info.get("rank", 0) if e.get("hex") else -1,
        }
        # Normalised once here, not for every keystroke and every row.
        row["_search"] = _search_key(" ".join(str(row.get(k) or "") for k in
                                              ("sku", "source_id", "manufacturer_sku", "brand", "material", "product", "color_name", "hex")))
        out.append(row)
    return out


# ─── Familles de matières ────────────────────────────────────────────────
# Les sources écrivent la matière de façons diverses (« ABS+MATTE »,
# « EASYASA », « HTPLA+ », « PA6-CF »). Le filtre et le regroupement utilisent
# la famille ; la valeur source reste affichée et exportée telle quelle.
MATERIAL_FAMILIES = (
    "PLA", "PETG", "PCTG", "PET", "ABS", "ASA", "TPU", "TPE", "TPC", "TPI", "PA", "PC", "PP", "PVA",
    "HIPS", "PEEK", "PEKK", "PEI", "PPSU", "PSU", "PES", "PPS", "PBT", "POM", "PMMA", "PVB", "PVDF",
    "PHA", "PCL", "EVA", "PVC", "CPE", "BVOH", "PPE", "PEBA",
)
_MATERIAL_ALIASES = {"BVOH": "PVA", "PVOH": "PVA", "PPA": "PA", "NYLON": "PA", "PA6": "PA", "PA66": "PA",
                     "PA11": "PA", "PA12": "PA"}
_MATERIAL_PREFIXES = {"HT": "HT", "EASY": "Easy", "LW": "LW", "HS": "HS", "RAPID": "Rapid", "HF": "HF"}


def material_family(material: str) -> tuple[str, str]:
    """(famille, variante) d'un libellé de matière source ; famille inconnue = libellé nettoyé."""
    raw = re.sub(r"\s+", "", str(material or "")).upper()
    if not raw:
        return "", ""
    prefix = ""
    for key, label in _MATERIAL_PREFIXES.items():
        if raw.startswith(key) and len(raw) > len(key) and raw[len(key)] not in "+-":
            candidate = raw[len(key):]
            if any(candidate.startswith(f) for f in (*MATERIAL_FAMILIES, *_MATERIAL_ALIASES)):
                prefix, raw = label, candidate
                break
    base = next((f for f in sorted((*MATERIAL_FAMILIES, *_MATERIAL_ALIASES), key=len, reverse=True) if raw.startswith(f)), "")
    if not base:
        return raw.title() if raw.islower() else raw, prefix
    rest = raw[len(base):]
    family = _MATERIAL_ALIASES.get(base, base)
    grade = base if base in _MATERIAL_ALIASES and base not in ("BVOH", "PVOH", "NYLON") else ""
    rest = re.sub(r"^[-_/ ]+", "", rest)
    rest = rest.replace("MATTE", "Matte").replace("GLOSS", "Gloss").replace("SILK", "Silk")
    parts = [p for p in (prefix, grade, rest) if p]
    return family, " ".join(parts)


def fmt_int(value: int) -> str:
    """Nombre avec séparateur de milliers français (espace fine insécable)."""
    return f"{value:,}".replace(",", "\u202f")


def filament_identity(row: dict) -> tuple:
    """Presentation identity, not a destructive merge or an assertion of equivalence.

    Only punctuation/trademarks and a leading manufacturer name in the colour
    are normalized. Grades, diameter, transparency and multicolours stay distinct.
    """
    from scripts.catalogue_merge import normalized
    brand = catalogue_sources.brand_key(row.get("brand", ""))
    product = normalized(row.get("product"))
    if product.startswith(brand): product = product[len(brand):]
    color = display_color(row)
    return (brand, product, normalized(color), normalized(row.get("material")),
            row.get("diameter"), row.get("alpha"), tuple(row.get("source_colors") or []),
            tuple(sorted((row.get("source_traits") or {}).items())))


def display_color(row: dict) -> str:
    color = str(row.get("color_name") or "").strip()
    brand = str(row.get("brand") or "").strip()
    if brand:
        color = re.sub(r"^" + re.escape(brand) + r"(?:[™®]?[\s:–-]+)", "", color, flags=re.I)
    return color


def group_filaments(rows: list[dict]) -> list[dict]:
    """Group display variants, preserving every source reference and its values."""
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        groups.setdefault(filament_identity(row), []).append(row)
    out = []
    for identity_key, members in groups.items():
        ranked = sorted(members, key=lambda r: (-r.get("_hex_rank", 0), not r.get("ready"), r["sku"]))
        primary = ranked[0]
        group = dict(primary)
        group["filament_id"] = hashlib.sha256(json.dumps(identity_key, ensure_ascii=False).encode()).hexdigest()
        group["color_name"] = display_color(primary)
        group["variants"] = [dict(r) for r in sorted(members, key=lambda r: (r.get("diameter") or 0, r.get("weight") or 0, r["sku"]))]
        group["variant_count"] = len(members)
        group["hex_variants"] = len({r["hex"] for r in members if r.get("hex")})
        if group["hex_variants"] > 1:
            group["ready"] = False
            group["quality"] = "Teintes à vérifier — choisir une référence"
        group["_search"] = " ".join(_row_search(r) for r in members)
        out.append(group)
    return out


CATALOGUE_SORT_FIELDS = {
    "reference": "Référence", "sku": "Réf. interne", "brand": "Fabricant", "material": "Matière",
    "product": "Produit", "color_name": "Couleur", "diameter": "Diamètre",
    "weight": "Masse", "density": "Densité", "quality": "État des données",
}


def _search_key(value) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(value or "")).casefold()
                   if not unicodedata.combining(c))


def _row_search(r: dict) -> str:
    cached = r.get("_search")
    if cached is None:
        cached = r["_search"] = _search_key(" ".join(str(r.get(k) or "") for k in
                                                   ("sku", "source_id", "manufacturer_sku", "brand", "material", "product", "color_name", "hex")))
    return cached


def query_catalogue(rows: list[dict], *, text: str = "", brand: str = "", material: str = "",
                    quality: str = "all", sort1: str = "brand", sort2: str = "product",
                    descending1: bool = False, descending2: bool = False) -> list[dict]:
    """Filter the entire catalogue, then apply two stable keys (numeric where appropriate)."""
    if sort1 not in CATALOGUE_SORT_FIELDS or sort2 not in (*CATALOGUE_SORT_FIELDS, ""):
        raise ValueError("Colonne de tri inconnue.")
    if quality not in ("all", "ready", "incomplete", "suspect"):
        raise ValueError("Filtre de qualité inconnu.")
    terms = _search_key(text).split()
    brand_key, material_key = brand.casefold().strip(), material.casefold().strip()
    result = [r for r in rows if (not brand_key or r["brand"].casefold() == brand_key)
              and (not material_key or material_key in (r["material"].casefold(), r.get("family", "").casefold()))
              and (quality == "all" or (quality == "suspect" and "à vérifier" in r["quality"].casefold())
                   or (quality in ("ready", "incomplete") and r["ready"] == (quality == "ready")))
              and all(t in _row_search(r) for t in terms)]
    result.sort(key=lambda r: _search_key(r["sku"]))
    for key, reverse in ((sort2, descending2), (sort1, descending1)):
        if not key:
            continue
        # Unknown numeric values always come last, including in descending order.
        known = [r for r in result if r.get(key) is not None and r.get(key) != ""]
        missing = [r for r in result if r.get(key) is None or r.get(key) == ""]
        known.sort(key=lambda r: r[key] if key in ("diameter", "weight", "density") else _search_key(r[key]),
                   reverse=reverse)
        result = known + missing
    return result


def add_sku(db: dict, sku: str, product: str, color_name: str,
            hex_val: Optional[str] = None, persist: bool = True,
            path: Optional[str] = None) -> dict:
    """Ajoute/maj un SKU dans la DB. Retourne l'entrée créée."""
    openspool_filename(sku, product, color_name)
    if product not in db.get("_products", {}):
        raise ExportValidationError("Produit inconnu pour ce nouveau SKU.")
    if hex_val is not None and not validate_hex(hex_val):
        raise ExportValidationError("HEX invalide pour ce nouveau SKU.")
    entry = {"product": product, "color_name": color_name, "hex": validate_hex(hex_val) if hex_val else None}
    db.setdefault("_skus", {})[sku] = entry
    if persist:
        save_db(db, path)
    return entry


def set_sku_hex(db: dict, sku: str, hex_val: str, persist: bool = True,
                path: Optional[str] = None, *, alpha: Optional[str] = None) -> Optional[str]:
    """Définit le HEX d'un SKU. Retourne le HEX normalisé ou None si invalide."""
    norm = validate_hex(hex_val)
    if not norm:
        return None
    if sku not in db.get("_skus", {}):
        raise ExportValidationError("SKU introuvable pour enregistrer cette couleur.")
    if alpha is not None and (not isinstance(alpha, str) or not re.fullmatch(r"[0-9A-Fa-f]{2}", alpha)):
        raise ValueError("Opacité alpha invalide : deux caractères HEX requis.")
    if sku in db.get("_skus", {}):
        import copy
        previous = copy.deepcopy(db["_skus"][sku])
        provenance = db["_skus"][sku].setdefault("_field_sources", {})
        provenance["hex"] = db_io.user_correction(norm)
        if alpha is not None: provenance["alpha"] = db_io.user_correction(alpha.upper())
        db["_skus"][sku]["hex"] = norm
        if alpha is not None:
            db["_skus"][sku]["alpha"] = alpha.upper()
        try:
            if persist:
                save_db(db, path)
        except Exception:
            db["_skus"][sku] = previous
            raise
    return norm


def set_product_physical(db: dict, sku: str, values: dict, *, path: Optional[str] = None) -> None:
    """Explicit local edit of a product's shared physical fields; unknowns remain null."""
    view = get_sku_view(db, sku)
    allowed = {"min_temp", "max_temp", "bed_min_temp", "bed_max_temp", "density", "diameter"}
    if view is None or not values or set(values) - allowed:
        raise ExportValidationError("Produit ou caractéristiques à corriger invalides.")
    import copy
    updated = copy.deepcopy(view.product_data)
    updated.update(values)
    for field, value in values.items():
        updated.setdefault("_field_sources", {})[field] = db_io.user_correction(value)
    db_io.validate_db({"_products": {view.product: updated}})
    for key, value in values.items():
        if key.endswith("temp") and value is not None and int(value) != value:
            raise ExportValidationError("Les températures doivent être entières.")
    # Publish through the revision-aware storage before updating the UI's object.
    import copy
    changed = copy.deepcopy(db)
    changed["_products"][view.product] = updated
    save_db(changed, path)
    db.clear()
    db.update(changed)
    if isinstance(db, db_io.Database):
        db.revision, db.source_path = changed.revision, changed.source_path


def save_personal_filament(db: dict, sku: str, values: dict, suffix: str, *, path=None) -> str:
    """Save one independent spool reference; never rename or modify its source.

    Copied values are frozen at personal priority; only explicitly edited values
    become user-confirmed. Copying must not confirm an implausible source colour.
    An explicit ``hex`` is stored on the copy's own reference, never on the source.
    """
    import uuid
    suffix=suffix.strip().lstrip('@').strip() if isinstance(suffix,str) else ''
    if not suffix or len(suffix)>40 or not all(c.isalnum() or c in ' _-' for c in suffix):
        raise ExportValidationError('Suffixe personnel : 1 à 40 lettres, chiffres, espaces, tirets ou underscores.')
    view=get_sku_view(db,sku)
    allowed={'min_temp','max_temp','bed_min_temp','bed_max_temp','density','diameter','hex'}
    if view is None or not values or set(values)-allowed:raise ExportValidationError('Caractéristiques personnelles invalides.')
    for key,value in values.items():
        if key.endswith('temp') and value is not None and (type(value) not in (int,float) or not math.isfinite(value) or int(value)!=value):
            raise ExportValidationError('Les températures doivent être entières.')
    colour=None
    if 'hex' in values:
        colour=validate_hex(values['hex']) if isinstance(values['hex'],str) else None
        if not colour:raise ExportValidationError('Couleur invalide : six caractères HEX requis.')
    physical={key:value for key,value in values.items() if key!='hex'}
    origin=db['_skus'][sku].get('_personal_origin') or sku
    existing=next((key for key,record in db['_skus'].items() if record.get('_personal') and record.get('_personal_origin')==origin and record.get('_personal_suffix')==suffix),None)
    changed=copy.deepcopy(db);entry=copy.deepcopy(db['_skus'][existing or sku])
    product=copy.deepcopy(get_sku_view(db,existing).product_data if existing else view.product_data)
    identifier=existing or 'USER-'+uuid.uuid4().hex
    pkey=entry['product'] if existing else '@personal/'+identifier
    base=product.get('_personal_base_name') or view.display_product
    product.update(physical);product.update(display_name=f'{base} @{suffix}',_personal=True,_personal_base_name=base)
    entry.update(product=pkey,source='Personnalisation locale',_personal=True,_personal_suffix=suffix,
                 _personal_origin=origin)
    # Keep the original source reference as metadata, but give the copy its own identity.
    for record in (entry,product):
        previous=record.get('_field_sources',{})
        record['_field_sources']={key:(copy.deepcopy(previous[key]) if previous.get(key,{}).get('source')==db_io.USER_SOURCE else
            dict(source='Copie personnelle',rank=db_io.USER_RANK,value=copy.deepcopy(value))) for key,value in record.items() if not key.startswith('_')}
    for key,value in physical.items():product['_field_sources'][key]=db_io.user_correction(value)
    if colour:
        entry['hex']=colour;entry['_field_sources']['hex']=db_io.user_correction(colour)
    changed['_products'][pkey]=product;changed['_skus'][identifier]=entry
    db_io.validate_db(changed)
    save_db(changed,path)
    db.clear();db.update(changed)
    if isinstance(db,db_io.Database):db.revision,db.source_path=changed.revision,changed.source_path
    return identifier


# ─── Comparaison des valeurs (présentation, aucune écriture) ──────────────
COMPARED_FIELDS = ("min_temp", "max_temp", "bed_min_temp", "bed_max_temp", "diameter", "density", "hex")
_OPENTAG_BOUNDS = {"min_temp": "min_print_temp", "max_temp": "max_print_temp",
                   "bed_min_temp": "min_bed_temp", "bed_max_temp": "max_bed_temp"}


def field_provenance(record: dict, key: str) -> dict:
    """Classify the winning provenance of one stored value; never upgrade it.

    ``manufacturer`` requires a manufacturer-rank source. A value without any
    provenance record stays ``unknown`` (historical catalogue, older installs).
    """
    info = (record.get("_field_sources") or {}).get(key) if isinstance(record, dict) else None
    if not isinstance(info, dict) or not info:
        return {"kind": "unknown", "source": None}
    source = info.get("source")
    if source == db_io.USER_SOURCE:
        kind = "user"
    elif source == "Copie personnelle":
        kind = "copy"
    elif isinstance(info.get("rank"), (int, float)) and info["rank"] >= db_io.MANUFACTURER_RANK:
        kind = "manufacturer"
    else:
        kind = "source"
    return {"kind": kind, "source": source}


def value_comparison(db: dict, sku: str, *, use_orca_overrides: bool = False, nfc_format: str = "openspool",
                     opentag_settings: Optional[dict] = None) -> Optional[dict]:
    """Reference / Orca / personal / effective values per field, for display only.

    Effective values follow the encoders' own policy (``_apply_orca`` and the
    OpenTag3D explicit settings); a value that is unknown stays ``None``. The
    reference of a personal copy is its origin's *current* record when present.
    """
    view = get_sku_view(db, sku)
    if view is None:
        return None
    entry = db["_skus"][sku]
    product = view.product_data
    personal = bool(entry.get("_personal"))
    origin_entry = origin_product = None
    if personal:
        origin = entry.get("_personal_origin")
        origin_entry = db["_skus"].get(origin) if origin and origin != sku else None
        origin_product = db["_products"].get(origin_entry.get("product")) if origin_entry else None
        reference_entry, reference_product = origin_entry, origin_product
    else:
        reference_entry, reference_product = entry, product
    result = {"sku": sku, "personal": personal, "origin_missing": personal and reference_product is None,
              "format": nfc_format, "orca": {"status": "none", "path": None, "values": {}, "applied": []},
              "targets": {}, "rows": []}
    effective = dict(product)
    orca_path = find_orca_profile(entry.get("product", ""))
    orca_values: dict = {}
    if orca_path:
        try:
            orca_values, applied = _apply_orca(effective, orca_path, use_orca_overrides)
            result["orca"] = {"status": "applied" if applied else "unused", "path": orca_path,
                              "values": orca_values, "applied": sorted(applied)}
        except (ValueError, TypeError, OSError) as exc:
            result["orca"] = {"status": "error", "path": orca_path, "values": {}, "applied": [], "message": str(exc)}
    elif personal and origin_entry:
        origin_path = find_orca_profile(origin_entry.get("product", ""))
        if origin_path:
            try:
                origin_values = load_orca_temps(origin_path)
            except ExportValidationError as exc:
                result["orca"] = {"status": "error", "path": origin_path, "values": {}, "applied": [], "message": str(exc)}
            else:
                # Shown for comparison only: the encoders do not apply it to the copy.
                result["orca"] = {"status": "origin_only", "path": origin_path, "values": origin_values, "applied": []}
    settings = opentag_settings if nfc_format == "opentag3d" and isinstance(opentag_settings, dict) else {}
    for key in COMPARED_FIELDS:
        if key == "hex":
            ref_value = reference_entry.get("hex") if reference_entry else None
            ref_info = field_provenance(reference_entry, "hex") if reference_entry else {"kind": "absent", "source": None}
            suspect = bool(reference_entry and db_io.implausible_color(reference_entry))
            own = entry.get("hex")
            effective_value = validate_hex(own)
            origin = "personal" if personal else "reference"
        else:
            ref_value = reference_product.get(key) if reference_product else None
            ref_info = field_provenance(reference_product, key) if reference_product else {"kind": "absent", "source": None}
            suspect = bool(reference_product and any(issue for issue in db_io.implausible_physical(
                {key: ref_value, "_field_sources": reference_product.get("_field_sources", {})})))
            own = product.get(key)
            effective_value = effective.get(key)
            origin = "orca" if key in result["orca"]["applied"] else "personal" if personal else "reference"
            if key in _OPENTAG_BOUNDS and _OPENTAG_BOUNDS[key] in settings:
                effective_value = settings[_OPENTAG_BOUNDS[key]]
                origin = "opentag_settings"
        row = {"key": key,
               "reference": {"value": ref_value, **ref_info, "suspect": suspect},
               "orca": ({"value": (result["orca"]["values"] or {}).get(key),
                         "applied": key in result["orca"]["applied"]} if key != "hex" and result["orca"]["values"] else None),
               "personal": ({"value": own, **field_provenance(product if key != "hex" else entry, key)} if personal else None),
               "effective": {"value": effective_value, "origin": origin}}
        row["differs"] = ref_value is not None and effective_value is not None and ref_value != effective_value
        result["rows"].append(row)
    if nfc_format == "opentag3d":
        result["targets"] = {key: settings.get(key) for key in ("print_temp", "bed_temp", "chamber_temp")}
    return result


# ─── Payload OpenSpool / NFC ──────────────────────────────────────────────
class ExportValidationError(ValueError):
    """Invalid data, before any output file is opened."""


class MissingColorError(ExportValidationError):
    pass


class NfcCapacityError(ExportValidationError):
    pass


NTAG215_NDEF_AREA_BYTES = 496
NTAG216_NDEF_AREA_BYTES = 872
NFC_CAPACITIES = {"NTAG215": NTAG215_NDEF_AREA_BYTES, "NTAG216": NTAG216_NDEF_AREA_BYTES}
# Explicit opt-in profile: preserve all printing/color values, omit descriptive fields only.
NFC_ESSENTIAL_FIELDS = ("protocol", "version", "type", "color_hex", "brand", "min_temp", "max_temp",
                        "bed_min_temp", "bed_max_temp", "diameter", "density", "subtype",
                        "alpha", "additional_color_hexes")
UPDATE_STATUS_LABELS = {"complete": "complète", "partial": "partielle", "failed": "en échec"}


def _validate_physical(values: dict) -> None:
    for key in ("min_temp", "max_temp", "bed_min_temp", "bed_max_temp", "diameter", "density"):
        value = values.get(key)
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ExportValidationError(f"{key} : nombre fini requis, reçu {value!r}.")
        if value < 0 or (key in ("diameter", "density") and value == 0):
            raise ExportValidationError(f"{key} : valeur physique invalide ({value!r}).")
        if key.endswith("temp") and int(value) != value:
            raise ExportValidationError(f"{key} : température entière requise.")
    for low, high in (("min_temp", "max_temp"), ("bed_min_temp", "bed_max_temp")):
        if values[low] > values[high]:
            raise ExportValidationError(f"Plage {low}/{high} inversée.")


def validate_openspool(payload: dict) -> None:
    if not isinstance(payload, dict):
        raise ExportValidationError("Le payload doit être un objet JSON.")
    if payload.get("protocol") != "openspool" or payload.get("version") != "1.0":
        raise ExportValidationError("Protocole openspool / version 1.0 requis.")
    for key in ("type", "brand"):
        if not isinstance(payload.get(key), str) or not payload[key].strip():
            raise ExportValidationError(f"{key} : texte non vide requis.")
    hx = payload.get("color_hex")
    if not isinstance(hx, str) or not re.fullmatch(r"[0-9A-F]{6}", hx):
        raise ExportValidationError("color_hex : six caractères HEX normalisés requis.")
    _validate_physical(payload)
    for key in ("subtype", "sku", "product", "color_name", "logo_url", "image"):
        if key in payload and payload[key] is not None and not isinstance(payload[key], str):
            raise ExportValidationError(f"{key} : texte requis si renseigné.")
    if "alpha" in payload and (not isinstance(payload["alpha"], str)
                               or not re.fullmatch(r"[0-9A-F]{2}", payload["alpha"])):
        raise ExportValidationError("alpha : deux caractères HEX requis (00 transparent, FF opaque).")
    if "additional_color_hexes" in payload:
        colors = payload["additional_color_hexes"]
        if not isinstance(colors, list) or len(colors) > 4 or any(
            not isinstance(h, str) or not re.fullmatch(r"[0-9A-F]{6}", h) for h in colors
        ):
            raise ExportValidationError("additional_color_hexes : au plus quatre couleurs HEX requises.")
    if "brand_meta" in payload:
        meta = payload["brand_meta"]
        if not isinstance(meta, dict) or any(v is not None and not isinstance(v, str) for v in meta.values()):
            raise ExportValidationError("brand_meta : métadonnées textuelles requises.")
    try:
        json.dumps(payload, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise ExportValidationError(f"Payload JSON invalide : {exc}") from exc


def build_openspool(entry: dict, product_data: dict, brand_meta: Optional[dict] = None,
                   *, use_orca_overrides: bool = False) -> dict:
    """Keep the existing fields; reject unknowns instead of inventing values."""
    if not isinstance(entry, dict) or not isinstance(product_data, dict) or not product_data:
        raise ExportValidationError("Référence ou produit absent du catalogue.")
    hx = validate_hex(entry.get("hex"))
    if not hx:
        if not entry.get("hex"):
            raise MissingColorError("Couleur HEX inconnue : renseignez explicitement une couleur représentative "
                                    "avant l'export NFC. Aucune couleur noire n'est inventée.")
        raise ExportValidationError("Couleur HEX invalide.")
    suspect_color = db_io.implausible_color(entry)
    if suspect_color:
        raise MissingColorError(f"Couleur à confirmer avant l'export : {suspect_color}. "
                                "Renseignez explicitement la couleur représentative.")
    suspect_physical = db_io.implausible_physical(product_data)
    if suspect_physical:
        raise ExportValidationError("Caractéristiques à vérifier avant l'export : " + " ; ".join(suspect_physical)
                                    + ". Corrigez-les explicitement dans la fiche.")
    src = dict(product_data)
    orca_path = find_orca_profile(entry.get("product", ""))
    if orca_path:
        try:
            _apply_orca(src, orca_path, use_orca_overrides)
        except (ValueError, TypeError, OSError) as exc:
            raise ExportValidationError(f"Profil Orca inutilisable ({orca_path}) : {exc}") from exc
    payload = {
        "protocol": "openspool",
        "version": "1.0",
        "type": src.get("type"),
        "color_hex": hx,
        "brand": src.get("brand"),
        "min_temp": src.get("min_temp"),
        "max_temp": src.get("max_temp"),
        "bed_min_temp": src.get("bed_min_temp"),
        "bed_max_temp": src.get("bed_max_temp"),
        "diameter": src.get("diameter"),
        "density": src.get("density"),
    }
    if src.get("subtype"):
        payload["subtype"] = src["subtype"]
    if brand_meta:
        # Unknown metadata is omitted rather than written as null bytes on the tag.
        meta = {
            "name": brand_meta.get("name", src.get("brand")),
            "website": brand_meta.get("website"),
            "origin": brand_meta.get("origin"),
            "logo_url": brand_meta.get("logo_url"),
            "logo_path": brand_meta.get("logo_path"),
        }
        payload["brand_meta"] = {k: v for k, v in meta.items() if v is not None}
        if brand_meta.get("logo_url"):
            payload["logo_url"] = brand_meta.get("logo_url")
            payload["image"] = brand_meta.get("logo_url")
    for key in ("sku", "product", "color_name"):
        payload[key] = entry.get(key)
    if src.get("display_name"):
        payload["product"] = src["display_name"]
    for key in ("alpha", "additional_color_hexes"):
        if key in entry:
            payload[key] = entry[key]
    if entry.get("source_colors"):
        colors = entry["source_colors"]
        if not isinstance(colors, list) or any(not isinstance(c, str) or not re.fullmatch(r"[0-9A-F]{6}", c) for c in colors):
            raise ExportValidationError("Couleurs source multiples avec alpha ou format incompatible ; aucune couleur n'est supprimée.")
        additional = list(dict.fromkeys(c for c in colors if c != hx))
        if len(additional) > 4:
            raise ExportValidationError("Trop de couleurs pour OpenSpool (quatre couleurs supplémentaires maximum).")
        if "additional_color_hexes" not in payload:
            payload["additional_color_hexes"] = additional
    validate_openspool(payload)
    return payload


@dataclass(frozen=True)
class NfcSize:
    characters: int
    utf8_bytes: int
    ndef_bytes: int
    type2_bytes: int
    capacity_bytes: int = NTAG216_NDEF_AREA_BYTES
    reserved_bytes: int = 0

    @property
    def remaining_bytes(self) -> int:
        return self.capacity_bytes - self.type2_bytes - self.reserved_bytes

    @property
    def fits(self) -> bool:
        return self.remaining_bytes >= 0


def nfc_size(text: str, *, tag_type: str = "NTAG216", reserved_bytes: int = 0) -> NfcSize:
    """One MIME application/json record, no ID, Type 2 TLV + terminator.

    Excludes the CC itself. Additional records written by another app are not
    included and must be checked by that writer.
    """
    if tag_type not in NFC_CAPACITIES:
        raise ValueError("Tag attendu : NTAG215 ou NTAG216.")
    if type(reserved_bytes) is not int or not 0 <= reserved_bytes <= NFC_CAPACITIES[tag_type]:
        raise ValueError("Réserve d'écriture invalide.")
    length = len(text.encode("utf-8"))
    record = (3 if length < 256 else 6) + len(b"application/json") + length
    total = record + (2 if record < 255 else 4) + 1
    return NfcSize(len(text), length, record, total, NFC_CAPACITIES[tag_type], reserved_bytes)


def serialize_openspool(payload: dict, *, mode: str = "nfc", tag_type: str = "NTAG216",
                        profile: str = "full", reserved_bytes: int = 0) -> str:
    validate_openspool(payload)
    if profile not in ("full", "essential"):
        raise ValueError("Profil attendu : full ou essential.")
    if mode not in ("nfc", "archive"):
        raise ValueError("Mode d'export attendu : nfc ou archive.")
    exported = ({key: payload[key] for key in NFC_ESSENTIAL_FIELDS if key in payload}
                if mode == "nfc" and profile == "essential" else payload)
    text = (json.dumps(exported, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
            if mode == "nfc" else json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False))
    size = nfc_size(text, tag_type=tag_type, reserved_bytes=reserved_bytes)
    if mode == "nfc" and not size.fits:
        raise NfcCapacityError(f"Export trop volumineux pour {tag_type} : {size.type2_bytes} + "
                               f"{reserved_bytes} de réserve / "
                               f"{size.capacity_bytes} octets avec NDEF/TLV "
                               f"({size.utf8_bytes} octets JSON UTF-8). Choisissez le profil essentiel, "
                               "un tag plus grand ou l'archive complète.")
    return text


def openspool_filename(sku: str, product: str, color_name: str) -> str:
    if not isinstance(sku, str) or not isinstance(product, str) or not isinstance(color_name, str):
        raise ExportValidationError("SKU, produit et nom de couleur doivent être du texte.")
    safe_sku = slugify(sku)
    if not safe_sku or len(safe_sku) > 100:
        raise ExportValidationError("SKU vide ou trop long pour un nom de fichier.")
    return f"{safe_sku}_{slugify(product)[:60]}_{slugify(color_name)[:50]}_openspool.json"


def write_openspool(sku: str, entry: dict, product_data: dict,
                    output_dir: Optional[str] = None,
                    brand_meta: Optional[dict] = None, *, mode: str = "nfc",
                    use_orca_overrides: bool = False, tag_type: str = "NTAG216",
                    profile: str = "full", reserved_bytes: int = 0) -> str:
    entry_with_sku = dict(entry, sku=sku)
    payload = build_openspool(entry_with_sku, product_data, brand_meta=brand_meta,
                             use_orca_overrides=use_orca_overrides)
    text = serialize_openspool(payload, mode=mode, tag_type=tag_type, profile=profile,
                              reserved_bytes=reserved_bytes)
    filename = openspool_filename(sku, product_data.get('display_name') if entry.get('_personal') else entry.get("product", ""), entry.get("color_name", ""))
    if mode == "archive":
        filename = filename.removesuffix(".json") + "_archive.json"
    elif tag_type != "NTAG216" or profile != "full":
        filename = filename.removesuffix(".json") + f"_{tag_type.lower()}_{profile}.json"
    directory = Path(output_dir or OUTPUT_DIR).resolve()
    destination = directory / filename
    if destination.resolve().parent != directory:
        raise ExportValidationError("Le fichier d'export doit rester dans le dossier de sortie.")
    db_io.atomic_write(destination, text.encode("utf-8"))
    return str(destination)


# ─── Mise à jour DB (scrapers) ────────────────────────────────────────────
@dataclass
class StepResult:
    label: str
    ok: bool
    code: int = 0
    stderr: str = ""
    status: str = ""


def update_status(results: list[StepResult]) -> str:
    if results and all(r.ok for r in results):
        return "complete"
    if any(r.ok or r.status == "partial" for r in results):
        return "partial"
    return "failed"


def _run_step_process(cmd: list[str], *, env: dict, timeout: int, cancel=None) -> subprocess.CompletedProcess:
    """Run one worker; a cancel event (threading.Event) stops it between polls."""
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               encoding="utf-8", errors="replace", env=env)
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                out, err = process.communicate(timeout=0.5)
                return subprocess.CompletedProcess(cmd, process.returncode, out, err)
            except subprocess.TimeoutExpired:
                if cancel is not None and cancel.is_set():
                    process.kill()
                    out, err = process.communicate()
                    raise UpdateCancelled("Mise à jour annulée par l'utilisateur.")
                if time.monotonic() >= deadline:
                    process.kill()
                    out, err = process.communicate()
                    raise subprocess.TimeoutExpired(cmd, timeout, out, err)
    finally:
        if process.poll() is None:
            process.kill()


class UpdateCancelled(RuntimeError):
    pass


def run_update_pipeline(
    progress: Optional[Callable[[str, int, int], None]] = None,
    python: Optional[str] = None,
    consent: bool = False,
    sources: Optional[list[str]] = None,
    cancel=None,
) -> list[StepResult]:
    """
    Exécute toute la pipeline de scrapers (accès réseau).

    SÉCURITÉ / TRANSPARENCE : aucun accès réseau n'est effectué sans
    consentement explicite. `consent=True` doit être passé par l'appelant
    APRÈS avoir informé l'utilisateur (voir NETWORK_SOURCES). Sans consentement
    (ni argument ni config), la fonction retourne une étape d'erreur claire.

    `progress(label, index, total)` est appelé avant chaque étape (optionnel).
    Ne lève jamais : chaque échec est capturé dans un StepResult.
    """
    if not (consent or has_network_consent()):
        return [StepResult("Consentement réseau requis", False, -2,
                           "Mise à jour annulée : aucun consentement réseau accordé.")]

    try:
        load_db()  # Includes conservative bundle merging in the packaged app.
        db_io.backup_db(DB_PATH)
    except (DatabaseError, OSError) as exc:
        return [StepResult("Sauvegarde avant mise à jour", False, -1, str(exc), "error")]

    selected = sources if sources is not None else load_config().get("selected_sources")
    # A caller overriding the legacy pipeline (including offline regression tests)
    # can still execute its supplied steps; normal application use selects groups.
    pipeline = selected_pipeline(selected) if UPDATE_PIPELINE == _ALL_PIPELINE else UPDATE_PIPELINE
    if not pipeline:
        return [StepResult("Sources", False, -2, "Sélectionnez au moins une source.", "unavailable")]
    python = python or venv_python()
    results: list[StepResult] = []
    total = len(pipeline)
    # Force l'UTF-8 dans les process enfants : sous Windows, stdout utilise
    # cp1252 par défaut et les scripts (qui impriment —, ─, →…) plantent en
    # UnicodeEncodeError. PYTHONUTF8/PYTHONIOENCODING corrigent ça à la source.
    child_env = dict(os.environ)
    child_env["PYTHONUTF8"] = "1"
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env["SPOOLSCRIBE_DATA_HOME"] = DATA_HOME
    child_env["SPOOLSCRIBE_RESOURCE_DIR"] = RESOURCE_DIR
    for i, (script, label, timeout) in enumerate(pipeline, 1):
        if cancel is not None and cancel.is_set():
            results.append(StepResult(label, False, -3, "Annulée avant exécution.", "cancelled"))
            continue
        if progress:
            try:
                progress(label, i, total)
            except Exception:
                pass
        path = os.path.join(SCRIPTS_DIR, script)
        if not os.path.isfile(path):
            results.append(StepResult(label, False, -1, "script introuvable"))
            continue
        try:
            cmd = _script_command(python, path)
            with tempfile.TemporaryDirectory(prefix="spoolscribe-step-") as result_dir:
                result_path = Path(result_dir) / "result.json"
                step_env = dict(child_env, SPOOLSCRIBE_STEP_RESULT_PATH=str(result_path))
                r = _run_step_process(cmd, env=step_env, timeout=timeout, cancel=cancel)
                record = None
                if result_path.is_file():
                    record = db_io.parse_json(result_path.read_bytes())
                else:
                    # Also accept standalone/older command-line worker output.
                    for line in (r.stdout or "").splitlines():
                        if line.startswith(db_io.STEP_PREFIX):
                            try:
                                record = json.loads(line[len(db_io.STEP_PREFIX):])
                            except ValueError:
                                record = None
                if not isinstance(record, dict):
                    record = None
            status = record.get("status") if isinstance(record, dict) else "error"
            ok = r.returncode == 0 and status in ("changed", "unchanged")
            detail = (r.stderr or "").strip()
            if record and record.get("message"):
                detail = str(record["message"])
            if not record:
                detail = detail or "Le worker n'a pas fourni de résultat vérifiable."
            results.append(StepResult(label, ok, r.returncode, detail, status))
        except UpdateCancelled as e:
            results.append(StepResult(label, False, -3, str(e), "cancelled"))
        except Exception as e:
            results.append(StepResult(label, False, -1, str(e)))
    now = datetime.now().isoformat()
    status = update_status(results)
    try:
        db = load_db()
        metadata = {
            "_update_status": status,
            "_selected_sources": list(selected or []),
            "_source_results": [dict(source=r.label, status=r.status, ok=r.ok, message=r.stderr) for r in results],
        }
        if status == "complete":
            metadata["_last_updated"] = now
        # An offline launch that changes nothing must not rewrite (and back up)
        # the whole database: only changed outcomes are recorded in it. The
        # attempt itself lives in the settings file.
        if any(r.status == "changed" for r in results) or any(db.get(k) != v for k, v in metadata.items()):
            db.update(metadata)
            db.pop("_last_attempt", None)
            save_db(db)
    except (DatabaseError, OSError) as exc:
        results.append(StepResult("Validation / sauvegarde finale", False, -1, str(exc), "error"))
    try:
        cfg = load_config()
        cfg["last_update_attempt"] = now
        cfg["last_update_status"] = update_status(results)
        save_config(cfg)
    except OSError:
        pass
    return results



# Source switches are explicit and are shared by GUI, CLI and subprocess workers.
SOURCE_GROUPS = {
    "polymaker": {"name": "Polymaker — fabricant", "detail": "Catalogue et couleurs officiels · us-wholesale.polymaker.com", "scripts": ["sync_polymaker_official.py"]},
    "ofd": {"name": "Open Filament Database — communauté", "detail": "Catalogue multi-fabricants · codeload.github.com", "scripts": ["sync_universal_catalogue.py"]},
    "spoolman": {"name": "SpoolmanDB — communauté", "detail": "Références complémentaires, rapprochement sans doublon certain · donkie.github.io", "scripts": ["sync_spoolman_catalogue.py"]},
    "bambu": {"name": "Bambu Lab — fabricant", "detail": "Complément des fiches Bambu déjà présentes : profils officiels Bambu Studio · raw.githubusercontent.com", "scripts": ["sync_bambu_official.py"]},
    "sunlu": {"name": "SUNLU — fabricant", "detail": "Complément PLA : densité, plateau et couleurs officiels · www.sunlu.com", "scripts": ["sync_sunlu_official.py"]},
    "orca": {"name": "Polymaker — profils Orca officiels", "detail": "Profils compatibles Snapmaker U1 · raw.githubusercontent.com", "scripts": ["download_orca_profiles.py", "import_orca_profiles.py"]},
    "thefilamentdb": {"name": "TheFilamentDB — complément historique", "detail": "Instantané local historique seulement ; ROSA3D absent. Disponible depuis le dépôt, non embarqué.", "scripts": ["scrape_thefilamentdb_hex.py", "scrape_thefilamentdb_multibrand_hex.py"]},
}
UPDATE_PIPELINE += [("sync_polymaker_official.py", "Polymaker officiel", 300), ("sync_bambu_official.py", "Bambu Lab officiel", 600), ("sync_sunlu_official.py", "SUNLU officiel", 180)]
_ALL_PIPELINE = list(UPDATE_PIPELINE)

def selected_pipeline(sources=None):
    selected = DEFAULT_CONFIG["selected_sources"] if sources is None else sources
    if not isinstance(selected, list) or any(key not in SOURCE_GROUPS for key in selected):
        raise ValueError("Sélection de sources invalide")
    scripts = {script for key in selected for script in SOURCE_GROUPS[key]["scripts"]}
    # Catalogues establish identity; authoritative manufacturer enrichment runs
    # last and wins over source-owned community fields, never over user edits.
    steps = [step for step in UPDATE_PIPELINE if step[0] in scripts]
    return sorted(steps, key=lambda step: 0 if step[0] == "sync_polymaker_official.py" else 1)

def recommended_nfc(payload, tag_type="NTAG216", profile="auto", reserved_bytes=0):
    """``auto`` recommends the essential profile: it carries everything a reader
    uses (material, colours, temperatures, diameter, density) and fits NTAG215.
    The full profile (descriptions, brand metadata, logo URL) is an explicit choice."""
    chosen = "essential" if profile == "auto" else profile
    try:
        serialize_openspool(payload, tag_type=tag_type, profile=chosen, reserved_bytes=reserved_bytes)
    except NfcCapacityError:
        if chosen == "essential":
            raise NfcCapacityError("Même les données essentielles ne tiennent pas : utilisez un NTAG216 ou réduisez la réserve après vérification du logiciel d’écriture.")
        raise
    return dict(tag_type=tag_type, profile=chosen, reserved_bytes=reserved_bytes)


NFC_PROFILES = ("auto", "essential", "full")


def preferred_packaging(variants: list[dict], cfg: dict, fallback: str) -> dict:
    """Prefer an existing package only. Callers handle colour ambiguity first."""
    current = next((v for v in variants if v['sku'] == fallback), variants[0] if variants else None)
    if current is None:
        raise ValueError('Aucun conditionnement disponible')
    weight = cfg.get('preferred_weight_g', 1000)
    form = cfg.get('preferred_packaging', 'any')
    candidates = [v for v in variants if weight and v.get('weight') == weight] if type(weight) is int else []
    if not candidates:
        return current
    wanted = {'spool': False, 'refill': True}.get(form)
    matching = [v for v in candidates if v.get('spool_refill') is wanted] if wanted is not None else candidates
    pool = matching or candidates
    return next((v for v in pool if v['sku'] == fallback), pool[0])


def nfc_defaults(cfg: Optional[dict] = None) -> dict:
    """Saved default tag/profile/reserve; invalid stored values fall back safely."""
    cfg = cfg if cfg is not None else load_config()
    tag = cfg.get("nfc_tag_type") if cfg.get("nfc_tag_type") in NFC_CAPACITIES else DEFAULT_CONFIG["nfc_tag_type"]
    profile = cfg.get("nfc_profile") if cfg.get("nfc_profile") in NFC_PROFILES else DEFAULT_CONFIG["nfc_profile"]
    reserve = cfg.get("nfc_reserved_bytes")
    if type(reserve) is not int or not 0 <= reserve <= NFC_CAPACITIES[tag]:
        reserve = 0
    return dict(tag_type=tag, profile=profile, reserved_bytes=reserve)


def save_nfc_defaults(tag_type: str, profile: str, reserved_bytes: int) -> dict:
    """Explicitly store the tag choice used for new exports (GUI button, CLI flag).

    Changing the tag for one export no longer changes this default.
    """
    if tag_type not in NFC_CAPACITIES or profile not in NFC_PROFILES:
        raise ValueError("Étiquette ou profil NFC invalide.")
    if type(reserved_bytes) is not int or not 0 <= reserved_bytes <= NFC_CAPACITIES[tag_type]:
        raise ValueError("Réserve NFC invalide pour cette étiquette.")
    cfg = load_config()
    cfg.update(nfc_tag_type=tag_type, nfc_profile=profile, nfc_reserved_bytes=reserved_bytes)
    save_config(cfg)
    return nfc_defaults(cfg)


def export_settings(path):
    # Consent is machine-local authorization, not transferable via a settings file.
    cfg = load_config()
    for key in ('network_consent', 'network_sources_revision', 'last_update'):
        cfg.pop(key, None)
    db_io.atomic_write(path, json.dumps({'format': 'spoolscribe-settings', 'version': 1, 'settings': cfg},
                                     ensure_ascii=False, indent=2, allow_nan=False).encode())


def import_settings(path):
    raw = Path(path).read_bytes()
    if len(raw) > 128 * 1024:
        raise ValueError('Fichier de réglages trop volumineux')
    doc = db_io.parse_json(raw)
    if not isinstance(doc, dict) or doc.get('format') != 'spoolscribe-settings' or doc.get('version') != 1:
        raise ValueError('Format de réglages inconnu')
    incoming = doc.get('settings')
    if not isinstance(incoming, dict): raise ValueError('Réglages invalides')
    cfg = load_config()
    allowed = set(DEFAULT_CONFIG) | {'recent_brands'}
    for key, value in incoming.items():
        if key in allowed and key not in ('network_consent', 'network_sources_revision', 'last_update'):
            cfg[key] = value
    if cfg.get('nfc_format') not in ('openspool','opentag3d') or cfg.get('opentag3d_output') not in ('nfctools-mobile','nfctools-desktop','ndef'):
        raise ValueError('Format NFC invalide')
    settings=cfg.get('opentag3d_settings')
    if not isinstance(settings,dict) or len(settings)>500:raise ValueError('Réglages OpenTag3D invalides')
    for sku,values in settings.items():
        if not isinstance(sku,str) or len(sku)>256:raise ValueError('Référence OpenTag3D invalide')
        validate_opentag_settings(values)
    if cfg['printer_profile'] in printer_profiles.PROFILES and printer_profiles.PROFILES[cfg['printer_profile']].get('hidden'):
        cfg['printer_profile'],cfg['printer_firmware']=printer_profiles.resolve(cfg['printer_profile'],cfg.get('printer_firmware'))
    if cfg['printer_profile'] not in printer_profiles.PROFILES or cfg['nfc_tag_type'] not in NFC_CAPACITIES or cfg['nfc_profile'] not in NFC_PROFILES:
        raise ValueError('Choix imprimante/NFC invalide')
    software=cfg.get('printer_firmware')
    if software not in (None,'unknown') and software not in [f['id'] for f in printer_profiles.PROFILES[cfg['printer_profile']]['firmwares']]:
        raise ValueError('Logiciel du lecteur invalide')
    if type(cfg['nfc_reserved_bytes']) is not int or not 0 <= cfg['nfc_reserved_bytes'] <= NFC_CAPACITIES[cfg['nfc_tag_type']]:
        raise ValueError('Réserve NFC invalide')
    if cfg['language'] not in ('auto','en','fr','es','zh_CN'):
        raise ValueError('Langue inconnue')
    selected_pipeline(cfg['selected_sources'])
    if not isinstance(cfg['ui'],dict):raise ValueError('Présentation invalide')
    ui=cfg['ui']
    for key in ('brand','material','quality','search','brand_search','sort1','sort2','view','header','geometry'):
        if key in ui and (not isinstance(ui[key],str) or len(ui[key])>20000):raise ValueError('Présentation invalide')
    for key in ('auto_update','orca_overrides','show_extra_fields'):
        if type(cfg[key]) is not bool:raise ValueError('Option invalide')
    if type(cfg['preferred_weight_g']) is not int or not 0 <= cfg['preferred_weight_g'] <= 20000 or cfg['preferred_packaging'] not in ('any','spool','refill'):
        raise ValueError('Conditionnement préféré invalide')
    if not valid_colour_delta_limit(cfg['colour_delta_max']):
        raise ValueError('Écart de couleur invalide')
    from . import qr_layout
    qr_layout.validate_settings(cfg['qr_label'])
    directory=cfg['export_directory']
    if not isinstance(directory,str) or len(directory)>4096 or '\x00' in directory or directory and not os.path.isabs(directory):
        raise ValueError('Dossier d’export invalide')
    for key, limit in (("favorite_brands", 500), ("favorite_filaments", 5000)):
        value = cfg.get(key)
        if not isinstance(value, list) or len(value) > limit or any(not isinstance(v, str) or len(v) > 256 for v in value):
            raise ValueError("Favoris invalides")
        cfg[key] = list(dict.fromkeys(value))
    if 'recent_brands' in cfg and (not isinstance(cfg['recent_brands'],list) or len(cfg['recent_brands'])>20 or any(not isinstance(v,str) for v in cfg['recent_brands'])):
        raise ValueError('Fabricants récents invalides')
    # Import never grants or widens network authorization silently.
    if cfg['selected_sources'] != load_config()['selected_sources']:
        cfg['network_sources_revision']=0
    save_config(cfg)

NETWORK_SOURCES = [dict(name=meta['name'], license=('MIT' if key in ('ofd','spoolman','orca') else 'CC-BY 4.0' if key=='thefilamentdb' else 'Données factuelles fabricant'), host=meta['detail']) for key,meta in SOURCE_GROUPS.items()]

# OpenTag3D is an independent wire format. The existing OpenSpool API stays unchanged.
@dataclass(frozen=True)
class OpenTagExport:
    payload: bytes
    data: bytes
    filename: str
    preview: str
    size: dict


def opentag_fields(entry, product_data, settings=None, *, use_orca_overrides=False):
    from . import opentag3d
    if not isinstance(entry,dict) or not isinstance(product_data,dict):raise ExportValidationError('Référence ou produit absent.')
    hx=validate_hex(entry.get('hex'))
    if not hx or db_io.implausible_color(entry):raise MissingColorError('Couleur représentative à confirmer avant l’export.')
    suspect=db_io.implausible_physical(product_data)
    if suspect:raise ExportValidationError('Caractéristiques à vérifier : '+' ; '.join(suspect))
    src=dict(product_data)
    orca_path=find_orca_profile(entry.get('product',''))
    if orca_path:
        try:_apply_orca(src,orca_path,use_orca_overrides)
        except (ValueError,TypeError,OSError) as exc:raise ExportValidationError('Profil Orca inutilisable : '+str(exc)) from exc
    fields=dict(material=src.get('type'),manufacturer=src.get('brand'),
                diameter=src.get('diameter'),density=src.get('density'))
    for key,source in [('min_print_temp','min_temp'),('max_print_temp','max_temp'),
                       ('min_bed_temp','bed_min_temp'),('max_bed_temp','bed_max_temp')]:
        if src.get(source) is not None:fields[key]=src[source]
    alpha=entry.get('alpha','FF')
    if not isinstance(alpha,str) or not re.fullmatch('[0-9A-Fa-f]{2}',alpha):raise ExportValidationError('Alpha explicite invalide.')
    fields['color_1']=hx+alpha.upper()
    additional=entry.get('additional_color_hexes',[])
    source_colors=entry.get('source_colors')
    if source_colors:
        if not isinstance(source_colors,list) or any(not isinstance(c,str) or not re.fullmatch('[0-9A-F]{6}',c) for c in source_colors):
            raise ExportValidationError('Couleurs source incompatibles ; aucune couleur n’est supprimée.')
        if 'additional_color_hexes' not in entry:additional=list(dict.fromkeys(c for c in source_colors if c!=hx))
    if not isinstance(additional,list) or any(not isinstance(c,str) or not re.fullmatch('[0-9A-F]{6}',c) for c in additional):
        raise ExportValidationError('Couleurs supplémentaires invalides.')
    if len(additional)>3:raise ExportValidationError('OpenTag3D : quatre couleurs au total maximum ; aucune couleur n’est supprimée.')
    for i,h in enumerate(additional,2):fields['color_'+str(i)]=h+alpha.upper()
    for dest,value in [('material_mod',src.get('subtype')),('color_name',entry.get('color_name')),
                       ('weight',entry.get('weight')),('sku',entry.get('manufacturer_sku'))]:
        if value is not None:fields[dest]=value
    if settings is not None:
        if not isinstance(settings,dict) or set(settings)-set(opentag3d.EDITABLE):
            raise ExportValidationError('Réglages OpenTag3D invalides.')
        fields.update(settings)
    return fields


def prepare_opentag3d(sku,entry,product_data,*,settings=None,tag_type='NTAG216',reserved_bytes=0,
                      output='nfctools-mobile',use_orca_overrides=False):
    from . import opentag3d
    try:
        fields=opentag_fields(entry,product_data,settings,use_orca_overrides=use_orca_overrides)
        payload=opentag3d.encode(fields);size=opentag3d.budget(payload,tag_type,reserved_bytes)
        data=opentag3d.export(payload,output)
    except ValueError as exc:raise ExportValidationError(str(exc)) from exc
    stem=openspool_filename(sku,entry.get('product',''),entry.get('color_name','')).removesuffix('_openspool.json')
    filename=stem+'_opentag3d_'+output+('.ndef' if output=='ndef' else '.json')
    preview=json.dumps({'format':'OpenTag3D','version':opentag3d.VERSION,
        'mime':opentag3d.MIME.decode(),'fields':fields,'size':size,
        'payload_hex':payload.hex().upper(),'ndef_hex':opentag3d.ndef(payload).hex().upper()},ensure_ascii=False,indent=2)
    return OpenTagExport(payload,data,filename,preview,size)


def write_opentag3d(export,output_dir):
    if not isinstance(export,OpenTagExport):raise ExportValidationError('Export OpenTag3D non validé.')
    directory=Path(output_dir).resolve();destination=directory/export.filename
    if destination.resolve().parent!=directory:raise ExportValidationError('Chemin d’export invalide.')
    db_io.atomic_write(destination,export.data)
    return str(destination)


def opentag_settings(sku):
    values=load_config().get('opentag3d_settings',{})
    result=values.get(sku,{}) if isinstance(values,dict) else {}
    return dict(result) if isinstance(result,dict) else {}


def save_opentag_settings(sku,settings):
    validate_opentag_settings(settings)
    cfg=load_config();all_values=cfg.get('opentag3d_settings',{})
    if not isinstance(all_values,dict):all_values={}
    cfg['opentag3d_settings']=dict(all_values,**{sku:dict(settings)})
    save_config(cfg)


def validate_opentag_settings(settings):
    from . import opentag3d
    from decimal import Decimal, InvalidOperation
    if not isinstance(settings,dict) or set(settings)-set(opentag3d.EDITABLE):raise ValueError('Réglages OpenTag3D invalides.')
    for key,value in settings.items():
        if value is None:continue
        _,length,kind=opentag3d.FIELDS[key]
        if kind=='text':
            if not isinstance(value,str) or len(value.encode('utf-8'))>length or any(ord(c)<32 or ord(c)==127 for c in value):
                raise ValueError('Texte OpenTag3D invalide : '+key)
        else:
            if type(value) not in (int,float):raise ValueError('Nombre OpenTag3D invalide : '+key)
            try:
                number=Decimal(str(value));units=number/Decimal(kind)
                if not number.is_finite() or units!=units.to_integral_value() or not 0<=units<256**length:raise ValueError('Valeur OpenTag3D non représentable : '+key)
            except InvalidOperation as exc:raise ValueError('Valeur OpenTag3D invalide : '+key) from exc

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

import json
import hashlib
import math
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional
from pathlib import Path

from scripts import db_io

DatabaseError = db_io.DatabaseError

# ─── Identité de l'application ────────────────────────────────────────────
# APP_VERSION est la référence de version. spoolscribe.spec la lit ici ;
# la CI vérifie que la version déclarée dans pyproject.toml reste alignée.
APP_NAME = "SpoolScribe"
APP_VERSION = "0.2.2"
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
    return os.path.dirname(os.path.abspath(__file__))


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
DATA_HOME   = os.environ.get("SPOOLSCRIBE_DATA_HOME") or (user_data_dir() if _FROZEN else RESOURCE_DIR)
DATA_DIR    = os.path.join(DATA_HOME, "data")
DB_PATH     = os.path.join(DATA_DIR, "polymaker_db.json")
ORCA_DIR    = os.path.join(DATA_HOME, "orca_profiles")
OUTPUT_DIR  = os.path.join(DATA_HOME, "output")
CONFIG_PATH = os.environ.get("SPOOLSCRIBE_CONFIG_PATH") or os.path.join(user_data_dir(), "config.json")

# Les scrapers (process séparés, lancés via runpy) ne peuvent pas importer
# core ; on leur transmet le dossier inscriptible via l'environnement.
os.environ.setdefault("SPOOLSCRIBE_DATA_HOME", DATA_HOME)
os.environ.setdefault("SPOOLSCRIBE_RESOURCE_DIR", RESOURCE_DIR)


def _seed_writable_data() -> None:
    """
    Au premier lancement en .exe, recopie les ressources embarquées (DB,
    profils Orca, logo) vers le dossier inscriptible pour que l'app
    fonctionne hors-ligne et que les mises à jour persistent.
    """
    if not _FROZEN:
        return
    bundled_path = Path(RESOURCE_DIR) / "data" / "polymaker_db.json"
    bundled = db_io.load_db(bundled_path)
    digest = hashlib.sha256(bundled_path.read_bytes()).hexdigest()
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
# Liste EXHAUSTIVE des hôtes contactés par la pipeline de mise à jour.
# Affichée à l'utilisateur avant tout accès réseau (consentement éclairé).
NETWORK_SOURCES: list[dict] = [
    {"name": "SpoolmanDB",            "license": "MIT",
     "host": "raw.githubusercontent.com/Donkie/SpoolmanDB"},
    {"name": "Open Filament Database", "license": "MIT",
     "host": "raw.githubusercontent.com/OpenFilamentCollective/open-filament-database"},
    {"name": "Polymaker Presets (officiel)", "license": "MIT",
     "host": "raw.githubusercontent.com/polymaker3d/Polymaker-Preset"},
    {"name": "TheFilamentDB",         "license": "CC-BY 4.0 (attribution requise)",
     "host": "issou.best / dump local thefilamentdb.jsonl.gz"},
    {"name": "Polymaker Wiki",        "license": "Données factuelles (HEX) — © Polymaker",
     "host": "wiki.polymaker.com"},
    {"name": "Polymaker US Wholesale", "license": "Catalogue factuel — © Polymaker",
     "host": "us-wholesale.polymaker.com"},
    {"name": "Prusament (spécifications matériaux)", "license": "Données factuelles — © Prusa Research",
     "host": "table interne hors-ligne + SpoolmanDB + TheFilamentDB (HEX couleurs) + Open Filament Database (logo)"},
    {"name": "ROSA3D (spécifications matériaux)", "license": "Données factuelles — © ROSA PLAST",
     "host": "table interne hors-ligne + SpoolmanDB (HEX couleurs) + Open Filament Database (logo)"},
]


DEFAULT_CONFIG = {
    "network_consent": None,    # None = jamais demandé ; True/False = choix explicite
    "auto_update": False,       # opt-in : aucune mise à jour automatique par défaut
    "update_interval_days": 7,
    "last_update": None,
    "orca_overrides": False,   # Explicit choice before replacing local values at export.
}


def load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        merged = dict(DEFAULT_CONFIG)
        merged.update(cfg)
        return merged
    except Exception:
        return dict(DEFAULT_CONFIG)


def save_config(cfg: dict) -> None:
    db_io.atomic_write(CONFIG_PATH, json.dumps(cfg, indent=2, ensure_ascii=False,
                                             allow_nan=False).encode("utf-8"))


def has_network_consent() -> bool:
    """True uniquement si l'utilisateur a explicitement accepté l'accès réseau."""
    return load_config().get("network_consent") is True


def consent_was_asked() -> bool:
    return load_config().get("network_consent") is not None


def set_network_consent(value: bool, auto_update: "bool | None" = None) -> None:
    cfg = load_config()
    cfg["network_consent"] = bool(value)
    if auto_update is not None:
        cfg["auto_update"] = bool(auto_update)
    save_config(cfg)


def mark_updated() -> None:
    cfg = load_config()
    cfg["last_update"] = datetime.now().isoformat()
    save_config(cfg)


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
    path = path or DB_PATH
    if _FROZEN and os.path.abspath(path) == os.path.abspath(DB_PATH) and not db_restored_this_session(path):
        _seed_writable_data()
    return db_io.load_db(path)


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


# ─── Logo SVG ─────────────────────────────────────────────────────────────
def app_logo_abs_path() -> Optional[str]:
    """Chemin absolu du logo de l'application SpoolScribe, ou None."""
    rel = os.path.join("data", "spoolscribe_logo.svg")
    for base in (DATA_HOME, RESOURCE_DIR):
        abs_p = os.path.join(base, rel)
        if os.path.exists(abs_p):
            return abs_p
    return None


def app_icon_abs_path() -> Optional[str]:
    """Chemin absolu de l'icône binaire (.png) de l'application, ou None."""
    for name in ("app.png", "app.ico"):
        for base in (DATA_HOME, RESOURCE_DIR):
            abs_p = os.path.join(base, "data", name)
            if os.path.exists(abs_p):
                return abs_p
    return None


def logo_abs_path(db: dict, brand: str = "Polymaker") -> Optional[str]:
    """Chemin absolu du logo de marque, ou None."""
    meta = db.get("_brands", {}).get(brand, {})
    logo_path = meta.get("logo_path", "")
    if not logo_path:
        # Repli : nom de fichier nu dans `logo` → cherché sous data/.
        logo = (meta.get("logo") or "").strip()
        if logo:
            logo_path = logo if ("/" in logo or os.sep in logo) else f"data/{logo}"
    if not logo_path:
        return None
    rel = logo_path.replace("/", os.sep)
    # Données inscriptibles (mises à jour) d'abord, puis bundle en repli.
    for base in (DATA_HOME, RESOURCE_DIR):
        abs_p = os.path.join(base, rel)
        if os.path.exists(abs_p):
            return abs_p
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
    def type_str(self) -> str:
        t = self.product_data.get("type", "")
        st = self.product_data.get("subtype")
        return f"{t} [{st}]" if st else t

    @property
    def nozzle_str(self) -> str:
        return f"{self.product_data.get('min_temp')}–{self.product_data.get('max_temp')} °C"

    @property
    def bed_str(self) -> str:
        lo = self.product_data.get("bed_min_temp")
        hi = self.product_data.get("bed_max_temp")
        return f"{lo} °C" if lo == hi else f"{lo}–{hi} °C"

    @property
    def density_str(self) -> str:
        return f"{self.product_data.get('density')} g/cm³"

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
        out.append({
            "sku": sku,
            "product": e.get("product", ""),
            "color_name": e.get("color_name", ""),
            "hex": e.get("hex"),
        })
    return out


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
        previous = dict(db["_skus"][sku])
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


# ─── Payload OpenSpool / NFC ──────────────────────────────────────────────
class ExportValidationError(ValueError):
    """Invalid data, before any output file is opened."""


class MissingColorError(ExportValidationError):
    pass


class NfcCapacityError(ExportValidationError):
    pass


NTAG216_NDEF_AREA_BYTES = 872
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
    src = dict(product_data)
    orca_path = find_orca_profile(entry.get("product", ""))
    if orca_path:
        try:
            values = load_orca_temps(orca_path)
            for key, value in values.items():
                if use_orca_overrides or src.get(key) is None:
                    src[key] = value
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
        payload["brand_meta"] = {
            "name": brand_meta.get("name", src.get("brand")),
            "website": brand_meta.get("website"),
            "origin": brand_meta.get("origin"),
            "logo_url": brand_meta.get("logo_url"),
            "logo_path": brand_meta.get("logo_path"),
        }
        payload["logo_url"] = brand_meta.get("logo_url")
        payload["image"] = brand_meta.get("logo_url")
    for key in ("sku", "product", "color_name"):
        payload[key] = entry.get(key)
    for key in ("alpha", "additional_color_hexes"):
        if key in entry:
            payload[key] = entry[key]
    validate_openspool(payload)
    return payload


@dataclass(frozen=True)
class NfcSize:
    characters: int
    utf8_bytes: int
    ndef_bytes: int
    type2_bytes: int
    capacity_bytes: int = NTAG216_NDEF_AREA_BYTES

    @property
    def fits(self) -> bool:
        return self.type2_bytes <= self.capacity_bytes


def nfc_size(text: str) -> NfcSize:
    """One MIME application/json record, no ID, Type 2 TLV + terminator.

    Excludes the CC itself. Additional records written by another app are not
    included and must be checked by that writer.
    """
    length = len(text.encode("utf-8"))
    record = (3 if length < 256 else 6) + len(b"application/json") + length
    total = record + (2 if record < 255 else 4) + 1
    return NfcSize(len(text), length, record, total)


def serialize_openspool(payload: dict, *, mode: str = "nfc") -> str:
    validate_openspool(payload)
    if mode not in ("nfc", "archive"):
        raise ValueError("Mode d'export attendu : nfc ou archive.")
    text = (json.dumps(payload, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
            if mode == "nfc" else json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False))
    size = nfc_size(text)
    if mode == "nfc" and not size.fits:
        raise NfcCapacityError(f"Export trop volumineux pour NTAG216 : {size.type2_bytes} / "
                               f"{size.capacity_bytes} octets avec NDEF/TLV "
                               f"({size.utf8_bytes} octets JSON UTF-8). Utilisez l'archive pour conserver la fiche.")
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
                    use_orca_overrides: bool = False) -> str:
    entry_with_sku = dict(entry, sku=sku)
    payload = build_openspool(entry_with_sku, product_data, brand_meta=brand_meta,
                             use_orca_overrides=use_orca_overrides)
    text = serialize_openspool(payload, mode=mode)
    filename = openspool_filename(sku, entry.get("product", ""), entry.get("color_name", ""))
    if mode == "archive":
        filename = filename.removesuffix(".json") + "_archive.json"
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


def run_update_pipeline(
    progress: Optional[Callable[[str, int, int], None]] = None,
    python: Optional[str] = None,
    consent: bool = False,
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

    python = python or venv_python()
    results: list[StepResult] = []
    total = len(UPDATE_PIPELINE)
    # Force l'UTF-8 dans les process enfants : sous Windows, stdout utilise
    # cp1252 par défaut et les scripts (qui impriment —, ─, →…) plantent en
    # UnicodeEncodeError. PYTHONUTF8/PYTHONIOENCODING corrigent ça à la source.
    child_env = dict(os.environ)
    child_env["PYTHONUTF8"] = "1"
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env["SPOOLSCRIBE_DATA_HOME"] = DATA_HOME
    child_env["SPOOLSCRIBE_RESOURCE_DIR"] = RESOURCE_DIR
    for i, (script, label, timeout) in enumerate(UPDATE_PIPELINE, 1):
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
                r = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=timeout,
                    encoding="utf-8", errors="replace", env=step_env,
                )
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
        except Exception as e:
            results.append(StepResult(label, False, -1, str(e)))
    try:
        db = load_db()
        status = update_status(results)
        db["_update_status"] = status
        db["_last_attempt"] = datetime.now().isoformat()
        if status == "complete":
            db["_last_updated"] = datetime.now().isoformat()
        save_db(db)
        # The database carries the sole complete-refresh date. Do not maintain
        # a second timestamp in consent settings that could diverge on failure.
    except (DatabaseError, OSError) as exc:
        results.append(StepResult("Validation / sauvegarde finale", False, -1, str(exc), "error"))
    return results


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
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional

# ─── Identité de l'application ────────────────────────────────────────────
APP_NAME = "SpoolScribe"
APP_VERSION = "0.1.3"
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
    d = os.path.join(base, APP_NAME)
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        d = os.path.abspath(".")
    return d


RESOURCE_DIR = _resource_dir()                     # lecture seule (bundle)
SCRIPTS_DIR  = os.path.join(RESOURCE_DIR, "scripts")
SCRIPT_DIR   = RESOURCE_DIR                         # alias rétro-compatible

# Données inscriptibles : repo en dev, dossier utilisateur en .exe (onefile :
# sinon tout irait dans le dossier temporaire _MEIPASS et serait perdu).
DATA_HOME   = user_data_dir() if _FROZEN else RESOURCE_DIR
DATA_DIR    = os.path.join(DATA_HOME, "data")
DB_PATH     = os.path.join(DATA_DIR, "polymaker_db.json")
ORCA_DIR    = os.path.join(DATA_HOME, "orca_profiles")
OUTPUT_DIR  = os.path.join(DATA_HOME, "output")
CONFIG_PATH = os.path.join(user_data_dir(), "config.json")

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
    import shutil
    for sub, dst in (("data", DATA_DIR), ("orca_profiles", ORCA_DIR)):
        src = os.path.join(RESOURCE_DIR, sub)
        try:
            os.makedirs(dst, exist_ok=True)
            if os.path.isdir(src):
                for name in os.listdir(src):
                    s = os.path.join(src, name)
                    d = os.path.join(dst, name)
                    if os.path.isfile(s) and not os.path.exists(d):
                        shutil.copy2(s, d)
        except Exception:
            pass
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
    except Exception:
        pass


_seed_writable_data()

# Pipeline de mise à jour : (fichier_script, libellé, timeout_s)
UPDATE_PIPELINE: list[tuple[str, str, int]] = [
    ("scrape_wholesale.py",            "Scrape wholesale",          120),
    ("scrape_wiki_hex.py",             "Scrape hex wiki",            60),
    ("scrape_spoolman_hex.py",         "Scrape hex SpoolmanDB",      60),
    ("scrape_thefilamentdb_hex.py",    "Scrape hex TheFilamentDB",   60),
    ("scrape_internal_exact_hex.py",   "Scrape hex internal exact",  30),
    ("sync_polymaker_brand_assets.py", "Sync Polymaker brand assets",60),
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
     "host": "table interne hors-ligne + SpoolmanDB + TheFilamentDB (HEX couleurs)"},
    {"name": "ROSA3D (spécifications matériaux)", "license": "Données factuelles — © ROSA PLAST",
     "host": "table interne hors-ligne + SpoolmanDB (HEX couleurs)"},
]


DEFAULT_CONFIG = {
    "network_consent": None,    # None = jamais demandé ; True/False = choix explicite
    "auto_update": False,       # opt-in : aucune mise à jour automatique par défaut
    "update_interval_days": 7,
    "last_update": None,
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
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


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
            # Les scripts impriment des caractères Unicode (—, ─…). Dans un exe
            # gelé sous Windows, stdout/stderr utilisent cp1252 par défaut, ce
            # qui provoque un UnicodeEncodeError. On force l'UTF-8.
            for _stream in (sys.stdout, sys.stderr):
                try:
                    _stream.reconfigure(encoding="utf-8", errors="replace")
                except Exception:
                    pass
            import runpy
            sys.argv = [script_path]
            runpy.run_path(script_path, run_name="__main__")
        return True
    return False


# ─── DB : lecture / écriture ──────────────────────────────────────────────
def load_db(path: str = DB_PATH) -> dict:
    """Charge la DB. Ne lève jamais : retourne une DB vide en cas d'erreur."""
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Garantit la présence des clés essentielles.
            for k, v in EMPTY_DB.items():
                data.setdefault(k, dict(v))
            return data
        except Exception:
            pass
    return {k: dict(v) for k, v in EMPTY_DB.items()}


def save_db(db: dict, path: str = DB_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


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
    h = (h or "").strip().lstrip("#")
    return h.upper() if re.fullmatch(r"[0-9A-Fa-f]{6}", h) else None


def slugify(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", name or "")


# ─── Profils Orca ─────────────────────────────────────────────────────────
def find_orca_profile(product_name: str) -> Optional[str]:
    """Chemin du profil Orca pour ce produit, ou None."""
    if not os.path.isdir(ORCA_DIR):
        return None
    path = os.path.join(ORCA_DIR, f"{product_name} @Snapmaker U1 - OrcaSlicer.json")
    return path if os.path.isfile(path) else None


def load_orca_temps(path: str) -> dict:
    """Extrait les overrides température/densité d'un profil Orca."""
    with open(path, encoding="utf-8") as f:
        p = json.load(f)

    def first(k, d):
        v = p.get(k, [d])
        return v[0] if v else d

    plate_keys = ["cool_plate_temp", "eng_plate_temp", "hot_plate_temp", "textured_plate_temp"]
    bed_temps = [int(first(k, 0)) for k in plate_keys]
    nz = [t for t in bed_temps if t > 0]
    return {
        "min_temp":     int(first("nozzle_temperature_range_low", 190)),
        "max_temp":     int(first("nozzle_temperature_range_high", 230)),
        "bed_min_temp": min(nz) if nz else 0,
        "bed_max_temp": max(nz) if nz else 0,
        "density":      float(first("filament_density", 1.24)),
        "diameter":     float(first("filament_diameter", 1.75)),
    }


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
    logo_path = db.get("_brands", {}).get(brand, {}).get("logo_path", "")
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
            path: str = DB_PATH) -> dict:
    """Ajoute/maj un SKU dans la DB. Retourne l'entrée créée."""
    entry = {"product": product, "color_name": color_name, "hex": validate_hex(hex_val) if hex_val else None}
    db.setdefault("_skus", {})[sku] = entry
    if persist:
        save_db(db, path)
    return entry


def set_sku_hex(db: dict, sku: str, hex_val: str, persist: bool = True,
                path: str = DB_PATH) -> Optional[str]:
    """Définit le HEX d'un SKU. Retourne le HEX normalisé ou None si invalide."""
    norm = validate_hex(hex_val)
    if not norm:
        return None
    if sku in db.get("_skus", {}):
        db["_skus"][sku]["hex"] = norm
        if persist:
            save_db(db, path)
    return norm


# ─── Payload OpenSpool / NFC ──────────────────────────────────────────────
def build_openspool(entry: dict, product_data: dict, brand_meta: Optional[dict] = None) -> dict:
    """Construit le payload OpenSpool/NFC (overrides Orca appliqués si dispo)."""
    src = dict(product_data)
    orca_path = find_orca_profile(entry.get("product", ""))
    if orca_path:
        try:
            src.update(load_orca_temps(orca_path))
        except Exception:
            pass

    payload = {
        "protocol": "openspool",
        "version": "1.0",
        "type": src.get("type"),
        "color_hex": entry["hex"] if entry.get("hex") else "000000",
        "brand": src.get("brand", "Polymaker"),
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
            "name": brand_meta.get("name", src.get("brand", "Polymaker")),
            "website": brand_meta.get("website"),
            "origin": brand_meta.get("origin"),
            "logo_url": brand_meta.get("logo_url"),
            "logo_path": brand_meta.get("logo_path"),
        }
        payload["logo_url"] = brand_meta.get("logo_url")
        payload["image"] = brand_meta.get("logo_url")

    payload["sku"] = entry.get("sku")
    payload["product"] = entry.get("product")
    payload["color_name"] = entry.get("color_name")
    return payload


def openspool_filename(sku: str, product: str, color_name: str) -> str:
    return f"{sku}_{slugify(product)}_{slugify(color_name)}_openspool.json"


def write_openspool(sku: str, entry: dict, product_data: dict,
                    output_dir: str = OUTPUT_DIR,
                    brand_meta: Optional[dict] = None) -> str:
    """Écrit le fichier JSON OpenSpool et retourne son chemin."""
    entry_with_sku = dict(entry)
    entry_with_sku["sku"] = sku
    payload = build_openspool(entry_with_sku, product_data, brand_meta=brand_meta)
    os.makedirs(output_dir, exist_ok=True)
    filename = openspool_filename(sku, entry["product"], entry["color_name"])
    out_path = os.path.join(output_dir, filename)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return out_path


# ─── Mise à jour DB (scrapers) ────────────────────────────────────────────
@dataclass
class StepResult:
    label: str
    ok: bool
    code: int = 0
    stderr: str = ""


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

    python = python or venv_python()
    results: list[StepResult] = []
    total = len(UPDATE_PIPELINE)
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
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
                encoding="utf-8", errors="replace",
            )
            results.append(StepResult(label, r.returncode == 0, r.returncode, (r.stderr or "").strip()))
        except Exception as e:
            results.append(StepResult(label, False, -1, str(e)))
    if any(r.ok for r in results):
        mark_updated()
    return results


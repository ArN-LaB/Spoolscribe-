"""Printer/reader catalogue: what each machine reads and what SpoolScribe can export for it.

The list lives in ``data/printers.json`` (bundled) and can be refreshed from the
project repository into the user's data folder. Exporting a file is never
writing a printer's tag; the ``openspool`` flag of the chosen firmware says
whether the machine can read an OpenSpool NTAG at all.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError

GROUP_ORDER = ("native", "external", "incompatible", "none")
_LEGACY_IDS = {"u1_stock": ("u1", "stock")}
DEFAULT = "u1"
PRINTERS_URL = "https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/data/printers.json"


def _resource_dir() -> str:
    import sys
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    return os.path.dirname(os.path.abspath(__file__))


def bundled_path() -> Path:
    return Path(os.environ.get("SPOOLSCRIBE_RESOURCE_DIR") or _resource_dir()) / "data" / "printers.json"


def user_path() -> Path | None:
    home = os.environ.get("SPOOLSCRIBE_DATA_HOME")
    return Path(home) / "data" / "printers.json" if home else None


def validate_catalogue(doc) -> dict:
    if not isinstance(doc, dict) or doc.get("format") != "spoolscribe-printers" or doc.get("version") != 1:
        raise ValueError("Liste d'imprimantes : format inconnu.")
    printers = doc.get("printers")
    if not isinstance(printers, list) or not printers:
        raise ValueError("Liste d'imprimantes vide.")
    seen = set()
    for printer in printers:
        if not isinstance(printer, dict) or not isinstance(printer.get("id"), str) or printer["id"] in seen:
            raise ValueError("Imprimante invalide ou dupliquée.")
        seen.add(printer["id"])
        if printer.get("group") not in GROUP_ORDER or not isinstance(printer.get("label"), str):
            raise ValueError(f"Imprimante {printer['id']} : groupe ou libellé invalide.")
        firmwares = printer.get("firmwares")
        if not isinstance(firmwares, list) or not firmwares or any(
                not isinstance(f, dict) or not isinstance(f.get("id"), str) or type(f.get("openspool")) is not bool for f in firmwares):
            raise ValueError(f"Imprimante {printer['id']} : firmwares invalides.")
        if any("\x00" in str(v) or len(str(v)) > 2000 for v in printer.values() if isinstance(v, str)):
            raise ValueError("Texte d'imprimante invalide.")
    return doc


def load_catalogue() -> dict:
    """User copy when valid and newer, otherwise the bundled list; never fails on a bad user file."""
    bundled = validate_catalogue(json.loads(bundled_path().read_text(encoding="utf-8")))
    user = user_path()
    if user and user.is_file():
        try:
            candidate = validate_catalogue(json.loads(user.read_text(encoding="utf-8")))
            if str(candidate.get("updated", "")) >= str(bundled.get("updated", "")):
                candidate["_origin"] = "user"
                return candidate
        except (OSError, ValueError):
            pass
    bundled["_origin"] = "bundled"
    return bundled


def _profiles() -> dict:
    out = {}
    for printer in load_catalogue()["printers"]:
        firmwares = printer["firmwares"]
        out[printer["id"]] = {
            "label": printer["label"], "vendor": printer.get("vendor", ""), "group": printer["group"],
            "reader": printer.get("reader", ""), "help": printer.get("help", ""),
            "fields": printer.get("fields", {}), "firmwares": firmwares,
            # Compatibility: the printer "can export" when at least one firmware reads OpenSpool.
            "nfc": any(f["openspool"] for f in firmwares),
        }
    return out


PROFILES = _profiles()


def reload() -> dict:
    PROFILES.clear()
    PROFILES.update(_profiles())
    return PROFILES


def resolve(printer_id: str | None, firmware_id: str | None = None) -> tuple[str, str]:
    """Valid (printer, firmware) pair for stored settings, with legacy identifiers mapped."""
    printer_id, legacy_firmware = _LEGACY_IDS.get(printer_id or "", (printer_id, None))
    if printer_id not in PROFILES:
        printer_id = DEFAULT if DEFAULT in PROFILES else next(iter(PROFILES))
    firmwares = PROFILES[printer_id]["firmwares"]
    wanted = legacy_firmware or firmware_id
    firmware = next((f["id"] for f in firmwares if f["id"] == wanted), firmwares[0]["id"])
    return printer_id, firmware


def firmware(printer_id: str, firmware_id: str | None) -> dict:
    printer_id, firmware_id = resolve(printer_id, firmware_id)
    return next(f for f in PROFILES[printer_id]["firmwares"] if f["id"] == firmware_id)


def can_export(printer_id: str, firmware_id: str | None = None) -> bool:
    return bool(firmware(printer_id, firmware_id)["openspool"])


def describe(printer_id: str, firmware_id: str | None = None) -> str:
    printer_id, firmware_id = resolve(printer_id, firmware_id)
    fw = firmware(printer_id, firmware_id)
    label = PROFILES[printer_id]["label"]
    return f"{label} — {fw['label']}" if len(PROFILES[printer_id]["firmwares"]) > 1 else label


def install_catalogue(raw: bytes) -> dict:
    """Store a downloaded list in the user folder after validation; return it."""
    candidate = validate_catalogue(json.loads(raw.decode("utf-8")))
    target = user_path()
    if target is None:
        raise ValueError("Dossier de données inconnu.")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_bytes(raw)
    os.replace(tmp, target)
    reload()
    return candidate


def refresh_catalogue(fetch) -> dict | None:
    """A development list may not exist on main yet; keep the bundled one.

    Other HTTP/network errors remain errors, and no invalid response is installed.
    """
    try:
        raw = fetch(PRINTERS_URL, 512 * 1024)
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    return install_catalogue(raw)

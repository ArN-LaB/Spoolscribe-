"""Documented printer + reader + software configurations, not brand-wide promises.

The legacy ``firmwares`` key remains compatible with saved settings and older
clients. Each entry now describes a complete reading configuration and its effect.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError

EXPORT_FORMATS = ("openspool", "opentag3d")

GROUP_ORDER = ("native", "external", "incompatible", "none")
_LEGACY_IDS = {"u1_stock": ("u1", "stock"),
               "bambu_openspool": ("bambu", "openspool_network"),
               "prusa": ("prusa_generic", "stock")}
CONNECTIONS = ('integrated','usb','network','can','none','custom')
FIRMWARE_KINDS = ('stock','modified','integration')
EFFECTS = ('printer','inventory','standalone','none')
DEFAULT = "u1"
PRINTERS_URL = "https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/data/printers.json"


def _resource_dir() -> str:
    import sys
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    return str(Path(__file__).resolve().parents[2])


def bundled_path() -> Path:
    return Path(os.environ.get("SPOOLSCRIBE_RESOURCE_DIR") or _resource_dir()) / "data" / "printers.json"


def user_path() -> Path | None:
    home = os.environ.get("SPOOLSCRIBE_DATA_HOME")
    return Path(home) / "data" / "printers.json" if home else None


def validate_catalogue(doc) -> dict:
    if not isinstance(doc, dict) or doc.get("format") != "spoolscribe-printers" or doc.get("version") != 1:
        raise ValueError("Liste d'imprimantes : format inconnu.")
    if 'configuration_schema' in doc and (type(doc['configuration_schema']) is not int or doc['configuration_schema']!=1):
        raise ValueError('Schéma de configuration inconnu.')
    printers = doc.get("printers")
    if not isinstance(printers, list) or not printers:
        raise ValueError("Liste d'imprimantes vide.")
    seen = set()
    for printer in printers:
        if not isinstance(printer, dict) or not isinstance(printer.get("id"), str) or printer["id"] in seen:
            raise ValueError("Imprimante invalide ou dupliquée.")
        seen.add(printer["id"])
        if 'hidden' in printer and type(printer['hidden']) is not bool:
            raise ValueError('Profil historique invalide.')
        if printer.get("group") not in GROUP_ORDER or not isinstance(printer.get("label"), str):
            raise ValueError(f"Imprimante {printer['id']} : groupe ou libellé invalide.")
        firmwares = printer.get("firmwares")
        if not isinstance(firmwares, list) or not firmwares or any(
                not isinstance(f, dict) or not isinstance(f.get("id"), str) or type(f.get("openspool")) is not bool for f in firmwares):
            raise ValueError(f"Imprimante {printer['id']} : firmwares invalides.")
        if any("\x00" in str(v) or len(str(v)) > 2000 for v in printer.values() if isinstance(v, str)):
            raise ValueError("Texte d'imprimante invalide.")
    for printer in printers:
        ids=set()
        for fw in printer['firmwares']:
            if 'choice_label' in fw and (not isinstance(fw['choice_label'],str) or not fw['choice_label'] or len(fw['choice_label'])>120):
                raise ValueError('Libellé de choix invalide.')
            supported=fw.get('formats',['openspool'] if fw['openspool'] else [])
            if (fw['id'] in ids or not isinstance(supported,list) or
                any(x not in EXPORT_FORMATS for x in supported) or len(set(supported))!=len(supported)
                or ('openspool' in supported)!=fw['openspool']):
                raise ValueError('Formats de lecteur invalides.')
            ids.add(fw['id'])
            if 'connection' in fw or doc.get('configuration_schema') == 1 and not printer.get('hidden'):
                read=fw.get('reader_formats')
                if (fw.get('connection') not in CONNECTIONS or fw.get('firmware_kind') not in FIRMWARE_KINDS
                    or fw.get('effect') not in EFFECTS or fw.get('evidence') not in ('documented','experimental','unverified')
                    or not isinstance(read,list) or any(not isinstance(x,str) for x in read)
                    or not set(supported).issubset(read) or (supported and (fw['evidence']=='unverified' or fw['effect']=='none'))
                    or not isinstance(fw.get('reader'),str) or not isinstance(fw.get('notes'),str)
                    or not isinstance(fw.get('url'),str) or not fw['url'].startswith('https://')
                    or not isinstance(fw.get('checked'),str)):
                    raise ValueError('Configuration de lecture invalide ou non documentée.')
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
            "hidden": printer.get('hidden') is True,
            # The printer can export when a firmware reads at least one supported format.
            "nfc": any(f.get("formats",["openspool"] if f["openspool"] else []) for f in firmwares),
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


def formats(printer_id: str, firmware_id: str | None = None) -> tuple[str, ...]:
    printer_id,legacy=_LEGACY_IDS.get(printer_id,(printer_id,None))
    firmware_id=legacy or firmware_id
    if printer_id not in PROFILES or firmware_id is not None and firmware_id not in [f['id'] for f in PROFILES[printer_id]['firmwares']]:
        return ()
    fw=firmware(printer_id,firmware_id)
    return tuple(fw.get('formats',['openspool'] if fw['openspool'] else []))


def configuration(printer_id: str, firmware_id: str | None = None) -> dict:
    """Description for presentation; old catalogues keep their historical API."""
    printer_id,firmware_id=resolve(printer_id,firmware_id)
    fw=dict(firmware(printer_id,firmware_id))
    profile=PROFILES[printer_id]
    fw.setdefault('connection','integrated' if profile['group'] in ('native','incompatible') else 'none' if profile['group']=='none' else 'custom')
    fw.setdefault('firmware_kind','integration')
    fw.setdefault('reader',profile.get('reader',''))
    fw.setdefault('reader_formats',list(formats(printer_id,firmware_id)))
    fw.setdefault('effect','standalone' if formats(printer_id,firmware_id) else 'none')
    fw.setdefault('evidence','unverified')
    return fw


def categories(printer_id: str) -> set[str]:
    """A printer may have both a proprietary original reader and an added one."""
    result=set()
    for fw in PROFILES[printer_id]['firmwares']:
        c=configuration(printer_id,fw['id'])
        if formats(printer_id,fw['id']):
            result.update(('compatible',c['connection'],c['firmware_kind']))
        elif c['reader_formats']:
            result.add('rfid')
    if 'compatible' not in result and 'rfid' not in result:result.add('none')
    return result


def can_export(printer_id: str, firmware_id: str | None = None, export_format=None) -> bool:
    supported=formats(printer_id,firmware_id)
    return export_format in supported if export_format is not None else bool(supported)


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

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _deny_network(event, args):
    if event in ("socket.connect", "socket.getaddrinfo"):
        raise AssertionError("Les tests SpoolScribe doivent rester hors ligne.")


sys.addaudithook(_deny_network)


def catalogue():
    return json.loads((ROOT / "data/polymaker_db.json").read_text(encoding="utf-8"))


def product():
    return {"type": "PLA", "brand": "Polymaker", "min_temp": 190, "max_temp": 230,
            "bed_min_temp": 60, "bed_max_temp": 60, "diameter": 1.75, "density": 1.24}


def entry():
    return {"sku": "LOCAL", "product": "Audit PLA", "color_name": "Red", "hex": "FF0000"}


def small_db():
    return {"_products": {"Audit PLA": product()}, "_skus": {"LOCAL": entry()}, "_brands": {}}

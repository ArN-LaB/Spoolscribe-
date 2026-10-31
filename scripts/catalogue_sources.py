"""Offline source adapters. No HTTP, application imports or filesystem writes.

OFD's source tree is its path-addressed canonical dataset. Reading its official
archive avoids thousands of requests and rejects unsafe archive/JSON structures.
"""
from __future__ import annotations

import hashlib
import io
import math
from pathlib import PurePosixPath
import re
import tarfile
import uuid

from scripts import db_io

OFD_ARCHIVE_URL = "https://codeload.github.com/OpenFilamentCollective/open-filament-database/tar.gz/refs/heads/main"
OFD_REPOSITORY = "https://github.com/OpenFilamentCollective/open-filament-database"
CURATED_BRANDS = {"polymaker", "prusament", "rosa3d_filaments"}
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024


def read_ofd_archive(raw: bytes) -> dict[str, bytes]:
    if len(raw) > MAX_ARCHIVE_BYTES:
        raise db_io.SourceUnavailable("Archive OFD trop volumineuse.")
    files = {}
    total = 0
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
            for index, member in enumerate(archive):
                if index > 100000:
                    raise ValueError("Trop d'entrées dans l'archive")
                parts = PurePosixPath(member.name).parts
                if not parts or member.name.startswith("/") or ".." in parts or "\\" in member.name:
                    raise ValueError("Chemin d'archive invalide")
                if member.isdir():
                    continue
                if not member.isfile():
                    raise ValueError("Liens d'archive non autorisés")
                total += member.size
                if member.size > 16 * 1024 * 1024 or total > 256 * 1024 * 1024:
                    raise ValueError("Limite de décompression dépassée")
                relative = "/".join(parts[1:])
                if relative == "LICENSE" or relative.startswith("data/"):
                    if relative in files:
                        raise ValueError("Chemin dupliqué")
                    files[relative] = archive.extractfile(member).read()
    except (tarfile.TarError, OSError, ValueError) as exc:
        raise db_io.SourceUnavailable(f"Archive OFD inutilisable : {exc}") from exc
    if not files or "LICENSE" not in files:
        raise db_io.SourceUnavailable("Archive OFD vide ou sans licence.")
    return files


def _text(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > 500 or any(ord(c) < 32 for c in value):
        raise ValueError(f"{field} : texte non vide, sans caractères de contrôle requis")
    return value.strip()


def _number(value, field, *, integer=False, positive=False):
    if value is None:
        return None
    if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{field} : nombre positif fini requis")
    if positive and value == 0 or integer and int(value) != value:
        raise ValueError(f"{field} : valeur physique invalide")
    return int(value) if integer else value


def _uuid(value):
    if not isinstance(value, str):
        raise ValueError("UUID source manquant")
    return str(uuid.UUID(value))


def _hex(value):
    if not isinstance(value, str) or not re.fullmatch(r"#?[a-fA-F0-9]{6}(?:[a-fA-F0-9]{2})?", value):
        raise ValueError("Couleur source HEX invalide")
    return value.lstrip("#").upper()


def adapt_ofd(files: dict[str, bytes], *, source_digest: str, logos: dict | None = None, preserve_curated: bool = True) -> tuple[dict, dict]:
    """Normalize all usable brands; preserve unknowns and record every rejected row.

    Existing curated brands keep their established entries, avoiding unreliable
    fuzzy cross-source joins. IDs are namespaced OFD UUIDs, never invented SKUs.
    """
    result = {"_products": {}, "_skus": {}, "_brands": {}}
    report = {"source": OFD_REPOSITORY, "sha256": source_digest, "license": "MIT",
              "brands_seen": 0, "curated_brands_preserved": [], "rejected": [], "empty_brands": [],
              "incomplete": 0, "references": 0}
    parsed = {}

    def read(path):
        if path not in parsed:
            raw = files[path]
            if len(raw) > 1024 * 1024:
                raise ValueError("Document JSON trop volumineux")
            parsed[path] = db_io.parse_json(raw)
        return parsed[path]

    for path in sorted(files):
        parts = PurePosixPath(path).parts
        if len(parts) != 6 or parts[0] != "data" or parts[-1] != "variant.json":
            continue
        _, slug, material_slug, filament_slug, variant_slug, _ = parts
        if preserve_curated and slug in CURATED_BRANDS:
            if slug not in report["curated_brands_preserved"]:
                report["curated_brands_preserved"].append(slug)
            continue
        try:
            brand = read(f"data/{slug}/brand.json")
            material = read(f"data/{slug}/{material_slug}/material.json")
            filament = read(f"data/{slug}/{material_slug}/{filament_slug}/filament.json")
            variant = read(path)
            brand_name = _text(brand.get("name"), "Fabricant")
            brand_uuid = _uuid(brand.get("uuid"))
            material_name = _text(material.get("material"), "Matière")
            filament_name = _text(filament.get("name"), "Produit")
            filament_uuid = _uuid(filament.get("uuid"))
            variant_uuid = _uuid(variant.get("uuid"))
            color_name = _text(variant.get("name"), "Couleur")
            source_color = variant.get("color_hex")
            colors = [] if source_color in (None, "") else [_hex(h) for h in
                     (source_color if isinstance(source_color, list) else [source_color])]
            if len(colors) > 32:
                raise ValueError("Trop de couleurs source")
            traits = variant.get("traits") or {}
            if not isinstance(traits, dict) or any(type(v) is not bool for v in traits.values()):
                raise ValueError("Caractéristiques de couleur invalides")
            sizes_path = path.removesuffix("variant.json") + "sizes.json"
            sizes = read(sizes_path) if sizes_path in files else []
            if not isinstance(sizes, list):
                raise ValueError("Liste de formats attendue")
            # A missing size stays visibly incomplete instead of inventing 1.75 mm.
            sizes = sizes or [{"uuid": variant_uuid}]
            physical = {target: _number(filament.get(source), target, integer=target.endswith("temp"),
                                       positive=target == "density")
                        for target, source in (("min_temp", "min_print_temperature"),
                        ("max_temp", "max_print_temperature"), ("bed_min_temp", "min_bed_temperature"),
                        ("bed_max_temp", "max_bed_temperature"), ("density", "density"))}
            for lo, hi in (("min_temp", "max_temp"), ("bed_min_temp", "bed_max_temp")):
                if physical[lo] is not None and physical[hi] is not None and physical[lo] > physical[hi]:
                    raise ValueError(f"Plage {lo}/{hi} inversée")
            incoming = []
            for size in sizes:
                source_id = _uuid(size.get("uuid"))
                diameter = _number(size.get("diameter"), "diameter", positive=True)
                weight = _number(size.get("filament_weight"), "weight", positive=True)
                key = "OFD-" + source_id.upper()
                pname = f"{brand_name} {material_name} {filament_name} · {diameter or '?'} mm [{filament_uuid[:8]}]"
                product = dict(physical, type=material_name, brand=brand_name, diameter=diameter)
                product["display_name"] = (f"{brand_name} {filament_name}" if material_name.casefold() in filament_name.casefold()
                                           else f"{brand_name} {material_name} {filament_name}")
                item = {"product": pname, "color_name": color_name, "hex": None,
                        "source": "Open Filament Database", "source_id": source_id,
                        "source_path": sizes_path if sizes_path in files else path,
                        "weight": weight, "source_variant_id": variant_uuid}
                if len(colors) == 1:
                    item["hex"] = colors[0][:6]
                    if len(colors[0]) == 8:
                        item["alpha"] = colors[0][6:]
                elif colors:
                    item["source_colors"] = colors
                if traits:
                    item["source_traits"] = traits
                if size.get("article_number") is not None:
                    item["manufacturer_sku"] = _text(str(size["article_number"]), "SKU fabricant")
                if "spool_refill" in size:
                    if type(size["spool_refill"]) is not bool:
                        raise ValueError("spool_refill : booléen requis")
                    item["spool_refill"] = size["spool_refill"]
                if key in result["_skus"] or any(row[0] == key for row in incoming):
                    raise ValueError(f"Identifiant source dupliqué : {source_id}")
                incoming.append((key, pname, product, item))
            # Validate the entire variant before publishing any of its sizes.
            db_io.validate_db({"_products": {n: p for _, n, p, _ in incoming},
                               "_skus": {k: e for k, _, _, e in incoming}})
            for key, pname, product, item in incoming:
                if pname in result["_products"] and result["_products"][pname] != product:
                    raise ValueError("Collision d'identité produit")
            for key, pname, product, item in incoming:
                result["_products"][pname] = product
                result["_skus"][key] = item
                if not item["hex"] or any(v is None for v in product.values()):
                    report["incomplete"] += 1
            meta = {"name": brand_name, "origin": brand.get("origin"), "source": OFD_REPOSITORY,
                    "source_id": brand_uuid, "source_slug": slug}
            website = brand.get("website")
            if isinstance(website, str) and website.strip():
                meta["website"] = website if website.startswith("https://") else "https://" + website.removeprefix("http://")
            approved = (logos or {}).get(brand_uuid)
            if approved:
                meta["logo_path"] = approved["path"]
            result["_brands"].setdefault(brand_name, meta)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            report["rejected"].append({"path": path, "reason": str(exc)})
    brand_paths = [p for p in files if len(PurePosixPath(p).parts) == 3 and p.endswith("/brand.json")]
    report["brands_seen"] = len(brand_paths)
    imported_slugs = {b["source_slug"] for b in result["_brands"].values()}
    report["empty_brands"] = [PurePosixPath(p).parts[1] for p in brand_paths
                              if PurePosixPath(p).parts[1] not in imported_slugs | CURATED_BRANDS]
    report["references"] = len(result["_skus"])
    report["brands_imported"] = len(result["_brands"])
    if not result["_skus"]:
        raise db_io.SourceUnavailable("OFD ne contient aucune référence exploitable.")
    db_io.validate_db(result)
    result["_source_snapshot"] = {k: v for k, v in report.items() if k not in ("rejected", "empty_brands")}
    return result, report


SPOOLMAN_URL = "https://donkie.github.io/SpoolmanDB/filaments.json"


def brand_key(name):
    key = re.sub(r"[^a-z0-9]", "", name.casefold())
    return {"esun": "esun3d", "rosa3dfilaments": "rosa3d"}.get(key, key)


def adapt_spoolman(rows, *, source_digest: str, covered_brands=()) -> tuple[dict, dict]:
    """Supplement manufacturers not covered by the curated/OFD catalogues.

    No fuzzy product joins, no material-default temperature invention. Compiled
    source IDs are kept verbatim; short internal references are namespaced hashes.
    """
    if not isinstance(rows, list) or not rows:
        raise db_io.SourceUnavailable("Catalogue SpoolmanDB vide ou mal formé.")
    covered = {brand_key(name) for name in covered_brands}
    result = {"_products": {}, "_skus": {}, "_brands": {}}
    report = {"source": SPOOLMAN_URL, "sha256": source_digest, "license": "MIT", "rejected": [],
              "references": 0, "incomplete": 0, "brands_imported": 0, "already_covered": 0}
    seen = set()

    def temperatures(row, field):
        bounds = row.get(field + "_range")
        if bounds is not None:
            if not isinstance(bounds, list) or len(bounds) != 2:
                raise ValueError("Plage de température mal formée")
            low, high = (_number(v, field, integer=True) for v in bounds)
        else:
            low = high = _number(row.get(field), field, integer=True)
        if low is not None and high is not None and low > high:
            raise ValueError("Plage de température inversée")
        return low, high

    for index, row in enumerate(rows):
        try:
            name = _text(row.get("manufacturer"), "Fabricant")
            identifier = _text(row.get("id"), "Identifiant source")
            material = _text(row.get("material"), "Matière")
            color_name = _text(row.get("name"), "Nom")
            if brand_key(name) in covered:
                report["already_covered"] += 1
                continue
            if identifier in seen:
                raise ValueError("Identifiant source dupliqué")
            seen.add(identifier)
            sku = "SMDB-" + hashlib.sha256(identifier.encode()).hexdigest()[:24].upper()
            if sku in result["_skus"]:
                raise ValueError("Collision de référence")
            low, high = temperatures(row, "extruder_temp")
            bed_low, bed_high = temperatures(row, "bed_temp")
            physical = {"min_temp": low, "max_temp": high, "bed_min_temp": bed_low, "bed_max_temp": bed_high,
                        "diameter": _number(row.get("diameter"), "diameter", positive=True),
                        "density": _number(row.get("density"), "density", positive=True)}
            display = f"{name} {material} {color_name}"
            pname = f"{display} [{sku}]"
            product = dict(physical, brand=name, type=material, display_name=display)
            item = {"product": pname, "color_name": color_name, "hex": None, "source": "SpoolmanDB",
                    "source_id": identifier, "weight": _number(row.get("weight"), "weight", positive=True)}
            single, multi = row.get("color_hex"), row.get("color_hexes")
            if single is not None and multi:
                raise ValueError("Couleur simple et multiple simultanées")
            if single is not None:
                color = _hex(single); item["hex"] = color[:6]
                if len(color) == 8:
                    item["alpha"] = color[6:]
            elif multi:
                if not isinstance(multi, list) or len(multi) > 32:
                    raise ValueError("Liste de couleurs invalide")
                item["source_colors"] = [_hex(c) for c in multi]
            if row.get("translucent") is True:
                item["source_traits"] = {"translucent": True}
            db_io.validate_db({"_products": {pname: product}, "_skus": {sku: item}})
            result["_products"][pname] = product
            result["_skus"][sku] = item
            result["_brands"].setdefault(name, {"name": name, "source": "SpoolmanDB"})
            if not item["hex"] or any(v is None for v in physical.values()):
                report["incomplete"] += 1
        except (ValueError, TypeError, AttributeError) as exc:
            report["rejected"].append({"index": index, "reason": str(exc)})
    if not result["_skus"] and not report["already_covered"]:
        raise db_io.SourceUnavailable("Aucune référence SpoolmanDB exploitable.")
    report["references"] = len(result["_skus"])
    report["brands_imported"] = len(result["_brands"])
    result["_source_snapshot"] = {k:v for k,v in report.items() if k != "rejected"}
    return result, report


SOURCE_ADAPTERS = {"ofd": adapt_ofd, "spoolman": adapt_spoolman}

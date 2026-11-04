"""Paste interpretation and CSV/TSV mapping for colour measurements. No Qt, no network.

Everything read here is untrusted text: bounded sizes, explicit encodings and
separators, no formula/URL/command interpretation, no automatic linking to a
filament. The result of :func:`interpret_paste` and :func:`validate_rows` is a
*proposal*; the user confirms before anything is stored.

Nothing is guessed: a token is a value only when it is whole and labelled, a
colour space that is not sRGB is reported (never converted), unbalanced Lab
sets are reported, and when a file maps several colour spaces the principal
one is an explicit choice of the user.
"""
from __future__ import annotations

import csv
import hashlib
import io
import os
import re

from . import colour_measurements as cm

LIMITS = cm.LIMITS
MeasurementError = cm.MeasurementError
DELIMITERS = {",": "virgule", ";": "point-virgule", "\t": "tabulation"}
ENCODINGS = ("utf-8", "cp1252", "latin-1")
SPACE_LABELS = cm.SPACE_LABELS

# Column aliases, case-insensitive after trimming; '*' and spaces are ignored.
_ALIASES = {
    "L": ("l", "l*", "lab_l", "cielab_l", "lightness", "l (lab)", "lab l"),
    "a": ("a", "a*", "lab_a", "cielab_a", "a (lab)", "lab a"),
    "b": ("b", "b*", "lab_b", "cielab_b", "b (lab)", "lab b"),
    "hex": ("hex", "hex code", "color hex", "colour hex", "srgb hex", "rgb hex", "#"),
    "r": ("r", "red", "rgb_r", "srgb_r"),
    "g": ("g", "green", "rgb_g", "srgb_g"),
    "bl": ("b (rgb)", "blue", "rgb_b", "srgb_b"),
    "illuminant": ("illuminant", "illum", "light source", "éclairage", "illuminant/observer"),
    "observer": ("observer", "observateur", "obs"),
    "geometry": ("geometry", "géométrie", "measurement geometry", "optics"),
    "specular": ("specular", "sci/sce", "sci", "sce", "spéculaire", "specular component"),
    "aperture": ("aperture", "ouverture"),
    "name": ("name", "sample", "sample name", "label", "nom", "échantillon", "id", "target"),
    "device": ("device", "instrument", "appareil", "meter", "device model", "modèle"),
    "manufacturer": ("manufacturer", "device manufacturer", "fabricant", "instrument manufacturer"),
    "material": ("material", "matériau", "matiere", "matière"),
    "finish": ("finish", "finition", "surface finish"),
    "thickness": ("thickness", "épaisseur"),
    "backing": ("backing", "fond", "background"),
    "note": ("note", "notes", "comment", "comments", "remarque"),
    "date": ("date", "measured", "timestamp", "time"),
}
_ALIAS_INDEX = {alias: key for key, names in _ALIASES.items() for alias in names}
COLUMN_KEYS = ("L", "a", "b", "hex", "r", "g", "b_rgb", "name", "illuminant", "observer", "geometry", "specular", "aperture",
               "device", "manufacturer", "material", "finish", "thickness", "backing", "note", "date")

_NUM = r"[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][+-]?\d+)?(?![.,]?\d)"   # no second mark, no thousands groups
_TOKEN = r"[^\s,;()]+"
_HEX = re.compile(r"(?:\bHEX\b[^0-9A-Fa-f#]{0,12})?#\s*([0-9A-Fa-f]{6})\b|\bHEX\b[\s:=]*([0-9A-Fa-f]{6})\b", re.I)
# Whole tokens and their separators are captured and validated afterwards: a suffix (191.5, 1910) is never cut off.
_RGB_SEP = r"(\s*[,; ]\s*)"
_RGB = re.compile(r"((?:[\w.]+\s+){0,3}?)\b(s?RGB|RVB)\b[\s:=(]*(" + _TOKEN + ")" + _RGB_SEP + "(" + _TOKEN + ")" + _RGB_SEP
                  + "(" + _TOKEN + ")", re.I)
# What may still belong to the channels, matched *at* the end of the third token (anchored, so it cannot be
# skipped by backtracking): a remnant glued by a comma/semicolon (191,5 · 191;5 · 191 ,5) or a fourth number
# on the same line (191, 5 · 191 255) that is not an observer angle.
_RGB_REMNANT = re.compile(r"[ \t]*[,;][^\s,;()]+|(?:[ \t]*[,;][ \t]*|[ \t]+)[+-]?\d+(?:[.,]\d+)*(?![\w.°º%])(?![ \t]*(?:°|º|%|(?i:deg)))")
# Colour spaces explicitly not sRGB: reported, never converted.
_NON_SRGB = re.compile(r"\b(adobe|prophoto|pro\s*photo|wide\s*gamut|linear|apple|colormatch|display\s*p3|p3|dci|rec\.?\s*\d{3,4}"
                       r"|bt\.?\s*\d{3,4}|aces\w*|cie)\b", re.I)
_LAB_COMPACT = re.compile(r"\b(?:CIE)?L\*?a\*?b\*?\b[\s:=(]*(" + _NUM + r")\s*[,; ]\s*(" + _NUM + r")\s*[,; ]\s*(" + _NUM + r")\)?", re.I)
_LABELLED = {
    "L": re.compile(r"(?<![A-Za-z])L\*?\s*[:=]\s*(" + _NUM + ")", re.I),
    "a": re.compile(r"(?<![A-Za-z])a\*?\s*[:=]\s*(" + _NUM + ")"),
    "b": re.compile(r"(?<![A-Za-z])b\*?\s*[:=]\s*(" + _NUM + ")"),
}
_ILLUMINANT = re.compile(r"\b(D50|D65|D55|D75|A|F2|F11|TL84|CWF|UL3000|UL30)\b")
_OBSERVER = re.compile(r"(?<![\d.,+-])\b(2|10)\s*(?:°|º|deg|degrees?|degrés?)", re.I)
_OBSERVER_SIGNED = re.compile(r"[+-]\s*(?:2|10)\s*(?:°|º|deg|degrees?|degrés?)", re.I)
_OBSERVER_CELL = re.compile(r"^\s*(2|10)\s*(?:°|º|deg|degrees?|degrés?)?\s*$", re.I)
_LAB_WORD = re.compile(r"\bL\*?\s*a\*?\s*b\*?\b|\bCIELAB\b", re.I)


# ── paste ─────────────────────────────────────────────────────────────────
def interpret_paste(text: str) -> dict:
    """Recognise only labelled, whole values. Returns a proposal, never a measurement.

    ``candidates``: list of ``{"space", "components", "lexemes", "label"}``;
    ``conditions``: detected illuminant/observer or None; ``errors``;
    ``unsupported``: colour spaces named in the text but not accepted;
    ``needs_decision``: True when several candidate sets exist or something
    is ambiguous (unbalanced Lab sets, several conditions, refused values);
    ``consistent``: HEX and RGB agree when both are present.
    """
    result = {"candidates": [], "conditions": {"illuminant": None, "observer": None}, "errors": [], "error_items": [],
              "unsupported": [], "needs_decision": False, "consistent": None, "unlabelled_numbers": 0}

    def fail(template, **values):
        """French text in ``errors`` (as always), the translatable error in ``error_items``."""
        error = MeasurementError(template, **values)
        result["errors"].append(str(error)); result["error_items"].append(error)

    if not isinstance(text, str):
        fail("Texte attendu.")
        return result
    if len(text.encode("utf-8")) > LIMITS["paste_bytes"]:
        fail("Texte collé trop long (maximum {v0} Kio).", v0=LIMITS["paste_bytes"] // 1024)
        return result
    clean = text.replace("\x00", "")
    # HEX
    for match in _HEX.finditer(clean):
        value = next(g for g in match.groups() if g is not None)
        result["candidates"].append({"space": "sRGB_HEX", "components": {"hex": value.upper()},
                                     "lexemes": {"hex": "#" + value}, "label": "HEX"})
    # RGB: whole tokens, sRGB only, one kind of separator; any remnant of a channel refuses the set.
    for match in _RGB.finditer(clean):
        qualifier, word, *parts = match.groups()
        tokens, separators = parts[0::2], parts[1::2]
        space_name = (qualifier.strip() + " " + word).strip()
        if _NON_SRGB.search(qualifier or ""):
            result["unsupported"].append(space_name)
            fail("Espace « {v0} » non pris en charge : seules les valeurs sRGB sont acceptées ; aucune conversion n’est faite.", v0=space_name)
            result["needs_decision"] = True
            continue
        end = match.end()
        while remnant := _RGB_REMNANT.match(clean, end):
            end = remnant.end()
        # "116,5 202 191": a comma glued between digits is a separator only when every separator is of the same
        # kind — comma, semicolon or blanks alone; blanks around a comma/semicolon do not change its kind.
        mixed = len({s.strip() or " " for s in separators}) > 1
        if end > match.end() or mixed or not all(re.fullmatch(r"\d{1,3}", t) for t in tokens):
            fail("RGB « {v0} » refusé : trois entiers 0–255 sans décimale sont requis.", v0=clean[match.start(3):end].strip())
            result["needs_decision"] = True
            continue
        values = [int(t) for t in tokens]
        if any(not 0 <= v <= 255 for v in values):
            fail("RGB hors de 0–255 ignoré : {v0}", v0=", ".join(tokens))
            result["needs_decision"] = True
            continue
        result["candidates"].append({"space": "sRGB_RGB8", "components": dict(zip("rgb", values)),
                                     "lexemes": dict(zip("rgb", tokens)), "label": "RGB"})
    # Lab: compact triplets, then labelled components grouped by their position in the text.
    lab_sets = [list(m.groups()) for m in _LAB_COMPACT.finditer(clean)]
    labelled = sorted((m.start(), key, m.group(1)) for key, pattern in _LABELLED.items() for m in pattern.finditer(clean))
    groups, incomplete, current = [], [], {}
    for _, key, value in labelled:
        if key in current:
            incomplete.append(current)
            current = {}
        current[key] = value
        if len(current) == 3:
            groups.append(current)
            current = {}
    if current:
        incomplete.append(current)
    for group in incomplete:
        fail("Coordonnées L*, a*, b* incomplètes : {v0} (les trois sont requises).",
                                                 v0=" ".join(f"{k}* {group[k]}" for k in ("L", "a", "b") if k in group))
        result["needs_decision"] = True
    lab_sets += [[g["L"], g["a"], g["b"]] for g in groups]
    for groups_ in lab_sets:
        try:
            components = {k: cm.parse_decimal(g) for k, g in zip(("L", "a", "b"), groups_)}
            if not 0 <= components["L"] <= 100:
                raise MeasurementError("L* doit être compris entre 0 et 100.")
        except MeasurementError as exc:
            fail("Lab ignoré ({v0})", v0=exc)
            continue
        result["candidates"].append({"space": "CIELAB", "components": components,
                                     "lexemes": dict(zip(("L", "a", "b"), groups_)), "label": "Lab"})
    # Conditions: only explicit tokens. Several different tokens are an ambiguity.
    illuminants = {m.group(1).upper() for m in _ILLUMINANT.finditer(clean)}
    observers = {int(m.group(1)) for m in _OBSERVER.finditer(clean)}
    for match in _OBSERVER_SIGNED.finditer(clean):
        fail("Observateur « {v0} » refusé : notations admises 2°, 10°.", v0=match.group(0).strip())
        result["needs_decision"] = True
    if len(illuminants) == 1:
        token = illuminants.pop()
        result["conditions"]["illuminant"] = token if token in ("D50", "D65") else "other"
        if result["conditions"]["illuminant"] == "other":
            result["conditions"]["illuminant_note"] = token
    elif len(illuminants) > 1:
        fail("Plusieurs illuminants mentionnés : {v0}", v0=", ".join(sorted(illuminants)))
        result["needs_decision"] = True
    if len(observers) == 1:
        result["conditions"]["observer"] = observers.pop()
    elif len(observers) > 1:
        fail("Plusieurs observateurs mentionnés : {v0}", v0=", ".join(f"{o}°" for o in sorted(observers)))
        result["needs_decision"] = True
    # Unlabelled numbers are never coordinates.
    stripped = clean
    for pattern in (_HEX, _RGB, _LAB_COMPACT, *_LABELLED.values(), _ILLUMINANT, _OBSERVER, _OBSERVER_SIGNED):
        stripped = pattern.sub(" ", stripped)
    result["unlabelled_numbers"] = len(re.findall(_NUM, stripped))
    if _LAB_WORD.search(clean) and not any(c["space"] == "CIELAB" for c in result["candidates"]) \
            and result["unlabelled_numbers"] >= 3:
        fail("Le mot « Lab » apparaît mais les coordonnées ne sont pas étiquetées L*, a*, b*.")
    # Consistency between HEX and RGB (only these two can be compared without conditions).
    hexes = [c["components"]["hex"] for c in result["candidates"] if c["space"] == "sRGB_HEX"]
    rgbs = [f"{c['components']['r']:02X}{c['components']['g']:02X}{c['components']['b']:02X}"
            for c in result["candidates"] if c["space"] == "sRGB_RGB8"]
    if hexes and rgbs:
        result["consistent"] = set(hexes) == set(rgbs)
        if not result["consistent"]:
            fail("HEX et RGB ne correspondent pas : choisissez le jeu principal.")
    if len(result["candidates"]) > 1:
        result["needs_decision"] = True
    if not result["candidates"] and not result["errors"]:
        fail("Aucune valeur étiquetée reconnue (HEX, RGB ou L*/a*/b*).")
    return result


def error_messages(result: dict, translate=None) -> list[str]:
    """Readable (optionally translated) texts of a proposal's errors."""
    return [cm.error_text(e, translate) for e in result["error_items"]]


def candidate_to_original(candidate: dict, alternatives=(), conditions=None) -> dict:
    """Validated ``original`` block for a chosen paste candidate, keeping the others.

    ``conditions`` (the context recognised in the text, as confirmed by the
    user) is attached to every alternative so that nothing recognised is lost
    whichever set becomes the principal one.
    """
    context = cm.validate_conditions(conditions) if conditions else None
    original = {"space": candidate["space"], "components": candidate["components"], "lexemes": candidate["lexemes"],
                "alternatives": [dict({"space": c["space"], "components": c["components"], "lexemes": c["lexemes"]},
                                      **({"conditions": context} if context else {}))
                                 for c in alternatives if c is not candidate]}
    return cm.validate_original(original)


# ── CSV / TSV ─────────────────────────────────────────────────────────────
def read_local_file(path: str | os.PathLike, limit: int | None = None) -> bytes:
    """Bytes of a chosen file, read only when its size is within the bound (checked before and during the read)."""
    limit = LIMITS["file_bytes"] if limit is None else limit
    size = os.stat(path).st_size
    if size > limit:
        raise MeasurementError("Fichier trop volumineux (maximum {v0} Mio).", v0=limit // (1024 * 1024))
    with open(path, "rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise MeasurementError("Fichier trop volumineux (maximum {v0} Mio).", v0=limit // (1024 * 1024))
    return data


def decode_text(data: bytes, encoding: str | None = None) -> tuple[str, str]:
    """UTF-8 (with or without BOM) by default; another listed encoding only when asked.

    Returns ``(text, encoding_used)``; raises MeasurementError (a ValueError)
    so the caller can ask for an explicit choice. No replacement characters
    are ever introduced.
    """
    if len(data) > LIMITS["file_bytes"]:
        raise MeasurementError("Fichier trop volumineux (maximum {v0} Mio).", v0=LIMITS["file_bytes"] // (1024 * 1024))
    if encoding is None or encoding == "utf-8":
        if data.startswith(b"\xef\xbb\xbf"):
            return data[3:].decode("utf-8"), "utf-8-sig"
        try:
            return data.decode("utf-8"), "utf-8"
        except UnicodeDecodeError as exc:
            raise MeasurementError("Le fichier n'est pas en UTF-8 : choisissez explicitement un encodage (CP1252 ou Latin-1).") from exc
    if encoding not in ENCODINGS:
        raise MeasurementError("Encodage non pris en charge : {v0}.", v0=encoding)
    return data.decode(encoding), encoding


def guess_delimiters(text: str) -> list[str]:
    """Candidate delimiters, most frequent in the first lines first; ties stay visible."""
    sample = "\n".join(text.splitlines()[:20])
    counts = {d: sample.count(d) for d in DELIMITERS}
    ranked = [d for d, n in sorted(counts.items(), key=lambda item: -item[1]) if n > 0]
    return ranked or [","]


def _reader(text: str, delimiter: str):
    return csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, quotechar='"', strict=True)


def read_records(text: str, delimiter: str) -> list[list[str]]:
    """All logical records (quoted fields, CRLF and embedded newlines supported), bounded."""
    records = []
    try:
        for row in _reader(text, delimiter):
            if len(records) >= LIMITS["records"] + 1:
                raise MeasurementError("Plus de {v0} enregistrements : fichier refusé.", v0=LIMITS["records"])
            if len(row) > LIMITS["columns"]:
                raise MeasurementError("Plus de {v0} colonnes : fichier refusé.", v0=LIMITS["columns"])
            if any(len(cell) > LIMITS["cell"] for cell in row):
                raise MeasurementError("Cellule de plus de {v0} caractères : fichier refusé.", v0=LIMITS["cell"])
            records.append(row)
    except csv.Error as exc:
        raise MeasurementError("CSV illisible : {v0}", v0=exc) from exc
    return records


def preview_csv(data: bytes, *, encoding: str | None = None, delimiter: str | None = None) -> dict:
    """Decode, split and show the header and first five records.

    Separator and decimal mark are proposals the user confirms; ``ambiguous``
    says whether several separators are plausible.
    """
    text, used = decode_text(data, encoding)
    candidates = guess_delimiters(text)
    chosen = delimiter or candidates[0]
    if chosen not in DELIMITERS:
        raise MeasurementError("Séparateur inconnu.")
    records = read_records(text, chosen)
    if not records:
        raise MeasurementError("Fichier vide.")
    header = [cell.strip() for cell in records[0]]
    body = records[1:]
    return {"encoding": used, "delimiter": chosen, "delimiter_candidates": candidates,
            "ambiguous": len(candidates) > 1 and text.count(candidates[0]) == text.count(candidates[1]) if len(candidates) > 1 else False,
            "header": header, "preview": body[:5], "records": len(body), "file_sha256": hashlib.sha256(data).hexdigest()}


def _alias_key(label: str) -> str | None:
    key = re.sub(r"\s+", " ", label.strip().casefold()).replace("*", "")
    key = key.strip()
    return _ALIAS_INDEX.get(key) or _ALIAS_INDEX.get(key.replace(" ", "_")) or _ALIAS_INDEX.get(key.replace("_", " "))


def propose_mapping(header: list[str]) -> dict:
    """Column-index proposals per role. Duplicates are listed, never silently resolved.

    ``mapping`` holds a single index only when exactly one column matches; a
    role with several matching columns goes to ``duplicates`` and stays unmapped.
    """
    matches: dict[str, list[int]] = {}
    for index, label in enumerate(header):
        key = _alias_key(label)
        if key is None:
            continue
        if key == "bl":
            key = "b_rgb"
        matches.setdefault(key, []).append(index)
    # A bare "b" column is ambiguous between Lab b* and RGB blue when R/G exist.
    if "b" in matches and "r" in matches and "g" in matches and "L" not in matches and "a" not in matches:
        matches["b_rgb"] = matches.pop("b")
    mapping, duplicates = {}, {}
    for key, indices in matches.items():
        if len(indices) == 1:
            mapping[key] = indices[0]
        else:
            duplicates[key] = indices
    unmapped = [i for i in range(len(header)) if i not in mapping.values()]
    return {"mapping": mapping, "duplicates": duplicates, "unmapped": unmapped}


def mapped_spaces(mapping: dict) -> list[str]:
    """Colour spaces fully mapped (in a fixed display order); several mean the user must choose the principal."""
    spaces = []
    if all(mapping.get(k) is not None for k in ("L", "a", "b")):
        spaces.append("CIELAB")
    if mapping.get("hex") is not None:
        spaces.append("sRGB_HEX")
    if all(mapping.get(k) is not None for k in ("r", "g", "b_rgb")):
        spaces.append("sRGB_RGB8")
    return spaces


def validate_rows(records: list[list[str]], mapping: dict, *, decimal: str = ".", file_name: str | None = None,
                  file_sha256: str | None = None, default_conditions: dict | None = None, name_prefix: str = "",
                  principal: str | None = None) -> dict:
    """Turn logical records into measurement drafts; every record is checked.

    ``mapping``: role -> column index (as confirmed by the user). ``decimal``
    is the confirmed decimal mark, independent of the CSV separator. When the
    mapping covers several colour spaces, ``principal`` (``CIELAB``,
    ``sRGB_HEX`` or ``sRGB_RGB8``) must name the user's choice: the other
    spaces are kept as alternatives and their inconsistencies are listed in
    ``warnings``. Returns ``valid`` (list of ``{"record", "measurement"}``),
    ``errors`` (``[(record_number, message)]``), ``warnings`` (same shape) and
    ``duplicates`` (digest collisions inside the batch). Nothing is
    deduplicated or linked.
    """
    if decimal not in (".", ","):
        raise MeasurementError("Séparateur décimal : point ou virgule.")
    spaces = mapped_spaces(mapping)
    if len(spaces) > 1:
        if principal is None:
            raise MeasurementError("Plusieurs jeux de couleur sont mappés ({v0}) : choisissez le jeu principal.",
                                   v0=", ".join(SPACE_LABELS[s] for s in spaces))
        if principal not in spaces:
            raise MeasurementError("Jeu principal « {v0} » absent des colonnes mappées.", v0=SPACE_LABELS.get(principal, principal))
    elif spaces:
        principal = spaces[0]
    valid, errors, warnings, error_items, warning_items = [], [], [], [], []
    seen_digests: dict[str, int] = {}
    duplicates = []
    conditions_default = cm.validate_conditions(default_conditions or {})

    def cell(row, key):
        index = mapping.get(key)
        if index is None or index >= len(row):
            return None
        value = row[index].replace("\r\n", "\n").replace("\r", "\n").strip()
        return value or None

    def number(text):
        if text is None:
            raise MeasurementError("valeur manquante")
        if decimal == "," and "." in text:
            raise MeasurementError("« {v0} » utilise un point alors que la virgule décimale est confirmée", v0=text)
        if decimal == "." and "," in text:
            raise MeasurementError("« {v0} » utilise une virgule alors que le point décimal est confirmé", v0=text)
        return cm.parse_decimal(text)

    def read_space(row, space):
        if space == "CIELAB":
            lexemes = {k: cell(row, k) for k in ("L", "a", "b")}
            components = {k: number(lexemes[k]) for k in ("L", "a", "b")}
            return cm.validate_original({"space": "CIELAB", "components": components, "lexemes": {k: v for k, v in lexemes.items() if v}})
        if space == "sRGB_HEX":
            text = cell(row, "hex")
            return cm.validate_original({"space": "sRGB_HEX", "components": {"hex": text}, "lexemes": {"hex": text or ""}})
        lexemes = {k: cell(row, src) for k, src in (("r", "r"), ("g", "g"), ("b", "b_rgb"))}
        components = {}
        for k, text in lexemes.items():
            if text is None or not re.fullmatch(r"\d{1,3}", text):
                raise MeasurementError("canal {v0} : entier 0–255 requis", v0=k.upper())
            components[k] = int(text)
        return cm.validate_original({"space": "sRGB_RGB8", "components": components, "lexemes": lexemes})

    for number_of_record, row in enumerate(records, start=1):
        if not any(c.strip() for c in row):
            continue  # blank record
        try:
            if principal is None:
                raise MeasurementError("colonnes de couleur non mappées (L*/a*/b*, HEX ou R/G/B)")
            original = read_space(row, principal)
            original["alternatives"] = []
            for space in spaces:
                if space == principal:
                    continue
                try:
                    other = read_space(row, space)
                except MeasurementError as exc:
                    warning = MeasurementError("jeu {v0} ignoré : {v1}", v0=SPACE_LABELS[space], v1=exc)
                    warnings.append((number_of_record, str(warning))); warning_items.append((number_of_record, warning))
                    continue
                other.pop("alternatives", None); other.pop("raw_text", None)
                original["alternatives"].append(other)
            srgb = {s: h for s, h in ((o["space"], cm.hex_of({"original": o})) for o in [original, *original["alternatives"]]) if h}
            if len(set(srgb.values())) > 1:
                warning = MeasurementError("HEX et RGB diffèrent ({v0}) ; le jeu principal {v1} est conservé, l’autre reste en alternative.",
                                           v0=", ".join(f"{SPACE_LABELS[s]} #{h}" for s, h in srgb.items()), v1=SPACE_LABELS[principal])
                warnings.append((number_of_record, str(warning))); warning_items.append((number_of_record, warning))
            conditions = dict(conditions_default)
            illuminant = cell(row, "illuminant")
            if illuminant:
                token = illuminant.strip().upper()
                if token in ("D50", "D65"):
                    conditions["illuminant"] = token
                else:
                    conditions["illuminant"], conditions["illuminant_note"] = "other", illuminant.strip()[:LIMITS["short"]]
            observer = cell(row, "observer")
            if observer:
                match = _OBSERVER_CELL.match(observer)
                if match is None:
                    raise MeasurementError("observateur inconnu : « {v0} » (notations admises : 2, 2°, 10, 10°)", v0=observer)
                conditions["observer"] = int(match.group(1))
            for key in ("geometry", "specular", "aperture"):
                if cell(row, key):
                    conditions[key] = cell(row, key)
            name = cell(row, "name") or f"{name_prefix}{number_of_record}"
            provenance = {"method": "csv", "file_name": file_name, "file_sha256": file_sha256, "record_number": number_of_record,
                          "device_manufacturer": cell(row, "manufacturer"), "device_model": cell(row, "device"), "operator_note": cell(row, "note")}
            sample = {"type": "unknown"}
            for key in ("material", "finish", "thickness", "backing"):
                if cell(row, key):
                    sample[key] = cell(row, key)
            measurement = cm.new_measurement(original, name=name[:LIMITS["name"]], conditions=conditions,
                                             provenance=provenance, sample=sample, measured_at=cell(row, "date"))
        except (MeasurementError, ValueError) as exc:
            errors.append((number_of_record, str(exc))); error_items.append((number_of_record, exc))
            continue
        digest = measurement["content_digest"]
        if digest in seen_digests:
            duplicates.append((number_of_record, seen_digests[digest]))
        else:
            seen_digests[digest] = number_of_record
        valid.append({"record": number_of_record, "measurement": measurement})
    return {"valid": valid, "errors": errors, "warnings": warnings, "error_items": error_items, "warning_items": warning_items,
            "duplicates": duplicates, "total": len(valid) + len(errors), "principal": principal, "spaces": spaces}


def registry_duplicates(drafts, registry_measurements: dict) -> dict:
    """Existing measurements sharing a digest or the same file/record (information only)."""
    by_digest, by_file = {}, {}
    for key, existing in registry_measurements.items():
        by_digest.setdefault(existing.get("content_digest"), []).append(key)
        prov = existing.get("provenance") or {}
        if prov.get("file_sha256") and prov.get("record_number"):
            by_file.setdefault((prov["file_sha256"], prov["record_number"]), []).append(key)
    report = {"similar": {}, "reimported": {}}
    for draft in drafts:
        m = draft["measurement"] if isinstance(draft, dict) and "measurement" in draft else draft
        same = by_digest.get(m.get("content_digest"))
        if same:
            report["similar"][m["content_digest"]] = same
        prov = m.get("provenance") or {}
        key = (prov.get("file_sha256"), prov.get("record_number"))
        if key[0] and key[1] and key in by_file:
            report["reimported"][key] = by_file[key]
    return report

"""Colour measurements: model, validation, manual parsing, comparison policy.

Pure functions, no Qt, no I/O. A measurement keeps the user's original values
(components, lexemes and source text) and documented conditions; nothing is
inferred. P1 formats: ``sRGB_HEX``, ``sRGB_RGB8`` and ``CIELAB``.

A *catalogue* colour is a declared HEX, not a physical measurement. Comparing a
measurement to the catalogue therefore never yields more than an *indicative*
proximity; see :func:`comparison_policy`.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import re
import uuid

from . import colour_distance

SCHEMA = "spoolscribe-colour-measurements"
VERSION = 1
ID_PREFIX = "MEAS-"

SPACES = ("sRGB_HEX", "sRGB_RGB8", "CIELAB")
ROLES = ("target", "filament_sample")
SAMPLE_TYPES = ("raw_filament", "printed_sample", "painted_surface", "object", "other", "unknown")
METHODS = ("manual", "paste", "csv")
ILLUMINANTS = ("D65", "D50", "other")   # None = unknown
OBSERVERS = (2, 10)                     # None = unknown

# Software protection bounds (not scientific limits); shared with the importer.
LIMITS = {
    "name": 120, "short": 256, "note": 4096, "lexeme": 64, "paste_bytes": 64 * 1024,
    "file_bytes": 10 * 1024 * 1024, "records": 10_000, "columns": 64, "cell": 4096,
    "registry_bytes": 20 * 1024 * 1024, "registry_count": 10_000,
}
# Beyond this magnitude CIEDE2000's seventh powers overflow a double; such a
# value stays storable but is never ranked.
COMPUTABLE_MAGNITUDE = 1e40

_CONDITION_KEYS = ("illuminant", "illuminant_note", "observer", "geometry", "specular", "aperture", "calibration", "profile_note")
_PROVENANCE_KEYS = ("method", "device_manufacturer", "device_model", "source_app", "operator_note", "file_name", "file_sha256", "record_number")
_SAMPLE_KEYS = ("type", "material", "finish", "thickness", "backing", "surface_note")
_SHORT_TEXT = {"illuminant_note", "geometry", "specular", "aperture", "calibration", "profile_note",
               "device_manufacturer", "device_model", "source_app", "file_name", "material", "finish",
               "thickness", "backing"}
_NOTE_TEXT = {"operator_note", "surface_note"}

_NUMBER = re.compile(r"^[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][+-]?\d+)?$")


class MeasurementError(ValueError):
    """Invalid measurement data.

    ``template`` is the French source text and ``values`` its named parameters,
    so a caller can translate the message (``tr(template, **values)``) instead
    of looking up a sentence already concatenated with variable values.
    """

    def __init__(self, template: str, **values):
        super().__init__(template.format(**values) if values else template)
        self.template, self.values = template, values


def error_text(exc, translate=None) -> str:
    """Readable text of any error; ``translate(template, **values)`` is used when the error carries a template.

    Values that are themselves errors (a document error wrapping a validation
    error) are translated recursively.
    """
    template, values = getattr(exc, "template", None), getattr(exc, "values", None) or {}
    if template and translate is not None:
        return translate(template, **{k: (error_text(v, translate) if isinstance(v, BaseException) else v) for k, v in values.items()})
    return str(exc)


# ── helpers ──────────────────────────────────────────────────────────────
def new_id() -> str:
    return ID_PREFIX + str(uuid.uuid4())


def now_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_decimal(text) -> float:
    """One decimal number; '.' or ',' as decimal mark, never as a thousands separator.

    Mixed marks (``1.234,5``), several marks, spaces inside, or anything else
    than a plain number is refused rather than guessed.
    """
    if isinstance(text, bool):
        raise MeasurementError("Nombre attendu, pas un booléen.")
    if isinstance(text, (int, float)):
        value = float(text)
    else:
        if not isinstance(text, str):
            raise MeasurementError("Nombre attendu.")
        lexeme = text.strip()
        if not lexeme or len(lexeme) > LIMITS["lexeme"]:
            raise MeasurementError("Nombre manquant ou trop long.")
        if lexeme.count(",") + lexeme.count(".") > 1:
            raise MeasurementError("Syntaxe numérique ambiguë : « {v0} ».", v0=lexeme)
        if not _NUMBER.match(lexeme):
            raise MeasurementError("Nombre invalide : « {v0} ».", v0=lexeme)
        try:
            value = float(lexeme.replace(",", "."))
        except ValueError as exc:
            raise MeasurementError("Nombre invalide : « {v0} ».", v0=lexeme) from exc
    if not math.isfinite(value):
        raise MeasurementError("Nombre fini requis (NaN et infini refusés).")
    return value


def _text(value, limit, field):
    if value is None:
        return None
    if not isinstance(value, str):
        raise MeasurementError("{v0} : texte attendu.", v0=field)
    if len(value) > limit:
        raise MeasurementError("{v0} : {v1} caractères maximum.", v0=field, v1=limit)
    if any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise MeasurementError("{v0} : caractères de contrôle refusés.", v0=field)
    return value


def _number_components(components, keys):
    out = {}
    for key in keys:
        if key not in components:
            raise MeasurementError("Composante {v0} manquante.", v0=key)
        value = components[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise MeasurementError("Composante {v0} : nombre fini requis.", v0=key)
        out[key] = value
    return out


def validate_original(original: dict) -> dict:
    """Return a normalised copy of the ``original`` block or raise MeasurementError."""
    if not isinstance(original, dict):
        raise MeasurementError("Bloc « original » invalide.")
    space = original.get("space")
    if space not in SPACES:
        raise MeasurementError("Espace colorimétrique non pris en charge : {v0}.", v0=repr(space))
    components = original.get("components")
    if not isinstance(components, dict):
        raise MeasurementError("Composantes manquantes.")
    if space == "sRGB_HEX":
        hex_value = colour_distance.parse_hex(components.get("hex"))
        if hex_value is None:
            raise MeasurementError("HEX sRGB : six chiffres hexadécimaux requis.")
        clean = {"hex": hex_value}
    elif space == "sRGB_RGB8":
        clean = {}
        for key in ("r", "g", "b"):
            value = components.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 255:
                raise MeasurementError("Canal {v0} : entier entre 0 et 255 requis.", v0=key.upper())
            clean[key] = value
    else:
        clean = _number_components(components, ("L", "a", "b"))
        if not 0 <= clean["L"] <= 100:
            raise MeasurementError("L* doit être compris entre 0 et 100.")
    lexemes = original.get("lexemes") or {}
    if not isinstance(lexemes, dict):
        raise MeasurementError("Lexèmes invalides.")
    clean_lexemes = {}
    for key, value in lexemes.items():
        if key not in clean:
            raise MeasurementError("Lexème inconnu : {v0}.", v0=key)
        clean_lexemes[key] = _text(value, LIMITS["lexeme"], "Lexème")
    raw_text = _text(original.get("raw_text"), LIMITS["paste_bytes"], "Texte d'origine")
    alternatives = original.get("alternatives") or []
    if not isinstance(alternatives, list) or len(alternatives) > 16:
        raise MeasurementError("Alternatives invalides.")
    clean_alternatives = []
    for alternative in alternatives:
        if not isinstance(alternative, dict):
            raise MeasurementError("Alternative invalide.")
        inner = validate_original({k: v for k, v in alternative.items() if k != "conditions"} | {"alternatives": []})
        inner.pop("alternatives")
        if alternative.get("conditions") is not None:
            inner["conditions"] = validate_conditions(alternative["conditions"])
        clean_alternatives.append(inner)
    return {"space": space, "components": clean, "lexemes": clean_lexemes, "raw_text": raw_text, "alternatives": clean_alternatives}


def validate_conditions(conditions) -> dict:
    if conditions is None:
        conditions = {}
    if not isinstance(conditions, dict):
        raise MeasurementError("Conditions de mesure invalides.")
    unknown = set(conditions) - set(_CONDITION_KEYS)
    if unknown:
        raise MeasurementError("Condition inconnue : {v0}.", v0=sorted(unknown)[0])
    out = {key: None for key in _CONDITION_KEYS}
    illuminant = conditions.get("illuminant")
    if illuminant is not None and illuminant not in ILLUMINANTS:
        raise MeasurementError("Illuminant : D65, D50, « other » ou inconnu.")
    out["illuminant"] = illuminant
    observer = conditions.get("observer")
    if observer is not None and (isinstance(observer, bool) or observer not in OBSERVERS):
        raise MeasurementError("Observateur : 2°, 10° ou inconnu.")
    out["observer"] = observer
    for key in _CONDITION_KEYS[1:2] + _CONDITION_KEYS[3:]:
        out[key] = _text(conditions.get(key), LIMITS["short"], key)
    if illuminant == "other" and not out["illuminant_note"]:
        raise MeasurementError("Un illuminant « autre » doit être décrit.")
    return out


def validate_measurement(measurement: dict) -> dict:
    """Return a normalised deep copy of one measurement or raise MeasurementError."""
    if not isinstance(measurement, dict):
        raise MeasurementError("Mesure invalide.")
    out = {}
    name = measurement.get("name")
    if not isinstance(name, str) or not name.strip():
        raise MeasurementError("Nom de mesure requis.")
    out["name"] = _text(name.strip(), LIMITS["name"], "Nom")
    role = measurement.get("role", "target")
    if role not in ROLES:
        raise MeasurementError("Rôle : cible ou échantillon de filament.")
    out["role"] = role
    created = measurement.get("created_at")
    if not isinstance(created, str) or not created:
        raise MeasurementError("Horodatage de création manquant.")
    try:
        _dt.datetime.fromisoformat(created.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MeasurementError("Horodatage de création invalide.") from exc
    out["created_at"] = created
    out["measured_at"] = _text(measurement.get("measured_at"), LIMITS["short"], "Date de mesure")
    out["original"] = validate_original(measurement.get("original"))
    out["conditions"] = validate_conditions(measurement.get("conditions"))
    provenance = measurement.get("provenance") or {}
    if not isinstance(provenance, dict) or set(provenance) - set(_PROVENANCE_KEYS):
        raise MeasurementError("Provenance invalide.")
    method = provenance.get("method", "manual")
    if method not in METHODS:
        raise MeasurementError("Méthode : manual, paste ou csv.")
    clean_provenance = {"method": method}
    for key in _PROVENANCE_KEYS[1:]:
        value = provenance.get(key)
        if key == "record_number":
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 1):
                raise MeasurementError("Numéro d'enregistrement invalide.")
            clean_provenance[key] = value
        elif key == "file_sha256":
            if value is not None and (not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)):
                raise MeasurementError("Empreinte de fichier invalide.")
            clean_provenance[key] = value
        else:
            clean_provenance[key] = _text(value, LIMITS["note"] if key in _NOTE_TEXT else LIMITS["short"], key)
    out["provenance"] = clean_provenance
    sample = measurement.get("sample") or {}
    if not isinstance(sample, dict) or set(sample) - set(_SAMPLE_KEYS):
        raise MeasurementError("Échantillon invalide.")
    sample_type = sample.get("type", "unknown")
    if sample_type not in SAMPLE_TYPES:
        raise MeasurementError("Type d'échantillon inconnu.")
    clean_sample = {"type": sample_type}
    for key in _SAMPLE_KEYS[1:]:
        clean_sample[key] = _text(sample.get(key), LIMITS["note"] if key in _NOTE_TEXT else LIMITS["short"], key)
    out["sample"] = clean_sample
    association = measurement.get("association")
    if association is not None:
        if not isinstance(association, dict) or set(association) != {"sku"} or not isinstance(association["sku"], str) \
                or not association["sku"].strip() or len(association["sku"]) > LIMITS["short"]:
            raise MeasurementError("Association invalide : un SKU exact est requis.")
        association = {"sku": association["sku"]}
    out["association"] = association
    out["content_digest"] = content_digest(out)
    return out


def validate_registry(document) -> dict:
    """Return a normalised deep copy of a registry document or raise MeasurementError."""
    if not isinstance(document, dict):
        raise MeasurementError("Registre invalide : objet JSON attendu.")
    if document.get("schema") != SCHEMA:
        raise MeasurementError("Registre : schéma inconnu.")
    if document.get("version") != VERSION or isinstance(document.get("version"), bool):
        raise MeasurementError("Registre : version {v0} non prise en charge.", v0=repr(document.get('version')))
    measurements = document.get("measurements", {})
    if not isinstance(measurements, dict):
        raise MeasurementError("Registre : mesures invalides.")
    if len(measurements) > LIMITS["registry_count"]:
        raise MeasurementError("Registre : plus de {v0} mesures.", v0=LIMITS['registry_count'])
    clean = {}
    for key, value in measurements.items():
        if not isinstance(key, str) or not key.startswith(ID_PREFIX):
            raise MeasurementError("Identifiant de mesure invalide : {v0}.", v0=repr(key))
        try:
            uuid.UUID(key[len(ID_PREFIX):])
        except ValueError as exc:
            raise MeasurementError("Identifiant de mesure invalide : {v0}.", v0=repr(key)) from exc
        clean[key] = validate_measurement(value)
    return {"schema": SCHEMA, "version": VERSION, "measurements": clean}


def empty_registry() -> dict:
    return {"schema": SCHEMA, "version": VERSION, "measurements": {}}


# ── values for display and comparison ─────────────────────────────────────
def hex_of(measurement: dict) -> str | None:
    """Normalised HEX for sRGB originals (lossless from RGB8); None for Lab."""
    original = measurement["original"]
    if original["space"] == "sRGB_HEX":
        return original["components"]["hex"]
    if original["space"] == "sRGB_RGB8":
        c = original["components"]
        return f"{c['r']:02X}{c['g']:02X}{c['b']:02X}"
    return None


def lab_of(measurement: dict) -> tuple[float, float, float] | None:
    original = measurement["original"]
    if original["space"] != "CIELAB":
        return None
    c = original["components"]
    return (float(c["L"]), float(c["a"]), float(c["b"]))


def computable(measurement: dict) -> bool:
    """False when a finite but huge coordinate would overflow the ΔE arithmetic."""
    lab = lab_of(measurement)
    return lab is None or all(abs(v) <= COMPUTABLE_MAGNITUDE for v in lab)


def content_digest(measurement: dict) -> str:
    """Digest of normalised values and conditions; flags similar acquisitions, proves nothing."""
    original = measurement["original"]
    components = {k: (round(v, 6) if isinstance(v, float) else v) for k, v in original["components"].items()}
    conditions = measurement.get("conditions") or {}
    payload = {"space": original["space"], "components": components,
               "illuminant": conditions.get("illuminant"), "observer": conditions.get("observer"),
               "geometry": conditions.get("geometry"), "specular": conditions.get("specular")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


# ── manual entry ──────────────────────────────────────────────────────────
def parse_manual(space: str, fields: dict) -> dict:
    """Build the ``original`` block from text fields; nothing is inferred.

    ``fields``: ``{"hex": "#74CABF"}``, ``{"r": "116", "g": "202", "b": "191"}``
    or ``{"L": "73,2", "a": "-25,6", "b": "-12,4"}``.
    """
    if space not in SPACES:
        raise MeasurementError("Espace colorimétrique non pris en charge : {v0}.", v0=repr(space))
    fields = {k: (v.strip() if isinstance(v, str) else v) for k, v in (fields or {}).items()}
    if space == "sRGB_HEX":
        text = fields.get("hex")
        if not isinstance(text, str):
            raise MeasurementError("Code HEX manquant.")
        hex_value = colour_distance.parse_hex(text)
        if hex_value is None:
            raise MeasurementError("HEX sRGB : six chiffres hexadécimaux requis (ex. #74CABF).")
        return validate_original({"space": space, "components": {"hex": hex_value}, "lexemes": {"hex": text[:LIMITS["lexeme"]]}})
    if space == "sRGB_RGB8":
        components, lexemes = {}, {}
        for key in ("r", "g", "b"):
            text = fields.get(key)
            if not isinstance(text, str) or not re.fullmatch(r"[+-]?\d{1,3}", text):
                raise MeasurementError("Canal {v0} : entier entre 0 et 255 requis.", v0=key.upper())
            value = int(text)
            if not 0 <= value <= 255:
                raise MeasurementError("Canal {v0} : entier entre 0 et 255 requis.", v0=key.upper())
            components[key] = value
            lexemes[key] = text
        return validate_original({"space": space, "components": components, "lexemes": lexemes})
    components, lexemes = {}, {}
    for key in ("L", "a", "b"):
        text = fields.get(key)
        if not isinstance(text, str) or not text:
            raise MeasurementError("Composante {v0}* manquante.", v0=key)
        components[key] = parse_decimal(text)
        lexemes[key] = text
    return validate_original({"space": space, "components": components, "lexemes": lexemes})


def new_measurement(original: dict, *, name: str, role: str = "target", conditions=None, provenance=None,
                    sample=None, measured_at=None, association=None, created_at=None) -> dict:
    """Assemble and validate a measurement; ``created_at`` defaults to now (UTC)."""
    return validate_measurement({
        "name": name, "role": role, "created_at": created_at or now_utc(), "measured_at": measured_at,
        "original": original, "conditions": conditions or {}, "provenance": provenance or {"method": "manual"},
        "sample": sample or {"type": "unknown"}, "association": association,
    })


# ── comparison policies ───────────────────────────────────────────────────
DERIVED_BASIS = "sRGB → CIELAB D65/2° (conversion du moteur, pas une condition mesurée)"
CATALOGUE_BASIS = "HEX déclarés du catalogue, convertis en CIELAB D65/2°"


def comparison_policy(measurement: dict) -> dict:
    """Can this measurement be ranked against the catalogue's declared HEX colours?

    Returns ``level`` (``indicative`` or ``blocked``), a structured ``reason``
    code, and the ``reference`` actually used. Against the catalogue the level
    is never ``comparable``: the candidates are declared screen colours.
    """
    original = measurement["original"]
    conditions = measurement.get("conditions") or {}
    if original["space"] in ("sRGB_HEX", "sRGB_RGB8"):
        return {"level": "indicative", "reason": "srgb_declared", "reference": DERIVED_BASIS,
                "candidates": CATALOGUE_BASIS}
    illuminant, observer = conditions.get("illuminant"), conditions.get("observer")
    if illuminant is None or observer is None:
        return {"level": "blocked", "reason": "conditions_unknown", "reference": None, "candidates": CATALOGUE_BASIS}
    if illuminant == "D50":
        return {"level": "blocked", "reason": "adaptation_unavailable", "reference": None, "candidates": CATALOGUE_BASIS}
    if illuminant != "D65":
        return {"level": "blocked", "reason": "illuminant_unsupported", "reference": None, "candidates": CATALOGUE_BASIS}
    if observer != 2:
        return {"level": "blocked", "reason": "observer_unsupported", "reference": None, "candidates": CATALOGUE_BASIS}
    if not computable(measurement):
        return {"level": "blocked", "reason": "magnitude", "reference": None, "candidates": CATALOGUE_BASIS}
    return {"level": "indicative", "reason": "lab_d65_2", "reference": "CIELAB D65/2° (valeurs d'origine)",
            "candidates": CATALOGUE_BASIS}


_PAIR_FIELDS = ("illuminant", "observer", "geometry", "specular")
_PAIR_SAMPLE = ("type", "finish", "backing", "thickness")


def _same_text(a, b) -> bool:
    return str(a).strip().casefold() == str(b).strip().casefold()


def pair_policy(first: dict, second: dict) -> dict:
    """Comparability of two *physical* measurements (business rule only, no ranking screen in P1).

    ``comparable`` requires both to be CIELAB with documented and identical
    illuminant, observer, geometry, specular mode and instrument, and documented,
    identical sample preparation. Anything missing or different is
    ``insufficient``; sRGB values are ``blocked`` (not instrumental).

    An illuminant declared ``other`` is not an identity: both descriptions
    (``illuminant_note``) must exist and match textually. No equivalence between
    device names, illuminants or geometries is ever inferred.
    """
    if first["original"]["space"] != "CIELAB" or second["original"]["space"] != "CIELAB":
        return {"level": "blocked", "reason": "not_instrumental", "missing": [], "different": []}
    missing, different = [], []
    conditions_a, conditions_b = first.get("conditions") or {}, second.get("conditions") or {}
    for key in _PAIR_FIELDS:
        a, b = conditions_a.get(key), conditions_b.get(key)
        if a is None or b is None:
            missing.append(key)
            continue
        if not _same_text(a, b):
            different.append(key)
            continue
        if key == "illuminant" and a == "other":
            note_a, note_b = conditions_a.get("illuminant_note"), conditions_b.get("illuminant_note")
            if not note_a or not note_b:
                missing.append("illuminant_note")
            elif not _same_text(note_a, note_b):
                different.append("illuminant_note")
    for key in ("device_manufacturer", "device_model"):
        a, b = (first.get("provenance") or {}).get(key), (second.get("provenance") or {}).get(key)
        if a is None or b is None:
            missing.append(key)
        elif a.strip().casefold() != b.strip().casefold():
            different.append(key)
    for key in _PAIR_SAMPLE:
        a, b = (first.get("sample") or {}).get(key), (second.get("sample") or {}).get(key)
        if a in (None, "unknown") or b in (None, "unknown"):
            missing.append(key)
        elif str(a).strip().casefold() != str(b).strip().casefold():
            different.append(key)
    if not computable(first) or not computable(second):
        return {"level": "blocked", "reason": "magnitude", "missing": missing, "different": different}
    if missing or different:
        return {"level": "insufficient", "reason": "conditions", "missing": missing, "different": different}
    return {"level": "comparable", "reason": "same_documented_conditions", "missing": [], "different": []}


METHOD_LABELS = {"manual": "saisie manuelle", "paste": "texte collé", "csv": "fichier CSV/TSV"}
SPACE_LABELS = {"CIELAB": "Lab", "sRGB_HEX": "HEX", "sRGB_RGB8": "RGB"}


def _plain(template, **values):
    return template.format(**values) if values else template


def describe_space_conditions(space: str, conditions: dict | None, translate=None) -> str:
    """Short text of the conditions, built from separately translatable pieces.

    ``translate(template, **values)`` is applied to each piece, never to the
    composed sentence. For an sRGB value the declared context (if any) is shown
    as context: the comparison reference of sRGB is the derived basis, not a
    measured illuminant.
    """
    t = translate or _plain
    conditions = conditions or {}
    illuminant, observer = conditions.get("illuminant"), conditions.get("observer")
    if illuminant in ("D65", "D50"):
        light = illuminant
    elif illuminant == "other":
        light = t("autre éclairage : {v0}", v0=conditions.get("illuminant_note") or "?")
    else:
        light = t("éclairage inconnu")
    pieces = [light, t("{v0}°", v0=observer) if observer else t("observateur inconnu")]
    if space != "CIELAB":
        if illuminant is None and observer is None:
            return t("sRGB")
        return t("sRGB · contexte déclaré : {v0}", v0=" / ".join(pieces))
    return " / ".join(pieces)


def describe_conditions(measurement: dict, translate=None) -> str:
    """Short human text for the conditions (French source unless ``translate`` is given)."""
    return describe_space_conditions(measurement["original"]["space"], measurement.get("conditions"), translate)


def summary_values(measurement: dict) -> str:
    """Compact text of the original coordinates, e.g. ``L* 73,2 · a* -25,6 · b* -12,4``."""
    original = measurement["original"]
    lexemes = original.get("lexemes") or {}
    if original["space"] == "sRGB_HEX":
        return "#" + original["components"]["hex"]
    if original["space"] == "sRGB_RGB8":
        c = original["components"]
        return f"RGB {c['r']}, {c['g']}, {c['b']}"
    c = original["components"]
    return " · ".join(f"{label} {lexemes.get(key) or c[key]:g}" if not lexemes.get(key) else f"{label} {lexemes[key]}"
                      for key, label in (("L", "L*"), ("a", "a*"), ("b", "b*")))

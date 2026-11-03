"""Perceptual proximity of declared HEX colours (CIEDE2000), independent of Qt.

Conditions, stated once and applied everywhere:

* Input: a declared 8-bit sRGB HEX (IEC 61966-2-1). It describes how a source
  *displays* a filament, not a spectral measurement of a printed part.
* Decoding: the sRGB transfer function (linear segment below 0.04045).
* sRGB -> CIE XYZ: the matrix derived from the IEC 61966-2-1 primaries and the
  D65 white at seven decimals (the standard's four-decimal rounding would tint
  white by about 0.01). CIE 1931 2° observer.
* XYZ -> CIELAB: reference white D65 (Xn 0.95047, Yn 1.0, Zn 1.08883). No
  chromatic adaptation to D50 is applied: sRGB is defined for D65 and both
  colours of a comparison use the same white, which is what a distance needs.
* Distance: CIEDE2000 (Sharma, Wu, Dalal 2005) with kL = kC = kH = 1.

ΔE00 between two screen colours does not predict how two printed filaments
will look; gloss, translucency and effects (silk, glow, metallic) are outside
any HEX value.
"""
from __future__ import annotations

from functools import lru_cache
import math
import re

_HEX = re.compile(r"[0-9A-Fa-f]{6}")
_WHITE_D65 = (0.95047, 1.0, 1.08883)
_EPSILON = 216 / 24389
_KAPPA = 24389 / 27


def parse_hex(value) -> str | None:
    """Normalised ``RRGGBB`` or None; ``#`` is accepted, alpha is not."""
    if not isinstance(value, str):
        return None
    text = value.strip().removeprefix("#")
    return text.upper() if _HEX.fullmatch(text) else None


def _linear(channel: int) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def srgb_to_xyz(hex_value: str) -> tuple[float, float, float]:
    h = parse_hex(hex_value)
    if h is None:
        raise ValueError("HEX sRGB à six caractères requis.")
    r, g, b = (_linear(int(h[i:i + 2], 16)) for i in (0, 2, 4))
    return (0.4124564 * r + 0.3575761 * g + 0.1804375 * b,
            0.2126729 * r + 0.7151522 * g + 0.0721750 * b,
            0.0193339 * r + 0.1191920 * g + 0.9503041 * b)


def xyz_to_lab(xyz: tuple[float, float, float]) -> tuple[float, float, float]:
    def f(t):
        return t ** (1 / 3) if t > _EPSILON else (_KAPPA * t + 16) / 116
    fx, fy, fz = (f(v / w) for v, w in zip(xyz, _WHITE_D65))
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


@lru_cache(maxsize=65536)
def hex_to_lab(hex_value: str) -> tuple[float, float, float]:
    """CIELAB of a normalised HEX. Pure function: the cache never needs invalidation."""
    return xyz_to_lab(srgb_to_xyz(hex_value))


def ciede2000(lab1, lab2, kL: float = 1.0, kC: float = 1.0, kH: float = 1.0) -> float:
    """CIEDE2000 colour difference (Sharma, Wu, Dalal, 2005)."""
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    c_bar = (math.hypot(a1, b1) + math.hypot(a2, b2)) / 2
    g = 0.5 * (1 - math.sqrt(c_bar ** 7 / (c_bar ** 7 + 25 ** 7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360 if c1p else 0.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360 if c2p else 0.0
    d_lp = L2 - L1
    d_cp = c2p - c1p
    if c1p * c2p == 0:
        d_hp = 0.0
    elif abs(h2p - h1p) <= 180:
        d_hp = h2p - h1p
    elif h2p - h1p > 180:
        d_hp = h2p - h1p - 360
    else:
        d_hp = h2p - h1p + 360
    d_Hp = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(d_hp) / 2)
    l_bar = (L1 + L2) / 2
    c_bar_p = (c1p + c2p) / 2
    if c1p * c2p == 0:
        h_bar = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        h_bar = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        h_bar = (h1p + h2p + 360) / 2
    else:
        h_bar = (h1p + h2p - 360) / 2
    t = (1 - 0.17 * math.cos(math.radians(h_bar - 30)) + 0.24 * math.cos(math.radians(2 * h_bar))
         + 0.32 * math.cos(math.radians(3 * h_bar + 6)) - 0.20 * math.cos(math.radians(4 * h_bar - 63)))
    d_theta = 30 * math.exp(-(((h_bar - 275) / 25) ** 2))
    r_c = 2 * math.sqrt(c_bar_p ** 7 / (c_bar_p ** 7 + 25 ** 7))
    s_l = 1 + (0.015 * (l_bar - 50) ** 2) / math.sqrt(20 + (l_bar - 50) ** 2)
    s_c = 1 + 0.045 * c_bar_p
    s_h = 1 + 0.015 * c_bar_p * t
    r_t = -math.sin(math.radians(2 * d_theta)) * r_c
    return math.sqrt((d_lp / (kL * s_l)) ** 2 + (d_cp / (kC * s_c)) ** 2 + (d_Hp / (kH * s_h)) ** 2
                     + r_t * (d_cp / (kC * s_c)) * (d_Hp / (kH * s_h)))


def delta_e00(hex1: str, hex2: str) -> float:
    return ciede2000(hex_to_lab(parse_hex(hex1)), hex_to_lab(parse_hex(hex2)))


_EFFECT_WORDS = re.compile(r"\b(silk|glow|metallic|metal|sparkle|glitter|galaxy|marble|pearl|shimmer|"
                           r"soie|métallique|phosphorescent|paillet\w*)\b", re.I)
_TRANSLUCENT_WORDS = re.compile(r"\b(transparent|translucent|clear|translucide|cristal|crystal)\b", re.I)


def _multicolour(row: dict) -> bool:
    """Several declared colours: ``source_colors`` (as before) or ``additional_color_hexes``."""
    if len(row.get("source_colors") or []) > 1:
        return True
    main = parse_hex(row.get("hex"))
    extra = {parse_hex(c) for c in (row.get("additional_color_hexes") or [])} - {None, main}
    return bool(extra)


def classify(row: dict) -> str:
    """Ranking policy of one catalogue row: ``ranked``, ``effect`` or an exclusion.

    Exclusions are explicit and never replaced by a representative colour:
    unknown HEX, conflicting shades in a group, several declared colours, and
    translucent or transparent filaments. Effects stay ranked but are flagged.
    """
    if row.get("hex_variants", 0) > 1:
        return "conflict"
    if not parse_hex(row.get("hex")):
        return "unknown"
    # Any member of a displayed group, through either supported representation.
    if any(_multicolour(member) for member in [row, *(row.get("variants") or [])]):
        return "multicolour"
    traits = row.get("source_traits") or {}
    alpha = str(row.get("alpha") or "FF").upper()
    names = " ".join(str(row.get(k) or "") for k in ("color_name", "product", "material", "variant"))
    if (alpha != "FF" or any(traits.get(k) for k in ("transparent", "translucent"))
            or _TRANSLUCENT_WORDS.search(names)):
        return "translucent"
    if any(traits.get(k) for k in ("silk", "glow", "metallic", "sparkle", "glitter")) or _EFFECT_WORDS.search(names):
        return "effect"
    return "ranked"


def _tie_key(row: dict) -> tuple:
    return tuple(str(row.get(k) or "").casefold() for k in ("brand", "product", "color_name")) + (str(row.get("sku", "")),)


def build_index(rows) -> dict:
    """Per-row ranking facts computed once for a catalogue: id(row) -> (kind, hex, tie key).

    Valid only while the *same* row objects are alive; callers keep a reference
    to the indexed list and rebuild the index when the catalogue is replaced.
    """
    index = {}
    for row in rows:
        kind = classify(row)
        index[id(row)] = (kind, parse_hex(row.get("hex")) if kind in ("ranked", "effect") else None, _tie_key(row))
    return index


def rank(target_hex: str, rows, *, limit: int | None = None, cache: dict | None = None, index: dict | None = None) -> dict:
    """Rank rows by ΔE00 to ``target_hex``; deterministic, rows are never merged.

    ``cache`` maps candidate HEX -> ΔE00 for this target; callers keep one per
    target so that refiltering the same query does not recompute distances.
    ``index`` (from ``build_index``) avoids reclassifying unchanged rows.
    Ties are broken by brand, product, colour name and SKU (stable).
    """
    target = parse_hex(target_hex)
    if target is None:
        raise ValueError("HEX sRGB à six caractères requis.")
    lab = hex_to_lab(target)
    cache = {} if cache is None else cache
    ranked, excluded = [], {}
    for row in rows:
        facts = index.get(id(row)) if index is not None else None
        if facts is None:
            kind = classify(row)
            facts = (kind, parse_hex(row.get("hex")) if kind in ("ranked", "effect") else None, _tie_key(row))
        kind, h, tie = facts
        if kind not in ("ranked", "effect"):
            excluded[kind] = excluded.get(kind, 0) + 1
            continue
        distance = cache.get(h)
        if distance is None:
            distance = cache[h] = round(ciede2000(lab, hex_to_lab(h)), 6)
        ranked.append((distance, tie, row, kind == "effect"))
    ranked.sort(key=lambda item: (item[0], item[1]))
    items = [dict(row=row, delta=delta, effect=effect) for delta, _, row, effect in ranked]
    return {"target": target, "items": items[:limit] if limit else items, "total": len(items), "excluded": excluded}


def display_delta(value):
    """Display only: round upwards to 0.01, never conceal a threshold excess.

    Ranking/filtering retain the existing six-decimal computed score.
    Decimal conversion avoids e.g. a binary 3.0 being displayed as 3.01.
    """
    from decimal import Decimal, ROUND_CEILING
    return str(Decimal(str(value)).quantize(Decimal("0.01"),rounding=ROUND_CEILING))

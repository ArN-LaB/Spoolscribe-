"""QR matrix, physical label geometry and faithful PNG/SVG files; no widgets.

Sizes are whole printer dots per module, computed from the paper, margins and
resolution actually used, never from the screen zoom. A code that does not fit
at the accepted density is refused for printing; nothing is shrunk or dropped.
"""
from dataclasses import dataclass, field
from fractions import Fraction
import io
import math

import segno

from . import qr_transfer

QUIET_ZONE = 4  # Modules of white on each side (ISO/IEC 18004).
ERROR_LEVELS = ("M", "Q")
PRUDENT_DOTS, SMALL_DOTS = 4, 3
MAX_MODULE_MM = Fraction(1)  # Beyond 1 mm per module a larger QR adds nothing.
TEXT_LINE_MM, TEXT_GAP_MM, MAX_TEXT_LINES = Fraction(13, 5), Fraction(1), 3
MM_PER_INCH = Fraction(254, 10)
DPI_RANGE, SIZE_RANGE_MM, MARGIN_MAX_MM = (96, 2400), (5, 1000), 100


@dataclass(frozen=True)
class QrSymbol:
    """One standard QR (no Micro QR, ECI or Structured Append), single alphanumeric segment."""
    text: str
    protocol: int
    codec: int
    error: str
    version: int
    modules: tuple = field(repr=False)  # Rows of booleans, True = dark, without quiet zone.
    ndef_bytes: int = 0
    sha256: str = ""

    @property
    def size(self) -> int:
        return len(self.modules)

    @property
    def total_modules(self) -> int:
        return self.size + 2 * QUIET_ZONE


def _segno(text, error):
    return segno.make(text, error=error, mode="alphanumeric", micro=False, boost_error=False)


def make_symbol(protocol: int, message: bytes, error: str = "M") -> QrSymbol:
    """Smallest version of the two codecs at this error level; raw on a tie."""
    if error not in ERROR_LEVELS:
        raise qr_transfer.TransferError("Correction QR attendue : M ou Q.")
    qr_transfer.validate_ndef(protocol, message)  # Business errors are raised, not skipped as a size.
    best = None
    for codec in (qr_transfer.RAW, qr_transfer.ZLIB):
        # Candidates are independent: a raw text above its bound does not stop zlib.
        try:
            text = qr_transfer.envelope(protocol, message, codec)
            code = _segno(text, error.lower())
        except (qr_transfer.TextTooLong, segno.DataOverflowError):
            continue
        if best is None or code.version < best[1].version:
            best = (text, code, codec)
    if best is None:
        raise qr_transfer.TransferError("Message trop volumineux pour un seul QR Code à ce niveau de correction.")
    text, code, codec = best
    if qr_transfer.decode(text).ndef != bytes(message):  # Self-check of the emitted text.
        raise qr_transfer.TransferError("Contrôle du texte de transfert en échec.")
    rows = tuple(tuple(bool(v) for v in row) for row in code.matrix_iter(scale=1, border=0))
    return QrSymbol(text, protocol, codec, error, code.version, rows, len(message),
                    qr_transfer.Transfer(protocol, codec, bytes(message)).sha256)


# ── Label profiles and geometry ─────────────────────────────────────────
@dataclass(frozen=True)
class LabelProfile:
    width_mm: float
    height_mm: float
    margins_mm: tuple = (1.0, 1.0, 1.0, 1.0)  # left, top, right, bottom
    dpi: int = 203
    orientation: str = "portrait"


PRESETS = {
    # D101: 25 mm roll, 24 mm printable; 0.5 mm more kept on each side (23 mm, 183 dots).
    "d101-25x50": ("NIIMBOT D101 · 25 × 50 mm", LabelProfile(25, 50, (1.0, 1.0, 1.0, 1.0), 203)),
    "label-50x50": ("Étiquette 50 × 50 mm", LabelProfile(50, 50, (1.5, 1.5, 1.5, 1.5), 203)),
    "label-62x100": ("Étiquette 62 × 100 mm", LabelProfile(62, 100, (1.5, 1.5, 1.5, 1.5), 300)),
    "a4": ("Page A4", LabelProfile(210, 297, (10, 10, 10, 10), 300)),
}
DEFAULT_PRESET = "d101-25x50"


def _number(value, low, high, name):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} : nombre entre {low} et {high} attendu.")
    return Fraction(str(value))


def validate_profile(profile: LabelProfile) -> LabelProfile:
    if not isinstance(profile, LabelProfile):
        raise ValueError("Profil d’étiquette invalide.")
    width = _number(profile.width_mm, *SIZE_RANGE_MM, "Largeur")
    height = _number(profile.height_mm, *SIZE_RANGE_MM, "Hauteur")
    if not isinstance(profile.margins_mm, tuple) or len(profile.margins_mm) != 4:
        raise ValueError("Quatre marges attendues.")
    left, top, right, bottom = (_number(m, 0, MARGIN_MAX_MM, "Marge") for m in profile.margins_mm)
    if type(profile.dpi) is not int or not DPI_RANGE[0] <= profile.dpi <= DPI_RANGE[1]:
        raise ValueError(f"Résolution : entier entre {DPI_RANGE[0]} et {DPI_RANGE[1]} ppp attendu.")
    if profile.orientation not in ("portrait", "landscape"):
        raise ValueError("Orientation : portrait ou paysage.")
    if left + right >= width or top + bottom >= height:
        raise ValueError("Les marges ne laissent aucune zone imprimable.")
    return profile


def dots(mm, dpi) -> int:
    """Whole dots inside a length: rounded down, never in favour of the fit."""
    return math.floor(Fraction(str(mm)) * dpi / MM_PER_INCH)


def dots_to_mm(count, dpi) -> float:
    return float(Fraction(count) * MM_PER_INCH / dpi)


@dataclass(frozen=True)
class LabelPlan:
    paper_mm: tuple            # width, height after orientation
    dpi: int
    area: tuple                # printable x, y, w, h in dots, from the drawing origin
    total_modules: int         # symbol + quiet zone
    dots_per_module: int       # 0 when refused
    qr_rect: tuple             # x, y, side, side in dots (quiet zone included)
    text_rect: tuple           # x, y, w, h in dots; (0, 0, 0, 0) without room
    text_lines: int
    status: str                # "ready" (≥ 4 dots), "small" (3 dots, chosen), "refused"
    reason: str = ""           # "", "needs_small", "too_dense"
    fitting_dots: int = 0      # Dots per module the area could hold

    @property
    def qr_mm(self) -> float:
        return dots_to_mm(self.qr_rect[2], self.dpi)

    @property
    def module_mm(self) -> float:
        return dots_to_mm(self.dots_per_module, self.dpi) if self.dots_per_module else 0.0

    @property
    def printable_mm(self) -> tuple:
        return dots_to_mm(self.area[2], self.dpi), dots_to_mm(self.area[3], self.dpi)

    @property
    def printable(self) -> bool:
        return self.status in ("ready", "small")


def minimum_width_mm(total_modules: int, dpi: int, dots_per_module: int = PRUDENT_DOTS) -> float:
    """Printable width a QR needs at this density, quiet zone included."""
    return dots_to_mm(total_modules * dots_per_module, dpi)


def plan_label(total_modules: int, profile: LabelProfile, *, small_format: bool = False, device=None) -> LabelPlan:
    """Geometry of the template: QR square (with quiet zone) first, then identity lines.

    ``device`` is (dpi, paint_rect_dots, page_size_dots) read back from the
    accepted printer after its dialog: the printable area is the driver's
    paint area intersected with the profile margins, at the driver's resolution.
    """
    validate_profile(profile)
    if type(total_modules) is not int or not 21 + 2 * QUIET_ZONE <= total_modules <= 177 + 2 * QUIET_ZONE:
        raise ValueError("Taille de QR invalide.")
    width, height = profile.width_mm, profile.height_mm
    if profile.orientation == "landscape":
        width, height = height, width
    left, top, right, bottom = profile.margins_mm  # Relative to the page as oriented.
    if device is None:
        dpi = profile.dpi
        x0, y0 = math.ceil(Fraction(str(left)) * dpi / MM_PER_INCH), math.ceil(Fraction(str(top)) * dpi / MM_PER_INCH)
        x1, y1 = dots(Fraction(str(width)) - Fraction(str(right)), dpi), dots(Fraction(str(height)) - Fraction(str(bottom)), dpi)
        origin = (0, 0)
    else:
        dpi, paint, page = device
        if type(dpi) is not int or not DPI_RANGE[0] <= dpi <= DPI_RANGE[1]:
            raise ValueError("Résolution du pilote hors bornes.")
        px, py, pw, ph = (int(v) for v in paint)
        page_w, page_h = (int(v) for v in page)
        if pw <= 0 or ph <= 0 or page_w <= 0 or page_h <= 0:
            raise ValueError("Zone d’impression du pilote vide.")
        mx0 = math.ceil(Fraction(str(left)) * dpi / MM_PER_INCH)
        my0 = math.ceil(Fraction(str(top)) * dpi / MM_PER_INCH)
        mx1 = page_w - math.ceil(Fraction(str(right)) * dpi / MM_PER_INCH)
        my1 = page_h - math.ceil(Fraction(str(bottom)) * dpi / MM_PER_INCH)
        x0, y0, x1, y1 = max(mx0, px), max(my0, py), min(mx1, px + pw), min(my1, py + ph)
        origin = (px, py)  # QPainter on a printer starts at the paint rectangle.
        width, height = dots_to_mm(page_w, dpi), dots_to_mm(page_h, dpi)
    area_w, area_h = max(0, x1 - x0), max(0, y1 - y0)
    area = (x0 - origin[0], y0 - origin[1], area_w, area_h)
    side = min(area_w, area_h)
    fitting = side // total_modules
    cap = max(PRUDENT_DOTS, math.floor(MAX_MODULE_MM * dpi / MM_PER_INCH))
    if fitting >= PRUDENT_DOTS:
        status, reason, module = "ready", "", min(fitting, cap)
    elif fitting == SMALL_DOTS and small_format:
        status, reason, module = "small", "", SMALL_DOTS
    else:
        status, reason, module = "refused", "needs_small" if fitting == SMALL_DOTS else "too_dense", 0
    qr_side = total_modules * module
    qr_rect = (area[0] + (area_w - qr_side) // 2, area[1], qr_side, qr_side) if module else (area[0], area[1], 0, 0)
    gap, line = dots(TEXT_GAP_MM, dpi), max(1, dots(TEXT_LINE_MM, dpi))
    below = area_h - qr_side - gap
    lines = max(0, min(MAX_TEXT_LINES, below // line)) if module else 0
    text_rect = (area[0], area[1] + qr_side + gap, area_w, lines * line) if lines else (0, 0, 0, 0)
    return LabelPlan((float(width), float(height)), dpi, area, total_modules, module, qr_rect, text_rect,
                     lines, status, reason, fitting)


def dark_runs(symbol: QrSymbol):
    """Horizontal runs of dark modules (column, row, length), quiet zone excluded."""
    for y, row in enumerate(symbol.modules):
        x = 0
        while x < len(row):
            if row[x]:
                start = x
                while x < len(row) and row[x]:
                    x += 1
                yield start, y, x - start
            else:
                x += 1


def module_rects(symbol: QrSymbol, origin, dots_per_module):
    """Integer device rectangles of the dark modules: no scaling, no interpolation."""
    ox, oy = origin[0] + QUIET_ZONE * dots_per_module, origin[1] + QUIET_ZONE * dots_per_module
    return [(ox + x * dots_per_module, oy + y * dots_per_module, n * dots_per_module, dots_per_module)
            for x, y, n in dark_runs(symbol)]


# ── Files ───────────────────────────────────────────────────────────────
PNG_MAX_SCALE = 64       # Pixels per module: at most 193 × 64 = 12 352 px per side (V40), 1 bit per pixel.
PNG_TARGET_DPI = 1200    # Raster density sought for a printable plan; the physical size never changes.


def png_scale(plan: LabelPlan) -> tuple:
    """(pixels per module, pixels per inch) for a printable plan, both within the PNG bounds.

    Whole printer dots map to whole pixels when the device is at most 1 200 dpi; above,
    a module is still a whole number of pixels (≤ PNG_MAX_SCALE) and the density written
    in the file keeps the physical size of the plan.
    """
    factor = max(1, PNG_TARGET_DPI // plan.dpi)
    scale = max(1, min(PNG_MAX_SCALE, plan.dots_per_module * factor))
    return scale, Fraction(scale * plan.dpi, plan.dots_per_module)


def png_bytes(symbol: QrSymbol, scale: int, dpi=None) -> bytes:
    """1-bit black/white PNG, ``scale`` pixels per module, quiet zone included.

    ``dpi`` (may be fractional) is written exactly as pixels per metre, rounded once.
    """
    if type(scale) is not int or not 1 <= scale <= PNG_MAX_SCALE:
        raise ValueError(f"Échelle PNG : entier entre 1 et {PNG_MAX_SCALE}.")
    out = io.BytesIO()
    _segno(symbol.text, symbol.error.lower()).save(out, kind="png", scale=scale, border=QUIET_ZONE,
                                                     dark="#000", light="#fff")
    data = out.getvalue()
    if dpi is None:
        return data
    import struct, zlib
    per_metre = round(Fraction(dpi) * 10000 / 254)
    if not 1 <= per_metre < 2 ** 31:
        raise ValueError("Résolution PNG invalide.")
    body = b"pHYs" + struct.pack(">IIB", per_metre, per_metre, 1)
    chunk = struct.pack(">I", 9) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    end = 8 + 4 + 4 + 13 + 4  # Signature, then the IHDR chunk; pHYs must precede IDAT.
    return data[:end] + chunk + data[end:]


# Smallest accepted module: 3 dots at 2 400 dpi (0.03175 mm); largest: 10 mm.
SVG_MODULE_MM = (float(SMALL_DOTS * MM_PER_INCH / DPI_RANGE[1]), 10.0)


def _mm(value) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def svg_bytes(symbol: QrSymbol, module_mm: float, title: str = "", description: str = "") -> bytes:
    """Filled squares in module units (exact viewBox), physical size in millimetres."""
    if type(module_mm) not in (int, float) or not math.isfinite(module_mm) or not SVG_MODULE_MM[0] <= module_mm <= SVG_MODULE_MM[1]:
        raise ValueError("Taille de module SVG invalide.")
    from xml.sax.saxutils import escape
    total = symbol.total_modules
    path = "".join(f"M{x + QUIET_ZONE} {y + QUIET_ZONE}h{n}v1h-{n}z" for x, y, n in dark_runs(symbol))
    side = _mm(total * module_mm)
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{side}mm" height="{side}mm" '
            f'viewBox="0 0 {total} {total}" shape-rendering="crispEdges">\n'
            f'<title>{escape(title)}</title>\n<desc>{escape(description)}</desc>\n'
            f'<rect width="{total}" height="{total}" fill="#fff"/>\n'
            f'<path fill="#000" d="{path}"/>\n</svg>\n').encode("utf-8")


# ── Saved paper settings (dedicated configuration section) ──────────────
def validate_settings(value) -> dict:
    """``qr_label`` section: preset, custom profile, small format, error level."""
    if not isinstance(value, dict) or set(value) - {"preset", "custom", "small_format", "error"}:
        raise ValueError("Réglages QR invalides.")
    preset, error = value.get("preset", DEFAULT_PRESET), value.get("error", "M")
    if type(preset) is not str or (preset not in PRESETS and preset != "custom"):
        raise ValueError("Support QR inconnu.")
    if type(value.get("small_format", False)) is not bool or type(error) is not str or error not in ERROR_LEVELS:
        raise ValueError("Réglages QR invalides.")
    if "custom" in value:
        profile_from_dict(value["custom"])
    elif preset == "custom":
        raise ValueError("Support personnalisé incomplet.")
    return value


def profile_from_dict(value) -> LabelProfile:
    if not isinstance(value, dict) or set(value) != {"width_mm", "height_mm", "margins_mm", "dpi", "orientation"}:
        raise ValueError("Support personnalisé invalide.")
    margins = value["margins_mm"]
    if not isinstance(margins, list) or len(margins) != 4:
        raise ValueError("Quatre marges attendues.")
    if type(value["orientation"]) is not str:
        raise ValueError("Orientation : portrait ou paysage.")
    return validate_profile(LabelProfile(value["width_mm"], value["height_mm"], tuple(margins),
                                         value["dpi"], value["orientation"]))


def profile_to_dict(profile: LabelProfile) -> dict:
    return dict(width_mm=profile.width_mm, height_mm=profile.height_mm, margins_mm=list(profile.margins_mm),
                dpi=profile.dpi, orientation=profile.orientation)


def settings_profile(value) -> LabelProfile:
    try:
        settings = validate_settings(value)
    except ValueError:
        return PRESETS[DEFAULT_PRESET][1]
    preset = settings.get("preset", DEFAULT_PRESET)
    return profile_from_dict(settings["custom"]) if preset == "custom" else PRESETS[preset][1]

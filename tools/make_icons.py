#!/usr/bin/env python3
"""
tools/make_icons.py — Génère les icônes binaires de l'app à partir du SVG.

Source unique : data/spoolscribe_logo.svg
Produit       : data/app.ico (Windows) et data/app.png (macОS/Linux/usage divers).

Lancement :  python tools/make_icons.py
"""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG = os.path.join(ROOT, "data", "spoolscribe_logo.svg")
ICO = os.path.join(ROOT, "data", "app.ico")
PNG = os.path.join(ROOT, "data", "app.png")


def render(size: int) -> Image.Image:
    r = QSvgRenderer(SVG)
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    r.render(p)
    p.end()
    tmp = os.path.join(ROOT, "data", f"_tmp_{size}.png")
    img.save(tmp)
    pil = Image.open(tmp).convert("RGBA")
    os.remove(tmp)
    return pil


def main() -> int:
    if not os.path.isfile(SVG):
        print(f"SVG introuvable : {SVG}", file=sys.stderr)
        return 1
    sizes = [16, 24, 32, 48, 64, 128, 256]
    imgs = {s: render(s) for s in sizes}
    imgs[256].save(PNG)
    imgs[256].save(ICO, format="ICO", sizes=[(s, s) for s in sizes])
    print(f"écrit : {ICO}")
    print(f"écrit : {PNG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

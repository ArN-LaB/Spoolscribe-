#!/usr/bin/env python3
"""
app_gui.py — Application graphique multiplateforme (Windows / macOS / Linux).

Construite sur PySide6 (Qt). Toute la logique métier vient de core.py :
cette couche ne fait que de l'affichage et de l'orchestration UI.

Lancement :  python app_gui.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
import math

from PySide6.QtCore import Qt, QThread, Signal, QSize, QTimer, QRectF
from PySide6.QtGui import (
    QColor, QFont, QPixmap, QPainter, QIcon, QPalette, QPainterPath, QAction, QPen,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLineEdit, QTableWidget, QTableWidgetItem, QLabel, QPushButton, QPlainTextEdit,
    QHeaderView, QAbstractItemView, QFrame, QMessageBox, QProgressBar, QGridLayout,
    QSizePolicy, QStackedWidget, QToolButton, QMenu, QListWidget, QListWidgetItem,
    QDialog, QDialogButtonBox, QCheckBox, QSpinBox, QButtonGroup,
    QGraphicsScene, QGraphicsPixmapItem, QGraphicsBlurEffect, QScrollArea,
)

try:
    from PySide6.QtSvgWidgets import QSvgWidget  # noqa: F401
    from PySide6.QtSvg import QSvgRenderer
    HAS_SVG = True
except Exception:
    HAS_SVG = False

import core

# Hauteur fixe de l'inspecteur JSON + espacement du layout (12 px) = delta
# appliqué à la fenêtre lors du toggle pour éviter tout scroll parasite.
_INSPECTOR_H = 210
_INSPECTOR_DELTA = _INSPECTOR_H + 12


# ─── Logo animé : la bobine tourne, le fil reste posé ─────────────────────
class SpinningLogo(QWidget):
    """Affiche le logo SVG et fait tourner la seule face de bobine (#disc).

    Le fil (#strand) et l'ombre portée restent immobiles : la bobine semble
    *dévider* le trait qu'elle écrit. Rotation lente et continue au repos,
    accélération nette et assumée au survol, retour en douceur — une logique
    affirmée mais sans esbroufe.
    """

    _VIEWBOX = 512.0          # le SVG est carré 512×512
    _DISC_CENTER = (256.0, 252.0)
    _DISC_RADIUS = 170.0
    _IDLE_SPEED = 26.0        # deg/s au repos (un tour ≈ 14 s)
    _HOVER_SPEED = 180.0      # deg/s au survol — franc, assumé
    _EASE = 6.0               # vitesse de convergence (plus grand = plus vif)

    def __init__(self, svg_path: str, size: int = 30, parent: QWidget | None = None):
        super().__init__(parent)
        self._renderer = QSvgRenderer(svg_path)
        self._angle = 0.0
        self._speed = self._IDLE_SPEED
        self._target = self._IDLE_SPEED
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self._last = time.perf_counter()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)  # ~60 fps

    # Survol : on assume une accélération nette.
    def enterEvent(self, event):
        self._target = self._HOVER_SPEED
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._target = self._IDLE_SPEED
        super().leaveEvent(event)

    def _tick(self):
        now = time.perf_counter()
        dt = min(now - self._last, 0.05)  # borne anti-saccade
        self._last = now
        # Lissage exponentiel de la vitesse vers la cible.
        k = 1.0 - pow(2.718281828, -self._EASE * dt)
        self._speed += (self._target - self._speed) * k
        self._angle = (self._angle + self._speed * dt) % 360.0
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)

        sc = self.width() / self._VIEWBOX
        full = QRectF(0, 0, self.width(), self.height())
        # 1) Logo complet, immobile (tuile + fil + ombre + bobine au repos).
        self._renderer.render(p, full)

        # 2) Re-rendu de la seule bobine, pivotée autour de son centre.
        if self._renderer.elementExists("disc"):
            cx = self._DISC_CENTER[0] * sc
            cy = self._DISC_CENTER[1] * sc
            r = self._DISC_RADIUS * sc
            p.save()
            clip = QPainterPath()
            clip.addEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
            p.setClipPath(clip)            # ne réécrit que le disque, pas le fil
            p.translate(cx, cy)
            p.rotate(self._angle)
            p.translate(-cx, -cy)
            b = self._renderer.boundsOnElement("disc")
            target = QRectF(b.x() * sc, b.y() * sc, b.width() * sc, b.height() * sc)
            self._renderer.render(p, "disc", target)
            p.restore()
        p.end()


# ─── Thread de mise à jour DB ─────────────────────────────────────────────
class UpdateWorker(QThread):
    """Exécute la pipeline de scrapers sans bloquer l'UI."""
    progress = Signal(str, int, int)   # label, index, total
    finished_ok = Signal(list)         # list[core.StepResult]
    failed = Signal(str)

    def run(self):
        try:
            results = core.run_update_pipeline(
                progress=lambda label, i, total: self.progress.emit(label, i, total),
                consent=core.has_network_consent(),
            )
            self.finished_ok.emit(results)
        except Exception:
            self.failed.emit(traceback.format_exc())


# ─── Pastille couleur ─────────────────────────────────────────────────────
def make_swatch_pixmap(hex_code: str | None, size: int = 18, dpr: float = 1.0,
                       radius: int = 4) -> QPixmap:
    px = max(1, int(round(size * dpr)))
    pm = QPixmap(px, px)
    h = (hex_code or "").strip().lstrip("#")
    known = len(h) == 6
    color = QColor(f"#{h}") if known else QColor("#e8e8e8")
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(color)
    p.setPen(QColor("#888888"))
    r = radius * dpr
    p.drawRoundedRect(0, 0, px - 1, px - 1, r, r)
    if not known:
        # Couleur inconnue : barre diagonale « pas de couleur » bien lisible.
        p.setPen(QPen(QColor("#b00020"), max(1.0, px * 0.09)))
        p.drawLine(int(px * 0.18), int(px * 0.82), int(px * 0.82), int(px * 0.18))
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def make_view_icon(kind: str, color: str, size: int = 18, dpr: float = 1.0) -> QIcon:
    """Dessine une petite icône nette « liste » ou « grille »."""
    px = max(1, int(round(size * dpr)))
    pm = QPixmap(px, px)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    col = QColor(color)
    s = px
    p.setPen(Qt.NoPen)
    p.setBrush(col)
    if kind == "list":
        bar_h = max(1.0, s * 0.13)
        dot = max(1.0, s * 0.13)
        for i in range(3):
            y = s * (0.22 + i * 0.28)
            p.drawEllipse(QRectF(s * 0.06, y, dot, dot))
            p.drawRoundedRect(QRectF(s * 0.30, y, s * 0.62, bar_h), bar_h / 2, bar_h / 2)
    else:  # grid
        cell = s * 0.34
        gap = s * 0.10
        x0 = s * 0.12
        y0 = s * 0.12
        r = max(1.0, s * 0.06)
        for cx in (x0, x0 + cell + gap):
            for cy in (y0, y0 + cell + gap):
                p.drawRoundedRect(QRectF(cx, cy, cell, cell), r, r)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return QIcon(pm)


def load_brand_pixmap(
    abs_path: str,
    size: int,
    dpr: float = 1.0,
    max_w: int | None = None,
) -> QPixmap | None:
    """Charge un logo de marque (SVG ou bitmap) en rendu net HiDPI.

    *size* fixe la hauteur maximale (axe court). *max_w* fixe la largeur
    maximale (axe long) ; les logos en format paysage (wordmarks) peuvent
    ainsi s'étendre horizontalement sans être écrasés dans un carré.
    Si *max_w* est omis, il vaut 3 × *size* (couvre les wordmarks courants).
    """
    if not abs_path or not os.path.exists(abs_path):
        return None
    ph = max(1, int(round(size * dpr)))
    pw = max(1, int(round((max_w or size * 3) * dpr)))
    ext = os.path.splitext(abs_path)[1].lower()
    try:
        if ext == ".svg" and HAS_SVG:
            renderer = QSvgRenderer(abs_path)
            vb = renderer.viewBoxF()
            src_w = vb.width()  if vb.width()  > 0 else pw
            src_h = vb.height() if vb.height() > 0 else ph
            scale = min(pw / src_w, ph / src_h)
            rw, rh = int(src_w * scale), int(src_h * scale)
            pm = QPixmap(rw, rh)
            pm.fill(Qt.transparent)
            painter = QPainter(pm)
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            renderer.render(painter, QRectF(0, 0, rw, rh))
            painter.end()
            pm.setDevicePixelRatio(dpr)
            return pm
        if ext in (".png", ".jpg", ".jpeg", ".webp"):
            src = QPixmap(abs_path)
            if src.isNull():
                return None
            pm = src.scaled(pw, ph, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pm.setDevicePixelRatio(dpr)
            return pm
    except Exception:
        return None


def add_soft_halo(pm: QPixmap, radius: float = 6.0, color: str = "#ffffff",
                  passes: int = 2) -> QPixmap:
    """Entoure un logo d'un halo *doux* qui épouse ses courbes (fond sombre).

    On isole la silhouette opaque (canal alpha → blanc), on lui applique un
    vrai flou gaussien (QGraphicsBlurEffect) puis on repose le logo net
    par-dessus. Le flou suit naturellement les contours, s'atténue avec la
    distance et se fond dans le fond sombre — aucun anneau tranché. À ne pas
    utiliser en thème clair (le halo y serait inutile et disgracieux).
    """
    if pm.isNull():
        return pm
    dpr = pm.devicePixelRatio() or 1.0

    # On travaille en pixels « bruts » (dpr neutralisé), restitué à la fin.
    base = QPixmap(pm)
    base.setDevicePixelRatio(1.0)
    W, H = base.width(), base.height()
    r_px = max(1.0, radius * dpr)

    # 1) Silhouette blanche = logo teinté en blanc via SourceIn.
    sil = QPixmap(W, H)
    sil.fill(Qt.transparent)
    sp = QPainter(sil)
    sp.drawPixmap(0, 0, base)
    sp.setCompositionMode(QPainter.CompositionMode_SourceIn)
    sp.fillRect(sil.rect(), QColor(color))
    sp.end()

    # 2) Flou gaussien de la silhouette dans une toile élargie.
    pad = int(math.ceil(r_px)) + 2
    ow, oh = W + pad * 2, H + pad * 2
    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(sil)
    blur = QGraphicsBlurEffect()
    blur.setBlurRadius(r_px)
    blur.setBlurHints(QGraphicsBlurEffect.QualityHint)
    item.setGraphicsEffect(blur)
    scene.addItem(item)

    glow = QPixmap(ow, oh)
    glow.fill(Qt.transparent)
    gp = QPainter(glow)
    gp.setRenderHint(QPainter.SmoothPixmapTransform, True)
    scene.render(gp, QRectF(0, 0, ow, oh), QRectF(-pad, -pad, ow, oh))
    gp.end()

    # 3) Composition : halo (renforcé en plusieurs couches douces) + logo net.
    out = QPixmap(ow, oh)
    out.fill(Qt.transparent)
    op = QPainter(out)
    op.setRenderHint(QPainter.SmoothPixmapTransform, True)
    for _ in range(max(1, passes)):
        op.drawPixmap(0, 0, glow)
    op.drawPixmap(pad, pad, base)
    op.end()

    out.setDevicePixelRatio(dpr)
    return out


# ─── Thème : suit automatiquement le système (clair / sombre) ─────────────
def build_palette(dark: bool) -> QPalette:
    """Construit une QPalette explicite et cohérente pour le thème courant.

    Indispensable : la palette par défaut ne repeint pas toujours les widgets
    de base (table, libellés, menus) selon la plateforme. En posant une
    palette complète, le texte et les fonds restent lisibles quel que soit le
    thème de l'OS.
    """
    pal = QPalette()
    if dark:
        window, base, alt = QColor("#1f2226"), QColor("#24282d"), QColor("#2a2f35")
        text, disabled = QColor("#f1f3f5"), QColor("#7a828b")
        button, tooltip = QColor("#2a2f35"), QColor("#2a2f35")
        highlight, htext = QColor("#2fd0e4"), QColor("#04282d")
    else:
        window, base, alt = QColor("#f4f5f7"), QColor("#ffffff"), QColor("#eef0f3")
        text, disabled = QColor("#1c1e21"), QColor("#9aa0a6")
        button, tooltip = QColor("#e9ebee"), QColor("#ffffff")
        highlight, htext = QColor("#127f8e"), QColor("#ffffff")

    pal.setColor(QPalette.Window, window)
    pal.setColor(QPalette.WindowText, text)
    pal.setColor(QPalette.Base, base)
    pal.setColor(QPalette.AlternateBase, alt)
    pal.setColor(QPalette.Text, text)
    pal.setColor(QPalette.Button, button)
    pal.setColor(QPalette.ButtonText, text)
    pal.setColor(QPalette.BrightText, QColor("#ffffff"))
    pal.setColor(QPalette.ToolTipBase, tooltip)
    pal.setColor(QPalette.ToolTipText, text)
    pal.setColor(QPalette.PlaceholderText, disabled)
    pal.setColor(QPalette.Highlight, highlight)
    pal.setColor(QPalette.HighlightedText, htext)
    pal.setColor(QPalette.Link, highlight)
    pal.setColor(QPalette.LinkVisited, highlight)
    for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, disabled)
    return pal


def init_theme(app: QApplication) -> None:
    """Initialise le style et la palette d'après le thème système courant."""
    try:
        if app.style().objectName().lower() != "fusion":
            app.setStyle("Fusion")
    except Exception:
        pass
    try:
        app.setPalette(build_palette(is_dark_theme(app)))
    except Exception:
        pass


def is_dark_theme(app: QApplication) -> bool:
    """Vrai si le système est en thème sombre.

    On tente d'abord colorScheme() (Qt 6.5+), puis on replie sur la luminance
    de la palette native de l'OS.
    """
    try:
        scheme = app.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    except Exception:
        pass
    # Fallback : lire la palette native de l'OS (avant toute modification
    # par Fusion), via un style natif éphémère.
    try:
        from PySide6.QtWidgets import QStyleFactory
        native = QStyleFactory.create("windows") or QStyleFactory.create("windowsvista")
        if native:
            return native.standardPalette().color(QPalette.Window).lightness() < 128
    except Exception:
        pass
    return app.palette().color(QPalette.Window).lightness() < 128


def theme_tokens(app: QApplication) -> dict:
    """Jeu de couleurs adapté au thème courant (contrastes renforcés).

    Toutes les surfaces ont une couleur *opaque* (pas de rgba sur fond
    inconnu) : c'est ce qui garantit un rendu identique et lisible en thème
    clair comme sombre, sans dépendre de la propagation de la palette Qt.
    """
    if is_dark_theme(app):
        return {
            "dark": True,
            "text": "#f1f3f5",
            "muted": "#c3cad2", "faint": "#9aa3ad",
            "accent": "#2fd0e4", "accent_hover": "#4adcee", "accent_text": "#04282d",
            "card": "#262b31", "border": "#3a414a",
            "field_bg": "#2b3138", "danger": "#ff8a8a",
            "sec_bg": "#2f353c", "sec_hover": "#3a414a",
            "window": "#1f2226", "base": "#23272c", "alt": "#272c32",
            "sel": "#2fd0e4", "sel_text": "#04282d", "header": "#2a2f35",
        }
    return {
        "dark": False,
        "text": "#1c1e21",
        "muted": "#41454a", "faint": "#6a6e73",
        "accent": "#127f8e", "accent_hover": "#0e6b78", "accent_text": "#ffffff",
        "card": "#ffffff", "border": "#d2d6db",
        "field_bg": "#ffffff", "danger": "#c5221f",
        "sec_bg": "#eceef1", "sec_hover": "#e1e4e8",
        "window": "#f4f5f7", "base": "#ffffff", "alt": "#f3f4f6",
        "sel": "#127f8e", "sel_text": "#ffffff", "header": "#eceef1",
    }


def contrast_text(hex_code: str | None) -> str:
    """Noir ou blanc selon la luminance d'une couleur, pour rester lisible."""
    h = (hex_code or "").strip().lstrip("#")
    if len(h) != 6:
        return "#000000"
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return "#000000"
    return "#000000" if (0.299 * r + 0.587 * g + 0.114 * b) > 140 else "#ffffff"


# ─── Fenêtre principale ───────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.app = QApplication.instance()
        self.setWindowTitle(f"SpoolScribe {core.APP_VERSION} — OpenSpool / NFC")
        self.resize(1060, 700)
        self.setMinimumSize(860, 560)

        icon_path = core.app_icon_abs_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        self.db = core.load_db()
        self.current_sku: str | None = None
        self.worker: UpdateWorker | None = None
        self._muted_labels: list[QLabel] = []
        self.view_mode = "list"

        self._build_ui()
        self._apply_theme()
        self._reload_table()
        self._refresh_logo()
        self._update_stats()
        self._show_empty()

        # Réagit aux changements de thème de l'OS à chaud (Qt 6.5+).
        try:
            self.app.styleHints().colorSchemeChanged.connect(self._on_os_scheme_changed)
        except Exception:
            pass

        # Mise à jour automatique au démarrage (opt-in, consentement requis).
        QTimer.singleShot(400, self._maybe_auto_update)

    def _on_os_scheme_changed(self, *_):
        """Le thème de l'OS a changé : on répercute clair/sombre à chaud."""
        init_theme(self.app)
        self._apply_theme()
        self._refresh_logo()

    # ── Construction UI ──────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 12, 14, 10)
        root.setSpacing(10)

        # ── Barre du haut : recherche · vues · update · menu ──────────────
        top = QHBoxLayout()
        top.setSpacing(8)

        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Rechercher : SKU, produit, couleur…")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(240)
        self.search.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.search.textChanged.connect(self._apply_filter)
        top.addWidget(self.search, 1)

        # Bascule de vue Liste / Grille (pilule segmentée)
        dpr = self.devicePixelRatioF()
        self.segwrap = QFrame()
        self.segwrap.setObjectName("segwrap")
        seg = QHBoxLayout(self.segwrap)
        seg.setContentsMargins(3, 3, 3, 3)
        seg.setSpacing(3)
        self.btn_view_list = QToolButton()
        self.btn_view_list.setObjectName("seg")
        self.btn_view_list.setIcon(make_view_icon("list", "#888", 18, dpr))
        self.btn_view_list.setIconSize(QSize(18, 18))
        self.btn_view_list.setToolTip("Vue liste")
        self.btn_view_list.setCheckable(True)
        self.btn_view_list.setChecked(True)
        self.btn_view_list.setCursor(Qt.PointingHandCursor)
        self.btn_view_grid = QToolButton()
        self.btn_view_grid.setObjectName("seg")
        self.btn_view_grid.setIcon(make_view_icon("grid", "#888", 18, dpr))
        self.btn_view_grid.setIconSize(QSize(18, 18))
        self.btn_view_grid.setToolTip("Vue grille")
        self.btn_view_grid.setCheckable(True)
        self.btn_view_grid.setCursor(Qt.PointingHandCursor)
        view_group = QButtonGroup(self)
        view_group.setExclusive(True)
        view_group.addButton(self.btn_view_list)
        view_group.addButton(self.btn_view_grid)
        self.btn_view_list.clicked.connect(lambda: self._set_view_mode("list"))
        self.btn_view_grid.clicked.connect(lambda: self._set_view_mode("grid"))
        seg.addWidget(self.btn_view_list)
        seg.addWidget(self.btn_view_grid)
        top.addWidget(self.segwrap)

        self.update_btn = QPushButton("Mettre à jour")
        self.update_btn.setObjectName("primary")
        self.update_btn.setCursor(Qt.PointingHandCursor)
        self.update_btn.clicked.connect(self._start_update)
        top.addWidget(self.update_btn)

        # Menu ⋯ : Paramètres, À propos
        self.menu_btn = QToolButton()
        self.menu_btn.setObjectName("ghost")
        self.menu_btn.setText("⋯")
        self.menu_btn.setToolTip("Plus")
        self.menu_btn.setCursor(Qt.PointingHandCursor)
        self.menu_btn.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self.menu_btn)
        act_settings = QAction("Paramètres…", self)
        act_settings.triggered.connect(self._open_settings)
        act_about = QAction("À propos de SpoolScribe", self)
        act_about.triggered.connect(self._open_about)
        menu.addAction(act_settings)
        menu.addSeparator()
        menu.addAction(act_about)
        self.menu_btn.setMenu(menu)
        top.addWidget(self.menu_btn)
        root.addLayout(top)

        # Ligne de stats discrète sous la barre.
        self.stats_label = QLabel()
        self.stats_label.setObjectName("stats")
        self._muted_labels.append(self.stats_label)
        root.addWidget(self.stats_label)

        # Barre de progression (cachée par défaut)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        self.progress.setFixedHeight(16)
        root.addWidget(self.progress)

        # ── Splitter : liste/grille à gauche, panneau à droite ──────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)

        # Pile des deux présentations : table (liste) + grille de cartes
        self.list_stack = QStackedWidget()

        # Vue liste (table)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["", "SKU", "Produit", "Couleur"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setDefaultSectionSize(28)
        hh = self.table.horizontalHeader()
        hh.setHighlightSections(False)
        # Produit occupe l'espace restant (toujours la colonne la plus large) ;
        # SKU et Couleur sont redimensionnables à la souris. Double-clic sur un
        # bord de colonne = ajustement auto au contenu (Qt natif).
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 34)
        hh.setSectionResizeMode(1, QHeaderView.Interactive)   # SKU
        hh.setSectionResizeMode(2, QHeaderView.Stretch)       # Produit (remplit)
        hh.setSectionResizeMode(3, QHeaderView.Interactive)   # Couleur
        hh.setStretchLastSection(False)
        hh.setMinimumSectionSize(46)
        hh.setCascadingSectionResizes(True)
        self.table.setColumnWidth(1, 104)
        self.table.setColumnWidth(3, 150)
        self.table.itemSelectionChanged.connect(self._on_select)
        self.list_stack.addWidget(self.table)

        # Vue grille (cartes)
        self.grid = QListWidget()
        self.grid.setObjectName("grid")
        self.grid.setViewMode(QListWidget.IconMode)
        self.grid.setResizeMode(QListWidget.Adjust)
        self.grid.setMovement(QListWidget.Static)
        self.grid.setUniformItemSizes(True)
        self.grid.setIconSize(QSize(72, 72))
        self.grid.setGridSize(QSize(136, 124))
        self.grid.setSpacing(4)
        self.grid.setWordWrap(True)
        self.grid.setTextElideMode(Qt.ElideRight)
        self.grid.itemSelectionChanged.connect(self._on_select_grid)
        self.list_stack.addWidget(self.grid)

        splitter.addWidget(self.list_stack)

        # ── Panneau droit : pile (état vide / fiche) ────────────────────
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_empty_page())

        detail_inner = self._build_detail_page()
        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setFrameShape(QFrame.NoFrame)
        detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        detail_scroll.setWidget(detail_inner)
        self.stack.addWidget(detail_scroll)

        splitter.addWidget(self.stack)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([580, 460])

        self.status = self.statusBar()
        self.status.showMessage("Prêt.")

    # ── Page « aucun filament sélectionné » ──────────────────────────────
    def _build_empty_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(32, 0, 32, 0)
        lay.setSpacing(0)

        # ── Respiration verticale ────────────────────────────────────────
        lay.addStretch(2)

        # ── Logo animé centré ────────────────────────────────────────────
        app_logo_path = core.app_logo_abs_path()
        if HAS_SVG and app_logo_path:
            logo_w = SpinningLogo(app_logo_path, size=108)
        else:
            logo_w = QLabel()
            ic = core.app_icon_abs_path()
            if ic:
                logo_w.setPixmap(QPixmap(ic).scaled(
                    108, 108, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            logo_w.setFixedSize(108, 108)
        logo_row = QHBoxLayout()
        logo_row.addStretch(1)
        logo_row.addWidget(logo_w)
        logo_row.addStretch(1)
        lay.addLayout(logo_row)

        lay.addSpacing(20)

        # ── Titre ────────────────────────────────────────────────────────
        title = QLabel("Aucun filament sélectionné")
        tf = QFont()
        tf.setPointSize(17)
        tf.setWeight(QFont.DemiBold)
        title.setFont(tf)
        title.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        lay.addWidget(title)

        lay.addSpacing(12)

        # ── Sous-texte : trois lignes séparées, chacune centrée ──────────
        lines = [
            "Choisissez une référence dans la liste",
            "ou utilisez la barre de recherche.",
            "Basculez entre vue liste et grille en haut à droite.",
        ]
        for i, txt in enumerate(lines):
            lbl = QLabel(txt)
            lbl.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            lf = QFont()
            lf.setPointSize(10 if i == 2 else 11)
            lbl.setFont(lf)
            self._muted_labels.append(lbl)
            lay.addWidget(lbl)
            if i < len(lines) - 1:
                lay.addSpacing(2)

        # ── Respiration verticale ────────────────────────────────────────
        lay.addStretch(3)
        return page

    # ── Page fiche détaillée ─────────────────────────────────────────────
    def _build_detail_page(self) -> QWidget:
        page = QWidget()
        dl = QVBoxLayout(page)
        dl.setContentsMargins(14, 6, 8, 8)
        dl.setSpacing(12)

        # En-tête : logo de marque + titre/SKU
        head = QHBoxLayout()
        head.setSpacing(12)
        self.logo = QLabel()
        # Largeur généreuse (160 px) pour accueillir les wordmarks larges type
        # ROSA3D (334×94). La hauteur reste bornée à 52 px de contenu rendu.
        self.logo.setFixedSize(160, 52)
        self.logo.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        head.addWidget(self.logo, 0, Qt.AlignTop)

        titles = QVBoxLayout()
        titles.setSpacing(3)
        self.title = QLabel("—")
        f = QFont()
        f.setPointSize(18)
        f.setWeight(QFont.Bold)
        self.title.setFont(f)
        self.title.setWordWrap(True)
        titles.addWidget(self.title)
        # SKU sur la première ligne, nom de couleur sur la deuxième — évite
        # que les SKU très longs écrasent le logo vers la gauche.
        self.subtitle_sku = QLabel("")
        self.subtitle_sku.setObjectName("subtitle_sku")
        self._muted_labels.append(self.subtitle_sku)
        titles.addWidget(self.subtitle_sku)
        self.subtitle_color = QLabel("")
        self.subtitle_color.setObjectName("subtitle_color")
        self._muted_labels.append(self.subtitle_color)
        titles.addWidget(self.subtitle_color)
        # Gardé pour compatibilité avec le reste du code (non affiché).
        self.subtitle = self.subtitle_sku
        head.addLayout(titles, 1)
        dl.addLayout(head)

        # Bande couleur (avec le HEX écrit dessus, donc auto-explicite)
        self.color_caption = QLabel("Couleur")
        self.color_caption.setObjectName("caption")
        self._muted_labels.append(self.color_caption)
        dl.addWidget(self.color_caption)
        self.swatch = QLabel("—")
        self.swatch.setObjectName("swatch")
        self.swatch.setAlignment(Qt.AlignCenter)
        self.swatch.setFixedHeight(40)
        sf = self.swatch.font()
        sf.setBold(True)
        sf.setPointSize(max(11, sf.pointSize() + 2))
        sf.setLetterSpacing(QFont.AbsoluteSpacing, 1.5)
        self.swatch.setFont(sf)
        dl.addWidget(self.swatch)

        # Carte des caractéristiques
        self.card = QFrame()
        self.card.setObjectName("card")
        cf = self.card.font()
        cf.setPointSize(max(11, cf.pointSize() + 1))
        self.card.setFont(cf)
        self.fields = QGridLayout(self.card)
        self.fields.setContentsMargins(16, 14, 16, 14)
        self.fields.setVerticalSpacing(9)
        self.fields.setHorizontalSpacing(16)
        self.fields.setColumnStretch(1, 1)

        self._field_widgets: dict[str, QLabel] = {}
        labels = ["Produit", "Type", "Couleur", "SKU", "Nozzle",
                  "Bed", "Densité", "Diamètre", "Marque"]
        for i, name in enumerate(labels):
            lab = QLabel(name)
            lab.setObjectName("fieldname")
            self._muted_labels.append(lab)
            val = QLabel("—")
            val.setObjectName("fieldvalue")
            val.setWordWrap(True)
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.fields.addWidget(lab, i, 0, Qt.AlignTop)
            self.fields.addWidget(val, i, 1)
            self._field_widgets[name] = val
        dl.addWidget(self.card)

        # Respiration au-dessus de l'action principale (la centre verticalement).
        dl.addStretch(1)

        # Action principale : c'est LA fonction de l'app → grande, pleine
        # largeur, bien en évidence au milieu du panneau.
        self.btn_generate = QPushButton("Générer le tag NFC")
        self.btn_generate.setObjectName("primary")
        self.btn_generate.setCursor(Qt.PointingHandCursor)
        self.btn_generate.setMinimumHeight(48)
        self.btn_generate.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        gf = self.btn_generate.font()
        gf.setPointSize(max(11, gf.pointSize() + 2))
        gf.setWeight(QFont.DemiBold)
        self.btn_generate.setFont(gf)
        self.btn_generate.clicked.connect(self._generate)
        dl.addWidget(self.btn_generate)

        # Actions secondaires juste sous l'action principale.
        sec = QHBoxLayout()
        sec.setSpacing(8)
        self.btn_inspect = QPushButton("Inspecter le JSON")
        self.btn_inspect.setObjectName("secondary")
        self.btn_inspect.setCursor(Qt.PointingHandCursor)
        self.btn_inspect.clicked.connect(self._toggle_inspect)
        self.btn_open_out = QPushButton("Dossier d'export")
        self.btn_open_out.setObjectName("secondary")
        self.btn_open_out.setCursor(Qt.PointingHandCursor)
        self.btn_open_out.clicked.connect(self._open_output)
        sec.addWidget(self.btn_inspect)
        sec.addWidget(self.btn_open_out)
        dl.addLayout(sec)

        # Zone d'inspection JSON (repliée par défaut, hauteur fixe pour
        # que le toggle puisse agrandir/rétrécir la fenêtre de façon prévisible).
        self.inspector = QPlainTextEdit()
        self.inspector.setReadOnly(True)
        self.inspector.setVisible(False)
        self.inspector.setFixedHeight(_INSPECTOR_H)
        self.inspector.setFont(QFont("Consolas" if os.name == "nt" else "monospace", 9))
        dl.addWidget(self.inspector)
        return page

    # ── Application du thème (clair / sombre) ────────────────────────────
    def _apply_theme(self):
        t = theme_tokens(self.app)
        self._tok = t
        muted, faint, accent = t["muted"], t["faint"], t["accent"]

        # Palette de base re-synchronisée (utile en mode auto quand l'OS bascule).
        try:
            self.app.setPalette(build_palette(t["dark"]))
        except Exception:
            pass

        for lab in self._muted_labels:
            name = lab.objectName()
            if name == "caption":
                lab.setStyleSheet(
                    f"color:{faint}; font-size:11px; "
                    f"text-transform:uppercase; letter-spacing:1px;")
            elif name == "stats":
                lab.setStyleSheet(f"color:{faint}; font-size:11px;")
            else:
                lab.setStyleSheet(f"color:{muted};")

        primary_qss = (
            f"QPushButton#primary {{ background:{accent}; color:{t['accent_text']};"
            f" border:none; border-radius:7px; padding:7px 16px; font-weight:600; }}"
            f"QPushButton#primary:hover {{ background:{t['accent_hover']}; }}"
            f"QPushButton#primary:disabled {{ background:{t['sec_bg']}; color:{faint}; }}"
        )
        secondary_qss = (
            f"QPushButton#secondary {{ background:{t['sec_bg']}; border:1px solid {t['border']};"
            f" border-radius:7px; padding:7px 14px; }}"
            f"QPushButton#secondary:hover {{ background:{t['sec_hover']}; }}"
        )
        search_qss = (
            f"QLineEdit#search {{ border:1px solid {t['border']}; border-radius:7px;"
            f" padding:6px 10px; background:{t['field_bg']}; }}"
            f"QLineEdit#search:focus {{ border:1px solid {accent}; }}"
        )
        card_qss = (
            f"QFrame#card {{ background:{t['card']}; border:1px solid {t['border']};"
            f" border-radius:10px; }}"
        )
        seg_qss = (
            f"QFrame#segwrap {{ background:{t['sec_bg']}; border:1px solid {t['border']};"
            f" border-radius:9px; }}"
            f"QToolButton#seg {{ background:transparent; border:none; border-radius:6px;"
            f" padding:5px 12px; }}"
            f"QToolButton#seg:hover {{ background:{t['sec_hover']}; }}"
            f"QToolButton#seg:checked {{ background:{t['accent']}; }}"
        )
        ghost_qss = (
            f"QToolButton#ghost {{ background:transparent; border:1px solid {t['border']};"
            f" border-radius:7px; padding:4px 10px; font-size:16px; color:{muted}; }}"
            f"QToolButton#ghost:hover {{ background:{t['sec_hover']}; }}"
            f"QToolButton#ghost::menu-indicator {{ image:none; width:0; }}"
        )
        grid_qss = (
            f"QListWidget#grid {{ background:transparent; border:none;"
            f" show-decoration-selected:1; outline:0;"
            f" selection-background-color:transparent; selection-color:{t['text']}; }}"
            f"QListWidget#grid::item {{ border:1px solid {t['border']}; border-radius:10px;"
            f" margin:4px; padding:8px 4px; color:{t['muted']}; }}"
            f"QListWidget#grid::item:selected {{ border:1px solid {accent};"
            f" background:{t['card']}; color:{t['text']}; }}"
            f"QListWidget#grid::item:hover {{ border:1px solid {accent}; }}"
        )
        # Surfaces de base stylées *par type* (jamais un sélecteur QWidget
        # global : sur Windows il brouille tout le rendu). Dès qu'une feuille
        # de style est active, Qt ignore la palette pour ces widgets — d'où des
        # règles explicites et opaques, identiques en mode auto comme forcé.
        base_qss = (
            f"QMainWindow {{ background:{t['window']}; }}"
            f"QDialog {{ background:{t['window']}; }}"
            f"QLabel {{ color:{t['text']}; background:transparent; }}"
            f"QToolTip {{ background:{t['card']}; color:{t['text']};"
            f" border:1px solid {t['border']}; }}"
            f"QTableWidget, QTableView {{ background:{t['base']}; color:{t['text']};"
            f" alternate-background-color:{t['alt']}; border:1px solid {t['border']};"
            f" border-radius:8px; gridline-color:{t['border']};"
            f" selection-background-color:{t['sel']}; selection-color:{t['sel_text']};"
            f" outline:0; }}"
            f"QTableView::item {{ padding:2px 6px; color:{t['text']}; }}"
            f"QTableView::item:selected {{ background:{t['sel']}; color:{t['sel_text']}; }}"
            f"QHeaderView {{ background:{t['header']}; }}"
            f"QHeaderView::section {{ background:{t['header']}; color:{t['muted']};"
            f" border:none; border-right:1px solid {t['border']};"
            f" border-bottom:1px solid {t['border']}; padding:5px 8px; font-weight:600; }}"
            f"QTableCornerButton::section {{ background:{t['header']};"
            f" border:none; border-bottom:1px solid {t['border']}; }}"
            f"QPlainTextEdit {{ background:{t['base']}; color:{t['text']};"
            f" border:1px solid {t['border']}; border-radius:8px;"
            f" selection-background-color:{t['sel']}; selection-color:{t['sel_text']}; }}"
            f"QMenu {{ background:{t['card']}; color:{t['text']};"
            f" border:1px solid {t['border']}; }}"
            f"QMenu::item {{ padding:5px 18px; }}"
            f"QMenu::item:selected {{ background:{t['sel']}; color:{t['sel_text']}; }}"
            f"QMenu::separator {{ height:1px; background:{t['border']}; margin:4px 8px; }}"
            f"QStatusBar {{ background:{t['window']}; color:{t['faint']}; }}"
            f"QStatusBar::item {{ border:none; }}"
            f"QComboBox {{ background:{t['field_bg']}; color:{t['text']};"
            f" border:1px solid {t['border']}; border-radius:6px; padding:4px 8px; }}"
            f"QComboBox QAbstractItemView {{ background:{t['card']}; color:{t['text']};"
            f" selection-background-color:{t['sel']}; selection-color:{t['sel_text']}; }}"
            f"QSpinBox {{ background:{t['field_bg']}; color:{t['text']};"
            f" border:1px solid {t['border']}; border-radius:6px; padding:3px 6px; }}"
            f"QCheckBox {{ color:{t['text']}; background:transparent; }}"
            f"QProgressBar {{ background:{t['field_bg']}; color:{t['text']};"
            f" border:1px solid {t['border']}; border-radius:6px; text-align:center; }}"
            f"QProgressBar::chunk {{ background:{accent}; border-radius:5px; }}"
            f"QScrollBar:vertical {{ background:transparent; width:11px; margin:2px; }}"
            f"QScrollBar::handle:vertical {{ background:{t['border']};"
            f" border-radius:5px; min-height:28px; }}"
            f"QScrollBar::handle:vertical:hover {{ background:{t['faint']}; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}"
            f"QScrollBar:horizontal {{ background:transparent; height:11px; margin:2px; }}"
            f"QScrollBar::handle:horizontal {{ background:{t['border']};"
            f" border-radius:5px; min-width:28px; }}"
            f"QScrollBar::handle:horizontal:hover {{ background:{t['faint']}; }}"
            f"QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}"
        )
        self.setStyleSheet(base_qss + primary_qss + secondary_qss + search_qss
                           + card_qss + seg_qss + ghost_qss + grid_qss
                           + f"QLabel#fieldvalue {{ color:{t['text']}; }}")

        # Titre de la fiche : contraste fort, indépendant du palette OS.
        if hasattr(self, "title"):
            self.title.setStyleSheet(f"color:{t['text']};")

        # Rafraîchit la bande couleur si une fiche est affichée.
        if self.current_sku:
            self._paint_swatch()
        else:
            self.swatch.setStyleSheet(
                f"#swatch {{ background:{t['field_bg']}; color:{faint};"
                f" border:1px dashed {t['border']}; border-radius:8px; }}")
        if hasattr(self, "btn_view_list"):
            self._update_seg_icons()

    def _show_empty(self):
        self.stack.setCurrentIndex(0)

    def _show_card(self):
        self.stack.setCurrentIndex(1)


    # ── Données / table ──────────────────────────────────────────────────
    def _reload_table(self):
        self._all_rows = core.list_skus(self.db)
        self._populate(self._all_rows)

    def _populate(self, rows):
        dpr = self.devicePixelRatioF()
        self._rows = rows
        # Vue liste
        self.table.setRowCount(0)
        self.table.setRowCount(len(rows))
        for r, e in enumerate(rows):
            sw = QTableWidgetItem()
            sw.setIcon(QIcon(make_swatch_pixmap(e.get("hex"), 18, dpr)))
            self.table.setItem(r, 0, sw)
            self.table.setItem(r, 1, QTableWidgetItem(e["sku"]))
            self.table.setItem(r, 2, QTableWidgetItem(e["product"]))
            color_item = QTableWidgetItem(e["color_name"])
            if not e.get("hex"):
                color_item.setForeground(QColor("#b00"))
            self.table.setItem(r, 3, color_item)
        # Vue grille
        self.grid.clear()
        for e in rows:
            it = QListWidgetItem()
            it.setIcon(QIcon(make_swatch_pixmap(e.get("hex"), 72, dpr, radius=12)))
            it.setText(f"{e['sku']}\n{e['color_name']}")
            it.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            it.setData(Qt.UserRole, e["sku"])
            it.setToolTip(f"{e['product']} · {e['color_name']}")
            self.grid.addItem(it)
        # Plus de sélection valide → revenir à l'état vide.
        if hasattr(self, "stack") and not self.table.selectedItems():
            self.current_sku = None
            self._show_empty()

    def _set_view_mode(self, mode: str):
        self.view_mode = mode
        self.list_stack.setCurrentIndex(0 if mode == "list" else 1)
        self._update_seg_icons()
        # Re-sélectionne la SKU courante dans la vue active.
        if self.current_sku:
            if mode == "grid":
                for i in range(self.grid.count()):
                    if self.grid.item(i).data(Qt.UserRole) == self.current_sku:
                        self.grid.setCurrentRow(i)
                        break
            else:
                for r in range(self.table.rowCount()):
                    it = self.table.item(r, 1)
                    if it and it.text() == self.current_sku:
                        self.table.selectRow(r)
                        break

    def _on_select_grid(self):
        items = self.grid.selectedItems()
        if not items:
            return
        sku = items[0].data(Qt.UserRole)
        if sku:
            self.current_sku = sku
            self._show_detail(sku)

    def _update_seg_icons(self):
        """Icône blanche pour la vue active, atténuée pour l'autre."""
        dpr = self.devicePixelRatioF()
        active = getattr(self, "_tok", {}).get("accent_text", "#fff")
        idle = getattr(self, "_tok", {}).get("muted", "#888")
        self.btn_view_list.setIcon(make_view_icon(
            "list", active if self.view_mode == "list" else idle, 18, dpr))
        self.btn_view_grid.setIcon(make_view_icon(
            "grid", active if self.view_mode == "grid" else idle, 18, dpr))

    def _apply_filter(self, text):
        t = text.strip().lower()
        if not t:
            self._populate(self._all_rows)
            return
        filtered = [
            e for e in self._all_rows
            if t in e["sku"].lower() or t in e["product"].lower() or t in e["color_name"].lower()
        ]
        self._populate(filtered)

    def _update_stats(self):
        st = core.db_stats(self.db)
        age = core.db_age_days(self.db)
        age_str = f"{age:.0f} j" if age is not None else "?"
        self.stats_label.setText(
            f"SKUs: {st['skus']}    Produits: {st['products']}    "
            f"HEX manquants: {st['missing_hex']}    DB: {age_str}"
        )

    def _refresh_logo(self, brand: str = "Polymaker"):
        abs_path = core.logo_abs_path(self.db, brand)
        dark = bool(getattr(self, "_tok", {}).get("dark"))
        # Hauteur max = 52 px, largeur max = 160 px (widget du logo).
        # load_brand_pixmap respecte l'aspect-ratio : les logos carrés (Polymaker,
        # Prusament) tiennent en 52×52, les wordmarks larges (ROSA3D 334×94)
        # s'étendent jusqu'à 160 px de large sans être écrasés.
        pm = (
            load_brand_pixmap(abs_path, 52, self.devicePixelRatioF(), max_w=160)
            if abs_path else None
        )
        if pm and not pm.isNull():
            if dark:
                pm = add_soft_halo(pm, radius=7.0)
            self.logo.setPixmap(pm)
            self.logo.setVisible(True)
            return
        # Marque sans logo : on masque le widget.
        self.logo.setPixmap(QPixmap())
        self.logo.setVisible(False)

    # ── Sélection ────────────────────────────────────────────────────────
    def _on_select(self):
        items = self.table.selectedItems()
        if not items:
            return
        row = items[0].row()
        sku_item = self.table.item(row, 1)
        if not sku_item:
            return
        self.current_sku = sku_item.text()
        self._show_detail(self.current_sku)

    def _paint_swatch(self):
        """Peint la bande couleur avec le HEX écrit dessus (texte contrasté)."""
        t = self._tok
        h = (getattr(self, "_cur_hex", None) or "").strip().lstrip("#")
        if len(h) == 6:
            self.swatch.setText(f"#{h.upper()}")
            self.swatch.setStyleSheet(
                f"#swatch {{ background:#{h}; color:{contrast_text(h)};"
                f" border:1px solid {t['border']}; border-radius:8px; letter-spacing:1px; }}")
        else:
            self.swatch.setText("HEX inconnu")
            self.swatch.setStyleSheet(
                f"#swatch {{ background:{t['field_bg']}; color:{t['faint']};"
                f" border:1px dashed {t['border']}; border-radius:8px;"
                f" letter-spacing:1px; }}")

    def _show_detail(self, sku):
        view = core.get_sku_view(self.db, sku)
        self._show_card()
        if view is None:
            self.title.setText(f"{sku} — produit introuvable")
            self.subtitle_sku.setText("")
            self.subtitle_color.setText("")
            for v in self._field_widgets.values():
                v.setText("—")
            self._cur_hex = None
            self._paint_swatch()
            self.btn_generate.setEnabled(False)
            self.btn_inspect.setEnabled(False)
            return

        self.title.setText(view.product)
        self.subtitle_sku.setText(view.sku)
        self.subtitle_color.setText(view.color_name or "")
        self._field_widgets["Produit"].setText(view.product)
        self._field_widgets["Type"].setText(view.type_str)
        self._field_widgets["Couleur"].setText(view.color_name or "—")
        self._field_widgets["SKU"].setText(view.sku)
        self._field_widgets["Nozzle"].setText(view.nozzle_str)
        self._field_widgets["Bed"].setText(view.bed_str)
        self._field_widgets["Densité"].setText(view.density_str)
        self._field_widgets["Diamètre"].setText(view.diameter_str)
        self._field_widgets["Marque"].setText(view.product_data.get("brand", "Polymaker"))

        self._refresh_logo(view.product_data.get("brand", "Polymaker"))

        self._cur_hex = view.hex
        self._paint_swatch()

        self.btn_generate.setEnabled(True)
        self.btn_inspect.setEnabled(True)
        if self.inspector.isVisible():
            self._refresh_inspector()

    def _build_payload(self):
        view = core.get_sku_view(self.db, self.current_sku)
        if view is None:
            return None
        entry = dict(self.db["_skus"][self.current_sku])
        entry["sku"] = self.current_sku
        return core.build_openspool(entry, view.product_data, brand_meta=view.brand_meta)

    # ── Actions ──────────────────────────────────────────────────────────
    def _generate(self):
        if not self.current_sku:
            return
        try:
            view = core.get_sku_view(self.db, self.current_sku)
            entry = self.db["_skus"][self.current_sku]
            out = core.write_openspool(self.current_sku, entry, view.product_data,
                                       brand_meta=view.brand_meta)
            self.status.showMessage(f"Généré : {out}", 8000)
            QMessageBox.information(self, "Export OpenSpool",
                                    f"Fichier généré :\n{out}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Échec de l'export :\n{e}")

    def _toggle_inspect(self):
        if self.inspector.isVisible():
            self.inspector.setVisible(False)
            self.btn_inspect.setText("Inspecter le JSON")
            new_h = max(self.height() - _INSPECTOR_DELTA, self.minimumHeight())
            self.resize(self.width(), new_h)
        else:
            self._refresh_inspector()
            self.inspector.setVisible(True)
            self.btn_inspect.setText("Masquer le JSON")
            avail = QApplication.primaryScreen().availableGeometry().height()
            new_h = min(self.height() + _INSPECTOR_DELTA, avail - 60)
            self.resize(self.width(), new_h)

    def _refresh_inspector(self):
        payload = self._build_payload()
        if payload is not None:
            self.inspector.setPlainText(json.dumps(payload, indent=2, ensure_ascii=False))

    def _open_output(self):
        out_dir = core.OUTPUT_DIR
        os.makedirs(out_dir, exist_ok=True)
        try:
            if sys.platform.startswith("win"):
                os.startfile(out_dir)  # noqa
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", out_dir])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", out_dir])
        except Exception as e:
            QMessageBox.warning(self, "Ouverture", f"Impossible d'ouvrir le dossier :\n{e}")

    # ── Mise à jour DB ───────────────────────────────────────────────────
    def _ask_network_consent(self) -> bool:
        """Affiche les sources et demande le consentement réseau explicite."""
        if core.has_network_consent():
            return True
        sources = "\n".join(
            f"  • {s['name']}  [{s['license']}]\n      {s['host']}"
            for s in core.NETWORK_SOURCES
        )
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("Mise à jour des données — accès réseau")
        box.setText(
            "Cette action va télécharger des données depuis Internet.\n"
            "Aucune donnée personnelle n'est envoyée.\n\n"
            "Sources contactées :"
        )
        box.setDetailedText(sources)
        box.setInformativeText("Autoriser les mises à jour réseau ?")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        consent = box.exec() == QMessageBox.Yes
        core.set_network_consent(consent)
        return consent

    def _start_update(self):
        if self.worker and self.worker.isRunning():
            return
        if not self._ask_network_consent():
            self.status.showMessage("Mise à jour annulée (réseau refusé).", 6000)
            return
        self.update_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, len(core.UPDATE_PIPELINE))
        self.progress.setValue(0)
        self.status.showMessage("Mise à jour en cours…")

        self.worker = UpdateWorker()
        self.worker.progress.connect(self._on_update_progress)
        self.worker.finished_ok.connect(self._on_update_done)
        self.worker.failed.connect(self._on_update_failed)
        self.worker.start()

    def _on_update_progress(self, label, i, total):
        self.progress.setValue(i)
        self.progress.setFormat(f"{i}/{total} — {label}")

    def _on_update_done(self, results):
        self.progress.setVisible(False)
        self.update_btn.setEnabled(True)
        self.db = core.load_db()
        self._reload_table()
        self._refresh_logo()
        self._update_stats()
        if self.current_sku:
            self._show_detail(self.current_sku)
        n_ok = sum(1 for r in results if r.ok)
        n_ko = [r for r in results if not r.ok]
        msg = f"Mise à jour terminée — {n_ok}/{len(results)} étapes OK."
        self.status.showMessage(msg, 10000)
        if n_ko:
            def _reason(r):
                err = (r.stderr or "").strip().replace("\r", "")
                if not err:
                    return f"• {r.label} (code {r.code})"
                last = err.splitlines()[-1].strip()
                if len(last) > 160:
                    last = last[:157] + "…"
                return f"• {r.label} (code {r.code}) — {last}"

            detail = "\n".join(_reason(r) for r in n_ko)
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle("Mise à jour partielle")
            box.setText(f"{msg}\n\nÉtapes en échec :\n{detail}")
            full = "\n\n".join(
                f"=== {r.label} (code {r.code}) ===\n{(r.stderr or '(aucun message)').strip()}"
                for r in n_ko
            )
            box.setDetailedText(full)
            box.exec()

    def _on_update_failed(self, tb):
        self.progress.setVisible(False)
        self.update_btn.setEnabled(True)
        QMessageBox.critical(self, "Erreur de mise à jour", tb)

    # ── Mise à jour automatique ──────────────────────────────────────────
    def _maybe_auto_update(self):
        """Lance une mise à jour au démarrage si l'option est activée et due."""
        try:
            cfg = core.load_config()
        except Exception:
            return
        if not cfg.get("auto_update") or not core.has_network_consent():
            return
        interval = int(cfg.get("update_interval_days", 7) or 7)
        if core.db_needs_update(self.db, interval):
            self.status.showMessage("Mise à jour automatique en cours…", 4000)
            self._start_update()

    # ── Paramètres ───────────────────────────────────────────────────────
    def _open_settings(self):
        cfg = core.load_config()
        dlg = QDialog(self)
        dlg.setWindowTitle("Paramètres")
        dlg.setMinimumWidth(380)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)
        lay.setContentsMargins(18, 18, 18, 14)

        chk_auto = QCheckBox("Mettre à jour automatiquement la base au démarrage")
        chk_auto.setChecked(bool(cfg.get("auto_update")))
        lay.addWidget(chk_auto)

        row = QHBoxLayout()
        row.addWidget(QLabel("Intervalle de mise à jour :"))
        spin = QSpinBox()
        spin.setRange(1, 90)
        spin.setSuffix(" jours")
        spin.setValue(int(cfg.get("update_interval_days", 7) or 7))
        row.addWidget(spin)
        row.addStretch(1)
        lay.addLayout(row)

        note = QLabel(
            "La mise à jour reste soumise à votre consentement réseau, demandé "
            "une seule fois. Aucune donnée personnelle n'est envoyée."
        )
        note.setWordWrap(True)
        self._muted_labels.append(note)
        note.setStyleSheet(f"color:{self._tok['faint']}; font-size:11px;")
        lay.addWidget(note)

        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)

        if dlg.exec() == QDialog.Accepted:
            cfg["auto_update"] = chk_auto.isChecked()
            cfg["update_interval_days"] = spin.value()
            core.save_config(cfg)
            self.status.showMessage("Paramètres enregistrés.", 4000)

    # ── À propos ─────────────────────────────────────────────────────────
    def _open_about(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("À propos de SpoolScribe")
        dlg.setMinimumWidth(420)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(22, 20, 22, 16)
        lay.setSpacing(12)

        head = QHBoxLayout()
        head.setSpacing(14)
        logo_path = core.app_logo_abs_path()
        logo = QLabel()
        pm = load_brand_pixmap(logo_path, 72, self.devicePixelRatioF()) if logo_path else None
        if pm is None:
            ic = core.app_icon_abs_path()
            if ic:
                pm = QPixmap(ic).scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if pm:
            logo.setPixmap(pm)
        head.addWidget(logo, 0, Qt.AlignTop)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        name = QLabel("SpoolScribe")
        nf = QFont()
        nf.setPointSize(16)
        nf.setBold(True)
        name.setFont(nf)
        titles.addWidget(name)
        ver = QLabel(f"Version {core.APP_VERSION}")
        ver.setStyleSheet(f"color:{self._tok['muted']};")
        titles.addWidget(ver)
        head.addLayout(titles, 1)
        lay.addLayout(head)

        desc = QLabel(
            "Écrit des tags OpenSpool / NFC pour le Snapmaker U1 à firmware "
            "ouvert. Recherche un filament (Polymaker, Prusament, ROSA3D), "
            "affiche sa couleur et ses températures, et génère le payload JSON.\n\n"
            "Projet hobby, non affilié à Polymaker, Prusa Research, ROSA3D ou "
            "Snapmaker. Licence MIT.\n\n"
            "Couleurs : SpoolmanDB (MIT) · TheFilamentDB (CC-BY 4.0). "
            "Logos de marque : Open Filament Database (MIT)."
        )
        desc.setWordWrap(True)
        desc.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(desc)

        link = QLabel(
            '<a href="https://github.com/ArN-LaB/Spoolscribe-">'
            'github.com/ArN-LaB/Spoolscribe-</a>'
        )
        link.setOpenExternalLinks(True)
        lay.addWidget(link)

        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(dlg.reject)
        bb.accepted.connect(dlg.accept)
        bb.button(QDialogButtonBox.Close).clicked.connect(dlg.accept)
        lay.addWidget(bb)
        dlg.exec()


def main():
    # Mode worker (exécutable gelé relançant un scraper) : agir puis sortir.
    if core.maybe_run_as_script_worker(sys.argv):
        return
    # Qt 6 ne livre plus ses propres polices ; pointer vers les polices
    # système *avant* QApplication pour supprimer l'avertissement de démarrage.
    if "QT_QPA_FONTDIR" not in os.environ:
        if os.name == "nt":
            winfonts = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Fonts")
            if os.path.isdir(winfonts):
                os.environ["QT_QPA_FONTDIR"] = winfonts
        else:
            for d in ("/usr/share/fonts", "/System/Library/Fonts"):
                if os.path.isdir(d):
                    os.environ["QT_QPA_FONTDIR"] = d
                    break
    app = QApplication(sys.argv)
    app.setApplicationName("SpoolScribe")
    # Police de base légèrement agrandie pour plus de présence visuelle.
    try:
        bf = app.font()
        bf.setPointSizeF(bf.pointSizeF() + 0.5)
        app.setFont(bf)
    except Exception:
        pass
    # Style Fusion + palette d'après le thème système (clair / sombre).
    try:
        init_theme(app)
    except Exception:
        pass
    icon_path = core.app_icon_abs_path()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

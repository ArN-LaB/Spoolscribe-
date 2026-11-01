#!/usr/bin/env python3
"""
app_gui.py — Application graphique multiplateforme (Windows / macOS / Linux).

Construite sur PySide6 (Qt). Toute la logique métier vient de core.py :
cette couche ne fait que de l'affichage et de l'orchestration UI.

Lancement :  python app_gui.py
"""
from __future__ import annotations

import os
import sys
import time
import functools
import threading
import traceback

from PySide6.QtCore import Qt, QThread, Signal, QSize, QTimer, QRectF, QLockFile
from PySide6.QtGui import (
    QColor, QFont, QPixmap, QPainter, QIcon, QPalette, QPainterPath, QAction, QPen,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLineEdit, QTableWidget, QTableWidgetItem, QLabel, QPushButton, QPlainTextEdit,
    QHeaderView, QAbstractItemView, QFrame, QMessageBox, QProgressBar, QGridLayout, QTabWidget,
    QSizePolicy, QStackedWidget, QToolButton, QMenu, QListWidget, QListWidgetItem,
    QDialog, QDialogButtonBox, QCheckBox, QSpinBox, QButtonGroup, QComboBox,
    QScrollArea,
)

try:
    from PySide6.QtSvg import QSvgRenderer
    HAS_SVG = True
except Exception:
    HAS_SVG = False

import core
from ui_catalogue import CatalogueUx, ClearableTable, ClearableList
from ui_widgets import SpoolPreview, MetricGrid, WrapLabel, FilamentDelegate, spool_icon, product_label, DetailScrollArea, CONTROL_HEIGHT

# Hauteur fixe de l'inspecteur JSON + espacement du layout (12 px) = delta
# appliqué à la fenêtre lors du toggle pour éviter tout scroll parasite.
_INSPECTOR_H = 210
_INSPECTOR_DELTA = _INSPECTOR_H + 12
# Coche des cases à cocher (QSS) : chemin POSIX absolu, lisible aussi en mode gelé.
CHECK_ICON_PATH = os.path.join(core.RESOURCE_DIR, "data", "check.svg").replace(os.sep, "/")
CHEVRON_ICON_PATH = os.path.join(core.RESOURCE_DIR, "data", "chevron-down.svg").replace(os.sep, "/")


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
    """Exécute la pipeline de scrapers sans bloquer l'UI ; annulable entre deux sondages."""
    progress = Signal(str, int, int)   # label, index, total
    finished_ok = Signal(list)         # list[core.StepResult]
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cancel = threading.Event()

    def run(self):
        try:
            results = core.run_update_pipeline(
                progress=lambda label, i, total: self.progress.emit(label, i, total),
                consent=core.has_network_consent(),
                cancel=self.cancel,
            )
            self.finished_ok.emit(results)
        except Exception:
            self.failed.emit(traceback.format_exc())


def fmt_int(value: int) -> str:
    """Nombre avec séparateur de milliers français (espace fine insécable)."""
    return f"{value:,}".replace(",", "\u202f")


# ─── Pastille couleur ─────────────────────────────────────────────────────
@functools.lru_cache(maxsize=4096)
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


MIN_RASTER_LOGO_PX = 24


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
            if not renderer.isValid():
                return None
            vb = renderer.viewBoxF()
            src_w = vb.width()  if vb.width()  > 0 else pw
            src_h = vb.height() if vb.height() > 0 else ph
            scale = min(pw / src_w, ph / src_h)
            rw, rh = max(1, int(src_w * scale)), max(1, int(src_h * scale))
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
            if src.isNull() or min(src.width(), src.height()) < MIN_RASTER_LOGO_PX:
                return None  # Too small to stay legible: the brand name is shown instead.
            # A bitmap may be enlarged up to 2× (smooth) so HiDPI screens do not
            # show it at half its intended size; beyond that it would blur.
            pm = src.scaled(min(pw, src.width() * 2), min(ph, src.height() * 2),
                            Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pm.setDevicePixelRatio(dpr)
            return pm
    except Exception:
        return None


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


def configure_application(app: QApplication) -> None:
    """Shared startup configuration for the app and its visual checks."""
    app.setApplicationName('SpoolScribe')
    if not app.property('spoolscribe_configured'):
        font=app.font();font.setPointSizeF(font.pointSizeF()+0.5);app.setFont(font)
        app.setProperty('spoolscribe_configured',True)
    init_theme(app)
    icon_path=core.app_icon_abs_path()
    if icon_path:app.setWindowIcon(QIcon(icon_path))


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
class MainWindow(CatalogueUx, QMainWindow):
    def __init__(self):
        super().__init__()
        self.app = QApplication.instance()
        self.setWindowTitle(f"SpoolScribe {core.APP_VERSION} — OpenSpool / NFC")
        self.resize(1280, 800)
        self.setMinimumSize(860, 560)

        icon_path = core.app_icon_abs_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        self.db = core.load_db()
        self._default_brand_pending = not self.db.get("_skus")
        self.current_sku: str | None = None
        self.worker: UpdateWorker | None = None
        self._muted_labels: list[QLabel] = []
        self.view_mode = "list"

        self._build_ui()
        self._install_ux()
        self._apply_theme()
        self._reload_table()
        self._refresh_logo()
        self._update_stats()
        self._show_empty()
        self._restore_ui_preferences()

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
        self.__dict__.pop("_logo_cache", None)
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
        self.search.setPlaceholderText("Rechercher : fabricant, matière, référence, couleur…")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedHeight(32)
        self.search.setMinimumWidth(240)
        self.search.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(180)
        self._search_timer.timeout.connect(self._apply_filter)
        self.search.textChanged.connect(lambda *_: self._search_timer.start())
        top.addWidget(self.search, 1)

        # Bascule de vue Liste / Grille (pilule segmentée)
        dpr = self.devicePixelRatioF()
        self.segwrap = QFrame()
        self.segwrap.setObjectName("segwrap")
        seg = QHBoxLayout(self.segwrap)
        self.segwrap.setFixedHeight(32)
        seg.setContentsMargins(2, 2, 2, 2)
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
        for button in (self.btn_view_list,self.btn_view_grid):button.setFixedSize(32,26)
        seg.addWidget(self.btn_view_list)
        seg.addWidget(self.btn_view_grid)
        # View controls sit with the catalogue, below the global search.

        self.update_btn = QPushButton("Synchroniser")
        self.update_btn.setObjectName("primary")
        self.update_btn.setFixedHeight(32)
        self.update_btn.setCursor(Qt.PointingHandCursor)
        self.update_btn.setToolTip("Choisir les sources et actualiser la base")
        self.update_btn.clicked.connect(self._sync_catalogue)
        top.addWidget(self.update_btn)

        # Menu ⚙ : matériel, sources, réglages, à propos
        self.menu_btn = QToolButton()
        self.menu_btn.setObjectName("ghost")
        self.menu_btn.setFixedSize(38,32)
        self.menu_btn.setText("⚙")
        self.menu_btn.setToolTip("Réglages")
        self.menu_btn.setAccessibleName("Réglages")
        self.menu_btn.setCursor(Qt.PointingHandCursor)
        self.menu_btn.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self.menu_btn)
        act_hardware = QAction("Mon matériel…", self)
        act_hardware.triggered.connect(self._open_hardware)
        menu.addAction(act_hardware)
        act_settings = QAction("Paramètres…", self)
        act_settings.triggered.connect(self._open_settings)
        menu.addAction(act_settings)
        menu.addSeparator()
        self.act_archive = QAction("Exporter une archive JSON…", self)
        self.act_archive.triggered.connect(lambda: self._generate(mode="archive"))
        menu.addAction(self.act_archive)
        menu.addSeparator()
        act_about = QAction("À propos de SpoolScribe", self)
        act_about.triggered.connect(self._open_about)
        self._about_action=act_about
        self.menu_btn.setMenu(menu)
        top.addWidget(self.menu_btn)
        root.addLayout(top)

        # Filtres : le modèle reste dans trois listes déroulantes cachées ;
        # la barre latérale (fabricants, matières, état) les pilote.
        self.brand_filter = QComboBox()
        self.brand_filter.setAccessibleName("Filtrer par fabricant")
        self.material_filter = QComboBox()
        self.material_filter.setAccessibleName("Filtrer par matière")
        self.quality_filter = QComboBox()
        for label, key in (("Toutes les fiches", "all"), ("Prêtes à exporter", "ready"),
                           ("À compléter", "incomplete"), ("À vérifier", "suspect")):
            self.quality_filter.addItem(label, key)
        for combo in (self.brand_filter, self.material_filter, self.quality_filter):
            combo.setParent(self)
            combo.hide()
            combo.currentIndexChanged.connect(self._apply_filter)

        sorting = QHBoxLayout()
        self.sort1, self.sort2 = QComboBox(), QComboBox()
        self.sort2.addItem("Aucun", "")
        for key, label in core.CATALOGUE_SORT_FIELDS.items():
            self.sort1.addItem(label, key)
            self.sort2.addItem(label, key)
        self.sort1.setCurrentIndex(self.sort1.findData("brand"))
        self.sort2.setCurrentIndex(self.sort2.findData("product"))
        self.sort1_direction, self.sort2_direction = QComboBox(), QComboBox()
        for direction in (self.sort1_direction, self.sort2_direction):
            direction.addItem("Croissant ↑", False)
            direction.addItem("Décroissant ↓", True)
        # Sorting is controlled only by column headers. These hidden state
        # controls retain the shared sorting model used by list and grid views.
        for combo in (self.sort1, self.sort2, self.sort1_direction, self.sort2_direction):
            combo.setParent(self)
            combo.hide()
            combo.currentIndexChanged.connect(self._apply_filter)

        pager = QHBoxLayout()
        self.page_label = QLabel()
        self.page_label.setWordWrap(False)
        pager.addWidget(self.page_label, 1)
        self.previous_page = QPushButton("← Précédent")
        self.next_page = QPushButton("Suivant →")
        self.previous_page.clicked.connect(lambda: self._change_page(-1))
        self.next_page.clicked.connect(lambda: self._change_page(1))
        pager.addWidget(self.previous_page)
        pager.addWidget(self.next_page)
        self._page = 0
        self._page_size = 250

        # Ligne de stats discrète sous la barre.
        self.stats_label = QLabel()
        self.stats_label.setWordWrap(True)
        self.stats_label.setObjectName("stats")
        self._muted_labels.append(self.stats_label)
        self.stats_label.hide()

        # Barre de progression (cachée par défaut) + annulation
        progress_row = QHBoxLayout()
        self.progress_label = QLabel()
        self.progress_label.setMinimumHeight(24)
        self.progress_label.setVisible(False)
        root.addWidget(self.progress_label)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        progress_row.addWidget(self.progress, 1)
        self.cancel_update_btn = QPushButton("Annuler")
        self.cancel_update_btn.setVisible(False)
        self.cancel_update_btn.setToolTip("Interrompt la synchronisation ; la base locale reste celle d'avant.")
        self.cancel_update_btn.clicked.connect(self._cancel_update)
        progress_row.addWidget(self.cancel_update_btn)
        root.addLayout(progress_row)

        # ── Splitter : facettes · liste/grille · fiche ───────────────────
        splitter = self.splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)
        self.sidebar = self._build_sidebar()
        splitter.addWidget(self.sidebar)

        # Pile des deux présentations : table (liste) + grille de cartes
        self.list_stack = QStackedWidget()

        # Vue liste (table)
        self.table = ClearableTable(0, 9)
        self._column_keys = ("", "reference", "product", "color_name", "brand", "material", "diameter", "weight", "quality")
        self.table.setHorizontalHeaderLabels(["", "Référence", "Produit", "Couleur", "Fabricant", "Matière", "Ø mm", "Masse g", "État des données"])
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
        hh.setSectionResizeMode(2, QHeaderView.Interactive)   # Keep names readable in a wide catalogue.
        hh.setSectionResizeMode(3, QHeaderView.Interactive)   # Couleur
        hh.setStretchLastSection(False)
        hh.setMinimumSectionSize(46)
        hh.setCascadingSectionResizes(True)
        hh.setSectionsClickable(True)
        hh.sectionClicked.connect(self._sort_column)
        hh.setToolTip("Clic : tri principal, second clic : inverser. Maj + clic ou clic droit : tri secondaire et colonnes.")
        self.table.setColumnWidth(1, 110)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)   # Produit absorbe la largeur restante.
        self.table.setColumnWidth(3, 112)
        for column, width in ((4, 96), (5, 70), (6, 54), (7, 62), (8, 122)):
            hh.setSectionResizeMode(column, QHeaderView.Interactive)
            self.table.setColumnWidth(column, width)
        # Référence, diamètre et masse restent disponibles dans « Colonnes » ;
        # masqués par défaut : la fiche liste les références de chaque
        # conditionnement, et le produit garde une largeur lisible.
        for column in (1, 6, 7):
            self.table.setColumnHidden(column, True)
        self.table.itemSelectionChanged.connect(self._on_select)
        self.list_stack.addWidget(self.table)

        # Vue grille (cartes)
        self.grid = ClearableList()
        self.grid.setObjectName("grid")
        self.grid.setViewMode(QListWidget.IconMode)
        self.grid.setResizeMode(QListWidget.Adjust)
        self.grid.setMovement(QListWidget.Static)
        self.grid.setUniformItemSizes(True)
        self.grid.setIconSize(QSize(112, 112))
        self.grid.setGridSize(QSize(188, 216))
        self.grid.setItemDelegate(FilamentDelegate(self.grid))
        self.grid.setSpacing(4)
        self.grid.setWordWrap(True)
        self.grid.setTextElideMode(Qt.ElideRight)
        self.grid.itemSelectionChanged.connect(self._on_select_grid)
        self.list_stack.addWidget(self.grid)

        table_panel = QWidget()
        table_panel.setMinimumWidth(340)
        table_layout = QVBoxLayout(table_panel)
        table_layout.setContentsMargins(0, 0, 0, 0)
        tools = QHBoxLayout()
        self.results_label = QLabel("Catalogue")
        tools.addWidget(self.results_label, 1)
        self.columns_btn = QToolButton()
        self.columns_btn.setText("Colonnes")
        self.columns_btn.setFixedHeight(32)
        self.columns_btn.setAccessibleName("Choisir les colonnes affichées")
        self.columns_btn.setToolTip("Choisir les colonnes affichées (aussi par clic droit sur un en-tête)")
        tools.addWidget(self.segwrap)
        tools.addWidget(self.columns_btn)
        table_layout.addLayout(tools)
        table_layout.addWidget(self.list_stack, 1)
        table_layout.addLayout(pager)
        splitter.addWidget(table_panel)

        # ── Panneau droit : pile (état vide / fiche) ────────────────────
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_empty_page())

        detail_inner = self._build_detail_page()
        detail_inner.setMinimumWidth(0)
        detail_inner.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        detail_scroll = self.detail_scroll = DetailScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setFrameShape(QFrame.NoFrame)
        detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        detail_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        detail_scroll.setWidget(detail_inner)
        detail_panel = QWidget()
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(12, 0, 8, 0)
        detail_layout.addWidget(detail_scroll, 1)
        self.detail_footer=QWidget();self.footer_layout=QVBoxLayout(self.detail_footer)
        self.footer_layout.setContentsMargins(0,0,0,0);self.footer_layout.setSpacing(8)
        self.footer_layout.addWidget(self.hardware_summary);self.footer_layout.addWidget(self.nfc_capacity)
        self.nfc_note.hide();self.footer_layout.addWidget(self.btn_generate)
        actions=QHBoxLayout();actions.setContentsMargins(0,0,0,0);actions.setSpacing(8)
        self.btn_inspect.setFixedHeight(32);self.btn_open_out.setFixedHeight(32)
        actions.addWidget(self.btn_inspect,1);actions.addWidget(self.btn_open_out,1)
        self.footer_layout.addLayout(actions);detail_layout.addWidget(self.detail_footer)
        detail_scroll.viewportChanged.connect(self._align_detail_footer)
        self.stack.addWidget(detail_panel)

        splitter.addWidget(self.stack)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)
        self.stack.setMinimumWidth(300)
        splitter.setSizes([220, 620, 400])

        self.status = self.statusBar()
        self.status.setSizeGripEnabled(False)
        self.status.setContentsMargins(14,4,20,4)
        self.database_btn = QToolButton()
        self.database_btn.setObjectName("statusControl");self.database_btn.setFixedHeight(24)
        self.status.addPermanentWidget(self.database_btn)
        self.database_btn.clicked.connect(self._database_details)
        self.status.showMessage("Choisissez un filament.")

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
        dl.setContentsMargins(0, 0, 0, 8)
        dl.setSpacing(12)

        # The hero carries identity once: brand, product, spool, colour and material.
        self.hero = QFrame();self.hero.setObjectName('filamentHero')
        hero_layout = QVBoxLayout(self.hero);hero_layout.setContentsMargins(14,12,14,12);hero_layout.setSpacing(8)
        head = QHBoxLayout()
        self.logo = QLabel();self.logo.setFixedSize(100,30);self.logo.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        head.addWidget(self.logo);head.addStretch(1)
        self.favorite_btn=QToolButton();self.favorite_btn.setText('☆ Favori');self.favorite_btn.setCheckable(True)
        self.favorite_btn.setFixedHeight(CONTROL_HEIGHT);self.favorite_btn.clicked.connect(self._toggle_filament_favorite);head.addWidget(self.favorite_btn)
        hero_layout.addLayout(head)
        body=QHBoxLayout();body.setSpacing(10)
        self.spool_preview=SpoolPreview();body.addWidget(self.spool_preview,0,Qt.AlignTop)
        titles=QVBoxLayout();titles.setSpacing(5)
        self.title=WrapLabel('—');self.title.setObjectName('filamentTitle');font=self.title.font();font.setPointSize(17);font.setBold(True);self.title.setFont(font)
        titles.addWidget(self.title)
        self.subtitle_sku=QLabel();self.subtitle_sku.hide()
        self.subtitle_color=WrapLabel();self.subtitle_color.setObjectName('subtitle_color');titles.addWidget(self.subtitle_color)
        self.filament_meta=WrapLabel();self.filament_meta.setObjectName('fieldvalue');titles.addWidget(self.filament_meta)
        self.swatch=QLabel('—');self.swatch.setObjectName('swatch');self.swatch.setMaximumHeight(28);self.swatch.setTextInteractionFlags(Qt.TextSelectableByMouse)
        titles.addWidget(self.swatch);titles.addStretch(1);body.addLayout(titles,1);hero_layout.addLayout(body)
        self.color_caption=QLabel('Couleur');self.color_caption.hide()
        self.variant_label=QLabel('Bobine')
        self.variant_choice=QComboBox();self.variant_choice.setMinimumWidth(0)
        self.variant_choice.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon);self.variant_choice.setMinimumContentsLength(8)
        self.variant_choice.currentIndexChanged.connect(self._variant_changed)
        packaging_row=QHBoxLayout();packaging_row.addWidget(self.variant_label);packaging_row.addWidget(self.variant_choice,1);hero_layout.addLayout(packaging_row)
        self.package_hint=WrapLabel();self.package_hint.setObjectName('packageHint');self.package_hint.hide();hero_layout.addWidget(self.package_hint)
        dl.addWidget(self.hero)
        self.shade_panel=QWidget();self.shade_layout=QVBoxLayout(self.shade_panel);self.shade_layout.setContentsMargins(0,0,0,0)
        self.shade_hint=WrapLabel('Quelle teinte correspond à votre bobine ?');self.shade_layout.addWidget(self.shade_hint)
        self.shade_row=QGridLayout();self.shade_layout.addLayout(self.shade_row);self.shade_buttons=[];dl.addWidget(self.shade_panel)
        # Four scannable tiles replace the label/value inventory.
        caption=QLabel('CARACTÉRISTIQUES');caption.setObjectName('caption');self._muted_labels.append(caption);dl.addWidget(caption)
        self.btn_edit_physical=QToolButton();self.btn_edit_physical.setText('Modifier…');self.btn_edit_physical.clicked.connect(self._edit_physical)
        self.card=QFrame();self.card.setObjectName('physicalCard');card_layout=QVBoxLayout(self.card);card_layout.setContentsMargins(0,0,0,0)
        self.characteristics=MetricGrid();card_layout.addWidget(self.characteristics);self._field_widgets=dict(self.characteristics.values)
        dl.addWidget(self.card)
        self.provenance_toggle=QToolButton();self.provenance_toggle.setText('Détails et sources');self.provenance_toggle.setCheckable(True);self.provenance_toggle.toggled.connect(self._toggle_provenance)
        self.characteristic_actions=QHBoxLayout();self.characteristic_actions.setSpacing(8)
        for button in (self.btn_edit_physical,self.provenance_toggle):
            button.setFixedHeight(CONTROL_HEIGHT);button.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
            self.characteristic_actions.addWidget(button,1)
        dl.addLayout(self.characteristic_actions)
        self.provenance_box=QFrame();self.provenance_box.setObjectName('provenanceCard')
        self.fields=QGridLayout(self.provenance_box);self.fields.setContentsMargins(12,10,12,10);self.fields.setHorizontalSpacing(12);self.fields.setVerticalSpacing(8)
        for i,name in enumerate(('Références','Source')):
            label=QLabel(name);label.setProperty('field_key',name);value=WrapLabel('—');value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value.setAlignment(Qt.AlignTop|Qt.AlignLeft)
            self.fields.addWidget(label,i,0,Qt.AlignTop);self.fields.addWidget(value,i,1,Qt.AlignTop);self._field_widgets[name]=value
        self.fields.setColumnStretch(1,1)
        for name in ('Produit','Type','Couleur','SKU','Marque','SKU fabricant','Masse'):
            value=QLabel('—');value.hide();self._field_widgets[name]=value
        dl.addWidget(self.provenance_box);self._toggle_provenance(False)
        self.hardware_summary=WrapLabel();self.hardware_summary.setObjectName('hardwareSummary')
        self.btn_hardware=QToolButton();self.btn_hardware.setText('Mon matériel…');self.btn_hardware.clicked.connect(self._open_hardware);self.btn_hardware.hide()

        cfg = core.load_config()
        self.hardware_page = QWidget()
        hardware_layout = QVBoxLayout(self.hardware_page)
        hardware_layout.setContentsMargins(0, 0, 0, 0)
        self._build_export_assistant(hardware_layout)
        self.nfc_advanced = QWidget()
        advanced_layout = QVBoxLayout(self.nfc_advanced)
        nfc_row = QHBoxLayout()
        self.tag_type = QComboBox()
        for tag, capacity in core.NFC_CAPACITIES.items():
            self.tag_type.addItem(f"{tag} · {capacity} octets", tag)
        defaults = core.nfc_defaults(cfg)
        self.tag_type.setCurrentIndex(max(0, self.tag_type.findData(defaults["tag_type"])))
        self.nfc_profile = QComboBox()
        self.nfc_profile.addItem("Automatique — format compact", "auto")
        self.nfc_profile.addItem("Essentiel", "essential")
        self.nfc_profile.addItem("Avec les descriptifs et le logo", "full")
        self.nfc_profile.setCurrentIndex(max(0, self.nfc_profile.findData(defaults["profile"])))
        self.tag_type.setParent(self.nfc_advanced)
        self.tag_type.hide()
        nfc_row.addWidget(self.nfc_profile, 1)
        advanced_layout.addLayout(nfc_row)
        reserve_row = QHBoxLayout()
        reserve_row.addWidget(QLabel("Réserve pour l'application d'écriture"))
        self.nfc_reserve = QSpinBox()
        self.nfc_reserve.setRange(0, core.NFC_CAPACITIES[self.tag_type.currentData()])
        self.nfc_reserve.setSuffix(" octets")
        self.nfc_reserve.setValue(defaults["reserved_bytes"])
        self.nfc_reserve.setToolTip("Espace réservé à d'autres enregistrements NDEF ou données du logiciel d'écriture. "
                                   "À vérifier dans ce logiciel ; zéro ne prédit pas ses ajouts.")
        reserve_row.addWidget(self.nfc_reserve)
        advanced_layout.addLayout(reserve_row)
        hardware_layout.addWidget(self.nfc_advanced)
        self.nfc_advanced.hide()
        self._build_hardware_dialog()
        self.nfc_note = QLabel()
        self.nfc_note.setWordWrap(True)
        self.nfc_note.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        dl.addWidget(self.nfc_note)
        self.nfc_capacity = QLabel("Sélectionnez une fiche pour calculer sa taille NFC.")
        self.nfc_capacity.setWordWrap(True)
        self.nfc_capacity.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        dl.addWidget(self.nfc_capacity)
        self.tag_type.currentIndexChanged.connect(self._nfc_changed)
        self.nfc_profile.currentIndexChanged.connect(self._nfc_changed)
        self.nfc_reserve.valueChanged.connect(self._nfc_changed)
        self._wire_export_assistant()

        # Respiration au-dessus de l'action principale (la centre verticalement).
        dl.addStretch(1)

        # Action principale : c'est LA fonction de l'app → grande, pleine
        # largeur, bien en évidence au milieu du panneau.
        self.btn_generate = QPushButton("Exporter pour NFC")
        self.btn_generate.setObjectName("primary")
        self.btn_generate.setProperty('large',True)
        self.btn_generate.setCursor(Qt.PointingHandCursor)
        self.btn_generate.setFixedHeight(48)
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
        self.btn_inspect = QPushButton("Voir le JSON")
        self.btn_inspect.setObjectName("secondary")
        self.btn_inspect.setCursor(Qt.PointingHandCursor)
        self.btn_inspect.clicked.connect(self._toggle_inspect)
        self.btn_open_out = QPushButton("Dossier d'export")
        self.btn_open_out.setObjectName("secondary")
        self.btn_open_out.setCursor(Qt.PointingHandCursor)
        self.btn_open_out.clicked.connect(self._open_output)


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
            f"QPushButton#primary[large=true] {{ min-height:34px; max-height:34px; }}"
        )
        secondary_qss = (
            f"QPushButton {{ background:{t['sec_bg']}; color:{t['text']}; border:1px solid {t['border']}; border-radius:7px; min-height:18px; padding:6px 12px; }}"
            f"QPushButton:hover {{ background:{t['sec_hover']}; }}"
            f"QPushButton:disabled {{ color:{faint}; }}"
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
            f" padding:0; }}"
            f"QToolButton#seg:hover {{ background:{t['sec_hover']}; }}"
            f"QToolButton#seg:checked {{ background:{t['accent']}; }}"
        )
        ghost_qss = (
            f"QToolButton {{ background:transparent; color:{t['text']}; border:1px solid {t['border']};"
            f" border-radius:7px; min-height:18px; padding:6px 8px; }}"
            f"QToolButton:hover {{ background:{t['sec_hover']}; border-color:{accent}; }}"
            f"QToolButton:checked {{ background:{t['sec_bg']}; border-color:{accent}; color:{accent}; }}"
            f"QToolButton#shadeOption {{ background:{t['card']}; padding:7px; border-radius:9px; }}"
            f"QToolButton#shadeOption:checked {{ border:2px solid {accent}; background:{t['sec_bg']}; }}"
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
            f"QCheckBox {{ color:{t['text']}; background:transparent; spacing:6px; }}"
            f"QCheckBox::indicator {{ width:15px; height:15px; border:1px solid {t['faint']};"
            f" border-radius:4px; background:{t['field_bg']}; }}"
            f"QCheckBox::indicator:checked {{ background:{accent}; border-color:{accent};"
            f" image:url({CHECK_ICON_PATH}); }}"
            f"QCheckBox::indicator:disabled {{ border-color:{t['border']}; background:{t['window']}; }}"
            f"QComboBox, QSpinBox, QLineEdit {{ background:{t['field_bg']}; color:{t['text']}; border:1px solid {t['border']}; border-radius:7px; min-height:18px; padding:6px 8px; }}"
            f"QComboBox:focus, QSpinBox:focus, QLineEdit:focus {{ border-color:{accent}; }}"
            f"QComboBox::drop-down {{ border:none; width:24px; subcontrol-origin:padding; subcontrol-position:top right; }}"
            f"QComboBox::down-arrow {{ image:url({CHEVRON_ICON_PATH}); width:12px; height:8px; }}"
            f"QComboBox#printerPicker::down-arrow {{ image:none; }}"
            f"QMenu {{ background:{t['card']}; color:{t['text']}; border:1px solid {t['border']}; border-radius:8px; padding:5px; }}"
            f"QMenu::item {{ min-height:18px; padding:6px 14px; border-radius:5px; }}"
            f"QMenu::item:selected {{ background:{t['sel']}; color:{t['sel_text']}; }}"
            f"QMenu::separator {{ height:1px; background:{t['border']}; margin:4px 8px; }}"
            f"QComboBox:disabled, QSpinBox:disabled, QLineEdit:disabled {{ color:{t['faint']};"
            f" background:{t['window']}; border-color:{t['border']}; }}"
            f"QPushButton:disabled, QToolButton:disabled {{ color:{t['faint']}; }}"
            f"QPushButton#chip {{ border:1px solid {t['border']}; border-radius:12px; padding:2px 11px;"
            f" background:{t['field_bg']}; color:{t['text']}; }}"
            f"QPushButton#chip:hover {{ border-color:{accent}; color:{accent}; }}"
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
                           + f"QFrame#filamentHero, QFrame#metricTile, QFrame#provenanceCard {{ background:{t['card']}; border:1px solid {t['border']}; border-radius:12px; }}"
                           + f"QLabel#metricLabel {{ color:{t['muted']}; font-size:10px; }}"
                           + f"QToolButton#favoriteFilter {{ padding:6px 4px; }}"
                           + f"QFrame#sourceCard {{ border:1px solid {t['border']}; border-radius:10px; background:{t['field_bg']}; }}"
                           + f"QToolButton#statusControl {{ border:none; color:{t['muted']}; font-size:11px; padding:2px 4px; }}"
                           + f"QTabWidget::pane {{ border:none; background:transparent; }}"
                           + f"QTabBar::tab {{ background:{t['sec_bg']}; color:{t['muted']}; border:1px solid {t['border']}; border-radius:7px; padding:7px 16px; margin-right:6px; min-width:72px; }}"
                           + f"QTabBar::tab:selected {{ background:{accent}; color:{t['accent_text']}; border-color:{accent}; }}"
                           + f"QListWidget#printerChoices {{ border:none; background:transparent; outline:0; }}"
                           + f"QListWidget#printerChoices::item {{ border:1px solid {t['border']}; border-radius:10px; background:{t['card']}; padding:0; }}"
                           + f"QListWidget#printerChoices::item:selected {{ border:2px solid {accent}; background:{t['sec_bg']}; }}"
                           + f"QLabel#printerBadge {{ background:{t['sec_bg']}; border-radius:12px; font-size:20px; color:{accent}; }}"
                           + f"QLabel#sourceStatus {{ color:{t['muted']}; font-weight:600; }}"
                           + f"QLabel#sourceStatus[success=true] {{ color:{accent}; }}"
                           + f"QLabel#fieldvalue {{ color:{t['text']}; }}")

        self._align_detail_footer()
        # Titre de la fiche : contraste fort, indépendant du palette OS.
        if hasattr(self, "title"):
            self.title.setStyleSheet(f"color:{t['text']};")
        if hasattr(self, 'printer_card'):
            self._refresh_printer_card()

        # Rafraîchit la bande couleur si une fiche est affichée.
        if self.current_sku:
            self._paint_swatch()
        else:
            self.swatch.setStyleSheet(
                f"#swatch {{ background:{t['field_bg']}; color:{faint};"
                f" border:1px dashed {t['border']}; border-radius:8px; }}")
        if hasattr(self, "btn_view_list"):
            self._update_seg_icons()
            self.grid.itemDelegate().dark=t['dark'];self.grid.viewport().update()

    def _show_empty(self):
        self.stack.setCurrentIndex(0)

    def _align_detail_footer(self):
        if hasattr(self,'footer_layout'):
            gutter=max(0,self.detail_scroll.width()-self.detail_scroll.viewport().width())
            self.footer_layout.setContentsMargins(0,0,gutter,0)

    def _show_card(self):
        self.stack.setCurrentIndex(1)


    # ── Données / table ──────────────────────────────────────────────────
    def _reload_table(self):
        self._sku_rows = core.list_skus(self.db)
        grouped = core.load_config().get("ui", {}).get("group", True) if isinstance(core.load_config().get("ui"), dict) else True
        self._all_rows = core.group_filaments(self._sku_rows) if grouped else list(self._sku_rows)
        for combo, key, label in ((self.brand_filter, "brand", "Tous les fabricants"),
                                  (self.material_filter, "family", "Toutes les matières")):
            selected = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(label, "")
            for value in sorted({r[key] for r in self._all_rows if r[key]}, key=str.casefold):
                combo.addItem(value, value)
            combo.setCurrentIndex(max(0, combo.findData(selected)))
            combo.blockSignals(False)
        self._fill_sidebar()
        self._apply_filter()

    def _populate(self, rows):
        dpr = self.devicePixelRatioF()
        self._rows = rows
        selected = self.current_sku
        self.table.blockSignals(True)
        self.grid.blockSignals(True)
        self.table.setUpdatesEnabled(False)
        self.grid.setUpdatesEnabled(False)
        # Vue liste
        self.table.setRowCount(len(rows))
        for r, e in enumerate(rows):
            sw = self.table.item(r,0)
            if sw is None:
                sw=QTableWidgetItem();self.table.setItem(r,0,sw)
            sw.setIcon(QIcon(make_swatch_pixmap(None if e.get("hex_variants",0)>1 else e.get("hex"), 18, dpr)))
            sw.setToolTip(f"#{e['hex']}" if e.get("hex") else "Couleur à renseigner")
            for col, key in enumerate(self._column_keys[1:], 1):
                value = e.get(key)
                if isinstance(value, float) and value.is_integer():
                    value = int(value)  # 1000 g, pas 1000.0
                item=self.table.item(r,col)
                if item is None:
                    item=QTableWidgetItem();self.table.setItem(r,col,item)
                item.setText(str(value) if value is not None else "—")
                item.setToolTip(str(value) if value is not None else "Inconnu")
                if col == 1:
                    item.setData(Qt.UserRole, e["sku"])
                    shown = e["reference"] if not e["reference"].startswith(("OFD-", "SMDB-")) else "—"
                    if e.get("variant_count", 1) > 1:
                        shown = f"{shown} +{e['variant_count'] - 1}" if shown != "—" else f"{e['variant_count']} cond."
                    item.setText(shown)
                    item.setToolTip(f"Référence interne : {e['sku']}" + (f"\nRéférence fabricant : {e['manufacturer_sku']}" if e.get("manufacturer_sku") else "")
                                    + ("\nConditionnements : " + ", ".join(v["reference"] for v in e["variants"]) if e.get("variant_count", 1) > 1 else ""))
                if key == 'product' and e.get('diameter'):
                    item.setText(f"{product_label(e['product'],e.get('brand',''))} · {e['diameter']:g} mm")
            color_item = self.table.item(r, 3)
            color_item.setText(e["color_name"] + (" ⚠" if e.get("hex_variants",0)>1 else ""))
            color_item.setToolTip(f"#{e['hex']}" if e.get("hex") else "Couleur à renseigner")
            if not e.get("hex"):
                color_item.setForeground(QColor("#b00"))
            else:
                color_item.setForeground(self.palette().text().color())
        favorite_keys=set(core.load_config().get("favorite_filaments",[]))
        # Qt stores only the string SKU. Keep Python display data in the delegate;
        # passing whole nested catalogue records through QVariant is unnecessary.
        self.grid.itemDelegate().rows={e['sku']:dict(e,_favorite=self._is_favorite(e,favorite_keys)) for e in rows}
        # Vue grille
        # Reuse the Qt-owned cards. Repeated clear()/recreation during filter
        # restoration triggered a native PySide crash; there is no reason to
        # destroy every card when only its contents change.
        while self.grid.count() > len(rows):
            removed = self.grid.takeItem(self.grid.count()-1)
            del removed
        for index, e in enumerate(rows):
            it = self.grid.item(index)
            if it is None:
                it = QListWidgetItem()
                self.grid.addItem(it)
            it.setSizeHint(QSize(180,208))
            it.setIcon(spool_icon(None if e.get("hex_variants",0)>1 else e.get("hex"),112,dpr,getattr(self,"_tok",{}).get("dark",False)))
            it.setText(e["product"]+"\n"+e["color_name"])
            it.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            it.setData(Qt.UserRole, e["sku"])
            it.setToolTip(f"{e['sku']}\n{e['product']} · {e['color_name']}\n{e['quality']}")
        self.table.setUpdatesEnabled(True)
        self.grid.setUpdatesEnabled(True)
        self.table.blockSignals(False)
        self.grid.blockSignals(False)
        selected_row = next((i for i, e in enumerate(rows) if e["sku"] == selected or any(v["sku"] == selected for v in e.get("variants", []))), None)
        if selected_row is not None:
            # The card already shows this reference: re-select silently in both views.
            self.table.blockSignals(True)
            self.grid.blockSignals(True)
            self.table.selectRow(selected_row)
            self.grid.setCurrentRow(selected_row)
            self.table.blockSignals(False)
            self.grid.blockSignals(False)
        elif hasattr(self, "stack"):
            self.current_sku = None
            self._show_empty()

    def _set_view_mode(self, mode: str):
        self.view_mode = mode
        self.btn_view_list.setChecked(mode=='list');self.btn_view_grid.setChecked(mode=='grid')
        self.columns_btn.setVisible(mode=="list")
        self.list_stack.setCurrentIndex(0 if mode == "list" else 1)
        self._update_seg_icons()
        # A displayed group may have a different representative SKU from the chosen package.
        if self.current_sku:
            row=next((i for i,e in enumerate(self._rows) if e['sku']==self.current_sku or any(v['sku']==self.current_sku for v in e.get('variants',[]))),None)
            if row is not None:
                previous=self.grid.blockSignals(True);self.grid.setCurrentRow(row);self.grid.blockSignals(previous)
                previous=self.table.blockSignals(True);self.table.selectRow(row);self.table.blockSignals(previous)

    def _on_select_grid(self):
        items = self.grid.selectedItems()
        if not items:
            self._clear_filament()
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

    def _apply_filter(self, *_):
        if not hasattr(self, "_all_rows"):
            return
        self._filtered_rows = core.query_catalogue(
            self._all_rows, text=self.search.text(), brand=self.brand_filter.currentData() or "",
            material=self.material_filter.currentData() or "", quality=self.quality_filter.currentData(),
            sort1=self.sort1.currentData(), sort2=self.sort2.currentData(),
            descending1=self.sort1_direction.currentData(), descending2=self.sort2_direction.currentData())
        if getattr(self, "brand_favorites_only", None) and self.brand_favorites_only.isChecked():
            brands=set(core.load_config().get("favorite_brands",[]))
            self._filtered_rows=[r for r in self._filtered_rows if r.get("brand") in brands]
        if getattr(self, 'favorites_only', None) and self.favorites_only.isChecked():
            favorites=set(core.load_config().get("favorite_filaments", []))
            self._filtered_rows = [r for r in self._filtered_rows if self._is_favorite(r, favorites)]
        index = next((i for i, r in enumerate(self._filtered_rows) if r['sku'] == self.current_sku or any(v['sku'] == self.current_sku for v in r.get('variants', []))), None) if self.current_sku else None
        self._page = index // self._page_size if index is not None else 0
        self._show_page()
        self._header_indicators()
        self._sync_sidebar_selection()
        self._schedule_ui_preferences()

    def _show_page(self):
        total = len(self._filtered_rows)
        start = self._page * self._page_size
        end = min(total, start + self._page_size)
        self._populate(self._filtered_rows[start:end])
        self.page_label.setText(f"{fmt_int(start + 1) if total else 0}–{fmt_int(end)} sur {fmt_int(total)}")
        self.results_label.setText(f"{fmt_int(total)} filaments trouvés")
        self.previous_page.setEnabled(self._page > 0)
        self.next_page.setEnabled(end < total)
        self.previous_page.setVisible(total > self._page_size)
        self.next_page.setVisible(total > self._page_size)

    def _change_page(self, delta):
        last = max(0, (len(self._filtered_rows) - 1) // self._page_size)
        self._page = max(0, min(last, self._page + delta))
        self._show_page()

    def _reset_filters(self):
        controls = (self.search, self.brand_search, self.material_search, self.favorites_only, self.brand_favorites_only, self.brand_filter, self.material_filter, self.quality_filter)
        self._search_timer.stop()
        for widget in controls:
            widget.blockSignals(True)
        self.search.clear()
        self.brand_search.clear()
        self.material_search.clear()
        self.favorites_only.setChecked(False)
        self.brand_favorites_only.setChecked(False)
        self.brand_filter.setCurrentIndex(0)
        self.material_filter.setCurrentIndex(0)
        self.quality_filter.setCurrentIndex(0)
        for widget in controls:
            widget.blockSignals(False)
        self._clear_filament()
        self._filter_brand_list('')
        self._filter_material_list('')
        self._apply_filter()

    def _update_stats(self):
        st = core.db_stats(self.db)
        age = core.db_age_days(self.db)
        age_str = f"{age:.0f} j" if age is not None else "?"
        conflicts = list(self.db.get("_bundle_conflicts", [])) + list(self.db.get("_source_conflicts", []))
        for values in self.db.get("_source_conflicts_by_source", {}).values():
            conflicts.extend(values)
        conflicts = list(dict.fromkeys(conflicts))
        self.stats_label.setText(
            f"Références : {st['skus']}    Fabricants : {len(self.db.get('_brands', {}))}    Produits : {st['products']}    "
            f"HEX à préciser : {st['missing_hex']}    Mise à jour complète : {age_str}"
            + (f"    Mise à jour : {core.UPDATE_STATUS_LABELS.get(self.db['_update_status'], self.db['_update_status'])}"
               if self.db.get('_update_status') else "")
            + (f"    Valeurs locales conservées : {len(conflicts)}" if conflicts else "")
        )
        self._refresh_database_summary()
        self.stats_label.setToolTip("Valeurs locales conservées lors de la fusion :\n" + "\n".join(conflicts[:100])
                                   + (f"\n… et {len(conflicts)-100} autres." if len(conflicts) > 100 else "")
                                   if conflicts else "")

    def _refresh_logo(self, brand: str | None = None):
        """Logo de la marque affichée ; sans argument, celle de la fiche courante."""
        if brand is None:
            view = core.get_sku_view(self.db, self.current_sku) if self.current_sku else None
            brand = (view.product_data.get("brand") if view else "") or ""
        self.logo.setTextFormat(Qt.PlainText)
        abs_path = core.logo_abs_path(self.db, brand) if brand else None
        dark = bool(getattr(self, "_tok", {}).get("dark"))
        dpr = self.devicePixelRatioF()
        key = (abs_path, dark, dpr, self.logo.width(), self.logo.height())
        cache = self.__dict__.setdefault("_logo_cache", {})
        if key not in cache:
            # Hauteur max = 48 px, largeur max = 152 px (widget du logo), aspect conservé.
            pm = load_brand_pixmap(abs_path, self.logo.height()-6, dpr, max_w=self.logo.width()-8) if abs_path else None
            cache[key] = self._transparent_logo(pm) if pm and not pm.isNull() else None
            if len(cache) > 64:
                cache.pop(next(iter(cache)))
        if cache[key] is not None:
            self.logo.setPixmap(cache[key])
            self.logo.setVisible(True)
            return
        # A readable brand name is preferable to a missing, tiny or incorrect logo.
        self.logo.setPixmap(QPixmap())
        self.logo.setText(brand)
        self.logo.setWordWrap(True)
        self.logo.setVisible(True)

    # ── Sélection ────────────────────────────────────────────────────────
    def _on_select(self):
        items = self.table.selectedItems()
        if not items:
            self._clear_filament()
            return
        row = items[0].row()
        sku_item = self.table.item(row, 1)
        if not sku_item:
            return
        self.current_sku = sku_item.data(Qt.UserRole) or sku_item.text()
        self._show_detail(self.current_sku)

    def _paint_swatch(self):
        t=self._tok;h=(getattr(self,'_cur_hex',None) or '').strip().lstrip('#')
        self.spool_preview.set_filament(h.upper() if len(h)==6 else None,t['dark'])
        self.swatch.setText('#'+h.upper() if len(h)==6 else 'Teintes à vérifier' if self._variant_needs_choice() else 'Couleur à renseigner')
        self.swatch.setStyleSheet(f"color:{t['muted']};background:transparent;font-size:11px;")

    def _show_detail(self, sku):
        sku = self._detail_packaging(sku)
        self.current_sku = sku
        view = core.get_sku_view(self.db, sku)
        self._show_card()
        self.status.showMessage("Échap : désélectionner")
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
            self._refresh_logo("")
            self.nfc_capacity.setText("Produit absent : export impossible.")
            return

        self.title.setText(product_label(view.display_product,view.product_data.get('brand','')))
        self.filament_meta.setText(view.type_str)
        group = self._group_for_sku(sku)
        self.subtitle_sku.setText(view.product_data.get('brand') or '')
        self.subtitle_sku.setToolTip('Référence interne : ' + view.sku)
        self._refresh_variant_choice(group, sku)
        self._refresh_favorite_button()
        self.subtitle_color.setText((group or {}).get('color_name') or view.color_name or "")
        self._field_widgets["Produit"].setText(view.display_product)
        self._field_widgets["Type"].setText(view.type_str)
        self._field_widgets["Couleur"].setText((group or {}).get('color_name') or view.color_name or "—")
        self._field_widgets["SKU"].setText(view.sku)
        self._field_widgets["Nozzle"].setText(view.nozzle_str)
        self._field_widgets["Bed"].setText(view.bed_str)
        self._field_widgets["Densité"].setText(view.density_str)
        self._field_widgets["Diamètre"].setText(view.diameter_str)
        brand = view.product_data.get("brand") or "Non renseignée"
        line = view.product_data.get("line")
        self._field_widgets["Marque"].setText(f"{brand} · {line}" if line else brand)
        entry = self.db["_skus"][sku]
        source_names = {entry.get("source", "Catalogue historique")}
        source_names.update(info["source"] for info in view.product_data.get("_field_sources", {}).values() if info.get("source") and info.get("value") is not None)
        source_names.update(info["source"] for info in entry.get("_field_sources", {}).values() if info.get("source"))
        source_names.update(view.product_data.get("_official_references", {}))
        self._field_widgets["Source"].setText(" + ".join(sorted(source_names)))
        self._field_widgets["SKU fabricant"].setText(entry.get("manufacturer_sku") or "Non fourni")
        self._field_widgets["Masse"].setText(f"{entry['weight']} g" if entry.get("weight") else "Non fournie")
        self._field_widgets["Références"].setText(self._references_text(sku))

        self._refresh_logo(view.product_data.get("brand") or "")

        self._cur_hex = None if self._variant_needs_choice() else view.hex
        self._paint_swatch()

        self.btn_generate.setEnabled(not (self.worker and self.worker.isRunning()))
        self.btn_inspect.setEnabled(True)
        self._refresh_nfc_capacity()
        self._printer_field_help()
        if self.inspector.isVisible():
            self._refresh_inspector()

    def _build_payload(self):
        view = core.get_sku_view(self.db, self.current_sku)
        if view is None:
            return None
        if self._variant_needs_choice():
            raise core.ExportValidationError('Comparez les pastilles de couleur et choisissez la teinte de votre bobine.')
        entry = dict(self.db["_skus"][self.current_sku])
        entry["sku"] = self.current_sku
        return core.build_openspool(entry, view.product_data, brand_meta=view.brand_meta,
                                    use_orca_overrides=core.load_config().get("orca_overrides") is True)

    # ── Actions ──────────────────────────────────────────────────────────
    def _edit_physical(self):
        if not self.current_sku or self.worker and self.worker.isRunning():
            return
        view = core.get_sku_view(self.db, self.current_sku)
        if view is None:
            return
        count = sum(e.get("product") == view.product for e in self.db["_skus"].values())
        dialog = QDialog(self)
        dialog.setWindowTitle("Caractéristiques locales du produit")
        dialog.resize(440,420)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16,16,16,16);layout.setSpacing(12)
        note = QLabel(f"Ces valeurs s’appliquent aux {count} références du produit.\n"
                      "Valeur inconnue : laissez la case vide. Vos corrections sont conservées lors des actualisations.")
        note.setWordWrap(True)
        layout.addWidget(note)
        fields = {}
        form=QGridLayout();form.setContentsMargins(0,0,0,0);form.setHorizontalSpacing(12);form.setVerticalSpacing(8);form.setColumnStretch(1,1)
        for key, label in (("min_temp", "Buse min. °C"), ("max_temp", "Buse max. °C"),
                           ("bed_min_temp", "Plateau min. °C"), ("bed_max_temp", "Plateau max. °C"),
                           ("diameter", "Diamètre mm"), ("density", "Densité g/cm³")):
            value = view.product_data.get(key)
            field = QLineEdit("" if value is None else str(value))
            field.setObjectName(key);field.setFixedHeight(CONTROL_HEIGHT)
            caption=QLabel(label);caption.setBuddy(field);row=len(fields)
            form.addWidget(caption,row,0);form.addWidget(field,row,1);fields[key] = field
        layout.addLayout(form)
        error = QLabel(); error.setWordWrap(True); layout.addWidget(error)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText('Enregistrer');buttons.button(QDialogButtonBox.Cancel).setText('Annuler')
        for button in buttons.buttons():button.setFixedHeight(CONTROL_HEIGHT)
        layout.addWidget(buttons)
        def save():
            try:
                values = {}
                for key, field in fields.items():
                    raw = field.text().strip().replace(",", ".")
                    value = float(raw) if raw else None
                    values[key] = int(value) if value is not None and key.endswith("temp") and value.is_integer() else value
                core.set_product_physical(self.db, self.current_sku, values)
                dialog.accept()
            except (ValueError, OSError) as exc:
                error.setText(str(exc))
        buttons.accepted.connect(save)
        buttons.rejected.connect(dialog.reject)
        if dialog.exec() == QDialog.Accepted:
            selected = self.current_sku
            self._reload_table()
            if self.current_sku == selected:
                self._show_detail(selected)
            self._update_stats()

    def _nfc_changed(self, *_):
        self.nfc_reserve.blockSignals(True)
        self.nfc_reserve.setMaximum(core.NFC_CAPACITIES[self.tag_type.currentData()])
        self.nfc_reserve.blockSignals(False)
        # Ce choix vaut pour les exports en cours ; le défaut ne change qu'avec
        # « Définir par défaut ».
        self._refresh_nfc_default_btn()
        self._refresh_nfc_capacity()
        if self.inspector.isVisible():
            self._refresh_inspector()

    def _complete_color(self) -> bool:
        entry = self.db["_skus"][self.current_sku]
        if core.validate_hex(entry.get("hex")):
            return True
        dlg = QDialog(self)
        dlg.setWindowTitle("Couleur à préciser")
        lay = QVBoxLayout(dlg)
        note = QLabel("La couleur est inconnue. Choisissez explicitement un HEX représentatif.\n"
                      "Une couleur transparente ou multicolore ne sera pas remplacée automatiquement par du noir.")
        note.setTextFormat(Qt.PlainText)
        if entry.get("source_colors"):
            note.setText(note.text() + "\nCouleurs fournies par la source : " + ", ".join(entry["source_colors"]))
        note.setWordWrap(True)
        lay.addWidget(note)
        lay.addWidget(QLabel("HEX représentatif (6 caractères)"))
        hx = QLineEdit()
        lay.addWidget(hx)
        lay.addWidget(QLabel("Alpha facultatif : 00 transparent, FF opaque ; vide pour conserver"))
        alpha = QLineEdit(entry.get("alpha", ""))
        lay.addWidget(alpha)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)
        if dlg.exec() != QDialog.Accepted:
            return False
        value = core.validate_hex(hx.text())
        if not value:
            raise core.ExportValidationError("Couleur invalide : six caractères HEX requis.")
        sku = self.current_sku
        core.set_sku_hex(self.db, sku, value, alpha=alpha.text().strip() or None)
        self._reload_table()
        self.current_sku = sku
        self._show_detail(sku)
        self._update_stats()
        return True

    def _generate(self, checked=False, *, mode="nfc"):
        if not self.current_sku:
            return
        if self.worker and self.worker.isRunning():
            self.status.showMessage("Attendez la fin de la mise à jour avant de modifier ou exporter la fiche.", 6000)
            return
        try:
            if mode == "nfc" and not self._can_export_for_printer():
                return
            if core.get_sku_view(self.db, self.current_sku) is None:
                raise core.ExportValidationError("Produit introuvable pour cette référence.")
            if not self._complete_color():
                return
            view = core.get_sku_view(self.db, self.current_sku)
            if view is None:
                raise core.ExportValidationError("Produit introuvable pour cette référence.")
            entry = self.db["_skus"][self.current_sku]
            export_options = self._nfc_options() if mode == "nfc" else dict(tag_type=self.tag_type.currentData(), profile="full", reserved_bytes=0)
            out = core.write_openspool(self.current_sku, entry, view.product_data,
                                       brand_meta=view.brand_meta, mode=mode,
                                       **export_options,
                                       use_orca_overrides=core.load_config().get("orca_overrides") is True)
            self.status.showMessage(f"Fichier généré : {out} — « Dossier d'export » l'ouvre.", 12000)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Échec de l'export :\n{e}")

    def _toggle_inspect(self):
        if self.inspector.isVisible():
            self.inspector.setVisible(False)
            self.btn_inspect.setText("Voir le JSON")
            self.detail_scroll.verticalScrollBar().setValue(getattr(self,"_inspect_scroll_before",0))
            new_h = max(self.height() - _INSPECTOR_DELTA, self.minimumHeight())
            self.resize(self.width(), new_h)
        else:
            self._inspect_scroll_before=self.detail_scroll.verticalScrollBar().value()
            self._refresh_inspector()
            self.inspector.setVisible(True)
            self.btn_inspect.setText("Masquer le JSON")
            avail = QApplication.primaryScreen().availableGeometry().height()
            new_h = min(self.height() + _INSPECTOR_DELTA, avail - 60)
            self.resize(self.width(), new_h)
            QTimer.singleShot(0,lambda:self.detail_scroll.ensureWidgetVisible(self.inspector) if self.inspector.isVisible() else None)

    def _refresh_inspector(self):
        try:
            payload = self._build_payload()
            if payload is not None:
                text = core.serialize_openspool(payload, **self._nfc_options())
                size = core.nfc_size(text, tag_type=self._nfc_options()["tag_type"], reserved_bytes=self._nfc_options()["reserved_bytes"])
                self.inspector.setPlainText(text)
                self.status.showMessage(f"JSON : {size.utf8_bytes} octets UTF-8 ; "
                                        f"occupation NFC : {size.type2_bytes}/{size.capacity_bytes} octets "
                                        "(un enregistrement MIME).", 10000)
        except (core.ExportValidationError, core.DatabaseError, OSError) as exc:
            self.inspector.setPlainText(f"Export impossible : {exc}")

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

    def _start_update(self, manual=False):
        if self.worker and self.worker.isRunning():
            return
        try:
            consent = self._ask_network_consent()
        except OSError as exc:
            QMessageBox.critical(self, "Consentement non enregistré", str(exc))
            return
        if not consent:
            self.status.showMessage("Mise à jour annulée (réseau refusé).", 6000)
            return
        self.update_btn.setEnabled(False)
        self.menu_btn.setEnabled(False)
        self.btn_generate.setEnabled(False)
        self.progress.setVisible(True)
        self.progress_label.setText('Préparation de la synchronisation…')
        self.progress_label.setVisible(True)
        self.cancel_update_btn.setVisible(True)
        self.cancel_update_btn.setEnabled(True)
        self.progress.setRange(0, len(core.selected_pipeline(core.load_config()["selected_sources"])))
        self.progress.setValue(0)
        self.status.showMessage("Mise à jour en cours…")

        self._sync_before = self._snapshot_stats()
        self._sync_manual = bool(manual)
        self.worker = UpdateWorker()
        self.worker.progress.connect(self._on_update_progress)
        self.worker.finished_ok.connect(self._on_update_done)
        self.worker.failed.connect(self._on_update_failed)
        self.worker.start()

    def _on_update_progress(self, label, i, total):
        self.progress.setValue(i)
        self.progress_label.setText(f"{i}/{total} · {label}")

    def _cancel_update(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel.set()
            self.cancel_update_btn.setEnabled(False)
            self.status.showMessage("Annulation demandée : l'étape en cours s'interrompt…", 8000)

    def _finish_update_ui(self):
        self.progress.setVisible(False)
        self.progress_label.setVisible(False)
        self.cancel_update_btn.setVisible(False)
        self.update_btn.setEnabled(True)
        self.menu_btn.setEnabled(True)

    def _on_update_done(self, results):
        self._finish_update_ui()
        if self.worker:
            self.worker.wait(2000)
        cancelled = any(r.status == "cancelled" for r in results)
        try:
            self.db = core.load_db()
        except (core.DatabaseError, OSError) as exc:
            QMessageBox.critical(self, "Base illisible", str(exc))
            return
        self._chosen_variant = None
        self._reload_table()
        if self._default_brand_pending and self.brand_filter.findData("Polymaker") >= 0:
            self._choose_brand("Polymaker")
            self._default_brand_pending = False
        self._refresh_logo()
        self._update_stats()
        if self.current_sku:
            self._show_detail(self.current_sku)
        n_ok = sum(1 for r in results if r.ok)
        n_ko = [r for r in results if not r.ok and r.status != "cancelled"]
        msg = f"Mise à jour {core.UPDATE_STATUS_LABELS[core.update_status(results)]} — {n_ok}/{len(results)} étapes OK."
        if cancelled:
            msg = f"Mise à jour annulée — {n_ok}/{len(results)} étapes terminées ; base locale conservée."
        self.status.showMessage(msg, 10000)
        offline = n_ko and all(r.status == "unavailable" for r in n_ko)
        before = self._sync_before or self._snapshot_stats()
        after = self._snapshot_stats()
        self._last_report = (results, before, after)
        if cancelled or (offline and not getattr(self, "_sync_manual", False)):
            # Being offline at launch is a normal situation: a status-bar line, not a window.
            if offline:
                self.status.showMessage(msg + " Sources injoignables ; base locale conservée.", 12000)
            return
        if n_ko or getattr(self, "_sync_manual", False):
            self._show_sync_report(results, before, after)

    def _on_update_failed(self, tb):
        self._finish_update_ui()
        if self.current_sku:
            self._show_detail(self.current_sku)
        QMessageBox.critical(self, "Erreur de mise à jour", tb)

    # ── Mise à jour automatique ──────────────────────────────────────────
    # ── Paramètres ───────────────────────────────────────────────────────
    def _open_settings(self):
        cfg=core.load_config();dlg=QDialog(self);dlg.setWindowTitle('Paramètres');dlg.resize(540,460)
        lay=QVBoxLayout(dlg);lay.setContentsMargins(18,18,18,14);lay.setSpacing(12);tabs=QTabWidget();tabs.setDocumentMode(True);lay.addWidget(tabs,1)
        catalogue=QWidget();catalogue_layout=QVBoxLayout(catalogue);catalogue_layout.setContentsMargins(0,12,0,0)
        catalogue_layout.addWidget(WrapLabel('Actualisez le catalogue à votre rythme. La dernière base locale reste disponible en cas d’échec.'))
        catalogue_layout.addWidget(QLabel('Actualisation au lancement'))
        cadence=QComboBox()
        for days,label in core.UPDATE_INTERVAL_CHOICES:cadence.addItem(label,days)
        cadence.setCurrentIndex(max(0,cadence.findData(cfg.get('update_interval_days',1))));catalogue_layout.addWidget(cadence)
        sources=QPushButton('Sources du catalogue…');sources.clicked.connect(self._choose_sources);catalogue_layout.addWidget(sources)
        revoke=QPushButton('Retirer l’autorisation réseau');revoke.setEnabled(core.has_network_consent())
        def revoke_consent():
            try:core.set_network_consent(False,auto_update=False);dlg.reject()
            except OSError as exc:QMessageBox.critical(self,'Paramètres',str(exc))
        revoke.clicked.connect(revoke_consent);catalogue_layout.addWidget(revoke);catalogue_layout.addStretch(1);tabs.addTab(catalogue,'Catalogue')
        export=QWidget();export_layout=QVBoxLayout(export);export_layout.setContentsMargins(0,12,0,0)
        export_layout.addWidget(QLabel('Ma bobine habituelle'))
        export_layout.addWidget(WrapLabel('Présélection utilisée si elle existe. Vous pouvez la modifier dans la fiche.'))
        weight=QComboBox();weight.setObjectName('preferred_weight_g')
        selected_weight=cfg.get('preferred_weight_g',1000)
        if type(selected_weight) is not int or not 0<=selected_weight<=20000:selected_weight=1000
        weights=sorted({0,250,500,750,1000,1500,2000,2500,3000,5000,selected_weight})
        for grams in weights:weight.addItem('Selon la fiche' if not grams else (f'{grams/1000:g} kg' if grams>=1000 else f'{grams} g').replace('.',','),grams)
        weight.setCurrentIndex(max(0,weight.findData(cfg.get('preferred_weight_g',1000))));weight.setFixedHeight(32)
        form=QComboBox();form.setObjectName('preferred_packaging')
        for label,key in (('Indifférent','any'),('Avec bobine','spool'),('Recharge','refill')):form.addItem(label,key)
        form.setCurrentIndex(max(0,form.findData(cfg.get('preferred_packaging','any'))));form.setFixedHeight(32)
        form_grid=QGridLayout();form_grid.setContentsMargins(0,0,0,0);form_grid.setHorizontalSpacing(16);form_grid.setVerticalSpacing(10)
        mass_label=QLabel('Masse');mass_label.setBuddy(weight);format_label=QLabel('Format');format_label.setBuddy(form)
        form_grid.addWidget(mass_label,0,0);form_grid.addWidget(weight,0,1);form_grid.addWidget(format_label,1,0);form_grid.addWidget(form,1,1);form_grid.setColumnStretch(1,1);export_layout.addLayout(form_grid)
        chk_orca=QCheckBox('Préférer les valeurs Orca à l’export');chk_orca.setChecked(cfg.get('orca_overrides') is True)
        chk_orca.setToolTip('Désactivé : vos corrections locales restent prioritaires. Le fichier JSON permet de vérifier les valeurs exportées.')
        export_layout.addStretch(1);tabs.addTab(export,'Bobines')
        advanced_export=QWidget();advanced_layout=QVBoxLayout(advanced_export);advanced_layout.setContentsMargins(0,12,0,0)
        advanced_layout.addWidget(QLabel('Valeurs du fichier NFC'));advanced_layout.addWidget(chk_orca)
        advanced_layout.addWidget(WrapLabel('Par défaut, vos corrections locales restent prioritaires. Activez cette option pour utiliser les paramètres Orca disponibles.'))
        advanced_layout.addStretch(1);tabs.addTab(advanced_export,'Export')
        bb=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);bb.button(QDialogButtonBox.Save).setText('Enregistrer');bb.button(QDialogButtonBox.Cancel).setText('Annuler');bb.button(QDialogButtonBox.Save).setFixedHeight(32);bb.button(QDialogButtonBox.Cancel).setFixedHeight(32)
        bb.accepted.connect(dlg.accept);bb.rejected.connect(dlg.reject);lay.addWidget(bb)
        if dlg.exec()==QDialog.Accepted:
            cfg=core.load_config();cfg.update(orca_overrides=chk_orca.isChecked(),update_interval_days=cadence.currentData(),preferred_weight_g=weight.currentData(),preferred_packaging=form.currentData())
            try:
                core.save_config(cfg)
                if self.current_sku:self._show_detail(self.current_sku)
                if self.inspector.isVisible():self._refresh_inspector()
                self.status.showMessage('Paramètres enregistrés. Le conditionnement préféré s’applique aux fiches sans choix manuel.',6000)
            except OSError as exc:QMessageBox.critical(self,'Paramètres non enregistrés',str(exc))

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
            "Prépare des données OpenSpool / NFC pour le Snapmaker U1 à firmware "
            "ouvert et d'autres lecteurs OpenSpool. Catalogue multi-fabricants "
            "téléchargé depuis des sources publiques, couleur, températures et "
            "densité. Le fichier exporté peut ensuite être écrit sur une étiquette NFC avec une application dédiée.\n\n"
            "Projet hobby, non affilié aux fabricants de filaments ni à Snapmaker. "
            "Code sous licence MIT.\n\n"
            "Données : Open Filament Database (MIT) · SpoolmanDB (MIT) · "
            "TheFilamentDB (CC-BY 4.0) · pages publiques des fabricants.\n"
            "Les logos restent la propriété de leurs marques respectives ; ils sont "
            "affichés à titre d'identification seulement (voir docs/TRADEMARKS.md)."
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
        bb.button(QDialogButtonBox.Close).setText("Fermer")
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
    configure_application(app)
    # Une seule instance par dossier de données : deux synchronisations
    # simultanées se disputeraient la base et ses sauvegardes.
    os.makedirs(core.DATA_HOME, exist_ok=True)
    instance_lock = QLockFile(os.path.join(core.DATA_HOME, "spoolscribe.instance.lock"))
    instance_lock.setStaleLockTime(0)
    if not instance_lock.tryLock(200):
        QMessageBox.information(None, "SpoolScribe", "SpoolScribe est déjà ouvert pour ce dossier de données.\n"
                                "Utilisez la fenêtre existante.")
        return 0
    try:
        win = MainWindow()
    except (core.DatabaseError, OSError) as exc:
        backup = core.DB_PATH + ".bak"
        if not os.path.isfile(backup) or QMessageBox.question(
            None, "Base illisible", f"{exc}\n\nRestaurer {backup} ?\n"
            "Le fichier actuel sera conservé séparément.", QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            QMessageBox.critical(None, "Base illisible", str(exc))
            return 1
        try:
            core.restore_db()
            win = MainWindow()
        except (core.DatabaseError, OSError) as recovery_error:
            QMessageBox.critical(None, "Restauration impossible", str(recovery_error))
            return 1
    win.show()
    code = app.exec()
    instance_lock.unlock()
    return code


if __name__ == "__main__":
    sys.exit(main())

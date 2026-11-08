#!/usr/bin/env python3
"""
app_gui.py — Application graphique multiplateforme (Windows / macOS / Linux).

Construite sur PySide6 (Qt). Toute la logique métier vient de core.py :
cette couche ne fait que de l'affichage et de l'orchestration UI.

Lancement :  python -m spoolscribe
"""
from __future__ import annotations

from .ui_surfaces import ReadingTabs, fit_dialog

import os
import sys
import time
import functools
import threading
import traceback

from PySide6.QtCore import Qt, QThread, Signal, QSize, QTimer, QRectF, QLockFile, QUrl, QPoint, QEvent
from PySide6.QtGui import (
    QColor, QFont, QPixmap, QPainter, QIcon, QPalette, QPainterPath, QAction, QPen, QDesktopServices,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLineEdit, QTableWidget, QTableWidgetItem, QLabel, QPushButton, QPlainTextEdit,
    QHeaderView, QAbstractItemView, QFrame, QMessageBox, QProgressBar, QGridLayout, QTabWidget,
    QSizePolicy, QStackedWidget, QToolButton, QMenu, QListWidget, QListWidgetItem,
    QDialog, QDialogButtonBox, QCheckBox, QSpinBox, QButtonGroup, QComboBox,
    QScrollArea, QFileDialog, QDoubleSpinBox, QGraphicsDropShadowEffect,
    QStatusBar, QStyle, QStyleOption,
)

try:
    from PySide6.QtSvg import QSvgRenderer
    HAS_SVG = True
except Exception:
    HAS_SVG = False

from . import core
from .i18n import tr, configure_language, LANGUAGES, display_quality
from .app_lifecycle import RESTART_EXIT_CODE, launch_replacement
from .ui_catalogue import CatalogueUx, ClearableTable, ClearableList
from .ui_detail import DetailUx
from .ui_widgets import SearchField, SpoolPreview, MetricGrid, WrapLabel, FilamentDelegate, spool_icon, product_label, display_delta, DetailScrollArea, CONTROL_HEIGHT, CARD_RADIUS, TILE_RADIUS, CONTROL_RADIUS, ReflowRow, ActionLabel

# The inspector lives inside the scroll area; toggling never changes the window.
_INSPECTOR_H = 210
# Coche des cases à cocher (QSS) : chemin POSIX absolu, lisible aussi en mode gelé.
CHECK_ICON_PATH = os.path.join(core.RESOURCE_DIR, "data", "ui", "check.svg").replace(os.sep, "/")
CHEVRON_ICON_PATH = os.path.join(core.RESOURCE_DIR, "data", "ui", "chevron-down.svg").replace(os.sep, "/")


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


class StatusLine(QStatusBar):
    """Status bar whose temporary message is drawn inside its contents margins.

    QStatusBar paints its message 6 px from the window edge whatever its margins, against
    the rounded corner. Here the text follows the margins, is elided when too long and keeps
    its full wording in the tooltip. It is only painted: a message never changes any
    geometry, so it never asks the window for a layout pass.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizeGripEnabled(False)
        self.messageChanged.connect(self._follow_message)

    def displayed_text(self):
        return self.fontMetrics().elidedText(self.currentMessage(), Qt.ElideRight, max(0, self.contentsRect().width()))

    def _follow_message(self, *_):
        text = self.currentMessage()
        self.setToolTip(text if self.displayed_text() != text else '')
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._follow_message()

    def paintEvent(self, event):
        painter = QPainter(self)
        option = QStyleOption()
        option.initFrom(self)
        self.style().drawPrimitive(QStyle.PE_PanelStatusBar, option, painter, self)
        if self.currentMessage():
            painter.setPen(self.palette().windowText().color())
            painter.drawText(self.contentsRect(), Qt.AlignLeading | Qt.AlignVCenter | Qt.TextSingleLine, self.displayed_text())


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


def prepare_qt_environment() -> None:
    """Set up system fonts before QApplication, including frozen UI workers."""
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


# Entry-point imports also run before offscreen tests and frozen workers create
# QApplication. These paths must use the same font discovery as normal startup.
prepare_qt_environment()


def configure_application(app: QApplication) -> None:
    """Shared startup configuration for the app and its visual checks."""
    app.setApplicationName('SpoolScribe')
    if not app.property('spoolscribe_configured'):
        font=app.font()
        # Use the native scalable Windows UI family for compact controls.
        if os.name == 'nt':font.setFamily('Segoe UI')
        font.setPointSizeF(font.pointSizeF()+0.5);app.setFont(font)
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
MIN_WINDOW_WIDTH = 860   # announced minimum; raised only if the real layout needs more (fonts, languages)
MIN_WINDOW_HEIGHT = 560


class MainWindow(DetailUx, CatalogueUx, QMainWindow):
    def __init__(self):
        super().__init__()
        self.app = QApplication.instance()
        configure_language(self.app, core.load_config().get("language", "auto"))
        self.setWindowTitle(f"SpoolScribe {core.APP_VERSION} — OpenSpool / NFC")
        self.resize(1280, 800)
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)

        icon_path = core.app_icon_abs_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        self.db = core.load_db()
        self._restart_requested = False
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
        self._fit_translated_headers()

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

        self.search = SearchField()
        self.search.setObjectName("search")
        self.search.setPlaceholderText(tr('Rechercher : fabricant, matière, référence, couleur…'))
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
        self.btn_view_list.setToolTip(tr('Vue liste'))
        self.btn_view_list.setCheckable(True)
        self.btn_view_list.setChecked(True)
        self.btn_view_list.setCursor(Qt.PointingHandCursor)
        self.btn_view_grid = QToolButton()
        self.btn_view_grid.setObjectName("seg")
        self.btn_view_grid.setIcon(make_view_icon("grid", "#888", 18, dpr))
        self.btn_view_grid.setIconSize(QSize(18, 18))
        self.btn_view_grid.setToolTip(tr('Vue grille'))
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

        # Catalogue synchronisation lives with the catalogue it updates (below),
        # apart from the instant local search of this bar.
        self.update_btn = QPushButton(tr('Actualiser le catalogue'))
        self.update_btn.setObjectName("secondary")
        self.update_btn.setFixedHeight(32)
        self.update_btn.setCursor(Qt.PointingHandCursor)
        self.update_btn.setToolTip(tr('Choisir les sources et actualiser la base'))
        self.update_btn.clicked.connect(self._sync_catalogue)

        # One navigation menu: hardware, settings (data and backups included), about.
        self.menu_btn = QToolButton()
        self.menu_btn.setObjectName("ghost")
        self.menu_btn.setFixedSize(38,32)
        self.menu_btn.setText("⚙")
        self.menu_btn.setToolTip(tr('Menu : matériel, paramètres, à propos'))
        self.menu_btn.setAccessibleName(tr('Menu'))
        self.menu_btn.setCursor(Qt.PointingHandCursor)
        menu = self.main_menu = QMenu(self.menu_btn)
        act_hardware = QAction(tr('Mon matériel…'), self)
        act_hardware.triggered.connect(self._open_hardware)
        menu.addAction(act_hardware)
        act_settings = QAction(tr('Paramètres…'), self)
        act_settings.triggered.connect(self._open_settings)
        menu.addAction(act_settings)
        menu.addSeparator()
        # The single-filament OpenSpool file belongs to that filament's export
        # details (« Détails »), not to this menu nor to data management.
        self.act_archive = QAction(tr('Exporter le JSON OpenSpool du filament…'), self)
        self.act_archive.triggered.connect(lambda: self._generate(mode="archive"))
        self.act_archive.setToolTip(tr('Fichier OpenSpool lisible du filament sélectionné. Ce n’est pas une sauvegarde de vos données.'))
        act_about = QAction(tr('À propos de SpoolScribe'), self)
        act_about.triggered.connect(self._open_about)
        self._about_action=act_about
        menu.addAction(act_about)
        self.menu_btn.clicked.connect(self._show_main_menu)
        top.addWidget(self.menu_btn)
        root.addLayout(top)

        # Filtres : le modèle reste dans trois listes déroulantes cachées ;
        # la barre latérale (fabricants, matières, état) les pilote.
        self.brand_filter = QComboBox()
        self.brand_filter.setAccessibleName(tr('Filtrer par fabricant'))
        self.material_filter = QComboBox()
        self.material_filter.setAccessibleName(tr('Filtrer par matière'))
        self.quality_filter = QComboBox()
        for label, key in ((tr('Toutes les fiches'), "all"), (tr('Prêtes à exporter'), "ready"),
                           (tr('À compléter'), "incomplete"), (tr('À vérifier'), "suspect")):
            self.quality_filter.addItem(label, key)
        for combo in (self.brand_filter, self.material_filter, self.quality_filter):
            combo.setParent(self)
            combo.hide()
            combo.currentIndexChanged.connect(self._apply_filter)

        sorting = QHBoxLayout()
        self.sort1, self.sort2 = QComboBox(), QComboBox()
        self.sort2.addItem(tr('Aucun'), "")
        for key, label in core.CATALOGUE_SORT_FIELDS.items():
            self.sort1.addItem(tr(label), key)
            self.sort2.addItem(tr(label), key)
        self.sort1.setCurrentIndex(self.sort1.findData("brand"))
        self.sort2.setCurrentIndex(self.sort2.findData("product"))
        self.sort1_direction, self.sort2_direction = QComboBox(), QComboBox()
        for direction in (self.sort1_direction, self.sort2_direction):
            direction.addItem(tr('Croissant ↑'), False)
            direction.addItem(tr('Décroissant ↓'), True)
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
        self.previous_page = QPushButton(tr('← Précédent'))
        self.next_page = QPushButton(tr('Suivant →'))
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
        self.update_progress_card = QFrame(); self.update_progress_card.setObjectName('updateProgressCard')
        progress_layout = QVBoxLayout(self.update_progress_card); progress_layout.setContentsMargins(12,10,12,10); progress_layout.setSpacing(6)
        heading = QHBoxLayout(); progress_title = QLabel(tr('Actualisation du catalogue')); progress_title.setObjectName('guidanceTitle')
        self.progress_step = QLabel(); self.progress_step.setObjectName('guidanceNote')
        heading.addWidget(progress_title,1); heading.addWidget(self.progress_step); progress_layout.addLayout(heading)
        progress_row = QHBoxLayout(); progress_row.setSpacing(12)
        self.progress_label = WrapLabel()
        self.progress_label.setMinimumHeight(24)
        self.progress_label.setVisible(False)
        progress_layout.addWidget(self.progress_label)
        self.progress = QProgressBar(); self.progress.setObjectName("catalogueProgress")
        self.progress.setVisible(False)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        progress_row.addWidget(self.progress, 1)
        self.cancel_update_btn = QPushButton(tr('Annuler'))
        self.cancel_update_btn.setVisible(False)
        self.cancel_update_btn.setToolTip(tr("Interrompt la synchronisation ; la base locale reste celle d'avant."))
        self.cancel_update_btn.clicked.connect(self._cancel_update)
        progress_row.addWidget(self.cancel_update_btn)
        progress_layout.addLayout(progress_row); self.update_progress_card.hide()

        # ── Splitter : facettes · liste/grille · fiche ───────────────────
        splitter = self.splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)
        self.sidebar = self._build_sidebar()
        splitter.addWidget(self.sidebar)

        # Pile des deux présentations : table (liste) + grille de cartes
        self.list_stack = QStackedWidget()

        # Vue liste (table)
        self.table = ClearableTable(0, 10)
        self._delta_column = 9
        self._column_keys = ("", "reference", "product", "color_name", "brand", "material", "diameter", "weight", "quality", "")
        self.table.setHorizontalHeaderLabels(["", tr('Référence'), tr('Produit'), tr('Couleur'), tr('Fabricant'), tr('Matière'), "Ø mm", tr('Masse g'), tr('État des données'), tr('Écart ΔE')])
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
        hh.setToolTip(tr('Clic : tri principal, second clic : inverser. Maj + clic ou clic droit : tri secondaire et colonnes.'))
        self.table.setColumnWidth(1, 110)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)   # Produit absorbe la largeur restante.
        self.table.setColumnWidth(3, 112)
        for column, width in ((4, 96), (5, 70), (6, 54), (7, 62), (8, 122)):
            hh.setSectionResizeMode(column, QHeaderView.Interactive)
            self.table.setColumnWidth(column, width)
        # Référence, diamètre et masse restent disponibles dans « Colonnes » ;
        # masqués par défaut : la fiche liste les références de chaque
        # conditionnement, et le produit garde une largeur lisible.
        hh.setSectionResizeMode(self._delta_column, QHeaderView.Fixed)
        self.table.setColumnWidth(self._delta_column, 86)
        hh.moveSection(hh.visualIndex(self._delta_column), 4)
        for column in (1, 6, 7, self._delta_column):
            self.table.setColumnHidden(column, True)
        self.table.itemSelectionChanged.connect(self._on_select)
        self.table.before_clear = lambda: self._confirm_draft_transition()
        self.table.before_navigate = self._before_view_navigation
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
        self.grid.before_clear = lambda: self._confirm_draft_transition()
        self.grid.before_navigate = self._before_view_navigation
        self.list_stack.addWidget(self.grid)

        table_panel = QWidget()
        # Minimum from its real content (toolbar, state, pager); columns scroll horizontally.
        table_panel.setMinimumWidth(0)
        table_layout = QVBoxLayout(table_panel)
        table_layout.setContentsMargins(0, 0, 0, 0)
        tools = QHBoxLayout()
        self.results_label = QLabel(tr('Catalogue'))
        tools.addWidget(self.results_label, 1)
        self.columns_btn = QToolButton()
        self.columns_btn.setText(tr('Colonnes'))
        self.columns_btn.setFixedHeight(32)
        self.columns_btn.setAccessibleName(tr('Choisir les colonnes affichées'))
        self.columns_btn.setToolTip(tr('Choisir les colonnes affichées (aussi par clic droit sur un en-tête)'))
        tools.addWidget(self.segwrap)
        tools.addWidget(self.columns_btn)
        table_layout.addLayout(tools)
        # Catalogue state and its refresh action, then the progress of a running
        # refresh: one stable place, never a floating message.
        # A wrapping, keyboard-reachable state (never elided in a narrow window) opens the report.
        self.database_btn = ActionLabel()
        self.database_btn.setObjectName("statusControl"); self.database_btn.setMinimumHeight(24)
        self.database_btn.setAccessibleName(tr('État du catalogue'))
        self.database_btn.clicked.connect(self._database_details)
        self.catalogue_state = ReflowRow()
        self.catalogue_state.setObjectName('catalogueState')
        self.catalogue_state.addWidget(self.database_btn, 1)
        self.catalogue_state.addWidget(self.update_btn)
        table_layout.addWidget(self.catalogue_state)
        table_layout.addWidget(self.update_progress_card)
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
        detail_inner.installEventFilter(self)
        detail_panel = QWidget()
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(12, 0, 8, 0)
        detail_layout.addWidget(detail_scroll, 1)
        self.detail_footer=QWidget();self.footer_layout=QVBoxLayout(self.detail_footer)
        self.footer_layout.setContentsMargins(0,0,0,0);self.footer_layout.setSpacing(8)
        self.nfc_note.hide()
        self._build_export_explanation(self.footer_layout)
        self.last_export_label=WrapLabel();self.last_export_label.setObjectName('exportState');self.footer_layout.addWidget(self.last_export_label)
        # Export and QR side by side at equal width when both labels fit, otherwise
        # stacked; the row's minimum is one action, so the detail panel can stay narrow.
        def export_actions_width():
            return 2*max(max(b.fontMetrics().horizontalAdvance(line) for line in b.text().splitlines())+32 for b in (self.btn_generate,self.btn_qr))+8
        self.export_action_row=ReflowRow(needed=export_actions_width)
        self.export_action_row.addWidget(self.btn_generate,1);self.export_action_row.addWidget(self.btn_qr,1)
        self.footer_layout.addWidget(self.export_action_row)
        self.btn_inspect.setFixedHeight(32);self.btn_open_out.setFixedHeight(32);self.btn_qr.setFixedHeight(self.btn_generate.height())
        # Own row: three labels do not fit side by side in every language and width.
        # Side by side while both labels fit with the button padding (QSS 12 px + border each side).
        self.secondary_export_row=ReflowRow(needed=lambda:sum(b.fontMetrics().horizontalAdvance(b.text())+26 for b in (self.btn_inspect,self.btn_open_out))+8)
        self.secondary_export_row.addWidget(self.btn_inspect,1);self.secondary_export_row.addWidget(self.btn_open_out,1)
        self.footer_layout.addWidget(self.secondary_export_row);detail_layout.addWidget(self.detail_footer)
        detail_scroll.viewportChanged.connect(self._align_detail_footer)
        self.stack.addWidget(detail_panel)

        splitter.addWidget(self.stack)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)
        # Minimum from the detail's content, whose action rows reflow when narrow.
        self.stack.setMinimumWidth(0)
        splitter.setSizes([220, 620, 400])

        self.setStatusBar(StatusLine(self))
        self.status = self.statusBar()
        # Text aligned with the window content (14 px), clear of the rounded corners.
        self.status.setContentsMargins(14,3,20,5)
        self.status.showMessage(tr('Choisissez un filament.'))

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
        title = WrapLabel(tr('Aucun filament sélectionné'))
        tf = QFont()
        tf.setPointSize(17)
        tf.setWeight(QFont.DemiBold)
        title.setFont(tf)
        title.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        lay.addWidget(title)

        lay.addSpacing(12)

        # ── Sous-texte : trois lignes séparées, chacune centrée ──────────
        lines = [
            tr('Choisissez une référence dans la liste'),
            tr('ou utilisez la barre de recherche.'),
            tr('Basculez entre vue liste et grille en haut à droite.'),
        ]
        for i, txt in enumerate(lines):
            lbl = WrapLabel(txt)   # wraps in a narrow panel instead of imposing its width
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
        # Logo and actions share a row, or stack when the detail panel is narrow.
        head = self.hero_head = ReflowRow()
        hero_actions = QWidget(); hero_actions_layout = QHBoxLayout(hero_actions)
        hero_actions_layout.setContentsMargins(0,0,0,0); hero_actions_layout.setSpacing(6); hero_actions_layout.addStretch(1)
        self.logo = QLabel();self.logo.setFixedSize(100,30);self.logo.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        halo=QGraphicsDropShadowEffect(self.logo);halo.setOffset(0,0);halo.setBlurRadius(7);halo.setColor(QColor(255,255,255,175));halo.setEnabled(False);self.logo.setGraphicsEffect(halo)
        head.addWidget(self.logo)
        self.favorite_btn=QToolButton();self.favorite_btn.setText(tr('☆ Favori'));self.favorite_btn.setCheckable(True)
        self.btn_similar=QToolButton();self.btn_similar.setText(tr('Teintes'));self.btn_similar.setFixedHeight(CONTROL_HEIGHT)
        self.btn_similar.setObjectName('colourAction')
        self.btn_similar.setToolTip(tr('Comparer cette couleur avec le catalogue'))
        self.btn_similar.clicked.connect(self._open_colour_search);hero_actions_layout.addWidget(self.btn_similar)
        self.favorite_btn.setFixedHeight(CONTROL_HEIGHT);self.favorite_btn.clicked.connect(self._toggle_filament_favorite);hero_actions_layout.addWidget(self.favorite_btn)
        head.addWidget(hero_actions,1)
        hero_layout.addWidget(head)
        # Spool beside the titles, or above them when the detail panel is narrow.
        def hero_body_width():
            words=self.title.text().split() or ['']
            return self.spool_preview.width()+10+max(self.title.fontMetrics().horizontalAdvance(word) for word in words)+40
        body=self.hero_body=ReflowRow(spacing=10,needed=hero_body_width)
        self.spool_preview=SpoolPreview();body.addWidget(self.spool_preview);body.box.setAlignment(self.spool_preview,Qt.AlignTop|Qt.AlignLeft)
        titles=QVBoxLayout();titles.setSpacing(5)
        self.title=WrapLabel('—');self.title.setObjectName('filamentTitle');font=self.title.font();font.setPointSize(17);font.setBold(True);self.title.setFont(font)
        titles.addWidget(self.title)
        self.subtitle_sku=QLabel();self.subtitle_sku.hide()
        self.subtitle_color=WrapLabel();self.subtitle_color.setObjectName('subtitle_color');titles.addWidget(self.subtitle_color)
        self.filament_meta=WrapLabel();self.filament_meta.setObjectName('fieldvalue');titles.addWidget(self.filament_meta)
        self.swatch=QLabel('—');self.swatch.setObjectName('swatch');self.swatch.setMaximumHeight(28);self.swatch.setTextInteractionFlags(Qt.TextSelectableByMouse)
        titles.addWidget(self.swatch);titles.addStretch(1)
        titles_widget=QWidget();titles_widget.setLayout(titles);body.addWidget(titles_widget,1);hero_layout.addWidget(body)
        self.color_caption=QLabel(tr('Couleur'));self.color_caption.hide()
        self.variant_label=QLabel(tr('Bobine'))
        self.variant_choice=QComboBox();self.variant_choice.setMinimumWidth(0)
        self.variant_choice.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon);self.variant_choice.setMinimumContentsLength(8)
        self.variant_choice.currentIndexChanged.connect(self._variant_changed)
        packaging_row=QHBoxLayout();packaging_row.addWidget(self.variant_label);packaging_row.addWidget(self.variant_choice,1);hero_layout.addLayout(packaging_row)
        self.package_hint=WrapLabel();self.package_hint.setObjectName('packageHint');self.package_hint.hide();hero_layout.addWidget(self.package_hint)
        dl.addWidget(self.hero)
        self.shade_panel=QWidget();self.shade_layout=QVBoxLayout(self.shade_panel);self.shade_layout.setContentsMargins(0,0,0,0)
        self.shade_hint=WrapLabel(tr('Quelle teinte correspond à votre bobine ?'));self.shade_layout.addWidget(self.shade_hint)
        self.shade_row=QGridLayout();self.shade_layout.addLayout(self.shade_row);self.shade_buttons=[];dl.addWidget(self.shade_panel)
        # Four scannable tiles replace the label/value inventory.
        caption=QLabel(tr('CARACTÉRISTIQUES'));caption.setObjectName('caption');self._muted_labels.append(caption);dl.addWidget(caption)
        self.btn_edit_physical=QToolButton();self.btn_edit_physical.setText(tr('Modifier…'));self.btn_edit_physical.clicked.connect(lambda:self._edit_physical())
        self.card=QFrame();self.card.setObjectName('physicalCard');card_layout=QVBoxLayout(self.card);card_layout.setContentsMargins(0,0,0,0)
        self.characteristics=MetricGrid();card_layout.addWidget(self.characteristics);self._field_widgets=dict(self.characteristics.values)
        dl.addWidget(self.card)
        self.provenance_toggle=QToolButton();self.provenance_toggle.setText(tr('Détails et sources'));self.provenance_toggle.setCheckable(True);self.provenance_toggle.toggled.connect(self._toggle_provenance)
        # Equal side by side, stacked when the detail panel cannot show both whole.
        self.characteristic_row=ReflowRow();self.characteristic_actions=self.characteristic_row.box;self.characteristic_actions.setSpacing(8)
        for button in (self.btn_edit_physical,self.provenance_toggle):
            button.setFixedHeight(CONTROL_HEIGHT);button.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
            self.characteristic_row.addWidget(button,1)
        dl.addWidget(self.characteristic_row)
        self._build_draft_editor(dl)
        self._build_comparison_card(dl)
        self.provenance_box=QFrame();self.provenance_box.setObjectName('provenanceCard')
        self.fields=QGridLayout(self.provenance_box);self.fields.setContentsMargins(12,10,12,10);self.fields.setHorizontalSpacing(12);self.fields.setVerticalSpacing(8)
        for i,name in enumerate(('Références','Source')):
            label=QLabel(tr(name));label.setProperty('field_key',name);value=WrapLabel('—');value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value.setAlignment(Qt.AlignTop|Qt.AlignLeft)
            self.fields.addWidget(label,i,0,Qt.AlignTop);self.fields.addWidget(value,i,1,Qt.AlignTop);self._field_widgets[name]=value
        self.fields.setColumnStretch(1,1)
        for name in ('Produit','Type','Couleur','SKU','Marque','SKU fabricant','Masse'):
            value=QLabel('—');value.hide();self._field_widgets[name]=value
        dl.addWidget(self.provenance_box);self._toggle_provenance(False)
        self.hardware_summary=WrapLabel();self.hardware_summary.setObjectName('hardwareSummary')
        self.btn_hardware=QToolButton();self.btn_hardware.setText(tr('Mon matériel…'));self.btn_hardware.clicked.connect(self._open_hardware);self.btn_hardware.hide()

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
        self.nfc_profile.addItem(tr('Automatique — format compact'), "auto")
        self.nfc_profile.addItem(tr('Essentiel'), "essential")
        self.nfc_profile.addItem(tr('Avec les descriptifs et le logo'), "full")
        self.nfc_profile.setCurrentIndex(max(0, self.nfc_profile.findData(defaults["profile"])))
        self.tag_type.setParent(self.nfc_advanced)
        self.tag_type.hide()
        nfc_row.addWidget(self.nfc_profile, 1)
        advanced_layout.addLayout(nfc_row)
        reserve_row = QHBoxLayout()
        reserve_row.addWidget(QLabel(tr("Réserve pour l'application d'écriture")))
        self.nfc_reserve = QSpinBox()
        self.nfc_reserve.setRange(0, core.NFC_CAPACITIES[self.tag_type.currentData()])
        self.nfc_reserve.setSuffix(tr(' octets'))
        self.nfc_reserve.setValue(defaults["reserved_bytes"])
        self.nfc_reserve.setToolTip(tr("Espace réservé à d'autres enregistrements NDEF ou données du logiciel d'écriture. À vérifier dans ce logiciel ; zéro ne prédit pas ses ajouts."))
        reserve_row.addWidget(self.nfc_reserve)
        advanced_layout.addLayout(reserve_row)
        self.setup_details.layout().addWidget(self.nfc_advanced)
        self.nfc_advanced.hide()
        self._build_hardware_dialog()
        self.nfc_note = QLabel()
        self.nfc_note.setWordWrap(True)
        self.nfc_note.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        dl.addWidget(self.nfc_note)
        self.nfc_capacity = QLabel(tr('Sélectionnez une fiche pour calculer sa taille NFC.'))
        self.nfc_capacity.setWordWrap(True)
        self.nfc_capacity.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        dl.addWidget(self.nfc_capacity)
        self.tag_type.currentIndexChanged.connect(self._nfc_changed)
        self.nfc_profile.currentIndexChanged.connect(self._nfc_changed)
        self.nfc_reserve.valueChanged.connect(self._nfc_changed)
        self.btn_opentag_settings=QPushButton(tr('Modifier les valeurs de l’étiquette…'))
        self.btn_opentag_settings.setFixedHeight(CONTROL_HEIGHT)
        self.btn_opentag_settings.clicked.connect(self._complete_opentag_settings)
        self.btn_opentag_settings.hide()  # Reparented into export details, outside the filament card.
        self._wire_export_assistant()

        # Respiration au-dessus de l'action principale (la centre verticalement).
        dl.addStretch(1)

        # Action principale : c'est LA fonction de l'app → grande, pleine
        # largeur, bien en évidence au milieu du panneau.
        self.btn_generate = QPushButton(tr('Exporter pour NFC'))
        self.btn_generate.setObjectName("primary")
        self.btn_generate.setProperty('large',True)
        self.btn_generate.setCursor(Qt.PointingHandCursor)
        self.btn_generate.setFixedHeight(48)
        self.btn_generate.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        gf = self.btn_generate.font()
        gf.setPointSize(max(11, gf.pointSize() + 2))
        gf.setWeight(QFont.DemiBold)
        self.btn_generate.setFont(gf)
        self.btn_generate.clicked.connect(self._primary_action)
        dl.addWidget(self.btn_generate)

        # Actions secondaires juste sous l'action principale.
        sec = QHBoxLayout()
        sec.setSpacing(8)
        self.btn_inspect = QPushButton(tr('Voir le JSON'))
        self.btn_inspect.setObjectName("secondary")
        self.btn_inspect.setCursor(Qt.PointingHandCursor)
        self.btn_inspect.clicked.connect(self._toggle_inspect)
        self.btn_open_out = QPushButton(tr('Afficher le fichier'))
        self.btn_open_out.setObjectName("secondary")
        self.btn_open_out.setCursor(Qt.PointingHandCursor)
        self.btn_open_out.clicked.connect(self._open_output)
        self.btn_qr = QPushButton(tr('Afficher le QR Code\nSpoolScribe Companion'))
        self.btn_qr.setObjectName("secondary")
        self.btn_qr.setProperty("actionTone", "companion")
        self.btn_qr.setCursor(Qt.PointingHandCursor)
        self.btn_qr.setAccessibleName(tr('Afficher le QR Code pour SpoolScribe Companion'))
        self.btn_qr.setEnabled(False)
        self.btn_qr.clicked.connect(self._open_qr)


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
        colour_ink = accent
        hardware_ink = '#96bce8' if t['dark'] else '#365f91'
        attention_ink = '#ebc381' if t['dark'] else '#895c12'
        # Accent meanings (same meaning, same style everywhere):
        # - accent (teal): the active choice, focus or selection, and the main action;
        # - accent border on an editor: a draft being edited (unsaved values);
        # - accent left rule on a parameter: value differs from the reference;
        # - attention ink (amber) left rule / badge: something to do or to know before
        #   an action (blocked export, unencrypted file). « Ready » only means the
        #   software preparation is complete: it gets no rule and never states that
        #   any hardware read the tag;
        # - hardware / colour rules: the subject of a guidance tile in its own dialog.
        card_radius,tile_radius,control_radius=CARD_RADIUS,TILE_RADIUS,CONTROL_RADIUS
        base_colour,accent_colour=QColor(t['card']),QColor(accent)
        facet_fill=QColor(*[round(base_colour.getRgb()[i]*.88+accent_colour.getRgb()[i]*.12) for i in range(3)]).name()

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
            f" border-radius:7px; padding:6px 12px; }}"
            f"QPushButton#secondary:hover {{ background:{t['sec_hover']}; }}"
        )
        qr_ink = "#cfb9ef" if t["dark"] else "#684494"
        qr_bg = "#343043" if t["dark"] else "#f0eaf8"
        qr_hover = "#443953" if t["dark"] else "#e6dcf2"
        secondary_qss += (
            f'QPushButton#secondary[actionTone="companion"] {{ background:{qr_bg}; color:{qr_ink}; border:1px solid {qr_ink}; }}'
            f'QPushButton#secondary[actionTone="companion"]:hover {{ background:{qr_hover}; }}'
            f'QPushButton#secondary[actionTone="companion"]:disabled {{ background:{t["sec_bg"]}; color:{faint}; border:1px solid {t["border"]}; }}'
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
            f" border-radius:7px; min-height:18px; padding:6px 8px; font-size:13px; }}"
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
            f"QSpinBox, QDoubleSpinBox {{ background:{t['field_bg']}; color:{t['text']};"
            f" border:1px solid {t['border']}; border-radius:6px; padding:3px 6px; }}"
            f"QCheckBox {{ color:{t['text']}; background:transparent; spacing:6px; }}"
            f"QCheckBox::indicator {{ width:15px; height:15px; border:1px solid {t['faint']};"
            f" border-radius:4px; background:{t['field_bg']}; }}"
            f"QCheckBox::indicator:checked {{ background:{accent}; border-color:{accent};"
            f" image:url({CHECK_ICON_PATH}); }}"
            f"QCheckBox::indicator:disabled {{ border-color:{t['border']}; background:{t['window']}; }}"
            f"QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{ background:{t['field_bg']}; color:{t['text']}; border:1px solid {t['border']}; border-radius:7px; min-height:18px; padding:6px 8px; }}"
            f"QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {{ border-color:{accent}; }}"
            f"QComboBox::drop-down {{ border:none; width:24px; subcontrol-origin:padding; subcontrol-position:top right; }}"
            f"QComboBox::down-arrow {{ image:url({CHEVRON_ICON_PATH}); width:12px; height:8px; }}"
            f"QComboBox#printerPicker::down-arrow {{ image:none; }}"
            f"QMenu {{ background:{t['card']}; color:{t['text']}; border:1px solid {t['border']}; border-radius:8px; padding:5px; }}"
            f"QMenu::item {{ min-height:18px; padding:6px 14px; border-radius:5px; }}"
            f"QMenu::item:selected {{ background:{t['sel']}; color:{t['sel_text']}; }}"
            f"QMenu::separator {{ height:1px; background:{t['border']}; margin:4px 8px; }}"
            f"QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QLineEdit:disabled {{ color:{t['faint']};"
            f" background:{t['window']}; border-color:{t['border']}; }}"
            f"QPushButton:disabled, QToolButton:disabled {{ color:{t['faint']}; }}"
            f"QPushButton#chip {{ border:1px solid {t['border']}; border-radius:12px; padding:2px 11px;"
            f" background:{t['field_bg']}; color:{t['text']}; }}"
            f"QPushButton#chip:hover {{ border-color:{accent}; color:{accent}; }}"
            f"QProgressBar {{ background:{t['field_bg']}; color:{t['text']};"
            f" border:1px solid {t['border']}; border-radius:6px; text-align:center; }}"
            f"QProgressBar::chunk {{ background:{accent}; border-radius:5px; }}"
            f"QFrame#updateProgressCard {{ background:{t['panel'] if 'panel' in t else t['field_bg']}; border:1px solid {t['border']}; border-radius:10px; }}"
            f"QProgressBar#catalogueProgress {{ border:0; border-radius:4px; background:{t['border']}; }}"
            f"QProgressBar#catalogueProgress::chunk {{ background:{accent}; border-radius:4px; }}"
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
                           + f"QFrame#filamentHero, QFrame#metricTile, QFrame#provenanceCard, QFrame#supportCard {{ background:{t['card']}; border:1px solid {t['border']}; border-radius:{card_radius}px; }}"
                           + f"QLabel#metricLabel {{ color:{t['muted']}; font-size:10px; }}"
                           + f"QToolButton#favoriteFilter {{ padding:6px 4px; }}"
                           + f"QFrame#sourceCard {{ border:1px solid {t['border']}; border-radius:{tile_radius}px; background:{t['field_bg']}; }}"
                           + f"QToolButton#statusControl {{ border:none; color:{t['muted']}; font-size:11px; padding:2px 4px; }}"
                           + f"QLabel#statusControl {{ color:{t['muted']}; font-size:11px; padding:2px 4px; border:1px solid transparent; border-radius:{control_radius}px; }}"
                           + f"QLabel#statusControl:hover {{ color:{t['text']}; }}"
                           + f"QLabel#statusControl:focus {{ border-color:{accent}; }}"
                           + f"QTabWidget::pane {{ border:none; background:transparent; }}"
                           + f"QTabBar::tab {{ background:{t['sec_bg']}; color:{t['muted']}; border:1px solid {t['border']}; border-radius:7px; padding:7px 16px; margin-right:6px; min-width:72px; }}"
                           + f"QTabBar::tab:selected {{ background:{accent}; color:{t['accent_text']}; border-color:{accent}; }}"
                           + f"QListWidget#printerChoices {{ border:none; background:transparent; outline:0; }}"
                           + f"QListWidget#printerChoices::item {{ border:1px solid {t['border']}; border-radius:10px; background:{t['card']}; padding:0; }}"
                           + f"QListWidget#printerChoices::item:selected {{ border:2px solid {accent}; background:{t['sec_bg']}; }}"
                           + f"QLabel#printerBadge {{ background:{t['sec_bg']}; border-radius:12px; font-size:20px; color:{accent}; }}"
                           + f"QLabel#sourceStatus {{ color:{t['muted']}; font-weight:600; }}"
                           + f"QLabel#sourceStatus[success=true] {{ color:{accent}; }}"
                           + f"QLabel#fieldvalue {{ color:{t['text']}; }}"
                           + f"QToolButton#sectionToggle {{ background:transparent; border:1px solid transparent; border-radius:5px; color:{faint};"
                           + f" font-size:11px; letter-spacing:1px; padding:3px 2px; min-height:24px; text-align:left; }}"
                           + f"QToolButton#sectionToggle:hover {{ color:{t['text']}; background:transparent; border-color:transparent; }}"
                           + f"QToolButton#sectionToggle:focus {{ border:1px solid {accent}; }}"
                           + f"QToolButton#sectionToggle:checked {{ background:transparent; color:{faint}; border-color:transparent; }}"
                           + f"QToolButton#sectionToggle:checked:focus {{ border:1px solid {accent}; }}"
                           + f"QToolButton#filterSummary {{ color:{t['muted']}; background:{t['card']}; border:1px solid {t['border']}; border-radius:8px; text-align:left; padding:5px 8px; font-size:11px; }}"
                           + f"QFrame#filterSection {{ background:{t['card']}; border:1px solid {t['border']}; border-radius:8px; }}"
                           + f"QListWidget#facets {{ background:{t['card']}; border:none; outline:0; }}"
                           + f"QListWidget#facets::item {{ padding:2px 4px; border:none; border-radius:4px; }}"
                           + f"QListWidget#facets::item:hover {{ background:{t['sec_bg']}; }}"
                           + f"QListWidget#facets::item:selected {{ background:{facet_fill}; color:{t['text']}; }}"
                           + f"QToolButton#favoriteFilter:checked {{ background:{facet_fill}; color:{t['text']}; border-color:{accent}; }}"
                           + f"QFrame#draftEditor, QFrame#comparisonCard {{ background:{t['card']}; border:1px solid {t['border']}; border-radius:{card_radius}px; }}"
                           + f"QFrame#parameterCard {{ background:{t['field_bg']}; border:1px solid {t['border']}; border-radius:{tile_radius}px; }}"
                           + f"QFrame#parameterCard[tone=changed] {{ border-left:3px solid {accent}; }}"
                           + f"QFrame#parameterCard[tone=attention] {{ border-left:3px solid {attention_ink}; }}"
                           + f"QLabel#parameterState {{ color:{t['muted']}; font-size:10px; }}"
                           + f"QLabel#readingTitle {{ color:{t['text']}; font-size:15px; font-weight:600; }}"
                           + "QFrame#colourFilter { border:none; background:transparent; }"
                           + "QToolButton[colourControl=true] { padding:6px; }"
                           + f"QFrame#exportJourney {{ background:{t['card']}; border:1px solid {t['border']}; border-radius:{card_radius}px; }}"
                           + f"QFrame#guidanceTile {{ background:{t['card']}; border:1px solid {t['border']}; border-radius:{tile_radius}px; }}"
                           + f"QFrame#exportJourney[tone=attention], QFrame#guidanceTile[tone=attention] {{ border-left:3px solid {attention_ink}; }}"
                           + f"QFrame#guidanceTile[tone=colour] {{ border-left:3px solid {colour_ink}; }}"
                           + f"QFrame#guidanceTile[tone=hardware] {{ border-left:3px solid {hardware_ink}; }}"
                           + f"QLabel#journeyStep {{ color:{hardware_ink}; border:1px solid {t['border']}; border-radius:12px; font-weight:600; }}"
                           + f"QLabel#guidanceTitle {{ font-weight:600; color:{t['text']}; }}"
                           + f"QLabel#guidanceValue {{ font-size:16px; font-weight:600; color:{t['text']}; }}"
                           + f"QLabel#guidanceHeading {{ font-size:18px; font-weight:600; color:{t['text']}; }}"
                           + f"QLabel#guidanceNote, QLabel#hardwareSummary {{ color:{t['muted']}; font-size:11px; }}"
                           + f"QLabel#guidanceCaution {{ color:{attention_ink}; }}"
                           + f"QFrame#draftEditor {{ border:1px solid {accent}; }}"
                           + f"QLabel#sectionTitle {{ color:{t['text']}; font-weight:600; }}"
                           + f"QLabel#unencryptedBadge {{ color:{attention_ink}; border:1px solid {attention_ink}; border-radius:{tile_radius}px; padding:2px 8px; font-size:11px; font-weight:600; }}"
                           + f"QLabel#unencryptedWarning, QLabel#exportPathWarning, QLabel#formatNotice {{ color:{attention_ink}; }}"
                           + f"QLabel#supportNote {{ color:{t['muted']}; }}"
                           + f"QLabel#draftBadge {{ color:{accent}; font-weight:600; }}"
                           + f"QLabel#comparisonHead {{ color:{t['muted']}; font-size:10px; }}"
                           + f"QLabel#comparisonNote, QLabel#exportState {{ color:{t['muted']}; font-size:11px; }}"
                           + f"QLabel#exportReady {{ font-weight:600; }}"
                           + f"QLineEdit[draftChanged=true] {{ border:1px solid {accent}; font-weight:600; }}")

        # Equal compact actions use their rendered text plus the QSS padding/border.
        # Windows tool-button hints may impose a larger native minimum; ignore
        # that hint while keeping an explicit minimum that fits the whole label.
        actions=(self.btn_edit_physical,self.provenance_toggle)
        for button in actions:button.ensurePolished()
        width=max(button.fontMetrics().horizontalAdvance(button.text())+18 for button in actions)
        for button in actions:
            button.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed);button.setMinimumWidth(width)
        if hasattr(self,'reset_filters'):
            buttons=(self.sections_menu,self.reset_filters,self.brand_favorites_only,self.favorites_only)
            for button in buttons:button.ensurePolished()
            width=max(button.fontMetrics().horizontalAdvance(button.text())+18 for button in buttons)
            for button in buttons:
                button.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed);button.setMinimumWidth(width)
            colour_width=0
            colour_minimum=max(button.fontMetrics().horizontalAdvance(button.text())+18 for button in (self.colour_rank_btn,self.colour_exit_btn,self.colour_details_button))
            for button in (self.colour_rank_btn,self.colour_exit_btn,self.colour_details_button):
                button.ensurePolished()
                minimum=colour_minimum
                button.setMinimumWidth(minimum);colour_width+=minimum
            # Three colour actions: two 6px gaps, 12px section margins,
            # 2px frame border and 6px sidebar margin. Extra rounding can
            # unnecessarily widen the sidebar with Linux font metrics.
            side_width=max(232,2*width+28,colour_width+32)
            side_width+=side_width%2  # equal paired buttons need an even width
            self.sidebar.setMinimumWidth(side_width); self.sidebar.setMaximumWidth(max(520,side_width+120))
            for index in (1,2):self.splitter.handle(index).setCursor(Qt.SplitHCursor)
            facet_palette=QPalette(self.palette())
            facet_palette.setColor(QPalette.Highlight,QColor(facet_fill));facet_palette.setColor(QPalette.HighlightedText,QColor(t['text']))
            for listing in (self.brand_list,self.family_list,self.state_list):listing.setPalette(facet_palette)
        self._align_detail_footer()
        self._fit_hardware_actions()
        # The two-line QR label keeps its whole height when the window is low.
        self.btn_qr.ensurePolished();self.btn_qr.setMinimumHeight(min(self.btn_qr.maximumHeight(),self.btn_qr.sizeHint().height()))
        self._fit_window_minimum()
        self._refresh_logo()
        for button in (self.favorite_btn,self.btn_similar):button.ensurePolished()
        action_width=max(max(b.sizeHint().width(), b.fontMetrics().horizontalAdvance(b.text())+24) for b in (self.favorite_btn,self.btn_similar))
        for button in (self.favorite_btn,self.btn_similar):button.setFixedWidth(action_width)
        # Titre de la fiche : contraste fort, indépendant du palette OS.
        if hasattr(self, "title"):
            self.title.setStyleSheet(f"color:{t['text']};")
        if hasattr(self, 'printer_card'):
            self._refresh_printer_card()
        if hasattr(self, 'export_journey'):
            self._refresh_export_journey()

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

    def _fit_translated_headers(self):
        # A layout saved in another language may have shorter header labels.
        metrics = self.table.horizontalHeader().fontMetrics()
        for column in range(1, self.table.columnCount()):
            minimum = metrics.horizontalAdvance(self.table.horizontalHeaderItem(column).text()) + 22
            if self.table.columnWidth(column) < minimum:
                self.table.setColumnWidth(column, minimum)

    def _show_empty(self):
        self.stack.setCurrentIndex(0)
        self._fit_window_minimum()

    def event(self, event):
        # Rows that reflow (stack/unstack) change the layout minimum: follow it, coalesced.
        if event.type() == QEvent.LayoutRequest:
            self._schedule_minimum_fit()
        return super().event(event)

    def eventFilter(self, watched, event):
        # The detail's content sits in a scroll area, which does not forward its size
        # changes (draft editor, details, reflowed rows) to the window.
        if event.type() == QEvent.LayoutRequest:
            self._schedule_minimum_fit()
        return super().eventFilter(watched, event)

    def _schedule_minimum_fit(self):
        if not getattr(self, '_minimum_fit_pending', False):
            self._minimum_fit_pending = True
            QTimer.singleShot(0, self, self._fit_window_minimum)

    def _fit_window_minimum(self):
        """Keep the announced minimum width only while the three panels really fit in it.

        The splitter's minimum is the sum of its panels' content minimums and handles; an
        explicit window minimum below it would let Qt overlap the panels. When fonts or a
        language need more, the minimum follows the layout instead of overlapping.
        """
        self._minimum_fit_pending = False
        if not hasattr(self, 'splitter'):return
        # Idempotent: geometry is refreshed and layouts invalidated only when a constraint
        # really changed. Doing it on every pass posted a new LayoutRequest each time,
        # which re-armed this fit forever on an idle window.
        # The detail scrolls vertically only: its viewport must hold the content's own
        # minimum (hero, actions, cards) plus the vertical scroll bar, or it would be cut.
        inner=self.detail_scroll.widget()
        if inner is not None:
            inner.layout().activate()
            bar=self.detail_scroll.verticalScrollBar().sizeHint().width()
            needed_detail=inner.layout().minimumSize().width()+bar+2*self.detail_scroll.frameWidth()
            if self.detail_scroll.minimumWidth()!=needed_detail:
                self.detail_scroll.setMinimumWidth(needed_detail)
                # Read the window minimum once the splitter has taken the new constraint;
                # the LayoutRequest this posts brings the next (settling) pass.
                self.splitter.updateGeometry()
                for layout in (self.centralWidget().layout(), self.layout()):
                    if layout:layout.invalidate()
        hint=self.minimumSizeHint()
        needed=max(MIN_WINDOW_WIDTH,hint.width())
        if self.minimumWidth()!=needed:self.setMinimumWidth(needed)
        needed_height=max(MIN_WINDOW_HEIGHT,hint.height())
        if self.minimumHeight()!=needed_height:self.setMinimumHeight(needed_height)

    def _align_detail_footer(self):
        if hasattr(self,'footer_layout'):
            gutter=max(0,self.detail_scroll.width()-self.detail_scroll.viewport().width())
            self.footer_layout.setContentsMargins(0,0,gutter,0)
            # On odd viewport widths, put the spare pixel in the gap: both
            # characteristic actions keep equal widths and their outer edges.
            self.characteristic_actions.setSpacing(8+self.detail_scroll.viewport().width()%2)
            self._arrange_export_actions()

    def _arrange_export_actions(self):
        if not hasattr(self,'export_action_row'):return
        self.export_action_row.reflow()

    @property
    def _export_actions_inline(self):
        """Export and QR side by side (True) or stacked, as currently laid out."""
        return self.export_action_row.box.direction()==QHBoxLayout.LeftToRight

    def _show_card(self):
        self.stack.setCurrentIndex(1)


    # ── Données / table ──────────────────────────────────────────────────
    def _reload_table(self):
        self._facet_signature = None
        self._sku_rows = core.list_skus(self.db)
        grouped = core.load_config().get("ui", {}).get("group", True) if isinstance(core.load_config().get("ui"), dict) else True
        self._all_rows = core.group_filaments(self._sku_rows) if grouped else list(self._sku_rows)
        for combo, key, label in ((self.brand_filter, "brand", tr('Tous les fabricants')),
                                  (self.material_filter, "family", tr('Toutes les matières'))):
            selected = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(tr(label), "")
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
        if self._colour_query and self.table.isColumnHidden(self._delta_column):
            header = self.table.horizontalHeader()
            header.moveSection(header.visualIndex(self._delta_column), 4)
        self.table.setColumnHidden(self._delta_column, not bool(self._colour_query))
        self.table.setRowCount(len(rows))
        for r, e in enumerate(rows):
            sw = self.table.item(r,0)
            if sw is None:
                sw=QTableWidgetItem();self.table.setItem(r,0,sw)
            sw.setIcon(QIcon(make_swatch_pixmap(None if e.get("hex_variants",0)>1 else e.get("hex"), 18, dpr)))
            sw.setToolTip(f"#{e['hex']}" if e.get("hex") else tr('Couleur à renseigner'))
            for col, key in enumerate(self._column_keys[1:], 1):
                value = e.get(key)
                if isinstance(value, float) and value.is_integer():
                    value = int(value)  # 1000 g, pas 1000.0
                item=self.table.item(r,col)
                if item is None:
                    item=QTableWidgetItem();self.table.setItem(r,col,item)
                item.setText((display_quality(str(value)) if key=="quality" else str(value)) if value is not None else "—")
                item.setToolTip((display_quality(str(value)) if key=="quality" else str(value)) if value is not None else tr("Inconnu"))
                if col == 1:
                    item.setData(Qt.UserRole, e["sku"])
                    shown = e["reference"] if not e["reference"].startswith(("OFD-", "SMDB-")) else "—"
                    if e.get("variant_count", 1) > 1:
                        shown = f"{shown} +{e['variant_count'] - 1}" if shown != "—" else tr('{v0} cond.',v0=e['variant_count'])
                    item.setText(shown)
                    item.setToolTip(tr('Référence interne : {v0}', v0=e['sku']) + (tr('\nRéférence fabricant : {v0}', v0=e['manufacturer_sku']) if e.get("manufacturer_sku") else "")
                                    + (tr("\nConditionnements : ") + ", ".join(v["reference"] for v in e["variants"]) if e.get("variant_count", 1) > 1 else ""))
                if key == 'product' and e.get('diameter'):
                    item.setText(f"{product_label(e['product'],e.get('brand',''))} · {e['diameter']:g} mm")
            color_item = self.table.item(r, 3)
            color_item.setText(e["color_name"] + (" ⚠" if e.get("hex_variants",0)>1 else ""))
            color_item.setToolTip(f"#{e['hex']}" if e.get("hex") else tr('Couleur à renseigner'))
            if not e.get("hex"):
                color_item.setForeground(QColor("#b00"))
            else:
                color_item.setForeground(self.palette().text().color())
            delta_item = self.table.item(r, self._delta_column)
            delta = getattr(self, '_colour_deltas', {}).get(e['sku'], {}).get('delta')
            delta_item.setText(display_delta(delta) if delta is not None else '—')
            delta_item.setTextAlignment(Qt.AlignCenter)
            font = delta_item.font(); font.setBold(True); delta_item.setFont(font)
            delta_item.setData(Qt.UserRole, delta)
            delta_item.setToolTip(tr('Plus l’écart ΔE est petit, plus la couleur d’écran est proche.') +
                (tr('\nÉcart calculé : {v0}. Affichage arrondi au centième supérieur.', v0=f'{delta:.6f}') if delta is not None else ''))
        favorite_keys=set(core.load_config().get("favorite_filaments",[]))
        # Qt stores only the string SKU. Keep Python display data in the delegate;
        # passing whole nested catalogue records through QVariant is unnecessary.
        self.grid.setGridSize(QSize(188,232 if self._colour_query else 216))
        self.grid.itemDelegate().rows={e['sku']:dict(e,_favorite=self._is_favorite(e,favorite_keys),_distance=self._colour_suffix(e['sku']),_delta=getattr(self,'_colour_deltas',{}).get(e['sku'],{}).get('delta')) for e in rows}
        self.grid.itemDelegate().context={'brand':self.brand_filter.currentData() or '','family':self.material_filter.currentData() or ''}
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
            it.setSizeHint(QSize(180,224 if self._colour_query else 208))
            it.setIcon(spool_icon(None if e.get("hex_variants",0)>1 else e.get("hex"),112,dpr,getattr(self,"_tok",{}).get("dark",False)))
            it.setText(e["product"]+"\n"+e["color_name"])
            it.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            it.setData(Qt.UserRole, e["sku"])
            distance=self._colour_suffix(e['sku'])
            help_text=tr('Plus l’écart ΔE est petit, plus la couleur d’écran est proche.') if distance else ''
            it.setToolTip(f"{e['sku']}\n{e['product']} · {e['color_name']}\n{display_quality(e['quality'])}{distance}\n{help_text}" + (tr('\nÉcart calculé : {v0}. Affichage arrondi au centième supérieur.',v0=f"{self._colour_deltas[e['sku']]['delta']:.6f}") if distance else ''))
            it.setData(Qt.AccessibleTextRole, f"{e['color_name'] or tr('Couleur à renseigner')}, {product_label(e['product'],e.get('brand',''))}, {e.get('brand','')}, {display_quality(e['quality'])}{distance}")
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
        elif hasattr(self, "stack") and getattr(self, "_draft", None) and self._draft["sku"] == self.current_sku:
            # A filter hid the reference being edited: keep its card and draft, no loss.
            self.status.showMessage(tr('La fiche en cours de modification n’est plus dans les résultats affichés.'), 8000)
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
        if sku and self._draft and self._group_for_sku(sku) is not self._group_for_sku(self._draft["sku"]) and not self._confirm_draft_transition():
            self._reselect_draft();return
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
        if getattr(self, '_colour_query', None):
            self._filtered_rows = self._rank_by_colour(self._filtered_rows)
        index = next((i for i, r in enumerate(self._filtered_rows) if r['sku'] == self.current_sku or any(v['sku'] == self.current_sku for v in r.get('variants', []))), None) if self.current_sku else None
        self._page = index // self._page_size if index is not None else 0
        self._refresh_facets()
        self._show_page()
        self._header_indicators()
        self._sync_sidebar_selection()
        self._schedule_ui_preferences()

    def _show_page(self):
        total = len(self._filtered_rows)
        start = self._page * self._page_size
        end = min(total, start + self._page_size)
        self._populate(self._filtered_rows[start:end])
        self.page_label.setText(tr('{v0}–{v1} sur {v2}',v0=fmt_int(start + 1) if total else 0,v1=fmt_int(end),v2=fmt_int(total)))
        self.results_label.setText((tr('1 couleur comparable') if total==1 else tr('{v0} couleurs comparables',v0=fmt_int(total))) if getattr(self,'_colour_query',None) else tr('{v0} filaments trouvés',v0=fmt_int(total)))
        self.previous_page.setEnabled(self._page > 0)
        self.next_page.setEnabled(end < total)
        self.previous_page.setVisible(total > self._page_size)
        self.next_page.setVisible(total > self._page_size)

    def _change_page(self, delta):
        if self._draft and self._draft_dirty():
            self.status.showMessage(tr('Brouillon conservé : la fiche reste affichée pendant la navigation.'), 6000)
        last = max(0, (len(self._filtered_rows) - 1) // self._page_size)
        self._page = max(0, min(last, self._page + delta))
        self._show_page()

    def _reset_filters(self):
        if not self._confirm_draft_transition():
            return
        self._clear_colour_filter()
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
            tr('Références : {v0}    Fabricants : {v1}    Produits : {v2}    HEX à préciser : {v3}    Mise à jour complète : {v4}', v0=st['skus'], v1=len(self.db.get('_brands', {})), v2=st['products'], v3=st['missing_hex'], v4=age_str)
            + (tr('    Mise à jour : {v0}', v0=tr(core.UPDATE_STATUS_LABELS.get(self.db['_update_status'], self.db['_update_status'])))
               if self.db.get('_update_status') else "")
            + (tr('    Valeurs locales conservées : {v0}', v0=len(conflicts)) if conflicts else "")
        )
        self._refresh_database_summary()
        self.stats_label.setToolTip(tr('Valeurs locales conservées lors de la fusion :\n') + "\n".join(conflicts[:100])
                                   + (f"\n… et {len(conflicts)-100} autres." if len(conflicts) > 100 else "")
                                   if conflicts else "")

    def _refresh_logo(self, brand: str | None = None):
        """Logo de la marque affichée ; sans argument, celle de la fiche courante."""
        if brand is None:
            view = core.get_sku_view(self.db, self.current_sku) if self.current_sku else None
            brand = (view.product_data.get("brand") if view else "") or ""
        self.logo.graphicsEffect().setEnabled(bool(getattr(self,'_tok',{}).get('dark')))
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
        sku = sku_item.data(Qt.UserRole) or sku_item.text()
        if self._draft and self._group_for_sku(sku) is not self._group_for_sku(self._draft["sku"]) and not self._confirm_draft_transition():
            self._reselect_draft();return
        self.current_sku = sku
        self._show_detail(self.current_sku)

    def _paint_swatch(self):
        t=self._tok;h=(getattr(self,'_cur_hex',None) or '').strip().lstrip('#')
        self.spool_preview.set_filament(h.upper() if len(h)==6 else None,t['dark'])
        self.swatch.setText('#'+h.upper() if len(h)==6 else tr('Teintes à vérifier') if self._variant_needs_choice() else tr('Couleur à renseigner'))
        self.swatch.setStyleSheet(f"color:{t['muted']};background:transparent;font-size:11px;")

    def _show_detail(self, sku):
        draft = getattr(self, "_draft", None)
        if draft and self._group_for_sku(sku) is not None and self._group_for_sku(sku) is self._group_for_sku(draft["sku"]):
            sku = draft["sku"]  # Same filament: the edited package stays shown.
        else:
            sku = self._detail_packaging(sku)
            if draft and draft["sku"] != sku:
                self._close_draft()
        self.current_sku = sku
        view = core.get_sku_view(self.db, sku)
        self._show_card()
        self.status.showMessage(tr('Échap : désélectionner'))
        if view is None:
            self.title.setText(tr('{v0} — produit introuvable', v0=sku))
            self.subtitle_sku.setText("")
            self.subtitle_color.setText("")
            for v in self._field_widgets.values():
                v.setText("—")
            self._cur_hex = None
            self._paint_swatch()
            self.btn_generate.setEnabled(False)
            self.btn_inspect.setEnabled(False)
            self._refresh_logo("")
            self.nfc_capacity.setText(tr('Produit absent : export impossible.'))
            return

        self.title.setText(product_label(view.display_product,view.product_data.get('brand','')))
        # The title wraps between words, never inside one.
        self.title.setMinimumWidth(max((self.title.fontMetrics().horizontalAdvance(word) for word in self.title.text().split()),default=0)+2)
        self.filament_meta.setText(view.type_str)
        group = self._group_for_sku(sku)
        self.subtitle_sku.setText(view.product_data.get('brand') or '')
        self.subtitle_sku.setToolTip(tr('Référence interne : ') + view.sku)
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
        brand = view.product_data.get("brand") or tr('Non renseignée')
        line = view.product_data.get("line")
        self._field_widgets["Marque"].setText(f"{brand} · {line}" if line else brand)
        entry = self.db["_skus"][sku]
        source_names = {entry.get("source", "Catalogue historique")}
        source_names.update(info["source"] for info in view.product_data.get("_field_sources", {}).values() if info.get("source") and info.get("value") is not None)
        source_names.update(info["source"] for info in entry.get("_field_sources", {}).values() if info.get("source"))
        source_names.update(view.product_data.get("_official_references", {}))
        self._field_widgets["Source"].setText(" + ".join(tr(name) for name in sorted(source_names)))
        self._field_widgets["SKU fabricant"].setText(entry.get("manufacturer_sku") or tr('Non fourni'))
        self._field_widgets["Masse"].setText(f"{entry['weight']} g" if entry.get("weight") else tr('Non fournie'))
        self._field_widgets["Références"].setText(self._references_text(sku))

        self._refresh_logo(view.product_data.get("brand") or "")

        self._cur_hex = None if self._variant_needs_choice() else view.hex
        self._paint_swatch()

        self.btn_generate.setEnabled(not (self.worker and self.worker.isRunning()))
        self.btn_inspect.setEnabled(True)
        self.btn_similar.setEnabled(bool(self._cur_hex))
        self._refresh_nfc_capacity()  # also refreshes the comparison of this context
        self._printer_field_help()
        if self.inspector.isVisible():
            self._refresh_inspector()
        self._fit_window_minimum()

    def _build_payload(self):
        view = core.get_sku_view(self.db, self.current_sku)
        if view is None:
            return None
        if self._variant_needs_choice():
            raise core.ExportValidationError(tr('Comparez les pastilles de couleur et choisissez la teinte de votre bobine.'))
        entry = dict(self.db["_skus"][self.current_sku])
        entry["sku"] = self.current_sku
        return core.build_openspool(entry, view.product_data, brand_meta=view.brand_meta,
                                    use_orca_overrides=core.load_config().get("orca_overrides") is True)

    # ── Actions ──────────────────────────────────────────────────────────
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
        dlg.setWindowTitle(tr('Couleur à préciser'))
        lay = QVBoxLayout(dlg)
        note = QLabel(tr('La couleur est inconnue. Choisissez explicitement un HEX représentatif.\nUne couleur transparente ou multicolore ne sera pas remplacée automatiquement par du noir.'))
        note.setTextFormat(Qt.PlainText)
        if entry.get("source_colors"):
            note.setText(note.text() + tr('\nCouleurs fournies par la source : ') + ", ".join(entry["source_colors"]))
        note.setWordWrap(True)
        lay.addWidget(note)
        lay.addWidget(QLabel(tr('HEX représentatif (6 caractères)')))
        hx = QLineEdit()
        lay.addWidget(hx)
        lay.addWidget(QLabel(tr('Alpha facultatif : 00 transparent, FF opaque ; vide pour conserver')))
        alpha = QLineEdit(entry.get("alpha", ""))
        lay.addWidget(alpha)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)
        fit_dialog(dlg,preferred_width=540)
        if dlg.exec() != QDialog.Accepted:
            return False
        value = core.validate_hex(hx.text())
        if not value:
            raise core.ExportValidationError(tr('Couleur invalide : six caractères HEX requis.'))
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
        if self._draft_dirty():
            # Never export a mix of saved values and unsaved draft fields.
            self.status.showMessage(tr('Enregistrez ou annulez le brouillon avant d’exporter.'), 8000)
            return
        if self.worker and self.worker.isRunning():
            self.status.showMessage(tr('Attendez la fin de la mise à jour avant de modifier ou exporter la fiche.'), 6000)
            return
        try:
            if mode == "nfc" and not self._can_export_for_printer():
                return
            if core.get_sku_view(self.db, self.current_sku) is None:
                raise core.ExportValidationError(tr('Produit introuvable pour cette référence.'))
            if not self._complete_color():
                return
            view = core.get_sku_view(self.db, self.current_sku)
            if view is None:
                raise core.ExportValidationError(tr('Produit introuvable pour cette référence.'))
            entry = self.db["_skus"][self.current_sku]
            if mode=='nfc' and self._opentag_selected():
                if not self._ensure_opentag_settings():return
                prepared=self._prepare_opentag()
                directory=QFileDialog.getExistingDirectory(self,tr('Choisir le dossier d’export'),core.export_directory())
                if not directory:return
                out=core.write_opentag3d(prepared,directory)
                self._last_export_directory=directory
                self._record_export(out,mode)
                try:
                    cfg=core.load_config();cfg['export_directory']=directory;core.save_config(cfg)
                except OSError:self.status.showMessage(tr('Fichier exporté ; le dossier n’a pas pu être mémorisé.'),8000)
                else:self.status.showMessage(tr('Export terminé : {v0}',v0=out),8000)
                QMessageBox.information(self,tr('Export terminé'),tr('Fichier enregistré :\n{v0}',v0=out))
                return
            export_options = self._nfc_options() if mode == "nfc" else dict(tag_type=self.tag_type.currentData(), profile="full", reserved_bytes=0)
            # Validate before opening a destination picker; cancellation writes nothing.
            core.serialize_openspool(self._build_payload(),mode=mode,**export_options)
            directory=QFileDialog.getExistingDirectory(self,tr('Choisir le dossier d’export'),core.export_directory())
            if not directory:return
            out = core.write_openspool(self.current_sku, entry, view.product_data,
                                       output_dir=directory,
                                       brand_meta=view.brand_meta, mode=mode,
                                       **export_options,
                                       use_orca_overrides=core.load_config().get("orca_overrides") is True)
            try:
                cfg=core.load_config();cfg['export_directory']=directory;core.save_config(cfg)
            except OSError:
                self.status.showMessage(tr('Fichier exporté ; le dossier n’a pas pu être mémorisé.'),8000)
            else:self.status.showMessage(tr('Export terminé : {v0}', v0=out),8000)
            self._last_export_directory=directory
            self._record_export(out,mode)
            QMessageBox.information(self,tr('Export terminé'),tr('Fichier enregistré :\n{v0}', v0=out))
        except Exception as e:
            QMessageBox.critical(self, "Erreur", tr("Échec de l'export :\n{v0}", v0=e))

    def _toggle_inspect(self):
        if self._draft_dirty() and not self.inspector.isVisible():
            self.status.showMessage(tr('Enregistrez ou annulez le brouillon avant d’exporter.'), 8000)
            return
        if self._opentag_selected() and not self.inspector.isVisible():
            if not self._complete_color() or not self._ensure_opentag_settings():return
        if self.inspector.isVisible():
            self.inspector.setVisible(False)
            self.btn_inspect.setText(tr('Voir l’export') if self._opentag_selected() else tr('Voir le JSON'))
            self.detail_scroll.verticalScrollBar().setValue(getattr(self,"_inspect_scroll_before",0))
        else:
            self._inspect_scroll_before=self.detail_scroll.verticalScrollBar().value()
            self._refresh_inspector()
            self.inspector.setVisible(True)
            self.btn_inspect.setText(tr('Masquer l’export') if self._opentag_selected() else tr('Masquer le JSON'))
            QTimer.singleShot(0,lambda:self.detail_scroll.ensureWidgetVisible(self.inspector) if self.inspector.isVisible() else None)

    def _refresh_inspector(self):
        if self.nfc_format.count() and self.nfc_format.currentIndex() < 0:
            # No format chosen for this setup: nothing to preview (never a substitute).
            self.inspector.setPlainText(tr('Choisissez le format de l’étiquette dans « Configurer ».'))
            return
        try:
            if self._opentag_selected():
                prepared=self._prepare_opentag()
                self.inspector.setPlainText(prepared.preview if self.opentag_output.currentData()=='ndef' else prepared.data.decode('utf-8'))
                return
            payload = self._build_payload()
            if payload is not None:
                text = core.serialize_openspool(payload, **self._nfc_options())
                size = core.nfc_size(text, tag_type=self._nfc_options()["tag_type"], reserved_bytes=self._nfc_options()["reserved_bytes"])
                self.inspector.setPlainText(text)
                self.status.showMessage(tr('JSON : {v0} octets UTF-8 ; occupation NFC : {v1}/{v2} octets (un enregistrement MIME).', v0=size.utf8_bytes, v1=size.type2_bytes, v2=size.capacity_bytes), 10000)
        except (core.ExportValidationError, core.DatabaseError, OSError) as exc:
            self.inspector.setPlainText(tr('Export impossible : {v0}', v0=exc))

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
        box.setWindowTitle(tr('Mise à jour des données — accès réseau'))
        box.setText(
            tr("Cette action va télécharger des données depuis Internet.\nAucune donnée personnelle n'est envoyée.\n\nSources contactées :")
        )
        box.setDetailedText(sources)
        box.setInformativeText(tr('Autoriser les mises à jour réseau ?'))
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        consent = box.exec() == QMessageBox.Yes
        core.set_network_consent(consent)
        return consent

    def _start_update(self, manual=False):
        if self.worker and self.worker.isRunning():
            return
        if getattr(self, "_draft", None):
            # A refresh replaces the catalogue: one explicit decision before any start.
            if not manual or not self._confirm_draft_transition():
                self.status.showMessage(tr('Actualisation non lancée : brouillon en cours.'), 6000)
                return
        try:
            consent = self._ask_network_consent()
        except OSError as exc:
            QMessageBox.critical(self, tr('Consentement non enregistré'), str(exc))
            return
        if not consent:
            self.status.showMessage(tr('Mise à jour annulée (réseau refusé).'), 6000)
            return
        self.update_btn.setEnabled(False)
        self.menu_btn.setEnabled(False)
        self.btn_generate.setEnabled(False)
        self.update_progress_card.show(); self.progress_step.clear()
        self.progress.setVisible(True)
        self.progress_label.setText(tr('Préparation de la synchronisation…'))
        self.progress_label.setVisible(True)
        self.cancel_update_btn.setVisible(True)
        self.cancel_update_btn.setEnabled(True)
        self.progress.setRange(0, len(core.selected_pipeline(core.load_config()["selected_sources"])))
        self.progress.setValue(0)
        self._update_outcome = None

        self._sync_before = self._snapshot_stats()
        self._sync_manual = bool(manual)
        self.worker = UpdateWorker()
        self.worker.progress.connect(self._on_update_progress)
        self.worker.finished_ok.connect(self._on_update_done)
        self.worker.failed.connect(self._on_update_failed)
        self.worker.start()
        self._refresh_database_summary()

    def _on_update_progress(self, label, i, total):
        self.progress.setRange(0,total)
        self.progress.setValue(max(0,i-1))  # Signal is emitted before this source starts.
        self.progress_step.setText(tr('Étape {v0} sur {v1}',v0=i,v1=total))
        self.progress_label.setText(tr(label))
        self.progress.setAccessibleDescription(tr('Étape {v0} sur {v1}',v0=i,v1=total))

    def _cancel_update(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel.set()
            self.cancel_update_btn.setEnabled(False)
            self.progress_label.setText(tr("Annulation demandée : l'étape en cours s'interrompt…"))

    def _show_main_menu(self):
        """Open the menu under the button, right-aligned, inside the window and the screen."""
        menu, button = self.main_menu, self.menu_btn
        menu.ensurePolished(); size = menu.sizeHint()
        below = button.mapToGlobal(QPoint(button.width(), button.height() + 4))
        window = self.frameGeometry()
        screen = (button.screen() or self.app.primaryScreen()).availableGeometry()
        left_limit = max(window.left(), screen.left()); right_limit = min(window.right(), screen.right())
        x = max(left_limit, min(below.x() - size.width(), right_limit - size.width()))
        y = below.y()
        if y + size.height() > screen.bottom():
            y = max(screen.top(), button.mapToGlobal(QPoint(0, 0)).y() - size.height() - 4)
        menu.popup(QPoint(x, y))

    def _finish_update_ui(self):
        self.update_progress_card.hide()
        self.progress.setVisible(False)
        self.progress_label.setVisible(False)
        self.cancel_update_btn.setVisible(False)
        self.update_btn.setEnabled(True)
        self.menu_btn.setEnabled(True)
        self._refresh_database_summary()

    def _on_update_done(self, results):
        self._finish_update_ui()
        if self.worker:
            self.worker.wait(2000)
        cancelled = any(r.status == "cancelled" for r in results)
        n_ko = [r for r in results if not r.ok and r.status != "cancelled"]
        offline = bool(n_ko) and all(r.status == "unavailable" for r in n_ko)
        # Outcome of this run, shown with the catalogue state (never a floating line).
        self._update_outcome = "cancelled" if cancelled else "offline" if offline else None
        try:
            self.db = core.load_db()
        except (core.DatabaseError, OSError) as exc:
            QMessageBox.critical(self, tr('Base illisible'), str(exc))
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
        self._refresh_database_summary()
        before = self._sync_before or self._snapshot_stats()
        after = self._snapshot_stats()
        self._last_report = (results, before, after)
        if cancelled or (offline and not getattr(self, "_sync_manual", False)):
            # Being offline at launch is a normal situation: the catalogue state says so, no window.
            return
        if n_ko or getattr(self, "_sync_manual", False):
            self._show_sync_report(results, before, after)

    def _on_update_failed(self, tb):
        self._update_outcome = "error"
        self._finish_update_ui()
        if self.current_sku:
            self._show_detail(self.current_sku)
        QMessageBox.critical(self, tr('Erreur de mise à jour'), tb)

    # ── Mise à jour automatique ──────────────────────────────────────────
    # ── Paramètres ───────────────────────────────────────────────────────
    def _open_settings(self, *, colour_tab=False):
        """Six tabs. Fields are written only on Enregistrer; Annuler discards them.

        Sources/actualisation and « Retirer l’autorisation réseau » act immediately
        (their own buttons) and are labelled as such: cancelling this window does
        not undo them. Data actions close this window first (see ``after``).
        """
        cfg=core.load_config();dlg=QDialog(self);dlg.setWindowTitle(tr('Paramètres'));dlg.resize(540,460)
        lay=QVBoxLayout(dlg);lay.setContentsMargins(18,18,18,14);lay.setSpacing(12);tabs=ReadingTabs();tabs.setDocumentMode(False);tabs.tabBar().setDrawBase(False);lay.addWidget(tabs,1)
        after={'action':None}

        def page():
            widget=QWidget();layout=QVBoxLayout(widget);layout.setContentsMargins(0,12,0,0);layout.setSpacing(10)
            return widget,layout

        # ── Catalogue ──
        catalogue,catalogue_layout=page()
        catalogue_layout.addWidget(WrapLabel(tr('Actualisez le catalogue à votre rythme. La dernière base locale reste disponible en cas d’échec.')))
        catalogue_layout.addWidget(QLabel(tr('Actualisation au lancement')))
        cadence=QComboBox();cadence.setObjectName('update_interval_days');cadence.setFixedHeight(CONTROL_HEIGHT)
        for days,label in core.UPDATE_INTERVAL_CHOICES:cadence.addItem(tr(label),days)
        effective,stored,valid=core.update_interval_state(cfg)
        unsupported=object()
        if valid:
            cadence.setCurrentIndex(cadence.findData(stored))
        else:
            # Never display an unrepresentable value as « À chaque lancement »; keep it until the user chooses.
            cadence.addItem(tr('Valeur actuelle non prise en charge — conservée'),unsupported);cadence.setCurrentIndex(cadence.count()-1)
        catalogue_layout.addWidget(cadence)
        if not valid:
            warning=WrapLabel(tr('La configuration locale contient une cadence que cette fenêtre ne peut pas représenter. Elle reste enregistrée telle quelle tant que vous n’en choisissez pas une autre.'))
            warning.setObjectName('cadenceWarning');catalogue_layout.addWidget(warning)
        catalogue_layout.addWidget(WrapLabel(tr('L’autorisation réseau reste requise. L’ancien réglage « actualisation automatique » est conservé pour compatibilité ; la cadence choisie ici fait foi.')))
        immediate=QLabel(tr('Actions immédiates'));immediate.setObjectName('sectionTitle');catalogue_layout.addWidget(immediate)
        catalogue_layout.addWidget(WrapLabel(tr('Ces boutons s’appliquent tout de suite. Annuler cette fenêtre ne les annule pas.')))
        sources=QPushButton(tr('Sources du catalogue…'));sources.clicked.connect(self._choose_sources);catalogue_layout.addWidget(sources)
        revoke=QPushButton(tr('Retirer l’autorisation réseau'));revoke.setObjectName('revokeNetworkConsent');revoke.setEnabled(core.has_network_consent())
        def revoke_consent():
            try:core.set_network_consent(False,auto_update=False);dlg.reject()
            except OSError as exc:QMessageBox.critical(self,tr('Paramètres'),str(exc))
        revoke.clicked.connect(revoke_consent);catalogue_layout.addWidget(revoke);catalogue_layout.addStretch(1);tabs.addTab(catalogue,tr('Catalogue'))

        # ── Filaments ──
        filaments,filament_layout=page()
        filament_layout.addWidget(QLabel(tr('Ma bobine habituelle')))
        filament_layout.addWidget(WrapLabel(tr('Présélection utilisée si elle existe. Vous pouvez la modifier dans la fiche.')))
        weight=QComboBox();weight.setObjectName('preferred_weight_g')
        selected_weight=cfg.get('preferred_weight_g',1000)
        if type(selected_weight) is not int or not 0<=selected_weight<=20000:selected_weight=1000
        weights=sorted({0,250,500,750,1000,1500,2000,2500,3000,5000,selected_weight})
        for grams in weights:weight.addItem(tr('Selon la fiche') if not grams else (f'{grams/1000:g} kg' if grams>=1000 else f'{grams} g').replace('.',','),grams)
        weight.setCurrentIndex(max(0,weight.findData(cfg.get('preferred_weight_g',1000))));weight.setFixedHeight(32)
        form=QComboBox();form.setObjectName('preferred_packaging')
        for label,key in ((tr('Indifférent'),'any'),(tr('Avec bobine'),'spool'),(tr('Recharge'),'refill')):form.addItem(label,key)
        form.setCurrentIndex(max(0,form.findData(cfg.get('preferred_packaging','any'))));form.setFixedHeight(32)
        form_grid=QGridLayout();form_grid.setContentsMargins(0,0,0,0);form_grid.setHorizontalSpacing(16);form_grid.setVerticalSpacing(10)
        mass_label=QLabel(tr('Masse'));mass_label.setBuddy(weight);format_label=QLabel(tr('Format'));format_label.setBuddy(form)
        form_grid.addWidget(mass_label,0,0);form_grid.addWidget(weight,0,1);form_grid.addWidget(format_label,1,0);form_grid.addWidget(form,1,1);form_grid.setColumnStretch(1,1);filament_layout.addLayout(form_grid)
        filament_layout.addStretch(1);tabs.addTab(filaments,tr('Filaments'))

        # ── Étiquettes et export ──
        labels_page,labels_layout=page()
        labels_layout.addWidget(QLabel(tr('Dossier d’export')))
        export_path=QLineEdit(core.export_directory(cfg));export_path.setObjectName('export_directory');export_path.setReadOnly(True);export_path.setFixedHeight(CONTROL_HEIGHT)
        browse=QPushButton(tr('Choisir…'));browse.setFixedHeight(CONTROL_HEIGHT)
        def choose_export_folder():
            chosen=QFileDialog.getExistingDirectory(dlg,tr('Choisir le dossier d’export'),export_path.text())
            if chosen:export_path.setText(chosen)
        browse.clicked.connect(choose_export_folder);folder_row=QHBoxLayout();folder_row.addWidget(export_path,1);folder_row.addWidget(browse);labels_layout.addLayout(folder_row)
        labels_layout.addWidget(QLabel(tr('Valeurs du fichier NFC')))
        chk_orca=QCheckBox(tr('Préférer les valeurs Orca à l’export'));chk_orca.setObjectName('orca_overrides');chk_orca.setChecked(cfg.get('orca_overrides') is True)
        chk_orca.setToolTip(tr('Désactivé : vos corrections locales restent prioritaires. Le fichier JSON permet de vérifier les valeurs exportées.'))
        labels_layout.addWidget(chk_orca)
        labels_layout.addWidget(WrapLabel(tr('Télécharger la source Orca rend des profils disponibles ; cette option décide seulement s’ils remplacent les valeurs du catalogue. Désactivée, un profil Orca applicable complète uniquement les valeurs manquantes.')))
        hardware=QPushButton(tr('Mon matériel…'));hardware.setObjectName('openHardware')
        hardware.setToolTip(tr('Imprimante, lecteur, logiciel et étiquette NFC'))
        def open_hardware():
            after['action']=self._open_hardware;dlg.reject()
        hardware.clicked.connect(open_hardware);labels_layout.addWidget(hardware,0,Qt.AlignLeft)
        labels_layout.addWidget(WrapLabel(tr('Le format papier des QR se règle dans la fenêtre QR.')))
        labels_layout.addStretch(1);tabs.addTab(labels_page,tr('Étiquettes et export'))

        # ── Couleurs ──
        colour_page,colour_layout=page()
        colour_layout.addWidget(QLabel(tr('Jusqu’à quelle distance chercher ?')))
        colour_layout.addWidget(WrapLabel(tr('ΔE est un écart de couleur, pas un pourcentage. Maximum 3 garde les scores de 0 à 3 inclus ; 3,04 est écarté. Aucune marge n’est ajoutée.')))
        delta_presets=QComboBox();delta_presets.setObjectName('colour_delta_preset');delta_presets.setFixedHeight(CONTROL_HEIGHT)
        for label,value in ((tr('Maximum 3 · ΔE ≤ 3'),3.0),(tr('Maximum 10 · ΔE ≤ 10'),10.0),(tr('Maximum 20 · ΔE ≤ 20'),20.0),(tr('Toutes les couleurs'),None),(tr('Personnalisé'),'custom')):delta_presets.addItem(label,value)
        delta_number=QDoubleSpinBox();delta_number.setObjectName('colour_delta_max');delta_number.setRange(0,200);delta_number.setDecimals(1);delta_number.setSingleStep(0.5);delta_number.setPrefix('ΔE ≤ ');delta_number.setFixedHeight(CONTROL_HEIGHT)
        initial_delta=core.colour_delta_limit(cfg);delta_number.setValue(initial_delta if initial_delta is not None else 10)
        delta_presets.setCurrentIndex(max(0,delta_presets.findData(initial_delta) if initial_delta in (None,3,10,20) else delta_presets.findData('custom')));delta_number.setEnabled(initial_delta is not None)
        def preset_changed():
            value=delta_presets.currentData();delta_number.setEnabled(value is not None)
            if type(value) in (float,int):delta_number.setValue(value)
        def number_changed():
            value=delta_number.value();index=delta_presets.findData(value) if value in (3,10,20) else delta_presets.findData('custom')
            delta_presets.blockSignals(True);delta_presets.setCurrentIndex(index);delta_presets.blockSignals(False)
        delta_presets.currentIndexChanged.connect(preset_changed);delta_number.valueChanged.connect(number_changed)
        colour_layout.addWidget(delta_presets);colour_layout.addWidget(delta_number);colour_layout.addWidget(WrapLabel(tr('Valeur initiale : 10. Choisissez « Toutes les couleurs » pour explorer sans limite.')))
        colour_layout.addWidget(WrapLabel(tr('Les références couleur saisies et les réglages d’appareil se gèrent dans « Références couleur ».')))
        colour_layout.addStretch(1)
        colour_index=tabs.addTab(colour_page,tr('Couleurs'))

        # ── Interface ──
        interface,interface_layout=page()
        interface_layout.addWidget(QLabel(tr('Langue de l’interface')))
        language=QComboBox();language.setObjectName('interface_language');language.setFixedHeight(CONTROL_HEIGHT)
        from .i18n import system_ui_languages, resolve_language
        system_languages = system_ui_languages()
        detected = resolve_language('auto', system_languages)
        language.addItem(tr('Automatique — {v0}', v0=LANGUAGES[detected]),'auto')
        language.setItemData(0,tr('Langues du système : {v0}. Si elles ne sont pas prises en charge : anglais.',v0=', '.join(system_languages) or tr('Inconnu')),Qt.ToolTipRole)
        for code,name in LANGUAGES.items():language.addItem(name,code)
        language.setCurrentIndex(max(0,language.findData(cfg.get('language','auto'))));interface_layout.addWidget(language)
        interface_layout.addWidget(WrapLabel(tr('Après enregistrement, vous pourrez redémarrer maintenant ou plus tard.')))
        interface_layout.addStretch(1);tabs.addTab(interface,tr('Interface'))

        # ── Données et sauvegardes ──
        # Files leave this computer only as the person decides: each creating action
        # carries a visible « Non chiffré » badge and its exact scope.
        data_page,data_layout=page()
        intro=WrapLabel(tr('Ces actions utilisent vos réglages déjà enregistrés : les modifications non enregistrées de cette fenêtre ne sont pas incluses. La fenêtre se ferme d’abord sans les enregistrer ; chaque action demande ensuite confirmation et Annuler n’écrit rien.'))
        intro.setObjectName('dataIntro');data_layout.addWidget(intro)
        def data_button(text,name,action):
            button=QPushButton(text);button.setObjectName(name);button.setFixedHeight(CONTROL_HEIGHT)
            button.clicked.connect(lambda _=False,action=action:(after.__setitem__('action',action),dlg.reject()))
            return button
        def unencrypted(name):
            badge=QLabel(tr('Non chiffré'));badge.setObjectName('unencryptedBadge');badge.setProperty('badgeFor',name)
            badge.setAccessibleName(tr('Fichier non chiffré'));return badge
        def section(title,text):
            heading=QLabel(title);heading.setObjectName('sectionTitle');data_layout.addWidget(heading)
            note=WrapLabel(text);data_layout.addWidget(note);return note
        prefs_note=section(tr('Préférences · fichier JSON'),
            tr('JSON en clair, partiel : langue, actualisation et sources, bobine préférée, favoris, imprimante et étiquette NFC, réglages OpenTag3D par référence, format papier QR, limite de couleur. Non inclus : catalogue, copies personnelles, registre couleur, autorisation réseau, dates et état des actualisations. En option : disposition et filtres, chemin du dossier d’export (chemin local).'))
        prefs_note.setObjectName('preferencesScope')
        prefs_row=QHBoxLayout();prefs_row.setSpacing(8)
        prefs_row.addWidget(data_button(tr('Exporter les préférences…'),'exportPreferences',self._export_settings))
        prefs_row.addWidget(unencrypted('exportPreferences'))
        prefs_row.addSpacing(8)
        prefs_row.addWidget(data_button(tr('Importer les préférences…'),'importPreferences',self._import_settings))
        prefs_row.addStretch(1);data_layout.addLayout(prefs_row)
        backup_note=section(tr('Mes données · archive ZIP'),
            tr('ZIP en clair, plus complet : catalogue avec vos copies personnelles et corrections, références couleur, réglages d’appareil de mesure, profils Orca locaux et liste d’imprimantes téléchargée s’ils existent. En option : préférences, disposition, chemin du dossier d’export, exports générés. Il peut contenir des données personnelles et des chemins locaux. La liste exacte s’affiche avant la création ; un aperçu précède toute restauration.'))
        backup_note.setObjectName('backupScope')
        backup_row=QHBoxLayout();backup_row.setSpacing(8)
        backup_row.addWidget(data_button(tr('Sauvegarder mes données…'),'createBackup',self._create_backup))
        backup_row.addWidget(unencrypted('createBackup'))
        backup_row.addSpacing(8)
        backup_row.addWidget(data_button(tr('Restaurer mes données…'),'restoreBackup',self._restore_backup))
        backup_row.addStretch(1);data_layout.addLayout(backup_row)
        from . import ui_backup
        revert=data_button(tr('Annuler la dernière restauration…'),'revertRestore',self._revert_restore)
        revert.setEnabled(ui_backup.last_restore() is not None)
        revert.setToolTip(tr('Rétablit vos fichiers dans leur état d’avant la dernière restauration, à partir de la copie exacte conservée sur cet ordinateur.'))
        revert_row=QHBoxLayout();revert_row.addWidget(revert);revert_row.addStretch(1);data_layout.addLayout(revert_row)
        encryption=WrapLabel(tr('Sauvegarde chiffrée : non disponible dans cette version. Conservez l’archive dans un emplacement protégé.'))
        encryption.setObjectName('backupEncryptionUnavailable');data_layout.addWidget(encryption)
        data_layout.addStretch(1);tabs.addTab(data_page,tr('Données et sauvegardes'))

        if colour_tab:tabs.setCurrentIndex(colour_index)
        bb=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);bb.button(QDialogButtonBox.Save).setText(tr('Enregistrer'));bb.button(QDialogButtonBox.Cancel).setText(tr('Annuler'));bb.button(QDialogButtonBox.Save).setFixedHeight(32);bb.button(QDialogButtonBox.Cancel).setFixedHeight(32)
        bb.accepted.connect(dlg.accept);bb.rejected.connect(dlg.reject);lay.addWidget(bb)
        fit_dialog(dlg,preferred_width=640)
        if dlg.exec()==QDialog.Accepted:
            cfg=core.load_config();previous_language=cfg.get('language','auto')
            cfg.update(language=language.currentData(),orca_overrides=chk_orca.isChecked(),preferred_weight_g=weight.currentData(),preferred_packaging=form.currentData(),export_directory=export_path.text(),colour_delta_max=None if delta_presets.currentData() is None else delta_number.value())
            if cadence.currentData() is not unsupported:
                cfg['update_interval_days']=cadence.currentData()
            try:
                core.save_config(cfg)
                self._refresh_colour_limit_label()
                if self._colour_query:self._apply_filter()
                if self.current_sku:self._show_detail(self.current_sku)
                if self.inspector.isVisible():self._refresh_inspector()
                self.status.showMessage(tr('Paramètres enregistrés. Le conditionnement préféré s’applique aux fiches sans choix manuel.'),6000)
            except OSError as exc:
                QMessageBox.critical(self,tr('Paramètres non enregistrés'),str(exc));return
            if previous_language != cfg['language']:
                self._offer_language_restart()
        elif after['action'] is not None:
            after['action']()

    def _restart_busy(self):
        return any(worker and worker.isRunning() for worker in (self.worker, self._release_worker))

    def _offer_language_restart(self):
        box = QMessageBox(self)
        box.setWindowTitle(tr('Changer la langue'))
        box.setIcon(QMessageBox.Information)
        box.setText(tr('La langue a été enregistrée. Redémarrer SpoolScribe pour l’appliquer ?'))
        if self._restart_busy():
            box.setInformativeText(tr('Une actualisation est en cours. Redémarrez après sa fin ; votre choix reste enregistré.'))
        now = box.addButton(tr('Redémarrer maintenant'), QMessageBox.AcceptRole)
        later = box.addButton(tr('Plus tard'), QMessageBox.RejectRole)
        now.setEnabled(not self._restart_busy())
        box.setDefaultButton(later)
        box.setEscapeButton(later)
        for button in (now, later):
            button.setFixedHeight(CONTROL_HEIGHT)
        box.exec()
        if box.clickedButton() is now and now.isEnabled():
            self._request_language_restart()

    def _request_language_restart(self):
        # Check again: a queued automatic refresh may have started in the dialog.
        if self._restart_busy():
            return
        self._restart_requested = True
        if self.close():  # Existing closeEvent saves the workspace first.
            self.app.exit(RESTART_EXIT_CODE)
        else:
            self._restart_requested = False

    # ── À propos ─────────────────────────────────────────────────────────
    def _open_about(self):
        """Short, exact description (four languages), credits on demand, Desktop links; donation optional."""
        from . import presentation
        dlg = QDialog(self)
        dlg.setWindowTitle(tr('À propos de SpoolScribe'))
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
        ver = QLabel(tr('Version {v0}', v0=core.APP_VERSION))
        ver.setObjectName('aboutVersion')
        ver.setStyleSheet(f"color:{self._tok['muted']};")
        titles.addWidget(ver)
        head.addLayout(titles, 1)
        lay.addLayout(head)

        for text, object_name in ((tr(presentation.ABOUT_SUMMARY, **presentation.format_arguments()), 'aboutSummary'),
                                  (tr(presentation.ABOUT_INDEPENDENCE), 'aboutLicence')):
            label = WrapLabel(text)
            label.setObjectName(object_name)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            lay.addWidget(label)

        credits_toggle = QToolButton()
        credits_toggle.setObjectName('aboutCreditsToggle')
        credits_toggle.setText(tr('Crédits et licences'))
        credits_toggle.setCheckable(True)
        credits_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        credits_toggle.setArrowType(Qt.RightArrow)
        credits = WrapLabel('\n'.join(tr(line) for line in presentation.CREDITS)
                            + '\n' + tr('Détails : NOTICE, docs/DATA_SOURCES.md et docs/TRADEMARKS.md du dépôt.'))
        credits.setObjectName('aboutCredits')
        credits.setTextInteractionFlags(Qt.TextSelectableByMouse)
        credits.hide()

        def toggle_credits(visible):
            credits.setVisible(visible)
            credits_toggle.setArrowType(Qt.DownArrow if visible else Qt.RightArrow)
            fit_dialog(dlg, preferred_width=dlg.width())
        credits_toggle.toggled.connect(toggle_credits)
        lay.addWidget(credits_toggle, 0, Qt.AlignLeft)
        lay.addWidget(credits)

        # Resources and assistance: comparable buttons in one grid that reflows to
        # one column in a narrow window; an odd last button spans the row.
        from .ui_reading import CardGrid
        resources_title = QLabel(tr('Ressources et assistance'))
        resources_title.setObjectName('sectionTitle')
        lay.addWidget(resources_title)
        resource_buttons = []
        for object_name, label, url in presentation.LINKS:
            button = QPushButton(tr(label))
            button.setObjectName(object_name)
            button.setToolTip(url)
            button.clicked.connect(lambda _=False, url=url: QDesktopServices.openUrl(QUrl(url)))
            resource_buttons.append(button)
        # Version-related, so it sits with the version and resources (no network until clicked).
        update = QPushButton(tr('Mise à jour de l’application…'))
        update.setObjectName('checkAppUpdate')
        update.setToolTip(tr('Comparer cette version avec la dernière version publiée sur GitHub'))
        update.clicked.connect(self._check_app_update)
        resource_buttons.append(update)
        for button in resource_buttons:
            button.setFixedHeight(CONTROL_HEIGHT)
            button.setMinimumWidth(0)
            button.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        resources = CardGrid(resource_buttons, 440)
        resources.setObjectName('aboutResources')
        lay.addWidget(resources)

        # Optional support: its own readable block, full width, no obligation.
        donation_name, donation_label, donation_url = presentation.DONATION
        support_box = QFrame()
        support_box.setObjectName('supportCard')
        support_layout = QVBoxLayout(support_box)
        support_layout.setContentsMargins(12, 10, 12, 10)
        support_layout.setSpacing(8)
        support_note = WrapLabel(tr('SpoolScribe est gratuit et le reste. Si l’application vous est utile, vous pouvez soutenir son développement.'))
        support_note.setObjectName('supportNote')
        support_layout.addWidget(support_note)
        support = QPushButton(tr(donation_label))
        support.setObjectName(donation_name)
        support.setFixedHeight(CONTROL_HEIGHT)
        support.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        support.setToolTip(tr('Ouvrir buymeacoffee.com/arn_lab dans votre navigateur'))
        support.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(donation_url)))
        support_layout.addWidget(support)
        lay.addWidget(support_box)

        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.button(QDialogButtonBox.Close).setText(tr('Fermer'))
        bb.button(QDialogButtonBox.Close).setFixedHeight(CONTROL_HEIGHT)
        bb.rejected.connect(dlg.reject)
        bb.accepted.connect(dlg.accept)
        bb.button(QDialogButtonBox.Close).clicked.connect(dlg.accept)
        lay.addWidget(bb)
        fit_dialog(dlg, preferred_width=640)
        dlg.exec()


def run_application(app, window, instance_lock):
    """Restart only after the event loop stops and its data-folder lock is freed."""
    from . import diagnostics  # opt-in ; sans session, record() ne fait rien
    try:
        while True:
            code = app.exec()
            if code != RESTART_EXIT_CODE or not window._restart_requested:
                return code
            instance_lock.unlock()
            diagnostics.record('restart_requested')
            try:
                launch_replacement(__file__)
            except OSError as exc:
                diagnostics.record('restart_spawn', ok=False, error=type(exc).__name__)
                # Failure to spawn must not strand the user with a closed app.
                if not instance_lock.tryLock(200):
                    QMessageBox.critical(None, tr('Redémarrage impossible'),
                        tr('Une autre instance utilise les données. Votre choix de langue reste enregistré.'))
                    return 1
                window._restart_requested = False
                window.show()
                QMessageBox.warning(window, tr('Redémarrage impossible'),
                    tr('La relance a échoué. Vos réglages sont enregistrés ; vous pouvez fermer puis rouvrir SpoolScribe.\n{v0}', v0=exc))
            else:
                diagnostics.record('restart_spawn', ok=True)
                return 0
    finally:
        instance_lock.unlock()


def main():
    # Mode worker (exécutable gelé relançant un scraper) : agir puis sortir.
    if core.maybe_run_as_script_worker(sys.argv):
        return
    from . import diagnostics
    # Opt-in --diagnostics : faulthandler ouvert avant QApplication, drapeau retiré d'argv.
    app, _ = diagnostics.create_application(sys.argv, QApplication, core.DATA_HOME)
    configure_application(app)
    configure_language(app, core.load_config().get("language", "auto"))
    # Une seule instance par dossier de données : deux synchronisations
    # simultanées se disputeraient la base et ses sauvegardes.
    os.makedirs(core.DATA_HOME, exist_ok=True)
    instance_lock = QLockFile(os.path.join(core.DATA_HOME, "spoolscribe.instance.lock"))
    instance_lock.setStaleLockTime(0)
    if not instance_lock.tryLock(200):
        QMessageBox.information(None, "SpoolScribe", tr('SpoolScribe est déjà ouvert pour ce dossier de données.\nUtilisez la fenêtre existante.'))
        return 0
    try:
        win = MainWindow()
    except (core.DatabaseError, OSError) as exc:
        backup = core.DB_PATH + ".bak"
        if not os.path.isfile(backup) or QMessageBox.question(
            None, tr('Base illisible'), tr('{v0}\n\nRestaurer {v1} ?\nLe fichier actuel sera conservé séparément.', v0=exc, v1=backup), QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            QMessageBox.critical(None, tr('Base illisible'), str(exc))
            return 1
        try:
            core.restore_db()
            win = MainWindow()
        except (core.DatabaseError, OSError) as recovery_error:
            QMessageBox.critical(None, tr('Restauration impossible'), str(recovery_error))
            return 1
    win.show()
    from . import ui_backup
    ui_backup.show_startup_recovery(win)  # what recovery.bootstrap() resolved before the model was loaded
    code = run_application(app, win, instance_lock)
    diagnostics.shutdown()  # sans session : aucun effet
    return code



if __name__ == "__main__":
    sys.exit(main())

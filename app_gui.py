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

from PySide6.QtCore import Qt, QThread, Signal, QSize, QTimer, QRectF
from PySide6.QtGui import (
    QColor, QFont, QPixmap, QPainter, QIcon, QPalette, QPainterPath,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLineEdit, QTableWidget, QTableWidgetItem, QLabel, QPushButton, QPlainTextEdit,
    QHeaderView, QAbstractItemView, QFrame, QMessageBox, QProgressBar, QGridLayout,
    QSizePolicy, QStackedWidget,
)

try:
    from PySide6.QtSvgWidgets import QSvgWidget  # noqa: F401  (capability probe)
    from PySide6.QtSvg import QSvgRenderer
    HAS_SVG = True
except Exception:
    HAS_SVG = False

import core


# ─── Logo animé : la bobine tourne, le fil reste posé ─────────────────────
class SpinningLogo(QWidget):
    """Affiche le logo SVG et fait tourner la seule face de bobine (#disc).

    Le fil (#strand) et l'ombre portée restent immobiles : la bobine semble
    *dévider* le trait qu'elle écrit. Rotation lente et continue au repos,
    accélération nette et assumée au survol, retour en douceur — une logique
    affirmée mais sans esbroufe.
    """

    _VIEWBOX = 512.0          # le SVG est carré 512×512
    _DISC_CENTER = (216.0, 252.0)
    _DISC_RADIUS = 150.0
    _IDLE_SPEED = 22.0        # deg/s au repos (un tour ≈ 16 s)
    _HOVER_SPEED = 165.0      # deg/s au survol — franc, assumé
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
def make_swatch_pixmap(hex_code: str | None, size: int = 18) -> QPixmap:
    pm = QPixmap(size, size)
    h = (hex_code or "").strip().lstrip("#")
    if len(h) == 6:
        color = QColor(f"#{h}")
    else:
        color = QColor("#dddddd")
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(color)
    p.setPen(QColor("#888888"))
    p.drawRoundedRect(0, 0, size - 1, size - 1, 4, 4)
    p.end()
    return pm


# ─── Thème clair / sombre ─────────────────────────────────────────────────
def is_dark_theme(app: QApplication) -> bool:
    """Vrai si l'OS/Qt utilise un thème sombre."""
    try:
        scheme = app.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    except Exception:
        pass
    return app.palette().color(QPalette.Window).lightness() < 128


def theme_tokens(app: QApplication) -> dict:
    """Jeu de couleurs adapté au thème courant."""
    if is_dark_theme(app):
        return {
            "dark": True,
            "muted": "#9aa3ad", "faint": "#6c737c",
            "accent": "#27c4d8", "accent_hover": "#34d3e6", "accent_text": "#04282d",
            "card": "rgba(255,255,255,0.05)", "border": "rgba(255,255,255,0.13)",
            "field_bg": "rgba(255,255,255,0.04)", "danger": "#ff7676",
            "sec_bg": "rgba(255,255,255,0.06)", "sec_hover": "rgba(255,255,255,0.12)",
        }
    return {
        "dark": False,
        "muted": "#5f6368", "faint": "#80868b",
        "accent": "#1499ab", "accent_hover": "#127f8e", "accent_text": "#ffffff",
        "card": "rgba(0,0,0,0.025)", "border": "rgba(0,0,0,0.12)",
        "field_bg": "rgba(0,0,0,0.02)", "danger": "#c5221f",
        "sec_bg": "rgba(0,0,0,0.04)", "sec_hover": "rgba(0,0,0,0.08)",
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

        self._build_ui()
        self._apply_theme()
        self._reload_table()
        self._refresh_logo()
        self._update_stats()
        self._show_empty()

        # Réagit aux changements de thème de l'OS à chaud (Qt 6.5+).
        try:
            self.app.styleHints().colorSchemeChanged.connect(lambda *_: self._apply_theme())
        except Exception:
            pass

    # ── Construction UI ──────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 12, 14, 10)
        root.setSpacing(10)

        # ── Barre du haut : logo + nom · recherche · bouton update ──────
        top = QHBoxLayout()
        top.setSpacing(10)

        brand = QHBoxLayout()
        brand.setSpacing(9)
        app_logo_path = core.app_logo_abs_path()
        if HAS_SVG and app_logo_path:
            self.app_logo = SpinningLogo(app_logo_path, size=30)
        else:
            self.app_logo = QLabel()
            ic = core.app_icon_abs_path()
            if ic:
                self.app_logo.setPixmap(QPixmap(ic).scaled(
                    30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.app_logo.setFixedSize(30, 30)
        brand.addWidget(self.app_logo)
        self.wordmark = QLabel("SpoolScribe")
        wf = QFont()
        wf.setPointSize(13)
        wf.setBold(True)
        self.wordmark.setFont(wf)
        brand.addWidget(self.wordmark)
        top.addLayout(brand)

        top.addSpacing(8)

        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Rechercher : SKU, produit, couleur…")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(240)
        self.search.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.search.textChanged.connect(self._apply_filter)
        top.addWidget(self.search, 1)

        self.update_btn = QPushButton("Mettre à jour la DB")
        self.update_btn.setObjectName("primary")
        self.update_btn.setCursor(Qt.PointingHandCursor)
        self.update_btn.clicked.connect(self._start_update)
        top.addWidget(self.update_btn)
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

        # ── Splitter : table à gauche, panneau à droite ─────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)

        # Table SKU
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
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 30)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._on_select)
        splitter.addWidget(self.table)

        # ── Panneau droit : pile (état vide / fiche) ────────────────────
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_empty_page())
        self.stack.addWidget(self._build_detail_page())
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
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(14)

        app_logo_path = core.app_logo_abs_path()
        if HAS_SVG and app_logo_path:
            big = SpinningLogo(app_logo_path, size=104)
        else:
            big = QLabel()
            ic = core.app_icon_abs_path()
            if ic:
                big.setPixmap(QPixmap(ic).scaled(
                    104, 104, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            big.setFixedSize(104, 104)
        wrap = QHBoxLayout()
        wrap.addStretch(1)
        wrap.addWidget(big)
        wrap.addStretch(1)
        lay.addLayout(wrap)

        title = QLabel("Aucun filament sélectionné")
        tf = QFont()
        tf.setPointSize(14)
        tf.setBold(True)
        title.setFont(tf)
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        hint = QLabel(
            "Choisissez une référence dans la liste à gauche — ou utilisez la "
            "recherche — pour voir ses caractéristiques et générer son tag "
            "NFC OpenSpool."
        )
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignCenter)
        hint.setMaximumWidth(360)
        self._muted_labels.append(hint)
        wrap2 = QHBoxLayout()
        wrap2.addStretch(1)
        wrap2.addWidget(hint)
        wrap2.addStretch(1)
        lay.addLayout(wrap2)
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
        if HAS_SVG:
            self.logo = QSvgWidget()
        else:
            self.logo = QLabel("")
        self.logo.setFixedSize(64, 64)
        head.addWidget(self.logo, 0, Qt.AlignTop)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.title = QLabel("—")
        f = QFont()
        f.setPointSize(15)
        f.setBold(True)
        self.title.setFont(f)
        self.title.setWordWrap(True)
        titles.addWidget(self.title)
        self.subtitle = QLabel("")
        self._muted_labels.append(self.subtitle)
        titles.addWidget(self.subtitle)
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
        sf = QFont()
        sf.setBold(True)
        self.swatch.setFont(sf)
        dl.addWidget(self.swatch)

        # Carte des caractéristiques
        self.card = QFrame()
        self.card.setObjectName("card")
        self.fields = QGridLayout(self.card)
        self.fields.setContentsMargins(14, 12, 14, 12)
        self.fields.setVerticalSpacing(7)
        self.fields.setHorizontalSpacing(14)
        self.fields.setColumnStretch(1, 1)

        self._field_widgets: dict[str, QLabel] = {}
        labels = ["Produit", "Type", "Nozzle", "Bed", "Densité", "Marque"]
        for i, name in enumerate(labels):
            lab = QLabel(name)
            lab.setObjectName("fieldname")
            self._muted_labels.append(lab)
            val = QLabel("—")
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.fields.addWidget(lab, i, 0, Qt.AlignTop)
            self.fields.addWidget(val, i, 1)
            self._field_widgets[name] = val
        dl.addWidget(self.card)

        # Action principale + actions secondaires
        self.btn_generate = QPushButton("Générer le tag NFC")
        self.btn_generate.setObjectName("primary")
        self.btn_generate.setCursor(Qt.PointingHandCursor)
        self.btn_generate.setMinimumHeight(36)
        self.btn_generate.clicked.connect(self._generate)
        dl.addWidget(self.btn_generate)

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

        # Zone d'inspection JSON
        self.inspector = QPlainTextEdit()
        self.inspector.setReadOnly(True)
        self.inspector.setVisible(False)
        self.inspector.setFont(QFont("Consolas" if os.name == "nt" else "monospace", 9))
        dl.addWidget(self.inspector, 1)
        dl.addStretch(0)
        return page

    # ── Application du thème (clair / sombre) ────────────────────────────
    def _apply_theme(self):
        t = theme_tokens(self.app)
        self._tok = t
        muted, faint, accent = t["muted"], t["faint"], t["accent"]

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
        self.setStyleSheet(primary_qss + secondary_qss + search_qss + card_qss)

        # Rafraîchit la bande couleur si une fiche est affichée.
        if self.current_sku:
            self._paint_swatch()
        else:
            self.swatch.setStyleSheet(
                f"#swatch {{ background:{t['field_bg']}; color:{faint};"
                f" border:1px dashed {t['border']}; border-radius:8px; }}")

    def _show_empty(self):
        self.stack.setCurrentIndex(0)

    def _show_card(self):
        self.stack.setCurrentIndex(1)


    # ── Données / table ──────────────────────────────────────────────────
    def _reload_table(self):
        self._all_rows = core.list_skus(self.db)
        self._populate(self._all_rows)

    def _populate(self, rows):
        self.table.setRowCount(0)
        self.table.setRowCount(len(rows))
        for r, e in enumerate(rows):
            sw = QTableWidgetItem()
            sw.setIcon(QIcon(make_swatch_pixmap(e.get("hex"))))
            self.table.setItem(r, 0, sw)
            self.table.setItem(r, 1, QTableWidgetItem(e["sku"]))
            self.table.setItem(r, 2, QTableWidgetItem(e["product"]))
            color_item = QTableWidgetItem(e["color_name"])
            if not e.get("hex"):
                color_item.setForeground(QColor("#b00"))
            self.table.setItem(r, 3, color_item)
        # Plus de sélection valide → revenir à l'état vide.
        if hasattr(self, "stack") and not self.table.selectedItems():
            self.current_sku = None
            self._show_empty()

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

    def _refresh_logo(self):
        abs_path = core.logo_abs_path(self.db)
        if HAS_SVG and abs_path and os.path.exists(abs_path):
            try:
                self.logo.load(abs_path)
                return
            except Exception:
                pass
        if not HAS_SVG:
            self.logo.setText("(SVG non dispo)")

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
            self.swatch.setText("HEX inconnu → #000000")
            self.swatch.setStyleSheet(
                f"#swatch {{ background:#000000; color:#ffffff;"
                f" border:1px solid {t['border']}; border-radius:8px; }}")

    def _show_detail(self, sku):
        view = core.get_sku_view(self.db, sku)
        self._show_card()
        if view is None:
            self.title.setText(f"{sku} — produit introuvable")
            self.subtitle.setText("")
            for v in self._field_widgets.values():
                v.setText("—")
            self._cur_hex = None
            self._paint_swatch()
            self.btn_generate.setEnabled(False)
            self.btn_inspect.setEnabled(False)
            return

        self.title.setText(view.product)
        self.subtitle.setText(f"{view.sku}  ·  {view.color_name}")
        self._field_widgets["Produit"].setText(view.product)
        self._field_widgets["Type"].setText(view.type_str)
        self._field_widgets["Nozzle"].setText(view.nozzle_str)
        self._field_widgets["Bed"].setText(view.bed_str)
        self._field_widgets["Densité"].setText(view.density_str)
        self._field_widgets["Marque"].setText(view.product_data.get("brand", "Polymaker"))

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
        else:
            self._refresh_inspector()
            self.inspector.setVisible(True)
            self.btn_inspect.setText("Masquer le JSON")

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
            detail = "\n".join(f"• {r.label} (code {r.code})" for r in n_ko)
            QMessageBox.warning(self, "Mise à jour partielle",
                                f"{msg}\n\nÉtapes en échec :\n{detail}")

    def _on_update_failed(self, tb):
        self.progress.setVisible(False)
        self.update_btn.setEnabled(True)
        QMessageBox.critical(self, "Erreur de mise à jour", tb)


def main():
    # Mode worker (exécutable gelé relançant un scraper) : agir puis sortir.
    if core.maybe_run_as_script_worker(sys.argv):
        return
    app = QApplication(sys.argv)
    app.setApplicationName("SpoolScribe")
    icon_path = core.app_icon_abs_path()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

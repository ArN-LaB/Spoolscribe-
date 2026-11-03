"""QR Code window: a frozen copy of the current NFC message, shown, saved or printed.

The message is built by the same calls as the NFC export; this window adds no
catalogue rule. It never writes a tag and never claims a label was printed.
"""
from dataclasses import dataclass
import hashlib
import os
import time

from PySide6.QtCore import QMarginsF, QRect, QSize, QSizeF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QPageLayout, QPageSize, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QSlider, QSpinBox, QStackedWidget, QToolButton,
    QVBoxLayout, QWidget)

from . import core, opentag3d, qr_layout, qr_transfer
from .i18n import tr
from .ui_guidance import FlowLabel
from .ui_widgets import CONTROL_HEIGHT, ChoiceButtons


@dataclass(frozen=True)
class QrSnapshot:
    """Everything shown, saved or printed by one window, frozen at opening."""
    sku: str
    source_sku: str            # Reference the personal copy was made from; the SKU itself otherwise.
    personal: bool
    product: str
    colour: str
    brand: str
    protocol: int
    format_label: str
    tag_type: str
    reserved_bytes: int
    nfc_profile: str           # "essential"/"full" for OpenSpool, "" for OpenTag3D
    settings: tuple            # OpenTag3D label values used (sorted pairs), () for OpenSpool
    ndef: bytes
    opened_at: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.ndef).hexdigest()

    @property
    def file_stem(self) -> str:
        stem = core.openspool_filename(self.sku, self.product, self.colour).removesuffix("_openspool.json")
        return f"{stem}_{'opentag3d' if self.protocol == qr_transfer.OPENTAG3D else 'openspool'}_qr"


def snapshot(window) -> QrSnapshot:
    """Same state and calls as « Exporter pour NFC »; raises ValueError when export is not possible."""
    sku = window.current_sku
    if not sku or getattr(window, "_primary_kind", "export") != "export" or not window.btn_generate.isEnabled():
        raise core.ExportValidationError(tr("Le QR Code est disponible lorsque l’export NFC est possible."))
    if window._draft_dirty() or (window.worker and window.worker.isRunning()) or not window._can_export_for_printer():
        raise core.ExportValidationError(tr("Le QR Code est disponible lorsque l’export NFC est possible."))
    view = core.get_sku_view(window.db, sku)
    if view is None:
        raise core.ExportValidationError(tr("Produit introuvable pour cette référence."))
    entry = window.db["_skus"][sku]
    tag, reserve = window.tag_type.currentData(), window.nfc_reserve.value()
    if window._opentag_selected():
        prepared = window._prepare_opentag()
        message, protocol = opentag3d.ndef(prepared.payload), qr_transfer.OPENTAG3D
        if len(message) != prepared.size["ndef"]:
            raise core.ExportValidationError(tr("Contrôle de taille NDEF en échec."))
        settings, profile = tuple(sorted(core.opentag_settings(sku).items())), ""
        label = f"OpenTag3D {opentag3d.VERSION} · {tag}"
    else:
        payload = window._build_payload()
        if payload is None:
            raise core.ExportValidationError(tr("Produit introuvable pour cette référence."))
        options = window._nfc_options()
        text = core.serialize_openspool(payload, mode="nfc", **options)
        message, protocol = qr_transfer.openspool_ndef(text.encode("utf-8")), qr_transfer.OPENSPOOL
        if len(message) != core.nfc_size(text, tag_type=options["tag_type"], reserved_bytes=options["reserved_bytes"]).ndef_bytes:
            raise core.ExportValidationError(tr("Contrôle de taille NDEF en échec."))
        settings, profile = (), options["profile"]
        label = f"OpenSpool 1.0 · {tr('profil essentiel') if profile == 'essential' else tr('profil complet')} · {tag}"
    personal = bool(entry.get("_personal"))
    product = (view.product_data.get("display_name") if personal else entry.get("product")) or entry.get("product") or ""
    return QrSnapshot(sku, entry.get("_personal_origin") or sku, personal, product, entry.get("color_name") or "",
                      view.product_data.get("brand") or "", protocol, label, tag, reserve, profile, settings,
                      message, time.strftime("%H:%M"))


class QrCanvas(QWidget):
    """White surface; whole screen pixels per module, never smoothed."""
    def __init__(self, symbol, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self.setMinimumSize(240, 240)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(tr("QR Code de transfert"))

    def scale(self):
        return min(self.width(), self.height()) // self.symbol.total_modules

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.white)
        scale = self.scale()
        if scale < 1:
            painter.setPen(Qt.black); painter.drawText(self.rect(), Qt.AlignCenter | Qt.TextWordWrap, tr("Agrandissez la fenêtre pour afficher le QR Code."))
            return
        side = self.symbol.total_modules * scale
        origin = ((self.width() - side) // 2, (self.height() - side) // 2)
        for x, y, w, h in qr_layout.module_rects(self.symbol, origin, scale):
            painter.fillRect(x, y, w, h, Qt.black)
        if self.hasFocus():
            painter.setPen(QPen(QColor("#2563eb"), 2)); painter.drawRect(self.rect().adjusted(1, 1, -2, -2))


class LabelPreview(QWidget):
    """Template drawn from the plan, at a zoom of its own; not a calibrated ruler."""
    def __init__(self, symbol, parent=None):
        super().__init__(parent)
        self.symbol, self.plan, self.lines, self.zoom = symbol, None, [], 100
        self.setMinimumSize(240, 240)
        self.setAccessibleName(tr("Aperçu de l’étiquette"))

    def set_plan(self, plan, lines):
        self.plan, self.lines = plan, lines
        self.set_zoom(self.zoom)

    def paper_pixels(self):
        pixels_per_dot = self.logicalDpiX() / self.plan.dpi * self.zoom / 100
        return pixels_per_dot, [round(v * self.plan.dpi / 25.4 * pixels_per_dot) for v in self.plan.paper_mm]

    def set_zoom(self, zoom):
        """Grows with the zoom inside its scroll area, so the whole label stays reachable."""
        self.zoom = zoom
        if self.plan is not None:
            _, (width, height) = self.paper_pixels()
            self.setMinimumSize(max(240, width + 16), max(240, height + 16))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())
        plan = self.plan
        if plan is None:
            return
        pixels_per_dot, (paper_w, paper_h) = self.paper_pixels()
        left, top = max(8, (self.width() - paper_w) // 2), max(8, (self.height() - paper_h) // 2)
        painter.fillRect(left, top, paper_w, paper_h, Qt.white)
        painter.setPen(QPen(QColor("#6b7280"), 1)); painter.drawRect(left, top, paper_w, paper_h)
        x, y, w, h = (round(v * pixels_per_dot) for v in plan.area)
        painter.setPen(QPen(QColor("#9ca3af"), 1, Qt.DashLine)); painter.drawRect(left + x, top + y, w, h)
        if plan.dots_per_module:
            qx, qy, side, _ = plan.qr_rect
            image = QImage(self.symbol.total_modules, self.symbol.total_modules, QImage.Format_RGB32)
            image.fill(Qt.white)
            for mx, my, n in qr_layout.dark_runs(self.symbol):
                for i in range(n):
                    image.setPixelColor(qr_layout.QUIET_ZONE + mx + i, qr_layout.QUIET_ZONE + my, QColor(Qt.black))
            size = max(1, round(side * pixels_per_dot))
            painter.drawImage(QRect(left + round(qx * pixels_per_dot), top + round(qy * pixels_per_dot), size, size),
                              image.scaled(size, size, Qt.IgnoreAspectRatio, Qt.FastTransformation))
            tx, ty, tw, th = (round(v * pixels_per_dot) for v in plan.text_rect)
            if plan.text_lines:
                font = painter.font(); font.setPixelSize(max(6, th // plan.text_lines - 2)); painter.setFont(font)
                painter.setPen(Qt.black)
                for i, line in enumerate(self.lines[:plan.text_lines]):
                    painter.drawText(QRect(left + tx, top + ty + i * th // plan.text_lines, tw, th // plan.text_lines),
                                     Qt.AlignCenter, painter.fontMetrics().elidedText(line, Qt.ElideRight, tw))


MIN_WIDTH = 420


class LowerArea(QScrollArea):
    """Vertical scrolling band whose preferred height ignores the folded details."""
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True); self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setMinimumHeight(CONTROL_HEIGHT * 2 + 10)

    def sizeHint(self):
        return QSize(super().sizeHint().width(), 8 * CONTROL_HEIGHT)


class QrWindow(QDialog):
    def __init__(self, snap: QrSnapshot, parent=None, *, printer_factory=None, print_dialog=None, printer_names=None):
        super().__init__(parent)
        self.snap = snap
        self._printer_factory = printer_factory
        self._print_dialog = print_dialog
        self._printer_names = printer_names
        cfg = core.load_config().get("qr_label", {})
        try:
            self.settings = dict(qr_layout.validate_settings(cfg))
        except ValueError:
            self.settings = {}
        self.setWindowTitle(tr("QR Code — {v0}", v0=self._identity()))
        self.setWindowModality(Qt.NonModal)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        layout = QVBoxLayout(self); layout.setContentsMargins(16, 16, 16, 16); layout.setSpacing(10)
        self.heading = FlowLabel(self._identity()); self.heading.setObjectName("guidanceHeading"); layout.addWidget(self.heading)
        self.subtitle = FlowLabel(); self.subtitle.setObjectName("guidanceNote"); layout.addWidget(self.subtitle)
        self.view_choice = ChoiceButtons()
        self.view_choice.setChoices([(tr("QR Code"), "qr"), (tr("Aperçu de l’étiquette"), "label")])
        self.view_choice.setChoice("qr"); self.view_choice.choiceChanged.connect(self._show_view)
        layout.addWidget(self.view_choice)
        self.stack = QStackedWidget(); layout.addWidget(self.stack, 1)
        self.symbol = None
        self._build_symbol()
        self.canvas = QrCanvas(self.symbol); self.stack.addWidget(self.canvas)
        self.stack.setMinimumWidth(MIN_WIDTH - 32)
        preview_page = QWidget(); preview = QVBoxLayout(preview_page); preview.setContentsMargins(0, 0, 0, 0); preview.setSpacing(6)
        self.preview = LabelPreview(self.symbol)
        preview_scroll = QScrollArea(); preview_scroll.setWidgetResizable(True); preview_scroll.setFrameShape(QFrame.NoFrame)
        preview_scroll.setWidget(self.preview); preview.addWidget(preview_scroll, 1)
        zoom_row = QHBoxLayout(); zoom_row.addWidget(QLabel(tr("Zoom")))
        self.zoom = QSlider(Qt.Horizontal); self.zoom.setRange(50, 800); self.zoom.setValue(100)
        self.zoom.setAccessibleName(tr("Zoom de l’aperçu")); self.zoom.valueChanged.connect(self._zoom_changed)
        zoom_row.addWidget(self.zoom, 1); preview.addLayout(zoom_row)
        self.preview_note = FlowLabel(); self.preview_note.setObjectName("guidanceNote"); preview.addWidget(self.preview_note)
        self.stack.addWidget(preview_page)
        self.summary = FlowLabel(); self.summary.setObjectName("guidanceTitle"); layout.addWidget(self.summary)
        actions = QHBoxLayout(); actions.setSpacing(8)
        self.btn_png = QPushButton(tr("Enregistrer en PNG…")); self.btn_svg = QPushButton(tr("Enregistrer en SVG…"))
        for button in (self.btn_png, self.btn_svg):
            button.setObjectName("secondary"); button.setFixedHeight(CONTROL_HEIGHT); actions.addWidget(button, 1)
        self.btn_png.clicked.connect(lambda: self._save("png")); self.btn_svg.clicked.connect(lambda: self._save("svg"))
        layout.addLayout(actions)
        self.status = FlowLabel(); self.status.setObjectName("exportState"); self.status.hide(); layout.addWidget(self.status)
        # Secondary: paper, printing and technical details scroll inside a band of stable height,
        # so opening them never takes room from the code.
        self.lower = LowerArea(); layout.addWidget(self.lower)
        lower_page = QWidget(); lower = QVBoxLayout(lower_page); lower.setContentsMargins(0, 0, 4, 0); lower.setSpacing(10)
        self.lower.setWidget(lower_page)
        support = QHBoxLayout(); support.setSpacing(8)
        support_label = QLabel(tr("Support")); support.addWidget(support_label)
        self.support = QComboBox(); self.support.setFixedHeight(CONTROL_HEIGHT)
        for key, (name, _) in qr_layout.PRESETS.items():
            self.support.addItem(tr(name), key)
        self.support.addItem(tr("Support personnalisé"), "custom")
        self.support.setAccessibleName(tr("Support d’impression"))
        support_label.setBuddy(self.support)
        self.companion = FlowLabel(tr("Ce QR Code contient tout le message de l’étiquette NFC. La programmation d’une puce demandera la future application SpoolScribe Companion ; un lecteur QR ordinaire affiche seulement un texte de transfert."))
        self.companion.setObjectName("guidanceNote"); lower.addWidget(self.companion)
        support.addWidget(self.support, 1); lower.addLayout(support)
        self.result_tile = QFrame(); self.result_tile.setObjectName("guidanceTile")  # Existing toned style.
        tile = QVBoxLayout(self.result_tile); tile.setContentsMargins(12, 8, 12, 8)
        self.result = FlowLabel(); tile.addWidget(self.result); lower.addWidget(self.result_tile)
        self.btn_print = QPushButton(tr("Imprimer…")); self.btn_print.setObjectName("secondary"); self.btn_print.setFixedHeight(CONTROL_HEIGHT)
        self.btn_print.clicked.connect(self._print); lower.addWidget(self.btn_print)
        self.details_toggle = QToolButton(); self.details_toggle.setText(tr("Détails techniques"))
        self.details_toggle.setCheckable(True); self.details_toggle.setArrowType(Qt.RightArrow)
        self.details_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); self.details_toggle.setFixedHeight(CONTROL_HEIGHT)
        self.details_toggle.toggled.connect(self._toggle_details); lower.addWidget(self.details_toggle)
        self.details = QWidget(); details = QVBoxLayout(self.details); details.setContentsMargins(0, 0, 0, 0); details.setSpacing(8)
        options = QHBoxLayout(); options.setSpacing(8)
        options.addWidget(QLabel(tr("Correction d’erreur")))
        self.error = QComboBox(); self.error.setFixedHeight(CONTROL_HEIGHT)
        self.error.addItem(tr("M — standard"), "M"); self.error.addItem(tr("Q — renforcée, QR plus grand"), "Q")
        self.error.setAccessibleName(tr("Correction d’erreur")); options.addWidget(self.error, 1); details.addLayout(options)
        self.small = QCheckBox(tr("Petit format — essai de lecture requis"))
        self.small.setToolTip(tr("Autorise 3 points d’imprimante par module au lieu de 4. Vérifiez la lecture de l’étiquette imprimée."))
        details.addWidget(self.small)
        self.custom = QWidget(); grid = QGridLayout(self.custom); grid.setContentsMargins(0, 0, 0, 0); grid.setSpacing(6)
        self.custom_fields = {}
        for row, (key, label, low, high) in enumerate((("width_mm", tr("Largeur (mm)"), 5, 1000), ("height_mm", tr("Hauteur (mm)"), 5, 1000),
                                                       ("margin", tr("Marges (mm)"), 0, 100))):
            spin = QDoubleSpinBox(); spin.setRange(low, high); spin.setDecimals(1); spin.setSingleStep(0.5); spin.setFixedHeight(CONTROL_HEIGHT)
            grid.addWidget(QLabel(label), row, 0); grid.addWidget(spin, row, 1); self.custom_fields[key] = spin
        self.custom_dpi = QSpinBox(); self.custom_dpi.setRange(*qr_layout.DPI_RANGE); self.custom_dpi.setFixedHeight(CONTROL_HEIGHT)
        grid.addWidget(QLabel(tr("Résolution (ppp)")), 3, 0); grid.addWidget(self.custom_dpi, 3, 1)
        self.custom_orientation = QComboBox(); self.custom_orientation.setFixedHeight(CONTROL_HEIGHT)
        self.custom_orientation.addItem(tr("Portrait"), "portrait"); self.custom_orientation.addItem(tr("Paysage"), "landscape")
        grid.addWidget(QLabel(tr("Orientation")), 4, 0); grid.addWidget(self.custom_orientation, 4, 1)
        details.addWidget(self.custom)
        self.technical = FlowLabel(); self.technical.setTextInteractionFlags(Qt.TextSelectableByMouse); details.addWidget(self.technical)
        self.details.hide(); lower.addWidget(self.details); lower.addStretch(1)
        self._load_settings()
        for widget in (self.support, self.error, self.custom_orientation):
            widget.currentIndexChanged.connect(self._settings_changed)
        self.small.toggled.connect(self._settings_changed)
        for spin in (*self.custom_fields.values(), self.custom_dpi):
            spin.valueChanged.connect(self._settings_changed)
        self._refresh()
        self._fit_code()
        available = (self.screen() or QApplication.primaryScreen()).availableGeometry().height()
        self.resize(560, max(self.minimumHeight(), min(800, available - 80)))

    def _fit_code(self):
        """Smallest code kept on screen: 3 pixels per module, 2 if the screen is too short."""
        available = (self.screen() or QApplication.primaryScreen()).availableGeometry().height()
        for pixels in (3, 2):
            side = self.symbol.total_modules * pixels
            self.canvas.setMinimumSize(side, side)
            if self.needed_height(MIN_WIDTH) <= available:
                break
        self._update_minimum()

    def needed_height(self, width):
        """Minimum height at this width, wrapped texts measured at their real width."""
        layout = self.layout(); margins = layout.contentsMargins()
        inner = width - margins.left() - margins.right()
        total, count = margins.top() + margins.bottom(), 0
        for i in range(layout.count()):
            item = layout.itemAt(i); widget = item.widget()
            if widget is not None and widget.isHidden():
                continue
            if isinstance(widget, QLabel) and widget.wordWrap():
                height = widget.heightForWidth(inner) if widget.text() else item.minimumSize().height()
            elif widget is self.stack:
                height = max(self.stack.minimumSizeHint().height(), self.canvas.minimumHeight())
            else:
                height = item.minimumSize().height()
            total += height; count += 1
        return total + layout.spacing() * max(0, count - 1)

    def _update_minimum(self):
        self.setMinimumSize(MIN_WIDTH, self.needed_height(max(MIN_WIDTH, self.width())))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if event.oldSize().width() != event.size().width():
            self._update_minimum()

    def _set_status(self, text):
        self.status.setText(text); self.status.setVisible(bool(text))  # No empty line taken from the code
        self._update_minimum()

    # ── State ──────────────────────────────────────────────────────────
    def _identity(self):
        parts = [p for p in (self.snap.product, self.snap.colour) if p]
        return " · ".join(parts) or self.snap.sku

    def _label_lines(self):
        return [line for line in (self.snap.product, self.snap.colour, self.snap.sku if not self.snap.personal else
                                  tr("Copie personnelle de {v0}", v0=self.snap.source_sku)) if line]

    def _build_symbol(self):
        self.symbol = qr_layout.make_symbol(self.snap.protocol, self.snap.ndef, self.settings.get("error", "M"))

    def _load_settings(self):
        widgets = (self.support, self.error, self.small, self.custom_orientation, *self.custom_fields.values(), self.custom_dpi)
        for widget in widgets:
            widget.blockSignals(True)
        self.support.setCurrentIndex(max(0, self.support.findData(self.settings.get("preset", qr_layout.DEFAULT_PRESET))))
        self.error.setCurrentIndex(max(0, self.error.findData(self.settings.get("error", "M"))))
        self.small.setChecked(self.settings.get("small_format", False))
        custom = qr_layout.profile_from_dict(self.settings["custom"]) if "custom" in self.settings else qr_layout.LabelProfile(40, 60)
        self.custom_fields["width_mm"].setValue(custom.width_mm); self.custom_fields["height_mm"].setValue(custom.height_mm)
        self.custom_fields["margin"].setValue(max(custom.margins_mm)); self.custom_dpi.setValue(custom.dpi)
        self.custom_orientation.setCurrentIndex(max(0, self.custom_orientation.findData(custom.orientation)))
        for widget in widgets:
            widget.blockSignals(False)

    def profile(self):
        if self.support.currentData() == "custom":
            margin = self.custom_fields["margin"].value()
            return qr_layout.LabelProfile(self.custom_fields["width_mm"].value(), self.custom_fields["height_mm"].value(),
                                          (margin,) * 4, self.custom_dpi.value(), self.custom_orientation.currentData())
        return qr_layout.PRESETS[self.support.currentData()][1]

    def support_name(self):
        return self.support.currentText()

    def _settings_changed(self, *_):
        error_changed = self.error.currentData() != self.settings.get("error", "M")
        settings = dict(preset=self.support.currentData(), small_format=self.small.isChecked(), error=self.error.currentData())
        if self.support.currentData() == "custom":
            settings["custom"] = qr_layout.profile_to_dict(self.profile())
        elif "custom" in self.settings:
            settings["custom"] = self.settings["custom"]
        try:
            qr_layout.validate_settings(settings)
        except ValueError as exc:
            self._set_status(tr("Réglage refusé : {v0}", v0=tr(str(exc))))
            self._refresh()
            return
        if error_changed:
            try:
                symbol = qr_layout.make_symbol(self.snap.protocol, self.snap.ndef, settings["error"])
            except ValueError as exc:
                self.error.blockSignals(True); self.error.setCurrentIndex(self.error.findData(self.settings.get("error", "M"))); self.error.blockSignals(False)
                self._set_status(tr("Correction non appliquée : {v0}", v0=tr(str(exc))))
                return
            self.symbol = self.canvas.symbol = self.preview.symbol = symbol
            self._fit_code()
        self.settings = settings
        try:
            cfg = core.load_config(); cfg["qr_label"] = settings; core.save_config(cfg)
        except OSError:
            self._set_status(tr("Réglages du support non enregistrés ; ils restent appliqués dans cette fenêtre."))
        self._refresh()

    def plan(self):
        try:
            return qr_layout.plan_label(self.symbol.total_modules, self.profile(), small_format=self.small.isChecked())
        except ValueError:
            return None

    def _refresh(self):
        plan = self.plan()
        self.custom.setVisible(self.support.currentData() == "custom")
        self.subtitle.setText(tr("{v0} · référence {v1} · données figées à l’ouverture ({v2})",
                                 v0=self.snap.format_label, v1=self.snap.sku, v2=self.snap.opened_at)
                              + ("\n" + tr("Copie personnelle de {v0}", v0=self.snap.source_sku) if self.snap.personal else ""))
        self.result_tile.setProperty("tone", "ready" if plan and plan.status == "ready" else "attention")
        self.result_tile.style().unpolish(self.result_tile); self.result_tile.style().polish(self.result_tile)
        self.result.setText(self._result_text(plan))
        self.btn_print.setEnabled(bool(plan and plan.printable))
        self.btn_print.setToolTip("" if plan and plan.printable else tr("Impression refusée pour ce support ; l’affichage et l’enregistrement restent disponibles."))
        self.preview.set_plan(plan, self._label_lines())
        self.preview_note.setText(self._preview_text(plan))
        self.technical.setText(self._technical_text(plan))
        self.summary.setText(tr("Transfert numérique : message NFC complet ({v0} octets), QR version {v1}-{v2}, sans serveur.",
                                v0=self.symbol.ndef_bytes, v1=self.symbol.version, v2=self.symbol.error))
        self.canvas.setAccessibleDescription(tr("Version {v0}, correction {v1}, {v2} modules", v0=self.symbol.version, v1=self.symbol.error, v2=self.symbol.size))
        self.canvas.update()
        self._update_minimum()

    def _result_text(self, plan):
        name = self.support_name()
        if plan is None:
            return tr("Support invalide : vérifiez ses dimensions et ses marges.")
        if plan.status == "ready":
            return tr("Prêt pour un essai d’impression sur {v0} : QR de {v1} mm, {v2} points par module. Vérifiez la lecture de l’étiquette imprimée.",
                      v0=name, v1=_mm(plan.qr_mm), v2=plan.dots_per_module)
        if plan.status == "small":
            return tr("Petit format sur {v0} : QR de {v1} mm, 3 points par module. Essai de lecture requis avant usage.", v0=name, v1=_mm(plan.qr_mm))
        prudent = qr_layout.minimum_width_mm(plan.total_modules, plan.dpi, qr_layout.PRUDENT_DOTS)
        small = qr_layout.minimum_width_mm(plan.total_modules, plan.dpi, qr_layout.SMALL_DOTS)
        if plan.reason == "needs_small":
            text = tr("Trop dense pour l’impression prudente sur {v0}. Le petit format (3 points par module, essai requis) est possible dans les détails techniques ; sinon choisissez un support plus large.", v0=name)
        else:
            text = tr("QR trop dense pour {v0} : il faut au moins {v1} mm de largeur imprimable ({v2} mm en petit format, essai requis). Choisissez un support plus large ; l’affichage et l’enregistrement restent disponibles.",
                      v0=name, v1=_mm(prudent), v2=_mm(small))
        if self.snap.protocol == qr_transfer.OPENSPOOL and self.snap.nfc_profile == "full":
            text += " " + tr("Le profil NFC essentiel, s’il convient à votre lecteur, donne un QR plus petit : choisissez-le dans la fenêtre principale puis rouvrez le QR.")
        return text

    def _preview_text(self, plan):
        if plan is None:
            return ""
        width, height = plan.paper_mm
        text = tr("Étiquette {v0} × {v1} mm ; zone imprimable {v2} × {v3} mm.", v0=_mm(width), v1=_mm(height),
                  v2=_mm(plan.printable_mm[0]), v3=_mm(plan.printable_mm[1]))
        if plan.dots_per_module:
            text += " " + tr("QR de {v0} mm, zone blanche comprise.", v0=_mm(plan.qr_mm))
        return text + " " + tr("Échelle à l’écran indicative : l’écran n’est pas calibré.")

    def _technical_text(self, plan):
        s = self.symbol
        lines = [tr("Texte de transfert : {v0} caractères (SSQR1, Base45, {v1}).", v0=len(s.text), v1="zlib" if s.codec == qr_transfer.ZLIB else tr("brut")),
                 tr("QR version {v0}, correction {v1}, {v2} × {v2} modules + 4 modules blancs par côté.", v0=s.version, v1=s.error, v2=s.size),
                 tr("Message NDEF : {v0} octets ; SHA-256 {v1}.", v0=s.ndef_bytes, v1=s.sha256),
                 tr("Étiquette NFC visée : {v0}, réserve {v1} octets.", v0=self.snap.tag_type, v1=self.snap.reserved_bytes)]
        if plan:
            lines.append(tr("Géométrie : {v0} ppp, zone imprimable {v1} × {v2} points ; {v3} modules × {v4} points = {v5} points.",
                            v0=plan.dpi, v1=plan.area[2], v2=plan.area[3], v3=plan.total_modules, v4=plan.dots_per_module or plan.fitting_dots,
                            v5=plan.total_modules * (plan.dots_per_module or plan.fitting_dots)))
        lines.append(tr("SHA-256 détecte une altération accidentelle ; ce n’est pas une signature d’authenticité."))
        return "\n".join(lines)

    def _show_view(self, key):
        self.view_choice.setChoice(key)
        self.stack.setCurrentIndex(0 if key == "qr" else 1)

    def _zoom_changed(self, value):
        self.preview.set_zoom(value)

    def _toggle_details(self, checked):
        self.details.setVisible(checked)
        self.details_toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        if checked:  # Bring the opened details into the band, the code stays where it is.
            QTimer.singleShot(0, lambda: self.lower.verticalScrollBar().setValue(self.details_toggle.y()))

    # ── Files ──────────────────────────────────────────────────────────
    def file_data(self, kind):
        plan = self.plan()
        title = tr("QR Code SpoolScribe — {v0}", v0=self._identity())
        if kind == "svg":
            module = plan.module_mm if plan and plan.printable else 0.5
            description = tr("{v0} ; QR version {v1}-{v2} ; module {v3} mm ; NDEF SHA-256 {v4}",
                             v0=self.snap.format_label, v1=self.symbol.version, v2=self.symbol.error, v3=_mm(module), v4=self.symbol.sha256)
            return qr_layout.svg_bytes(self.symbol, module, title, description)
        if plan and plan.printable:
            scale, density = qr_layout.png_scale(plan)  # Same physical size, whole pixels per module.
            return qr_layout.png_bytes(self.symbol, scale, dpi=density)
        return qr_layout.png_bytes(self.symbol, 10)

    def _save(self, kind):
        default = os.path.join(core.export_directory(), f"{self.snap.file_stem}.{kind}")
        name = {"png": tr("Image PNG (*.png)"), "svg": tr("Image SVG (*.svg)")}[kind]
        path, _ = QFileDialog.getSaveFileName(self, tr("Enregistrer le QR Code"), default, name)
        if not path:
            return None  # Cancelled: no file, no success message.
        if not path.lower().endswith("." + kind):
            # The native dialog confirmed the path it returned, not this one: ask again if it exists.
            path += "." + kind
            if os.path.exists(path):
                answer = QMessageBox.question(self, tr("Remplacer le fichier ?"),
                                              tr("Le fichier existe déjà :\n{v0}\nVoulez-vous le remplacer ?", v0=path),
                                              QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if answer != QMessageBox.Yes:
                    self._set_status(tr("Enregistrement annulé : le fichier existant est conservé."))
                    return None
        try:
            core.db_io.atomic_write(path, self.file_data(kind))
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, tr("Enregistrement impossible"), tr("Le fichier n’a pas été enregistré :\n{v0}", v0=exc))
            self._set_status(tr("Aucun fichier enregistré."))
            return None
        self._set_status(tr("Image enregistrée : {v0}", v0=path))
        return path

    # ── Printing ───────────────────────────────────────────────────────
    def _new_printer(self):
        if self._printer_factory:
            return self._printer_factory()
        from PySide6.QtPrintSupport import QPrinter
        return QPrinter(QPrinter.HighResolution)

    def _run_dialog(self, printer):
        if self._print_dialog:
            return self._print_dialog(printer, self)
        from PySide6.QtPrintSupport import QPrintDialog
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle(tr("Imprimer le QR Code"))
        return dialog.exec() == QDialog.Accepted

    def _available_printers(self):
        if self._printer_names:
            return self._printer_names()
        from PySide6.QtPrintSupport import QPrinterInfo
        return QPrinterInfo.availablePrinterNames()

    def _refuse(self, text):
        self._set_status(text)
        QMessageBox.warning(self, tr("Impression non envoyée"), text)
        return False

    def _print(self):
        """True only once Qt reports the job handed to the system; never « printed »."""
        plan, profile = self.plan(), self.profile()
        if not plan or not plan.printable:
            return self._refuse(self._result_text(plan))
        if not self._printer_factory and not self._available_printers():
            return self._refuse(tr("Aucune imprimante n’est disponible dans le système. Les enregistrements PNG et SVG restent possibles."))
        printer = self._new_printer()
        width, height = profile.width_mm, profile.height_mm
        printer.setPageSize(QPageSize(QSizeF(width, height), QPageSize.Millimeter, tr("Étiquette QR"), QPageSize.ExactMatch))
        printer.setPageOrientation(QPageLayout.Landscape if profile.orientation == "landscape" else QPageLayout.Portrait)
        printer.setPageMargins(QMarginsF(*profile.margins_mm), QPageLayout.Millimeter)
        printer.setResolution(profile.dpi)
        printer.setFullPage(False)
        if not self._run_dialog(printer):
            self._set_status(tr("Impression annulée : rien n’a été envoyé."))
            return False
        if not printer.isValid():
            return self._refuse(tr("L’imprimante choisie n’est pas utilisable. Rien n’a été envoyé."))
        dpi = printer.resolution()
        layout = printer.pageLayout()
        page_mm = layout.fullRect(QPageLayout.Millimeter)
        wanted = (height, width) if profile.orientation == "landscape" else (width, height)
        if abs(page_mm.width() - wanted[0]) > 0.5 or abs(page_mm.height() - wanted[1]) > 0.5:
            return self._refuse(tr("Le pilote n’a pas accepté le format {v0} × {v1} mm (format obtenu : {v2} × {v3} mm). Rien n’a été envoyé.",
                                   v0=_mm(wanted[0]), v1=_mm(wanted[1]), v2=_mm(page_mm.width()), v3=_mm(page_mm.height())))
        paint, page = layout.paintRectPixels(dpi), layout.fullRectPixels(dpi)
        try:
            device = qr_layout.plan_label(self.symbol.total_modules, profile, small_format=self.small.isChecked(),
                                          device=(dpi, (paint.x(), paint.y(), paint.width(), paint.height()), (page.width(), page.height())))
        except ValueError as exc:
            return self._refuse(tr("Réglages du pilote inutilisables : {v0}. Rien n’a été envoyé.", v0=tr(str(exc))))
        if not device.printable:
            return self._refuse(tr("Avec le format et la résolution acceptés par le pilote ({v0} ppp), le QR est trop dense. Rien n’a été envoyé.", v0=dpi))
        painter = QPainter()
        if not painter.begin(printer):
            return self._refuse(tr("Le pilote n’a pas démarré la tâche d’impression. Rien n’a été envoyé."))
        try:
            paint_label(painter, device, self.symbol, self._label_lines())
        finally:
            ended = painter.end()
        if not ended:
            return self._refuse(tr("La tâche d’impression n’a pas pu être terminée."))
        self.last_device_plan = device
        from PySide6.QtPrintSupport import QPrinter
        if printer.outputFormat() == QPrinter.PdfFormat and printer.outputFileName():
            self._set_status(tr("Fichier PDF écrit ({v0} ppp, QR de {v1} mm) : {v2}. Ce n’est pas une impression.",
                                   v0=dpi, v1=_mm(device.qr_mm), v2=printer.outputFileName()))
        else:
            self._set_status(tr("Tâche transmise au système ({v0} ppp, QR de {v1} mm). Vérifiez l’étiquette imprimée et faites un essai de lecture.",
                                   v0=dpi, v1=_mm(device.qr_mm)))
        return True


def paint_label(painter, plan, symbol, lines):
    """Device-dot rectangles only: no antialiasing, scaling or smoothing of modules."""
    painter.setRenderHint(QPainter.Antialiasing, False)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
    x, y, side, _ = plan.qr_rect
    painter.fillRect(x, y, side, side, Qt.white)
    for rect in qr_layout.module_rects(symbol, (x, y), plan.dots_per_module):
        painter.fillRect(*rect, Qt.black)
    if plan.text_lines:
        tx, ty, tw, th = plan.text_rect
        line = th // plan.text_lines
        font = QFont(painter.font()); font.setPixelSize(max(1, line * 3 // 4)); painter.setFont(font)
        painter.setPen(Qt.black)
        for i, text in enumerate(lines[:plan.text_lines]):
            painter.drawText(QRect(tx, ty + i * line, tw, line), Qt.AlignHCenter | Qt.AlignVCenter,
                             painter.fontMetrics().elidedText(text, Qt.ElideRight, tw))


def _mm(value):
    from .i18n import language
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") if language() in ("fr", "es") else text


def open_qr_window(window):
    """Fresh snapshot on every opening; an earlier window is closed, never refreshed silently."""
    try:
        snap = snapshot(window)
        qr = QrWindow(snap, window)
    except (ValueError, OSError) as exc:
        window.status.showMessage(tr("QR Code indisponible : {v0}", v0=tr(str(exc))), 8000)
        return None
    previous = getattr(window, "_qr_window", None)
    if previous is not None:
        try:
            previous.close()
        except RuntimeError:
            pass
    window._qr_window = qr
    qr.show(); qr.raise_(); qr.activateWindow()
    return qr

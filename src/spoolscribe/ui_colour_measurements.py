"""« Valeurs couleur : Lab, RGB, fichier… » : saisie, collage, import CSV et registre de mesures.

Presentation and orchestration only. Values are parsed by ``colour_import`` /
``colour_measurements``, stored by ``measurement_store`` and ranked through
``colour_targets``. Nothing here writes the catalogue, a personal copy or an NFC/QR encoder.
Device presets are stored separately only on explicit request. External text (pasted or imported)
is shown as plain text only.

Each entry (Saisir, Coller, Enregistrées) owns its draft: the actions below
the tabs always act on the draft of the *visible* entry, never on a hidden
one. Importer has no draft; its batch is saved only by its own button.
"""
from __future__ import annotations

import hashlib
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton,
    QSizePolicy, QStackedWidget, QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout, QWidget)

from scripts import db_io

from . import colour_import as ci, colour_measurements as cm, colour_targets as ct, measurement_store as ms
from .device_profiles import DeviceProfiles
from .i18n import tr
from .ui_guidance import FlowLabel, InfoTile
from .ui_surfaces import ReadingTabs, fit_dialog
from .ui_widgets import CONTROL_HEIGHT

LEVEL_LABELS = {"indicative": "Proximité indicative", "blocked": "Conditions insuffisantes"}
REASONS = {
    "srgb_declared": "Couleur d’écran sRGB : comparaison indicative avec les couleurs déclarées du catalogue.",
    "lab_d65_2": "CIELAB D65/2° : comparé tel quel aux couleurs déclarées du catalogue (converties en D65/2°). Ce n’est pas une mesure du filament imprimé.",
    "conditions_unknown": "Indiquez l’éclairage (illuminant) et l’observateur de la mesure : vérifiez la fiche ou l’application de votre appareil.",
    "adaptation_unavailable": "Mesure en D50 : aucune adaptation vers D65 n’est disponible dans cette version. La mesure reste enregistrable.",
    "illuminant_unsupported": "Cet éclairage n’est pas comparable aux couleurs du catalogue (D65). La mesure reste enregistrable.",
    "observer_unsupported": "Observateur 10° : il n’existe pas de conversion universelle vers 2°. La mesure reste enregistrable.",
    "magnitude": "Valeurs trop grandes pour le calcul ; la mesure reste enregistrable.",
}
ILLUMINANT_CHOICES = ((None, "Je ne sais pas"), ("D65", "D65"), ("D50", "D50"), ("other", "Autre (à décrire)"))
OBSERVER_CHOICES = ((None, "Je ne sais pas"), (2, "2°"), (10, "10°"))
SPECULAR_CHOICES = ((None, "Non renseigné"), ("SCI", "SCI (spéculaire inclus)"), ("SCE", "SCE (spéculaire exclu)"))
SAMPLE_CHOICES = (("unknown", "Non renseigné"), ("raw_filament", "Filament brut"), ("printed_sample", "Pièce imprimée"),
                  ("painted_surface", "Surface peinte"), ("object", "Objet"), ("other", "Autre"))
ROLE_CHOICES = (("target", "Cible à approcher"), ("filament_sample", "Mesure d’un filament"))
COLUMN_ROLES = (("L", "L*"), ("a", "a*"), ("b", "b*"), ("hex", "HEX"), ("r", "R"), ("g", "G"), ("b_rgb", "B (RGB)"),
                ("name", "Nom"), ("illuminant", "Illuminant"), ("observer", "Observateur"), ("geometry", "Géométrie"),
                ("specular", "SCI/SCE"), ("aperture", "Ouverture"), ("device", "Appareil"), ("manufacturer", "Fabricant"),
                ("material", "Matériau"), ("finish", "Finition"), ("thickness", "Épaisseur"), ("backing", "Fond"),
                ("note", "Note"), ("date", "Date"))
SPACE_LABELS = {"CIELAB": "Lab (L*, a*, b*)", "sRGB_HEX": "HEX", "sRGB_RGB8": "RGB"}
TAB_KEYS = {0: "manual", 1: "paste", 2: None, 3: "saved"}


def _combo(choices, current=None):
    box = QComboBox(); box.setFixedHeight(CONTROL_HEIGHT); box.setMinimumWidth(0)
    box.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon); box.setMinimumContentsLength(8)
    for value, label in choices:
        box.addItem(tr(label), value)
    if current is not None:
        box.setCurrentIndex(max(0, box.findData(current)))
    return box


def _field(placeholder="", width=None):
    edit = QLineEdit(); edit.setFixedHeight(CONTROL_HEIGHT); edit.setClearButtonEnabled(True)
    if placeholder:
        edit.setPlaceholderText(placeholder)
    if width:
        edit.setMaximumWidth(width)
    return edit


def _section(title):
    card = QFrame(); card.setObjectName("guidanceTile")
    layout = QVBoxLayout(card); layout.setContentsMargins(12, 10, 12, 10); layout.setSpacing(8)
    heading = FlowLabel(title); heading.setObjectName("guidanceTitle"); layout.addWidget(heading)
    return card, layout


def _labelled(label, widget, hint=None):
    """Labels above bounded-width fields: no competing nested form label columns."""
    cell = QWidget(); layout = QVBoxLayout(cell); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(4)
    caption = FlowLabel(label); caption.setObjectName("guidanceNote"); layout.addWidget(caption)
    caption.setBuddy(widget)
    if not widget.accessibleName(): widget.setAccessibleName(label)
    widget.setMinimumWidth(0); layout.addWidget(widget)
    if hint:
        note = FlowLabel(hint); note.setObjectName("guidanceNote"); layout.addWidget(note)
    return cell


def _toggle(label):
    button = QToolButton(); button.setText(label); button.setCheckable(True)
    button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); button.setArrowType(Qt.RightArrow)
    button.setMinimumHeight(CONTROL_HEIGHT); button.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    button.toggled.connect(lambda checked: button.setArrowType(Qt.DownArrow if checked else Qt.RightArrow))
    return button


def _error(exc) -> str:
    return cm.error_text(exc, tr)


class ConditionsForm(QWidget):
    """Illuminant / observer, then the optional documented conditions (progressive disclosure). Unknown by default."""
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        form = QGridLayout(self); form.setContentsMargins(0, 0, 0, 0); form.setSpacing(8)
        form.setColumnStretch(0, 1); form.setColumnStretch(1, 1)
        self.illuminant = _combo(ILLUMINANT_CHOICES); self.illuminant.setAccessibleName(tr("Éclairage de la mesure"))
        self.illuminant_note = _field(tr("Nom de l’éclairage, ex. TL84")); self.illuminant_note.setMaxLength(cm.LIMITS["short"]); self.illuminant_note.hide()
        self.observer = _combo(OBSERVER_CHOICES); self.observer.setAccessibleName(tr("Observateur"))
        form.addWidget(_labelled(tr("Éclairage de la mesure"), self.illuminant), 0, 0)
        form.addWidget(_labelled(tr("Observateur"), self.observer), 0, 1)
        form.addWidget(self.illuminant_note, 1, 0, 1, 2)
        note = FlowLabel(tr("Recopiez ces deux réglages depuis votre appareil. Pour comparer au catalogue : D65 et 2°. Si vous ne savez pas, vous pouvez conserver la mesure sans la comparer."))
        note.setObjectName("guidanceNote"); form.addWidget(note, 2, 0, 1, 2)
        self.advanced_toggle = _toggle(tr("Réglages avancés")); form.addWidget(self.advanced_toggle, 3, 0, 1, 2)
        self.advanced = QWidget(); advanced = QGridLayout(self.advanced); advanced.setContentsMargins(0, 0, 0, 0); advanced.setSpacing(8)
        advanced.setColumnStretch(0, 1); advanced.setColumnStretch(1, 1)
        self.geometry = _field(tr("ex. 45/0, d/8")); self.specular = _combo(SPECULAR_CHOICES); self.specular.setAccessibleName(tr("Composante spéculaire"))
        self.aperture = _field(tr("ex. 8 mm")); self.calibration = _field(tr("Date ou référence de calibration")); self.profile_note = _field(tr("Profil ou réglage de l’application"))
        hint = FlowLabel(tr("Facultatif : recopiez uniquement les informations documentées. Ne les déduisez pas du nom de l’appareil.")); hint.setObjectName("guidanceNote"); advanced.addWidget(hint, 0, 0, 1, 2)
        fields = ((tr("Géométrie"), self.geometry), (tr("SCI/SCE"), self.specular), (tr("Ouverture"), self.aperture), (tr("Calibration"), self.calibration), (tr("Profil"), self.profile_note))
        for i, (label, field) in enumerate(fields):
            if isinstance(field, QLineEdit): field.setMaxLength(cm.LIMITS["short"])
            advanced.addWidget(_labelled(label, field), 1 + i // 2, i % 2)
        self.geometry.setToolTip(tr("Disposition de l’éclairage et du capteur, indiquée par le fabricant."))
        self.specular.setToolTip(tr("SCI inclut les reflets ; SCE les exclut. Recopiez le réglage de l’appareil."))
        self.aperture.setToolTip(tr("Diamètre de la zone mesurée, indiqué par votre appareil."))
        self.advanced.hide(); self.advanced_toggle.toggled.connect(self.advanced.setVisible); form.addWidget(self.advanced, 4, 0, 1, 2)
        self.illuminant.currentIndexChanged.connect(lambda *_: (self.illuminant_note.setVisible(self.illuminant.currentData() == "other"), self.changed.emit()))
        for box in (self.observer, self.specular):
            box.currentIndexChanged.connect(lambda *_: self.changed.emit())
        for edit in (self.illuminant_note, self.geometry, self.aperture, self.calibration, self.profile_note):
            edit.textChanged.connect(lambda *_: self.changed.emit())

    def values(self) -> dict:
        conditions = {"illuminant": self.illuminant.currentData(), "observer": self.observer.currentData()}
        if conditions["illuminant"] == "other":
            conditions["illuminant_note"] = self.illuminant_note.text().strip() or None
        for key, edit in (("geometry", self.geometry), ("aperture", self.aperture), ("calibration", self.calibration), ("profile_note", self.profile_note)):
            if edit.text().strip():
                conditions[key] = edit.text().strip()
        if self.specular.currentData():
            conditions["specular"] = self.specular.currentData()
        return conditions

    def set_values(self, conditions: dict | None):
        conditions = conditions or {}
        for widget in (self.illuminant, self.observer, self.specular):
            widget.blockSignals(True)
        self.illuminant.setCurrentIndex(max(0, self.illuminant.findData(conditions.get("illuminant"))))
        self.observer.setCurrentIndex(max(0, self.observer.findData(conditions.get("observer"))))
        self.specular.setCurrentIndex(max(0, self.specular.findData(conditions.get("specular"))))
        self.illuminant_note.setText(conditions.get("illuminant_note") or ""); self.illuminant_note.setVisible(conditions.get("illuminant") == "other")
        for key, edit in (("geometry", self.geometry), ("aperture", self.aperture), ("calibration", self.calibration), ("profile_note", self.profile_note)):
            edit.setText(conditions.get(key) or "")
        for widget in (self.illuminant, self.observer, self.specular):
            widget.blockSignals(False)


class MeasurementWindow(QDialog):
    """One window, three entries (Saisir / Coller / Importer) and the saved measurements."""
    search_requested = Signal(dict)
    registry_changed = Signal()

    def __init__(self, parent, *, registry=None, current_sku_provider=None, db_provider=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Valeurs couleur : Lab, RGB, fichier"))
        self.setWindowModality(Qt.WindowModal); self.setMinimumSize(420, 420)
        self.registry = registry or ms.MeasurementRegistry()
        self._current_sku = current_sku_provider or (lambda: None)
        self._db = db_provider or (lambda: {})
        self._drafts = {"manual": None, "paste": None, "saved": None}        # one draft per entry, awaiting an explicit action
        self._identifiers = {"manual": None, "paste": None, "saved": None}   # registry id when the draft is a saved measurement
        self.import_report = None
        self._import_state = None
        self._paste_result = None
        self._paste_text = None   # the text that was interpreted; editing it invalidates the proposal
        layout = QVBoxLayout(self); layout.setContentsMargins(16, 16, 16, 16); layout.setSpacing(10)
        heading = FlowLabel(tr("Valeurs couleur : Lab, RGB, fichier")); heading.setObjectName("guidanceHeading"); layout.addWidget(heading)
        layout.addWidget(FlowLabel(tr("Recopiez une couleur, vérifiez ce qui peut être comparé, puis recherchez des filaments. Le catalogue reste inchangé.")))
        self.tabs = ReadingTabs(); layout.addWidget(self.tabs, 1)
        self.tabs.addTab(self._build_manual_page(), tr("Saisir"))
        self.tabs.addTab(self._build_paste_page(), tr("Coller"))
        self.tabs.addTab(self._build_import_page(), tr("Importer"))
        self.tabs.addTab(self._build_saved_page(), tr("Enregistrées"))
        self.tabs.currentChanged.connect(lambda *_: self._refresh_policy())
        # Comparison level, above the actions, readable without colour; a small swatch only for confirmed sRGB codes.
        level_row = QHBoxLayout(); level_row.setSpacing(8)
        self.swatch = QFrame(); self.swatch.setFixedSize(36, 36); self.swatch.setObjectName("measurementSwatch")
        self.swatch.setAccessibleName(tr("Aperçu du code sRGB confirmé")); self.swatch.hide(); level_row.addWidget(self.swatch, 0, Qt.AlignTop)
        self.level_tile = InfoTile(tr("Niveau de comparaison"), tone="neutral"); level_row.addWidget(self.level_tile, 1)
        self.level_tile.value.setText("—"); self.level_tile.note.show(); layout.addLayout(level_row)
        actions = QGridLayout(); actions.setSpacing(8)
        self.action_grid = actions
        self.btn_save = QPushButton(tr("Enregistrer la mesure")); self.btn_save.clicked.connect(self._save_draft)
        self.btn_search = QPushButton(tr("Rechercher des filaments proches")); self.btn_search.setObjectName("primary")
        self.btn_search.clicked.connect(self._search_draft)
        self.btn_close = QPushButton(tr("Fermer")); self.btn_close.clicked.connect(self.reject)
        for column, button in enumerate((self.btn_close, self.btn_save, self.btn_search)):
            button.setFixedHeight(CONTROL_HEIGHT); actions.addWidget(button, 0, column)
        actions.addWidget(self.btn_check, 0, 1); actions.addWidget(self.btn_import, 0, 2)
        actions.setColumnStretch(1, 1); actions.setColumnStretch(2, 1)
        layout.addLayout(actions)
        self.feedback = FlowLabel(); self.feedback.setObjectName("guidanceNote"); self.feedback.setAccessibleName(tr("Message")); layout.addWidget(self.feedback)
        self._refresh_policy()

    def showEvent(self, event):
        super().showEvent(event); fit_dialog(self, preferred_width=820)
        self._load_registry(); self._refresh_saved()

    # ── drafts: one per entry ────────────────────────────────────────────
    def _current_key(self):
        return TAB_KEYS.get(self.tabs.currentIndex()) if hasattr(self, "tabs") else "manual"

    @property
    def draft(self):
        """The draft of the visible entry only (None under Importer)."""
        key = self._current_key()
        return self._drafts.get(key) if key else None

    @property
    def draft_identifier(self):
        key = self._current_key()
        return self._identifiers.get(key) if key else None

    def _set_draft(self, key, draft, identifier=None):
        self._drafts[key] = draft; self._identifiers[key] = identifier
        self._refresh_policy()

    # ── Saisir ───────────────────────────────────────────────────────────
    def _build_manual_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(8, 12, 8, 12); layout.setSpacing(10)
        entry, entry_layout = _section(tr("1. Vos valeurs")); layout.addWidget(entry)
        entry_layout.addWidget(FlowLabel(tr("Choisissez le format affiché par votre appareil ou son application. Recopiez les nombres sans les convertir.")))
        form = QVBoxLayout(); form.setSpacing(8)
        self.space = _combo((("sRGB_HEX", "Code HEX sRGB"), ("sRGB_RGB8", "RGB sRGB 8 bits"), ("CIELAB", "CIELAB (L*, a*, b*)")))
        self.space.setAccessibleName(tr("Format des valeurs")); form.addWidget(_labelled(tr("Format des valeurs"), self.space))
        self.value_stack = QStackedWidget()
        hex_widget = QWidget(); hex_row = QHBoxLayout(hex_widget); hex_row.setContentsMargins(0, 0, 0, 0)
        self.hex_edit = _field("#74CABF", 160); self.hex_edit.setMaxLength(7); self.hex_edit.setAccessibleName(tr("Code HEX")); hex_row.addWidget(self.hex_edit); hex_row.addStretch(1)
        self.value_stack.addWidget(hex_widget)
        rgb_widget = QWidget(); rgb_row = QHBoxLayout(rgb_widget); rgb_row.setContentsMargins(0, 0, 0, 0)
        self.rgb_edits = {}
        for key, label in (("r", "R"), ("g", "G"), ("b", "B")):
            rgb_row.addWidget(QLabel(label)); edit = _field("0–255", 80); edit.setMaxLength(4); edit.setAccessibleName(tr("Canal {v0}", v0=label))
            self.rgb_edits[key] = edit; rgb_row.addWidget(edit)
        rgb_row.addStretch(1); self.value_stack.addWidget(rgb_widget)
        lab_widget = QWidget(); lab_row = QHBoxLayout(lab_widget); lab_row.setContentsMargins(0, 0, 0, 0)
        self.lab_edits = {}
        for key, label, example in (("L", "L*", "73,2"), ("a", "a*", "-25,6"), ("b", "b*", "-12,4")):
            edit = _field(example, 130); edit.setMaxLength(cm.LIMITS["lexeme"]); edit.setAccessibleName(tr("Coordonnée {v0}", v0=label))
            self.lab_edits[key] = edit; lab_row.addWidget(_labelled(label, edit), 1)
        lab_row.addStretch(1); self.value_stack.addWidget(lab_widget)
        form.addWidget(self.value_stack)
        self.value_help = FlowLabel(); self.value_help.setObjectName("guidanceNote"); form.addWidget(self.value_help)
        entry_layout.addLayout(form)
        self.conditions_box, conditions = _section(tr("2. Conditions de comparaison"))
        self.manual_conditions = ConditionsForm(); conditions.addWidget(self.manual_conditions)
        # Short names kept for the existing flows and tests.
        self.illuminant, self.illuminant_note, self.observer = self.manual_conditions.illuminant, self.manual_conditions.illuminant_note, self.manual_conditions.observer
        self.geometry, self.specular, self.aperture = self.manual_conditions.geometry, self.manual_conditions.specular, self.manual_conditions.aperture
        self.calibration, self.profile_note = self.manual_conditions.calibration, self.manual_conditions.profile_note
        layout.addWidget(self.conditions_box)
        self.details_toggle = _toggle(tr("Informations facultatives")); layout.addWidget(self.details_toggle)
        self.details = QWidget(); details = QGridLayout(self.details); details.setContentsMargins(0, 0, 0, 0); details.setSpacing(8)
        details.setColumnStretch(0, 1); details.setColumnStretch(1, 1)
        self.name_edit = _field(tr("ex. Échantillon vert")); self.name_edit.setMaxLength(cm.LIMITS["name"])
        self.role = _combo(ROLE_CHOICES); self.sample_type = _combo(SAMPLE_CHOICES)
        self.device_manufacturer = _field(tr("Fabricant de l’appareil")); self.device_model = _field(tr("Modèle ou application"))
        self.sample_material = _field(tr("ex. PLA, PETG")); self.sample_finish = _field(tr("ex. mat, brillant, soyeux"))
        self.sample_thickness = _field(tr("ex. 2 mm, 4 couches")); self.sample_backing = _field(tr("ex. fond blanc, fond noir"))
        for edit in (self.device_manufacturer, self.device_model, self.sample_material, self.sample_finish, self.sample_thickness, self.sample_backing):
            edit.setMaxLength(cm.LIMITS["short"])
        self.measured_at = _field(tr("Date de la mesure, si connue")); self.measured_at.setMaxLength(cm.LIMITS["short"])
        self.note_edit = _field(tr("Note libre")); self.note_edit.setMaxLength(cm.LIMITS["note"])
        self.sample_surface_note = _field(tr("État de surface, préparation")); self.sample_surface_note.setMaxLength(cm.LIMITS["note"])
        identity, identity_layout = _section(tr("Nom et utilisation"))
        identity_grid = QGridLayout(); identity_grid.setSpacing(8)
        for i, (label, field) in enumerate(((tr("Nom"), self.name_edit), (tr("Rôle"), self.role), (tr("Date"), self.measured_at), (tr("Note"), self.note_edit))):
            identity_grid.addWidget(_labelled(label, field), i // 2, i % 2)
        identity_layout.addLayout(identity_grid); details.addWidget(identity, 0, 0, 1, 2)
        sample, sample_layout = _section(tr("Échantillon mesuré"))
        sample_grid = QGridLayout(); sample_grid.setSpacing(8)
        for i, (label, field) in enumerate(((tr("Échantillon"), self.sample_type), (tr("Matériau"), self.sample_material), (tr("Finition"), self.sample_finish), (tr("Épaisseur"), self.sample_thickness), (tr("Fond"), self.sample_backing), (tr("Surface"), self.sample_surface_note))):
            sample_grid.addWidget(_labelled(label, field), i // 2, i % 2)
        sample_layout.addLayout(sample_grid); details.addWidget(sample, 1, 0, 1, 2)
        device, device_layout = _section(tr("Votre appareil"))
        device_grid = QGridLayout(); device_grid.setSpacing(8)
        device_grid.addWidget(_labelled(tr("Fabricant"), self.device_manufacturer), 0, 0)
        device_grid.addWidget(_labelled(tr("Modèle ou application"), self.device_model), 0, 1)
        device_layout.addLayout(device_grid)
        self.btn_profile_save = QPushButton(tr("Mémoriser ces réglages…")); self.btn_profile_save.setFixedHeight(CONTROL_HEIGHT)
        self.btn_profile_save.clicked.connect(self._save_device_profile); device_layout.addWidget(self.btn_profile_save, 0, Qt.AlignRight)
        details.addWidget(device, 2, 0, 1, 2)
        # Selecting a default preset never applies scientific conditions without an explicit click.
        self.device_profiles = DeviceProfiles(self.registry.path.with_name("colour_device_profiles.json"))
        profile_card, profile_layout = _section(tr("Appareil mémorisé"))
        profile_row = QHBoxLayout(); self.device_profile = _combo(())
        self.device_profile.setAccessibleName(tr("Appareil mémorisé")); profile_row.addWidget(self.device_profile, 1)
        self.btn_profile_apply = QPushButton(tr("Utiliser ces réglages")); self.btn_profile_apply.setFixedHeight(CONTROL_HEIGHT)
        self.btn_profile_apply.clicked.connect(self._apply_device_profile); profile_row.addWidget(self.btn_profile_apply)
        profile_layout.addLayout(profile_row)
        self.profile_status = FlowLabel(tr("Un profil prépare la saisie ; il ne certifie ni l’appareil ni sa calibration.")); self.profile_status.setObjectName("guidanceNote"); profile_layout.addWidget(self.profile_status)
        profile_actions = QHBoxLayout(); self.profile_default = QCheckBox(tr("Proposer au prochain démarrage")); profile_actions.addWidget(self.profile_default); profile_actions.addStretch()
        self.btn_profile_delete = QPushButton(tr("Oublier…")); self.btn_profile_delete.setFixedHeight(CONTROL_HEIGHT); profile_actions.addWidget(self.btn_profile_delete)
        profile_layout.addLayout(profile_actions); layout.insertWidget(0, profile_card)
        self.profile_card = profile_card
        self.device_profile.currentIndexChanged.connect(self._profile_selected)
        self.profile_default.clicked.connect(self._set_default_profile)
        self.btn_profile_delete.clicked.connect(self._delete_device_profile)
        self._load_device_profiles()
        self.details.hide(); self.details_toggle.toggled.connect(self.details.setVisible); layout.addWidget(self.details)
        self.manual_error = FlowLabel(); self.manual_error.setObjectName("guidanceCaution"); self.manual_error.hide(); layout.addWidget(self.manual_error)
        layout.addStretch(1)
        self.space.currentIndexChanged.connect(self._space_changed)
        self.manual_conditions.changed.connect(self._manual_changed)
        for edit in (self.hex_edit, *self.rgb_edits.values(), *self.lab_edits.values()):
            edit.textChanged.connect(self._manual_changed)
        self._space_changed()
        return page

    def _space_changed(self, *_):
        index = self.space.currentIndex(); self.value_stack.setCurrentIndex(index)
        self.conditions_box.setVisible(self.space.currentData() == "CIELAB")
        hints = {"CIELAB": tr("L* : clarté de 0 à 100 · a* : axe vert/rouge · b* : axe bleu/jaune. Gardez les signes + ou − indiqués par votre appareil."),
                 "sRGB_HEX": tr("HEX : six chiffres ou lettres, par exemple #74CABF."),
                 "sRGB_RGB8": tr("RGB : trois nombres entiers de 0 à 255, dans l’ordre rouge, vert, bleu.")}
        self.value_help.setText(hints[self.space.currentData()])
        self._manual_changed()

    def _manual_conditions(self):
        return self.manual_conditions.values() if self.space.currentData() == "CIELAB" else {}

    def _manual_changed(self, *_):
        """Rebuild the manual draft from the manual fields only; other entries are untouched."""
        space = self.space.currentData()
        fields = ({"hex": self.hex_edit.text()} if space == "sRGB_HEX" else
                  {k: e.text() for k, e in self.rgb_edits.items()} if space == "sRGB_RGB8" else
                  {k: e.text() for k, e in self.lab_edits.items()})
        if not any(str(v).strip() for v in fields.values()):
            self.manual_error.hide(); self._set_draft("manual", None); return
        try:
            original = cm.parse_manual(space, fields)
        except cm.MeasurementError as exc:
            self.manual_error.setText(_error(exc)); self.manual_error.show(); self._set_draft("manual", None); return
        self.manual_error.hide()
        self._set_draft("manual", {"original": original, "conditions": self._manual_conditions(), "method": "manual"})

    # ── explicit device entry presets ──────────────────────────────────
    def _load_device_profiles(self, selected=None):
        try:
            document = self.device_profiles.load()
        except (db_io.DatabaseError, cm.MeasurementError, OSError) as exc:
            self.profile_status.setText(_error(exc)); self.btn_profile_save.setEnabled(False)
            document = {"profiles": {}, "default": None}
        self.device_profile.blockSignals(True); self.device_profile.clear()
        self.device_profile.addItem(tr("Aucun appareil mémorisé"), None)
        for identifier, profile in document["profiles"].items():
            self.device_profile.addItem(profile["name"], identifier)
        chosen = selected or document["default"]
        self.device_profile.setCurrentIndex(max(0, self.device_profile.findData(chosen)))
        self.device_profile.blockSignals(False); self._profile_selected()
        self.profile_card.setVisible(bool(document["profiles"]))

    def _profile_selected(self, *_):
        identifier = self.device_profile.currentData()
        self.btn_profile_apply.setEnabled(bool(identifier)); self.btn_profile_delete.setEnabled(bool(identifier))
        self.profile_default.setEnabled(bool(identifier))
        self.profile_default.setChecked(bool(identifier) and self.device_profiles.document["default"] == identifier)
        if identifier:
            self.profile_status.setText(tr("Vérifiez les réglages de votre appareil, puis cliquez sur « Utiliser ces réglages ». Les valeurs de couleur et la calibration ne sont jamais reprises."))

    def _save_device_profile(self):
        name, accepted = QInputDialog.getText(self, tr("Mémoriser un appareil"), tr("Nom du profil :"), text=self.device_model.text().strip())
        if not accepted or not name.strip(): return
        try:
            identifier = self.device_profiles.add(name.strip(), self.manual_conditions.values(), self.device_manufacturer.text().strip(), self.device_model.text().strip())
        except (db_io.DatabaseError, cm.MeasurementError, OSError) as exc:
            self._say(_error(exc), error=True); return
        self._load_device_profiles(identifier)
        self._say(tr("Réglages mémorisés. Cochez « Proposer au prochain démarrage » si vous souhaitez les retrouver par défaut."))

    def _apply_device_profile(self):
        profile = self.device_profiles.document["profiles"].get(self.device_profile.currentData())
        if not profile: return
        # Explicit reuse only: calibration, values, sample and date remain untouched.
        conditions = dict(profile["conditions"])
        if self.calibration.text().strip(): conditions["calibration"] = self.calibration.text().strip()
        self.manual_conditions.set_values(conditions)
        self.device_manufacturer.setText(profile["manufacturer"]); self.device_model.setText(profile["model"])
        self._manual_changed()
        self.profile_status.setText(tr("Réglages repris. Vérifiez qu’ils correspondent à cette mesure ; la calibration reste à documenter pour chaque séance."))

    def _set_default_profile(self, checked):
        try:
            self.device_profiles.set_default(self.device_profile.currentData() if checked else None)
        except (db_io.DatabaseError, cm.MeasurementError, OSError) as exc:
            self._say(_error(exc), error=True); self._profile_selected()

    def _delete_device_profile(self):
        identifier = self.device_profile.currentData()
        if not identifier: return
        if QMessageBox.question(self, tr("Oublier cet appareil"), tr("Oublier ces réglages mémorisés ? Les mesures enregistrées ne changent pas."), QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes: return
        try:
            self.device_profiles.delete(identifier)
        except (db_io.DatabaseError, cm.MeasurementError, OSError) as exc:
            self._say(_error(exc), error=True); return
        self._load_device_profiles()

    # ── Coller ───────────────────────────────────────────────────────────
    def _build_paste_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(8, 12, 8, 12); layout.setSpacing(10)
        layout.addWidget(FlowLabel(tr("Collez le texte copié depuis l’application ou l’appareil. Seules les valeurs étiquetées (HEX, RGB, L*, a*, b*, D50/D65, 2°/10°) sont reconnues ; rien n’est deviné.")))
        self.paste_edit = QPlainTextEdit(); self.paste_edit.setPlaceholderText("L*=73,2 ; a*=-25,6 ; b*=-12,4 ; D65 2°")
        self.paste_edit.setAccessibleName(tr("Texte collé")); self.paste_edit.setMaximumHeight(140); layout.addWidget(self.paste_edit)
        self.paste_edit.textChanged.connect(self._paste_text_changed)
        row = QHBoxLayout(); self.btn_interpret = QPushButton(tr("Interpréter")); self.btn_interpret.setFixedHeight(CONTROL_HEIGHT)
        self.btn_interpret.clicked.connect(self._interpret_paste); row.addWidget(self.btn_interpret); row.addStretch(1); layout.addLayout(row)
        layout.addWidget(FlowLabel(tr("Interprétation proposée — choisissez le jeu de valeurs principal :")))
        self.paste_candidates = QListWidget(); self.paste_candidates.setObjectName("facets"); self.paste_candidates.setMaximumHeight(110)
        self.paste_candidates.setAccessibleName(tr("Jeux de valeurs reconnus")); self.paste_candidates.itemSelectionChanged.connect(self._paste_choice_changed)
        layout.addWidget(self.paste_candidates)
        self.paste_conditions = FlowLabel(); self.paste_conditions.setObjectName("guidanceNote"); layout.addWidget(self.paste_conditions)
        self.paste_conditions_form = ConditionsForm(); self.paste_conditions_form.hide(); layout.addWidget(self.paste_conditions_form)
        self.paste_illuminant, self.paste_observer = self.paste_conditions_form.illuminant, self.paste_conditions_form.observer
        self.paste_illuminant_note = self.paste_conditions_form.illuminant_note
        self.paste_conditions_form.changed.connect(self._paste_choice_changed)
        self.paste_errors = FlowLabel(); self.paste_errors.setObjectName("guidanceCaution"); self.paste_errors.hide(); layout.addWidget(self.paste_errors)
        layout.addStretch(1)
        return page

    def _paste_text_changed(self, *_):
        """Editing the text after an interpretation withdraws the proposal until a new one is confirmed."""
        if self._paste_result is None or self.paste_edit.toPlainText() == self._paste_text:
            return
        self._paste_result = None; self._paste_text = None
        self.paste_candidates.blockSignals(True); self.paste_candidates.clear(); self.paste_candidates.blockSignals(False)
        self.paste_conditions.setText(tr("Texte modifié : cliquez sur « Interpréter » pour une nouvelle proposition."))
        self.paste_errors.hide()
        self.paste_conditions_form.hide()
        self._set_draft("paste", None)

    def _interpret_paste(self):
        text = self.paste_edit.toPlainText()
        result = self._paste_result = ci.interpret_paste(text); self._paste_text = text
        self.paste_candidates.blockSignals(True); self.paste_candidates.clear()
        for candidate in result["candidates"]:
            if candidate["space"] == "sRGB_HEX":
                label = tr("HEX {v0}", v0="#" + candidate["components"]["hex"])
            elif candidate["space"] == "sRGB_RGB8":
                label = tr("RGB {v0}", v0=", ".join(candidate["lexemes"][k] for k in "rgb"))
            else:
                label = tr("Lab {v0}", v0=" · ".join(f"{k}* {candidate['lexemes'][k]}" for k in ("L", "a", "b")))
            item = QListWidgetItem(label); item.setData(Qt.UserRole, result["candidates"].index(candidate)); self.paste_candidates.addItem(item)
        self.paste_candidates.blockSignals(False)
        self.paste_conditions_form.setVisible(any(c["space"] == "CIELAB" for c in result["candidates"]))
        conditions = result["conditions"]
        self.paste_conditions_form.set_values(conditions)
        found = []
        if conditions.get("illuminant"):
            found.append(tr("éclairage {v0}", v0=conditions.get("illuminant_note") or conditions["illuminant"]))
        if conditions.get("observer"):
            found.append(tr("observateur {v0}°", v0=conditions["observer"]))
        self.paste_conditions.setText(tr("Conditions trouvées dans le texte : {v0}", v0=", ".join(found)) if found
                                      else tr("Aucune condition de mesure trouvée dans le texte."))
        messages = ci.error_messages(result, tr)
        if result["consistent"] is True:
            messages.append(tr("HEX et RGB sont cohérents."))
        if result["needs_decision"]:
            messages.append(tr("Une décision est nécessaire avant d’enregistrer ou de rechercher."))
        self.paste_errors.setText("\n".join(messages)); self.paste_errors.setVisible(bool(messages))
        if len(result["candidates"]) == 1 and not result["needs_decision"]:
            self.paste_candidates.setCurrentRow(0)
        else:
            self._set_draft("paste", None)

    def _paste_choice_changed(self, *_):
        result = self._paste_result
        items = self.paste_candidates.selectedItems()
        if not result or not items or self.paste_edit.toPlainText() != self._paste_text:
            self._set_draft("paste", None); return
        chosen = result["candidates"][items[0].data(Qt.UserRole)]
        conditions = self.paste_conditions_form.values()
        try:
            original = ci.candidate_to_original(chosen, result["candidates"], conditions=conditions)
            original["raw_text"] = self._paste_text[:cm.LIMITS["paste_bytes"]]
            original = cm.validate_original(original)
            cm.validate_conditions(conditions)
        except cm.MeasurementError as exc:
            self.paste_errors.setText(_error(exc)); self.paste_errors.show(); self._set_draft("paste", None); return
        self._set_draft("paste", {"original": original, "conditions": conditions, "method": "paste"})

    # ── Importer ─────────────────────────────────────────────────────────
    def _build_import_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(8, 12, 8, 12); layout.setSpacing(10)
        layout.addWidget(FlowLabel(tr("Fichier CSV ou TSV local. Le fichier n’est jamais modifié ; vous confirmez l’encodage, le séparateur, la virgule décimale et chaque colonne.")))
        row = QHBoxLayout(); self.btn_file = QPushButton(tr("Choisir un fichier…")); self.btn_file.setFixedHeight(CONTROL_HEIGHT)
        self.btn_file.clicked.connect(self._choose_file); row.addWidget(self.btn_file)
        self.file_label = FlowLabel(tr("Aucun fichier choisi")); self.file_label.setObjectName("guidanceNote"); row.addWidget(self.file_label, 1); layout.addLayout(row)
        self.import_setup = QWidget(); setup_layout = QVBoxLayout(self.import_setup); setup_layout.setContentsMargins(0, 0, 0, 0); setup_layout.setSpacing(8)
        options = QHBoxLayout()
        self.encoding = _combo((("utf-8", "UTF-8 (ou BOM)"), ("cp1252", "Windows-1252"), ("latin-1", "Latin-1")))
        self.delimiter = _combo(((",", "virgule"), (";", "point-virgule"), ("\t", "tabulation")))
        self.decimal = _combo(((".", "point décimal"), (",", "virgule décimale")))
        for label, box in ((tr("Encodage"), self.encoding), (tr("Séparateur"), self.delimiter), (tr("Décimales"), self.decimal)):
            options.addWidget(_labelled(label, box), 1)
        setup_layout.addLayout(options)
        self.encoding.currentIndexChanged.connect(lambda *_: self._reload_preview(auto=True))
        for box in (self.delimiter, self.decimal):
            box.currentIndexChanged.connect(lambda *_: self._reload_preview())
        self.import_note = FlowLabel(); self.import_note.setObjectName("guidanceNote"); layout.addWidget(self.import_note)
        self.preview = QTableWidget(0, 0); self.preview.setEditTriggers(QAbstractItemView.NoEditTriggers); self.preview.setMaximumHeight(170)
        self.preview.setAccessibleName(tr("Aperçu des cinq premières lignes")); self.preview.setSelectionMode(QAbstractItemView.NoSelection); setup_layout.addWidget(self.preview)
        setup_layout.addWidget(FlowLabel(tr("Associez les colonnes de couleur, puis vérifiez les lignes. Les colonnes non choisies ne seront pas importées.")))
        self.mapping_panel = QWidget(); mapping_layout = QVBoxLayout(self.mapping_panel); mapping_layout.setContentsMargins(0, 0, 0, 0)
        self.extra_mapping_toggle = _toggle(tr("Colonnes facultatives"))
        self.extra_mapping = QWidget(); extra_grid = QGridLayout(self.extra_mapping); extra_grid.setContentsMargins(0, 0, 0, 0)
        extra_grid.setColumnStretch(0, 1); extra_grid.setColumnStretch(1, 1)
        self.mapping_grid = QGridLayout(); self.mapping_grid.setHorizontalSpacing(8); self.mapping_combos = {}
        for i, (key, label) in enumerate(COLUMN_ROLES):
            box = _combo(()); box.setAccessibleName(tr("Colonne pour {v0}", v0=tr(label)))
            self.mapping_combos[key] = box
            grid = self.mapping_grid if i < 7 else extra_grid
            index = i if i < 7 else i - 7
            grid.addWidget(_labelled(tr(label), box), index // 3 if i < 7 else index // 2, index % 3 if i < 7 else index % 2)
            box.currentIndexChanged.connect(lambda *_: self._mapping_changed())
        for col in range(3): self.mapping_grid.setColumnStretch(col, 1)
        mapping_layout.addLayout(self.mapping_grid); mapping_layout.addWidget(self.extra_mapping_toggle)
        mapping_layout.addWidget(self.extra_mapping); self.extra_mapping.hide(); self.extra_mapping_toggle.toggled.connect(self.extra_mapping.setVisible)
        setup_layout.addWidget(self.mapping_panel)
        principal_row = QHBoxLayout(); self.principal_label = QLabel(tr("Jeu principal (plusieurs jeux de couleur sont mappés)"))
        self.principal = QComboBox(); self.principal.setFixedHeight(CONTROL_HEIGHT); self.principal.setAccessibleName(tr("Jeu de valeurs principal"))
        principal_row.addWidget(self.principal_label); principal_row.addWidget(self.principal, 1); setup_layout.addLayout(principal_row)
        self.principal_label.hide(); self.principal.hide(); self.principal.currentIndexChanged.connect(lambda *_: self._reset_report())
        defaults = QHBoxLayout()
        self.import_illuminant = _combo(ILLUMINANT_CHOICES); self.import_observer = _combo(OBSERVER_CHOICES)
        defaults.addWidget(_labelled(tr("Éclairage si absent du fichier"), self.import_illuminant), 1)
        defaults.addWidget(_labelled(tr("Observateur si absent du fichier"), self.import_observer), 1); setup_layout.addLayout(defaults)
        layout.addWidget(self.import_setup); self.import_setup.hide()
        for box in (self.import_illuminant, self.import_observer):
            box.currentIndexChanged.connect(lambda *_: self._mapping_changed())
        self.btn_check = QPushButton(tr("Vérifier les lignes")); self.btn_check.setFixedHeight(CONTROL_HEIGHT)
        self.btn_check.clicked.connect(self._check_rows); self.btn_check.setEnabled(False)
        self.partial_confirm = QCheckBox(tr("Enregistrer seulement les lignes valides")); self.partial_confirm.hide(); layout.addWidget(self.partial_confirm)
        self.btn_import = QPushButton(tr("Enregistrer les mesures")); self.btn_import.setObjectName("primary"); self.btn_import.setFixedHeight(CONTROL_HEIGHT)
        self.btn_import.clicked.connect(self._import_rows); self.btn_import.setEnabled(False)
        self.partial_confirm.toggled.connect(lambda *_: self._refresh_import_buttons())
        self.import_summary = FlowLabel(); self.import_summary.setObjectName("guidanceTitle"); layout.addWidget(self.import_summary)
        self.import_errors = QPlainTextEdit(); self.import_errors.setReadOnly(True); self.import_errors.setMaximumHeight(110); self.import_errors.hide()
        self.import_errors.setAccessibleName(tr("Lignes à corriger")); layout.addWidget(self.import_errors)
        layout.addStretch(1)
        return page

    def _choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Choisir un fichier CSV ou TSV"), "", "CSV/TSV (*.csv *.tsv *.txt);;" + tr("Tous les fichiers") + " (*)")
        if not path:
            return
        try:
            data = ci.read_local_file(path)   # size checked before and during the read
        except (OSError, ValueError) as exc:
            self.import_note.setText(_error(exc)); return
        self.import_setup.show(); self.btn_check.setEnabled(True)
        self._import_state = {"path": path, "data": data, "sha256": hashlib.sha256(data).hexdigest(), "records": []}
        self.file_label.setText(tr("{v0} · {v1} Kio", v0=os.path.basename(path), v1=max(1, len(data) // 1024)))
        self.encoding.setCurrentIndex(0)
        self._reload_preview(auto=True)

    def _reset_report(self):
        self.import_report = None; self.import_summary.clear(); self.import_errors.hide(); self.partial_confirm.hide(); self.btn_import.setEnabled(False)

    def _reload_preview(self, *_, auto=False):
        state = self._import_state
        if not state:
            return
        self._reset_report()
        try:
            text, used = ci.decode_text(state["data"], self.encoding.currentData())
        except ValueError as exc:
            self.import_note.setText(_error(exc)); self.preview.setRowCount(0); self.preview.setColumnCount(0); state["records"] = []
            self._fill_mapping([]); return
        candidates = ci.guess_delimiters(text)
        if auto:
            self.delimiter.blockSignals(True); self.delimiter.setCurrentIndex(max(0, self.delimiter.findData(candidates[0]))); self.delimiter.blockSignals(False)
            self.decimal.blockSignals(True); self.decimal.setCurrentIndex(1 if candidates[0] == ";" else 0); self.decimal.blockSignals(False)
        try:
            records = ci.read_records(text, self.delimiter.currentData())
        except ValueError as exc:
            self.import_note.setText(_error(exc)); state["records"] = []; self._fill_mapping([]); return
        if not records:
            self.import_note.setText(tr("Fichier vide.")); state["records"] = []; self._fill_mapping([]); return
        header = [cell.strip() for cell in records[0]]; body = records[1:]
        state["header"], state["records"], state["encoding"] = header, body, used
        notes = [tr("Encodage {v0} · {v1} enregistrements", v0=used, v1=len(body))]
        if len(candidates) > 1:
            notes.append(tr("Plusieurs séparateurs plausibles ({v0}) : confirmez le bon.", v0=", ".join(tr(ci.DELIMITERS[c]) for c in candidates)))
        self.import_note.setText(" · ".join(notes))
        self.preview.setColumnCount(len(header)); self.preview.setRowCount(min(5, len(body)))
        self.preview.setHorizontalHeaderLabels([f"{i + 1}: {name}" for i, name in enumerate(header)])
        for r, row in enumerate(body[:5]):
            for c in range(len(header)):
                item = QTableWidgetItem(row[c] if c < len(row) else ""); item.setToolTip(row[c] if c < len(row) else "")
                self.preview.setItem(r, c, item)
        self.preview.resizeColumnsToContents()
        self._fill_mapping(header)

    def _fill_mapping(self, header):
        proposal = ci.propose_mapping(header) if header else {"mapping": {}, "duplicates": {}, "unmapped": []}
        for key, box in self.mapping_combos.items():
            box.blockSignals(True); box.clear(); box.addItem(tr("— non importée —"), None)
            for i, name in enumerate(header):
                box.addItem(f"{i + 1}: {name}" if name else tr("{v0}: (sans titre)", v0=i + 1), i)
            chosen = proposal["mapping"].get(key)
            box.setCurrentIndex(max(0, box.findData(chosen)) if chosen is not None else 0); box.blockSignals(False)
        self.extra_mapping_toggle.setChecked(any(self.mapping_combos[key].currentData() is not None for key, _ in COLUMN_ROLES[7:]))
        if proposal["duplicates"]:
            labels = {key: label for key, label in COLUMN_ROLES}
            self.import_note.setText(self.import_note.text() + " · " + tr("Colonnes en double, à choisir vous-même : {v0}",
                                     v0=", ".join(f"{tr(labels.get(k, k))} ({', '.join(str(i + 1) for i in ids)})" for k, ids in proposal["duplicates"].items())))
        self._mapping_changed()

    def _mapping_changed(self):
        self._reset_report()
        spaces = ci.mapped_spaces(self._current_mapping())
        current = self.principal.currentData()
        self.principal.blockSignals(True); self.principal.clear()
        if len(spaces) > 1:
            self.principal.addItem(tr("— à choisir —"), None)
            for space in spaces:
                self.principal.addItem(tr(SPACE_LABELS[space]), space)
            self.principal.setCurrentIndex(max(0, self.principal.findData(current)) if current in spaces else 0)
        self.principal.blockSignals(False)
        self.principal_label.setVisible(len(spaces) > 1); self.principal.setVisible(len(spaces) > 1)

    def _current_mapping(self):
        return {key: box.currentData() for key, box in self.mapping_combos.items() if box.currentData() is not None}

    def _check_rows(self):
        state = self._import_state
        if not state or not state.get("records"):
            self.import_summary.setText(tr("Choisissez d’abord un fichier lisible.")); return
        mapping = self._current_mapping()
        spaces = ci.mapped_spaces(mapping)
        principal = self.principal.currentData() if len(spaces) > 1 else None
        if len(spaces) > 1 and principal is None:
            self.import_summary.setText(tr("Plusieurs jeux de couleur sont mappés ({v0}) : choisissez le jeu principal.", v0=", ".join(tr(SPACE_LABELS[s]) for s in spaces))); return
        defaults = {"illuminant": self.import_illuminant.currentData(), "observer": self.import_observer.currentData()}
        if defaults["illuminant"] == "other":
            defaults["illuminant_note"] = tr("Autre éclairage (fichier)")
        try:
            report = ci.validate_rows(state["records"], mapping, decimal=self.decimal.currentData(), file_name=os.path.basename(state["path"]),
                                      file_sha256=state["sha256"], default_conditions=defaults, name_prefix=os.path.basename(state["path"]) + " #",
                                      principal=principal)
        except ValueError as exc:
            self.import_summary.setText(_error(exc)); return
        self._load_registry()
        existing = ci.registry_duplicates(report["valid"], self.registry.measurements)
        report["similar"], report["reimported"] = existing["similar"], existing["reimported"]
        self.import_report = report
        duplicates = len(report["duplicates"]) + len(existing["similar"]) + len(existing["reimported"])
        self.import_summary.setText(tr("{v0} valides / {v1} à corriger / {v2} doublons potentiels", v0=len(report["valid"]), v1=len(report["errors"]), v2=duplicates))
        lines = [tr("Enregistrement {v0} : {v1}", v0=number, v1=_error(error)) for number, error in report["error_items"][:200]]
        lines += [tr("Enregistrement {v0}, avertissement : {v1}", v0=number, v1=_error(warning)) for number, warning in report["warning_items"][:200]]
        lines += [tr("Enregistrement {v0} répète l’enregistrement {v1} (mêmes valeurs et conditions).", v0=a, v1=b) for a, b in report["duplicates"][:50]]
        if existing["reimported"]:
            lines.append(tr("Déjà importé exactement (même fichier et numéro) : {v0} enregistrement(s).", v0=len(existing["reimported"])))
        if existing["similar"]:
            lines.append(tr("Valeurs identiques à des mesures déjà enregistrées : {v0}. Rien n’est fusionné ni ignoré automatiquement.", v0=len(existing["similar"])))
        if principal:
            lines.insert(0, tr("Jeu principal : {v0} ; les autres jeux mappés sont conservés en alternatives.", v0=tr(SPACE_LABELS[principal])))
        self.import_errors.setPlainText("\n".join(lines)); self.import_errors.setVisible(bool(lines))
        self.partial_confirm.setChecked(False); self.partial_confirm.setVisible(bool(report["errors"]) and bool(report["valid"]))
        self._refresh_import_buttons()

    def _refresh_import_buttons(self):
        report = self.import_report
        ok = bool(report) and bool(report["valid"]) and (not report["errors"] or self.partial_confirm.isChecked())
        self.btn_import.setEnabled(ok)
        if report:
            self.btn_import.setText(tr("Enregistrer {v0} mesure(s)", v0=len(report["valid"])))

    def _import_rows(self):
        """The only way a CSV batch is written: explicit, atomic, from the checked report."""
        report = self.import_report
        if not report or not report["valid"] or (report["errors"] and not self.partial_confirm.isChecked()):
            return
        try:
            identifiers = self.registry.create_many([v["measurement"] for v in report["valid"]])
        except (db_io.DatabaseError, ms.RegistryError, cm.MeasurementError) as exc:
            self._say(tr("Aucune mesure enregistrée : {v0}", v0=_error(exc)), error=True); return
        self._say(tr("{v0} mesure(s) enregistrée(s) dans le registre.", v0=len(identifiers)))
        self._reset_report()
        self.registry_changed.emit(); self._refresh_saved(); self.tabs.setCurrentIndex(3)

    # ── Enregistrées ─────────────────────────────────────────────────────
    def _build_saved_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(8, 12, 8, 12); layout.setSpacing(10)
        self.registry_info = FlowLabel(); self.registry_info.setObjectName("guidanceNote"); layout.addWidget(self.registry_info)
        self.registry_problem = FlowLabel(); self.registry_problem.setObjectName("guidanceCaution"); self.registry_problem.hide(); layout.addWidget(self.registry_problem)
        self.saved_list = QListWidget(); self.saved_list.setObjectName("facets"); self.saved_list.setAccessibleName(tr("Mesures enregistrées"))
        self.saved_list.setWordWrap(True)
        self.saved_list.itemSelectionChanged.connect(self._saved_selection_changed); layout.addWidget(self.saved_list, 1)
        self.saved_detail = FlowLabel(); self.saved_detail.setObjectName("guidanceNote"); layout.addWidget(self.saved_detail)
        grid = QGridLayout(); grid.setSpacing(6)
        self.btn_use = QPushButton(tr("Utiliser comme cible")); self.btn_use.clicked.connect(self._use_saved)
        self.btn_rename = QPushButton(tr("Renommer…")); self.btn_rename.clicked.connect(self._rename_saved)
        self.btn_link = QPushButton(tr("Lier à la fiche sélectionnée…")); self.btn_link.clicked.connect(self._link_saved)
        self.btn_detach = QPushButton(tr("Détacher")); self.btn_detach.clicked.connect(self._detach_saved)
        self.btn_delete = QPushButton(tr("Supprimer…")); self.btn_delete.clicked.connect(self._delete_saved)
        self.btn_restore = QPushButton(tr("Restaurer la sauvegarde du registre…")); self.btn_restore.clicked.connect(self._restore_registry)
        self.btn_use.hide()
        self.btn_use.setParent(page)
        self.btn_restore.setText(tr("Restaurer le registre…"))
        for i, button in enumerate((self.btn_rename, self.btn_link, self.btn_detach, self.btn_delete, self.btn_restore)):
            button.setFixedHeight(CONTROL_HEIGHT); grid.addWidget(button, i // 2, i % 2)
        grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        return page

    def _load_registry(self):
        try:
            self.registry.load()
        except db_io.DatabaseError as exc:
            self._say(tr("Registre illisible : {v0}", v0=_error(exc)), error=True)

    def _refresh_saved(self):
        current = self._selected_id()
        self.saved_list.blockSignals(True); self.saved_list.clear()
        db = self._db()
        for identifier, measurement in self.registry.items():
            context = self.registry.resolve_association(measurement, db)
            link = {"none": "", "resolved": tr(" · lié à {v0}", v0=context.get("sku")), "unresolved": tr(" · lien non résolu ({v0})", v0=context.get("sku"))}[context["state"]]
            level = cm.comparison_policy(measurement)["level"]
            text = f"{measurement['name']}\n{cm.summary_values(measurement)} · {cm.describe_conditions(measurement, tr)} · {tr(LEVEL_LABELS[level])}{link}"
            item = QListWidgetItem(text); item.setData(Qt.UserRole, identifier); item.setToolTip(text); self.saved_list.addItem(item)
            if identifier == current:
                self.saved_list.setCurrentItem(item)
        self.saved_list.blockSignals(False)
        count = len(self.registry.measurements)
        size = self.registry.serialized_size() if count else 0
        self.registry_info.setText(tr("{v0} mesure(s) · registre : {v1}", v0=count, v1=self.registry.path.name) + (f" · {max(1, size // 1024)} Kio" if count else ""))
        self.registry_info.setToolTip(str(self.registry.path))
        problem = self.registry.load_error
        if problem is not None:
            backup = self.registry.backup_path()
            self.registry_problem.setText(tr("Registre illisible : {v0}", v0=_error(problem)) + " " +
                                          (tr("Une sauvegarde existe ({v0}) : « Restaurer » la remet en place et conserve le fichier actuel à côté, tel quel.", v0=backup.name)
                                           if backup.is_file() else tr("Aucune sauvegarde à restaurer ; le fichier n’est pas modifié.")))
        self.registry_problem.setVisible(problem is not None)
        self._saved_selection_changed()

    def _selected_id(self):
        items = self.saved_list.selectedItems() if hasattr(self, "saved_list") else []
        return items[0].data(Qt.UserRole) if items else None

    def _saved_selection_changed(self, *_):
        identifier = self._selected_id(); measurement = self.registry.get(identifier) if identifier else None
        for button in (self.btn_use, self.btn_rename, self.btn_link, self.btn_detach, self.btn_delete):
            button.setEnabled(measurement is not None)
        self.btn_restore.setEnabled(self.registry.backup_path().is_file())
        if measurement is None:
            self.saved_detail.clear(); self._set_draft("saved", None); return
        context = self.registry.resolve_association(measurement, self._db())
        provenance, conditions, sample = measurement["provenance"], measurement["conditions"], measurement["sample"]
        parts = [tr("Créée le {v0}", v0=measurement["created_at"]), tr("Méthode : {v0}", v0=tr(cm.METHOD_LABELS.get(provenance["method"], provenance["method"])))]
        if measurement.get("measured_at"):
            parts.append(tr("Mesurée : {v0}", v0=measurement["measured_at"]))
        if provenance.get("device_model") or provenance.get("device_manufacturer"):
            parts.append(tr("Appareil : {v0}", v0=" ".join(p for p in (provenance.get("device_manufacturer"), provenance.get("device_model")) if p)))
        if provenance.get("file_name"):
            parts.append(tr("Fichier : {v0}, enregistrement {v1}", v0=provenance["file_name"], v1=provenance.get("record_number")))
        documented = [f"{tr(label)} {conditions[key]}" for key, label in (("geometry", "Géométrie"), ("specular", "SCI/SCE"), ("aperture", "Ouverture"),
                                                                            ("calibration", "Calibration"), ("profile_note", "Profil")) if conditions.get(key)]
        if documented:
            parts.append(tr("Conditions : {v0}", v0=", ".join(documented)))
        described = [f"{tr(label)} {sample[key]}" for key, label in (("material", "Matériau"), ("finish", "Finition"), ("thickness", "Épaisseur"),
                                                                       ("backing", "Fond"), ("surface_note", "Surface")) if sample.get(key)]
        if sample.get("type") != "unknown" or described:
            parts.append(tr("Échantillon : {v0}", v0=", ".join([tr(dict(SAMPLE_CHOICES)[sample["type"]])] + described)))
        if context["state"] == "resolved":
            parts.append(tr("Liée à : {v0}", v0=context["label"]))
        elif context["state"] == "unresolved":
            parts.append(tr("Lien conservé vers {v0}, référence absente du catalogue actuel.", v0=context["sku"]))
        self.btn_detach.setEnabled(context["state"] != "none")
        self.saved_detail.setText(" · ".join(parts))
        self._set_draft("saved", {"original": measurement["original"], "conditions": conditions, "method": provenance["method"], "saved": True}, identifier)

    def _use_saved(self):
        if self._selected_id():
            self._search_draft()

    def _rename_saved(self):
        identifier = self._selected_id()
        if not identifier:
            return
        name, ok = QInputDialog.getText(self, tr("Renommer la mesure"), tr("Nouveau nom :"), text=self.registry.get(identifier)["name"])
        if not ok or not name.strip():
            return
        try:
            self.registry.rename(identifier, name.strip()[:cm.LIMITS["name"]])
        except (db_io.DatabaseError, ms.RegistryError, cm.MeasurementError) as exc:
            self._say(tr("Registre non modifié : {v0}", v0=_error(exc)), error=True); return
        self.registry_changed.emit(); self._refresh_saved()

    def _link_saved(self):
        identifier = self._selected_id(); sku = self._current_sku()
        if not identifier:
            return
        if not sku:
            self._say(tr("Sélectionnez d’abord une fiche dans le catalogue."), error=True); return
        db = self._db(); entry = (db.get("_skus") or {}).get(sku)
        if entry is None:
            self._say(tr("La fiche sélectionnée n’a pas de référence exacte."), error=True); return
        product = (db.get("_products") or {}).get(entry.get("product"), {})
        label = f"{product.get('display_name') or entry.get('product', '')} · {entry.get('color_name', '')} ({sku})"
        if QMessageBox.question(self, tr("Lier la mesure"), tr("Lier cette mesure à la référence exacte {v0} ?\nLa couleur du catalogue et les exports ne changent pas.", v0=label),
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            self.registry.associate(identifier, sku)
        except (db_io.DatabaseError, ms.RegistryError, cm.MeasurementError) as exc:
            self._say(tr("Registre non modifié : {v0}", v0=_error(exc)), error=True); return
        self.registry_changed.emit(); self._refresh_saved(); self._say(tr("Mesure liée à {v0}.", v0=sku))

    def _detach_saved(self):
        identifier = self._selected_id()
        if not identifier:
            return
        try:
            self.registry.detach(identifier)
        except (db_io.DatabaseError, ms.RegistryError, cm.MeasurementError) as exc:
            self._say(tr("Registre non modifié : {v0}", v0=_error(exc)), error=True); return
        self.registry_changed.emit(); self._refresh_saved()

    def _delete_saved(self):
        identifier = self._selected_id()
        if not identifier:
            return
        name = self.registry.get(identifier)["name"]
        if QMessageBox.question(self, tr("Supprimer la mesure"), tr("Supprimer « {v0} » du registre ? La version précédente du registre est conservée en sauvegarde.", v0=name),
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            self.registry.delete(identifier)
        except (db_io.DatabaseError, ms.RegistryError) as exc:
            self._say(tr("Registre non modifié : {v0}", v0=_error(exc)), error=True); return
        self.deleted_identifier = identifier
        for key, saved in self._identifiers.items():
            if saved == identifier:
                self._set_draft(key, None)
        self.registry_changed.emit(); self._refresh_saved(); self._say(tr("Mesure supprimée. Sauvegarde : {v0}", v0=self.registry.backup_path().name))

    def _restore_registry(self):
        """Explicit restoration, also after an unreadable registry: the current file is kept next to it, whatever its state."""
        backup = self.registry.backup_path()
        if not backup.is_file():
            self._say(tr("Aucune sauvegarde du registre à restaurer."), error=True); return
        if QMessageBox.question(self, tr("Restaurer le registre"), tr("Remplacer le registre des mesures par sa sauvegarde {v0} ? Le fichier actuel est conservé à côté.", v0=backup.name),
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            self.registry.restore(backup)
        except (db_io.DatabaseError, ms.RegistryError) as exc:
            self._say(tr("Registre non restauré : {v0}", v0=_error(exc)), error=True); self._refresh_saved(); return
        for key in self._identifiers:
            if self._identifiers[key] and self.registry.get(self._identifiers[key]) is None:
                self._set_draft(key, None)
        self.registry_changed.emit(); self._refresh_saved(); self._say(tr("Registre restauré depuis {v0}.", v0=backup.name))

    # ── draft → policy → actions ─────────────────────────────────────────
    def _draft_measurement(self, *, name=None):
        """The measurement the visible entry would save or search; None when that entry has no confirmed draft."""
        draft, identifier = self.draft, self.draft_identifier
        if not draft:
            return None
        if draft.get("saved") and identifier:
            return self.registry.get(identifier)
        name = name or (self.name_edit.text().strip() if draft["method"] == "manual" else "") or self._auto_name(draft)
        provenance = {"method": draft["method"]}
        sample = {"type": "unknown"}
        role, measured_at = "target", None
        if draft["method"] == "manual":
            provenance.update(device_manufacturer=self.device_manufacturer.text().strip() or None, device_model=self.device_model.text().strip() or None,
                              operator_note=self.note_edit.text().strip() or None)
            sample = {"type": self.sample_type.currentData()}
            for key, edit in (("material", self.sample_material), ("finish", self.sample_finish), ("thickness", self.sample_thickness),
                              ("backing", self.sample_backing), ("surface_note", self.sample_surface_note)):
                if edit.text().strip():
                    sample[key] = edit.text().strip()
            role = self.role.currentData(); measured_at = self.measured_at.text().strip() or None
        return cm.new_measurement(draft["original"], name=name, role=role, conditions=draft["conditions"], provenance=provenance, sample=sample, measured_at=measured_at)

    def _auto_name(self, draft):
        original = draft["original"]
        if original["space"] == "sRGB_HEX":
            return tr("Couleur #{v0}", v0=original["components"]["hex"])
        if original["space"] == "sRGB_RGB8":
            c = original["components"]; return tr("Couleur RGB {v0}", v0=f"{c['r']}, {c['g']}, {c['b']}")
        c = original["components"]; return tr("Mesure Lab {v0}", v0=f"{c['L']:g} / {c['a']:g} / {c['b']:g}")

    def _refresh_policy(self):
        if not hasattr(self, "level_tile"):
            return  # pages are built before the level tile and the actions
        importing = self.tabs.currentIndex() == 2
        saved = self.tabs.currentIndex() == 3
        self.btn_check.setVisible(importing); self.btn_import.setVisible(importing)
        self.btn_save.setVisible(not importing and not saved); self.btn_search.setVisible(not importing)
        self.level_tile.setVisible(not importing)
        try:
            measurement = self._draft_measurement()
        except cm.MeasurementError as exc:
            measurement = None; self.level_tile.note.setText(_error(exc))
        hex_value = cm.hex_of(measurement) if measurement else None
        self.swatch.setVisible(hex_value is not None)   # never a preview of a Lab value
        self.swatch.setStyleSheet(f"QFrame#measurementSwatch {{ background:#{hex_value}; border:2px solid #89949c; border-radius:6px; }}" if hex_value else "")
        self.swatch.setToolTip("#" + hex_value if hex_value else "")
        if measurement is None:
            self.level_tile.value.setText("—"); self.level_tile.setProperty("tone", "neutral")
            if self.draft is None:
                self.level_tile.note.setText(tr("Saisissez, collez ou importez des valeurs, ou choisissez une mesure enregistrée."))
            self.btn_save.setEnabled(False); self.btn_search.setEnabled(False)
        else:
            policy = cm.comparison_policy(measurement)
            self.level_tile.value.setText(tr(LEVEL_LABELS[policy["level"]]))
            self.level_tile.note.setText(tr(REASONS[policy["reason"]]) + (f"\n{tr('Référentiel : {v0}', v0=tr(policy['reference']))}" if policy.get("reference") else ""))
            self.level_tile.setProperty("tone", "colour" if policy["level"] == "indicative" else "attention")
            self.btn_save.setEnabled(not self.draft.get("saved")); self.btn_search.setEnabled(policy["level"] == "indicative")
        self.level_tile.style().unpolish(self.level_tile); self.level_tile.style().polish(self.level_tile)
        self.level_tile.setAccessibleDescription(self.level_tile.value.text() + ". " + self.level_tile.note.text())
        self._fit_level_tile()

    def _fit_level_tile(self):
        """The tile sits outside the scrolling pages: reserve the height its wrapped text needs."""
        if not hasattr(self, "level_tile"):
            return
        width = max(280, self.level_tile.width() - 24)
        height = sum(label.heightForWidth(width) for label in (self.level_tile.title, self.level_tile.value, self.level_tile.note)) + 20 + 8
        self.level_tile.setMinimumHeight(height)

    def resizeEvent(self, event):
        super().resizeEvent(event); self._fit_level_tile()

    def _save_draft(self):
        key = self._current_key()
        try:
            measurement = self._draft_measurement()
            if measurement is None or key is None:
                return
            identifier = self.registry.create(measurement)
        except (db_io.DatabaseError, ms.RegistryError, cm.MeasurementError) as exc:
            self._say(tr("Mesure non enregistrée : {v0}", v0=_error(exc)), error=True); return
        self._set_draft(key, dict(self.draft, saved=True), identifier)
        self.registry_changed.emit(); self._refresh_saved()
        for i in range(self.saved_list.count()):
            if self.saved_list.item(i).data(Qt.UserRole) == identifier:
                self.saved_list.setCurrentRow(i)
        self._say(tr("Mesure « {v0} » enregistrée.", v0=measurement["name"])); self._refresh_policy()

    def _search_draft(self):
        try:
            measurement = self._draft_measurement()
            if measurement is None:
                return
            target = ct.target_from_measurement(measurement, self.draft_identifier)
        except ct.TargetBlocked as exc:
            self._say(tr(REASONS.get(exc.policy.get("reason", ""), "Conditions insuffisantes")), error=True); return
        except cm.MeasurementError as exc:
            self._say(_error(exc), error=True); return
        self.search_requested.emit(target); self.accept()

    def _say(self, text, error=False):
        self.feedback.setObjectName("guidanceCaution" if error else "guidanceNote"); self.feedback.setText(text)
        self.feedback.style().unpolish(self.feedback); self.feedback.style().polish(self.feedback)

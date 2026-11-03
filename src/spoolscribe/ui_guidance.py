"""Readable explanations of existing colour ranking and NFC calculations.

Presentation only: no catalogue edits, compatibility decisions or encoders here.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QProgressBar, QScrollArea, QSizePolicy, QTabWidget, QVBoxLayout, QWidget)

from .i18n import tr
from .ui_surfaces import ReadingTabs, fit_dialog
from .ui_widgets import CONTROL_HEIGHT


class FlowLabel(QLabel):
    """Native height-for-width text, without retaining an earlier narrow height."""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setWordWrap(True); self.setTextFormat(Qt.PlainText)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)


class InfoTile(QFrame):
    def __init__(self, title, note="", *, tone="neutral", parent=None):
        super().__init__(parent)
        self.setObjectName("guidanceTile"); self.setProperty("tone", tone)
        layout = QVBoxLayout(self); layout.setContentsMargins(12, 10, 12, 10); layout.setSpacing(4)
        self.title = FlowLabel(title); self.title.setObjectName("guidanceTitle")
        self.value = FlowLabel(); self.value.setObjectName("guidanceValue")
        self.note = FlowLabel(note); self.note.setObjectName("guidanceNote")
        layout.addWidget(self.title); layout.addWidget(self.value); layout.addWidget(self.note)
        self.note.setVisible(bool(note))


class GuidanceDialog(QDialog):
    def __init__(self, title, parent):
        super().__init__(parent)
        self.setWindowTitle(title); self.resize(680, 620)
        self.setMinimumSize(400, 380)
        self.setWindowModality(Qt.NonModal)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        layout = QVBoxLayout(self); layout.setContentsMargins(16, 16, 16, 16); layout.setSpacing(12)
        self.heading = FlowLabel(title); self.heading.setObjectName("guidanceHeading"); layout.addWidget(self.heading)
        self.tabs = ReadingTabs(); layout.addWidget(self.tabs, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText(tr("Fermer"))
        buttons.button(QDialogButtonBox.Close).setFixedHeight(CONTROL_HEIGHT)
        buttons.rejected.connect(self.close); layout.addWidget(buttons)

    def showEvent(self,event):
        super().showEvent(event);fit_dialog(self,preferred_width=700)

    def page(self, title):
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget(); content.setMinimumWidth(0)
        layout = QVBoxLayout(content); layout.setContentsMargins(8, 12, 8, 12); layout.setSpacing(12)
        scroll.setWidget(content); self.tabs.addTab(scroll, title)
        return layout


class ColourGuidance(GuidanceDialog):
    def __init__(self, parent):
        super().__init__(tr("Comparer les couleurs"), parent)
        overview = self.page(tr("Les résultats"))
        self.target = FlowLabel(); self.target.setObjectName("guidanceTitle"); overview.addWidget(self.target)
        self.swatch = QFrame(); self.swatch.setFixedHeight(20); overview.addWidget(self.swatch)
        summary = QHBoxLayout(); summary.setSpacing(8)
        self.comparable = InfoTile(tr("Couleurs comparables"), tone="colour")
        self.excluded = InfoTile(tr("Fiches écartées"))
        summary.addWidget(self.comparable, 1); summary.addWidget(self.excluded, 1); overview.addLayout(summary)
        overview.addWidget(FlowLabel(tr("Vos filtres de fabricant, matière et favoris restent appliqués.")))
        overview.addWidget(FlowLabel(tr("Pourquoi certaines fiches sont-elles écartées ?")))
        grid = QGridLayout(); grid.setSpacing(8); self.reasons = {}
        definitions = (
            ("unknown", tr("Couleur manquante"), tr("La source ne donne pas de couleur utilisable.")),
            ("conflict", tr("Teinte à confirmer"), tr("Les sources proposent plusieurs teintes pour la même fiche.")),
            ("translucent", tr("Filament transparent"), tr("Le fond et la lumière changent sa couleur apparente.")),
            ("multicolour", tr("Plusieurs couleurs"), tr("Une seule pastille ne représente pas ce filament.")))
        for i, (key, title, note) in enumerate(definitions):
            tile = InfoTile(title, note); grid.addWidget(tile, i // 2, i % 2); self.reasons[key] = tile
        grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 1); overview.addLayout(grid)
        self.scope = FlowLabel(); overview.addWidget(self.scope)
        self.effects = FlowLabel(); self.effects.setObjectName("guidanceCaution"); overview.addWidget(self.effects)
        overview.addWidget(FlowLabel(tr("Une couleur proche à l’écran peut donner un résultat différent une fois imprimée.")))
        overview.addStretch(1)
        method = self.page(tr("La méthode"))
        for title, note in (
            (tr("1. Une couleur de référence"), tr("Vous choisissez une pastille ou saisissez son code couleur.")),
            (tr("2. Un classement visuel"), tr("Les couleurs déclarées sont classées de la plus proche à la plus éloignée. Un écart plus petit indique une couleur d’écran plus proche.")),
            (tr("3. Une vérification de la bobine"), tr("L’écran ne mesure ni la brillance, ni la transparence, ni le rendu après impression."))):
            tile = InfoTile(title, note, tone="colour"); tile.value.hide(); method.addWidget(tile)
        method.addWidget(FlowLabel(tr("Calcul utilisé : CIEDE2000 (ΔE00), sur les codes HEX déclarés par les sources. Il ne s’agit pas d’une mesure physique du filament.")))
        method.addWidget(FlowLabel(tr('Maximum 3 signifie ΔE ≤ 3, sans marge ni pourcentage. L’écran arrondit au centième supérieur : un dépassement ne devient pas artificiellement 3,00. Le filtre utilise le score calculé, à six décimales.')))
        method.addStretch(1)

    def update_result(self, target, total, excluded, effects, limit=None, outside_limit=0):
        self.target.setText(tr("Couleur comparée : #{v0}", v0=target))
        self.swatch.setStyleSheet(f"background:#{target}; border-radius:5px;")
        self.scope.setText(tr("{v0} couleurs affichées · {v1} au-delà de la limite", v0=total, v1=outside_limit)
                           + (f" (ΔE {limit:g})" if limit is not None else ""))
        self.comparable.value.setText(str(total)); self.excluded.value.setText(str(sum(excluded.values())))
        for key, tile in self.reasons.items():
            tile.value.setText(str(excluded.get(key, 0)))
        self.effects.setText(tr("{v0} filaments à effet : comparez aussi leur aspect réel (soie, métal, lueur…).", v0=effects))
        self.effects.setVisible(effects > 0)


class ExportGuidance(GuidanceDialog):
    def __init__(self, parent):
        super().__init__(tr("De l’imprimante à l’étiquette"), parent)
        overview = self.page(tr("Votre parcours"))
        self.destination = InfoTile(tr("1. Le matériel qui lira l’étiquette"), tone="hardware")
        overview.addWidget(self.destination)
        row = QHBoxLayout(); row.setSpacing(8)
        self.format_tile = InfoTile(tr("Format du fichier"), tone="hardware")
        self.tag_tile = InfoTile(tr("Étiquette choisie"), tone="hardware")
        row.addWidget(self.format_tile, 1); row.addWidget(self.tag_tile, 1); overview.addLayout(row)
        self.readiness = InfoTile(tr("2. Préparer le fichier"), tone="ready"); overview.addWidget(self.readiness)
        self.memory = QProgressBar(); self.memory.setFixedHeight(8); self.memory.setTextVisible(False)
        self.memory.setAccessibleName(tr("Place disponible sur l’étiquette")); overview.addWidget(self.memory)
        tile = InfoTile(tr("3. Écrire, puis relire"),
            tr("Exportez le fichier, ouvrez-le dans votre application NFC, puis écrivez l’étiquette. Relisez-la avant de l’utiliser sur votre imprimante."), tone="hardware")
        tile.value.hide(); overview.addWidget(tile)
        overview.addWidget(FlowLabel(tr("SpoolScribe prépare le fichier. Il n’écrit pas l’étiquette et ne confirme pas sa lecture par votre matériel.")))
        overview.addStretch(1)
        technical = self.page(tr("Informations techniques"))
        self.configuration = FlowLabel(); technical.addWidget(self.configuration)
        self.profile = FlowLabel(); technical.addWidget(self.profile)
        grid = QGridLayout(); grid.setSpacing(8); self.metrics = {}
        for i, (key, title, note) in enumerate((
            ("payload", tr("Contenu du filament"), tr("Données seules, avant leur emballage NFC.")),
            ("ndef", tr("Enregistrement NFC"), tr("Contenu et en-tête nécessaires au lecteur.")),
            ("occupied", tr("Place occupée"), tr("Total écrit sur l’étiquette, hors réserve.")),
            ("reserved", tr("Réserve choisie"), tr("Place gardée pour le logiciel d’écriture.")),
            ("remaining", tr("Place disponible"), tr("Ce qui reste après le fichier et la réserve.")),
            ("capacity", tr("Capacité utilisable"), tr("Mémoire disponible pour ce type d’étiquette.")))):
            tile = InfoTile(title, note); grid.addWidget(tile, i // 2, i % 2); self.metrics[key] = tile
        grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 1); technical.addLayout(grid)
        technical.addWidget(FlowLabel(tr("Diagnostic du calcul")))
        self.diagnostic = FlowLabel(); self.diagnostic.setTextInteractionFlags(Qt.TextSelectableByMouse)
        technical.addWidget(self.diagnostic); technical.addStretch(1)

    def update_context(self, context):
        self.destination.value.setText(context.get("printer", ""))
        self.destination.note.setText(context.get("effect", "")); self.destination.note.show()
        self.format_tile.value.setText(context.get("format", ""))
        self.format_tile.note.setText(context.get("writer", "")); self.format_tile.note.setVisible(bool(context.get("writer")))
        self.tag_tile.value.setText(context.get("tag", ""))
        self.readiness.value.setText(context.get("reason", ""))
        self.readiness.setProperty("tone", "ready" if context.get("state") == "ready" else "attention")
        self.readiness.style().unpolish(self.readiness); self.readiness.style().polish(self.readiness)
        budget = context.get("budget") or {}
        self.memory.setVisible(bool(budget))
        if budget:
            self.memory.setRange(0, budget["capacity"]); self.memory.setValue(budget["remaining"])
        self.configuration.setText(tr("Configuration : {v0}", v0=context.get("configuration", "")))
        self.profile.setText(context.get("technical_format", ""))
        self.profile.setVisible(bool(context.get("technical_format")))
        for key, tile in self.metrics.items():
            tile.value.setText(tr("{v0} octets", v0=budget[key]) if key in budget else "—")
        self.diagnostic.setText(context.get("diagnostic") or tr("Aucun blocage détecté par le calcul."))

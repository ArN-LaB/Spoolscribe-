"""Detail card workflow: in-place personal draft, value comparison, export state, colour proximity.

Everything here is presentation and orchestration. Persistence stays in
``core.save_personal_filament``; export bytes stay in the existing encoders.
"""
import hashlib
import os
import re
import sys

from PySide6.QtCore import Qt, QEvent, QItemSelectionModel, QTimer
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QColorDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton,
    QSizePolicy, QToolButton, QVBoxLayout, QWidget)
from PySide6.QtGui import QColor

from . import colour_distance
from . import colour_measurements
from . import colour_targets
from . import core
from . import printer_profiles
from .i18n import tr
from .printer_profiles import PROFILES
from .ui_widgets import WrapLabel, CONTROL_HEIGHT, CARD_MARGINS, ReflowRow, printer_visual
from .ui_guidance import ColourGuidance, ExportGuidance, FlowLabel
from .ui_reading import CardGrid, ParameterCard

FIELD_LABELS = (("min_temp", "Buse min. °C"), ("max_temp", "Buse max. °C"),
                ("bed_min_temp", "Plateau min. °C"), ("bed_max_temp", "Plateau max. °C"),
                ("diameter", "Diamètre mm"), ("density", "Densité g/cm³"), ("hex", "Couleur HEX"))
PAIRS = (("min_temp", "max_temp", "Plage buse min./max. inversée."),
         ("bed_min_temp", "bed_max_temp", "Plage plateau min./max. inversée."))


def _text(value, key):
    if value is None:
        return ""
    if key == "hex":
        return str(value).upper()
    if isinstance(value, float) and value.is_integer() and key.endswith("temp"):
        value = int(value)
    return f"{value:g}" if isinstance(value, float) else str(value)


def _shown(value, key):
    text = _text(value, key)
    return ("#" + text if key == "hex" else text) if text else "—"


class DetailUx:
    # ── Construction ────────────────────────────────────────────────────
    def _build_draft_editor(self, layout):
        """In-card editor replacing the former modal dialog; hidden until « Modifier… »."""
        self._draft = None
        self.draft_editor = QFrame(); self.draft_editor.setObjectName("draftEditor")
        box = QVBoxLayout(self.draft_editor); box.setContentsMargins(12, 10, 12, 10); box.setSpacing(8)
        self.draft_badge = QLabel(tr("Brouillon non enregistré")); self.draft_badge.setObjectName("draftBadge")
        box.addWidget(self.draft_badge)
        # Identity stays readable even when the hero has scrolled out of view.
        self.draft_identity = WrapLabel(); self.draft_identity.setObjectName("fieldvalue"); box.addWidget(self.draft_identity)
        self.draft_note = WrapLabel(tr("Enregistrez une copie personnelle de cette bobine. La référence source reste intacte. Valeur inconnue : laissez la case vide."))
        self.draft_note.setObjectName("comparisonNote"); box.addWidget(self.draft_note)
        form = QGridLayout(); form.setContentsMargins(0, 0, 0, 0); form.setHorizontalSpacing(8); form.setVerticalSpacing(6)
        form.setColumnStretch(1, 1)
        self.draft_suffix = QLineEdit(); self.draft_suffix.setObjectName("personal_suffix"); self.draft_suffix.setFixedHeight(CONTROL_HEIGHT)
        self.draft_suffix.setPlaceholderText(tr("Personnel, U1…"))
        suffix_label = QLabel(tr("Suffixe @")); suffix_label.setBuddy(self.draft_suffix)
        form.addWidget(suffix_label, 0, 0); form.addWidget(self.draft_suffix, 0, 1)
        self.draft_fields, self.draft_restore, self.draft_hints = {}, {}, {}
        for index, (key, label) in enumerate(FIELD_LABELS):
            row = 2 * index + 1
            field = QLineEdit(); field.setObjectName(key); field.setFixedHeight(CONTROL_HEIGHT); field.setMinimumWidth(0)
            field.setAccessibleName(tr(label))
            if key == "hex":
                field.setMaxLength(7); field.setPlaceholderText("#RRGGBB")
            field.textEdited.connect(self._draft_edited)
            caption = QLabel(tr(label)); caption.setBuddy(field)
            restore = QToolButton(); restore.setObjectName("restore_" + key); restore.setText("↺")
            restore.setFixedSize(CONTROL_HEIGHT, CONTROL_HEIGHT)
            restore.setAccessibleName(tr("Rétablir la valeur de référence : {v0}", v0=tr(label)))
            restore.clicked.connect(lambda _checked=False, k=key: self._restore_reference(k))
            form.addWidget(caption, row, 0); form.addWidget(field, row, 1); form.addWidget(restore, row, 2)
            hint = QLabel(); hint.setObjectName("comparisonNote"); hint.setWordWrap(True); hint.hide()
            form.addWidget(hint, row + 1, 1, 1, 2)
            self.draft_fields[key] = field; self.draft_restore[key] = restore; self.draft_hints[key] = hint
        # Explicit gesture to confirm a suspect HEX as it is (a provenance decision,
        # distinct from a value change); never implied by opening or copying.
        self.draft_confirm_hex = QCheckBox(tr("Confirmer ce HEX tel quel"))
        self.draft_confirm_hex.setObjectName("confirm_hex")
        self.draft_confirm_hex.setToolTip(tr("La couleur source est à vérifier. Cochez pour la confirmer explicitement dans la copie personnelle ; la source ne change pas."))
        self.draft_confirm_hex.toggled.connect(self._draft_edited); self.draft_confirm_hex.hide()
        form.addWidget(self.draft_confirm_hex, 2 * len(FIELD_LABELS) + 1, 1, 1, 2)
        box.addLayout(form)
        self.draft_error = WrapLabel(); self.draft_error.setObjectName("draftError"); self.draft_error.hide()
        box.addWidget(self.draft_error)
        # Side by side, or stacked in a narrow detail panel (never wider than one action).
        actions = self.draft_actions = ReflowRow()
        self.draft_save = QPushButton(tr("Enregistrer une copie")); self.draft_save.setObjectName("primary")
        self.draft_cancel = QPushButton(tr("Annuler")); self.draft_cancel.setObjectName("secondary")
        for button in (self.draft_save, self.draft_cancel):
            button.setFixedHeight(CONTROL_HEIGHT); button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            actions.addWidget(button, 1)
        self.draft_save.clicked.connect(self._save_draft)
        self.draft_cancel.clicked.connect(self._cancel_draft)
        box.addWidget(actions)
        self.draft_editor.hide()
        layout.addWidget(self.draft_editor)

    def _build_comparison_card(self, layout):
        self.comparison_card = QFrame(); self.comparison_card.setObjectName("comparisonCard")
        box = QVBoxLayout(self.comparison_card); box.setContentsMargins(12, 10, 12, 10); box.setSpacing(6)
        self.comparison_heads=[WrapLabel(tr(text)) for text in ("Détails du filament","Référence","Orca","Personnel","Export")]
        heading=QHBoxLayout();self.comparison_heads[0].setObjectName('readingTitle')
        self.comparison_heads[4].setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Preferred)
        self.comparison_heads[4].setObjectName('comparisonHead');heading.addWidget(self.comparison_heads[0],1);heading.addWidget(self.comparison_heads[4]);box.addLayout(heading)
        self.comparison_summary=WrapLabel();self.comparison_summary.setObjectName('fieldvalue');box.addWidget(self.comparison_summary)
        self.comparison_origin=WrapLabel();self.comparison_origin.setObjectName('guidanceNote');box.addWidget(self.comparison_origin)
        self.comparison_alert=WrapLabel();self.comparison_alert.setObjectName('guidanceCaution');box.addWidget(self.comparison_alert)
        self.comparison_cells={}
        for key,label in FIELD_LABELS:
            cells=[WrapLabel(tr(label))]+[WrapLabel('—') for _ in range(4)]
            for cell in cells:cell.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.comparison_cells[key]=cells
        groups=(("Buse",(("min_temp","Min. °C"),("max_temp","Max. °C"))),
                ("Plateau",(("bed_min_temp","Min. °C"),("bed_max_temp","Max. °C"))),
                ("Diamètre",(("diameter","mm"),)),("Densité",(("density","g/cm³"),)),
                ("Couleur",(("hex","Couleur déclarée"),)))
        self.parameter_cards=[ParameterCard(title,fields,self.comparison_cells) for title,fields in groups]
        self.parameter_grid=CardGrid(self.parameter_cards,320);box.addWidget(self.parameter_grid)
        self.comparison_sources_toggle=QToolButton();self.comparison_sources_toggle.setText(tr('Origine et fiabilité'))
        self.comparison_sources_toggle.setCheckable(True);self.comparison_sources_toggle.setFixedHeight(CONTROL_HEIGHT)
        self.comparison_sources_toggle.toggled.connect(self._toggle_comparison_sources);box.addWidget(self.comparison_sources_toggle)
        self.comparison_legend=QWidget();legend=QHBoxLayout(self.comparison_legend);legend.setContentsMargins(0,0,0,0)
        for head in self.comparison_heads[1:4]:head.setObjectName('comparisonHead');legend.addWidget(head)
        box.addWidget(self.comparison_legend)
        self.comparison_note = WrapLabel(); self.comparison_note.setObjectName("comparisonNote")
        box.addWidget(self.comparison_note);self._toggle_comparison_sources(False)
        self.comparison_card.hide()
        layout.addWidget(self.comparison_card)

    def _toggle_comparison_sources(self,visible):
        for card in self.parameter_cards:card.sources.setVisible(visible)
        self.comparison_legend.hide()
        self.comparison_note.setVisible(visible)
        self.comparison_sources_toggle.setArrowType(Qt.DownArrow if visible else Qt.RightArrow)
        self.comparison_sources_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

    # ── Comparison ──────────────────────────────────────────────────────
    def _comparison(self):
        if not self.current_sku:
            return None
        nfc_format = "opentag3d" if self._opentag_selected() else "openspool"
        try:
            return core.value_comparison(self.db, self.current_sku,
                                         use_orca_overrides=core.load_config().get("orca_overrides") is True,
                                         nfc_format=nfc_format, opentag_settings=core.opentag_settings(self.current_sku))
        except (ValueError, OSError):
            return None

    @staticmethod
    def _provenance_text(info):
        kind, source = info.get("kind"), info.get("source")
        text = {"unknown": tr("provenance inconnue"), "manufacturer": tr("fabricant · {v0}", v0=tr(source or "")),
                "source": tr("source : {v0}", v0=tr(source or "")), "user": tr("personnel confirmé"),
                "copy": tr("copié, non confirmé"), "absent": tr("référence absente")}.get(kind, tr("provenance inconnue"))
        return text + (" · " + tr("à vérifier") if info.get("suspect") else "")

    def _effective_origin_text(self, row):
        """Origin of the value the export really uses, per field; unknown stays unknown."""
        effective = row["effective"]
        if effective["value"] is None:
            return tr("non renseigné")
        origin = effective["origin"]
        if origin == "opentag_settings":
            return tr("réglage OpenTag3D explicite")
        if origin == "orca":
            return (tr("profil Orca · complète une valeur absente") if effective.get("orca_mode") == "complement"
                    else tr("profil Orca · remplace la valeur (option activée)"))
        if origin == "personal" and row["personal"] is not None:
            return self._provenance_text(row["personal"])
        return self._provenance_text(row["reference"])

    def _field_names(self, keys):
        names = dict(FIELD_LABELS)
        return ", ".join(tr(names.get(key, key)) for key in keys)

    def _colour_references(self, sku):
        """Registry references linked to this filament: shown apart, never applied to the HEX."""
        try:
            from .measurement_store import MeasurementRegistry
            registry = MeasurementRegistry()
            if not registry.exists():
                return []
            document = registry.load()
        except Exception:
            return []
        store = document.get("measurements") if isinstance(document, dict) else None
        if not isinstance(store, dict):
            return []
        return [m for m in store.values() if isinstance(m, dict) and (m.get("association") or {}).get("sku") == sku]

    def _refresh_comparison(self):
        if not hasattr(self, "comparison_card"):
            return
        visible = bool(self.current_sku) and self.provenance_toggle.isChecked()
        data = self._comparison() if visible or self._draft is not None else None
        self.comparison_card.setVisible(visible and data is not None)
        self.card.setVisible(not visible and self._draft is None)
        if self._draft is not None:
            self._refresh_draft_hints(data)
        if data is None:
            return
        orca = data["orca"]
        show_orca = bool(orca["values"])
        show_personal = data["personal"]
        origin_text = {"reference": tr("référence"), "personal": tr("copie"), "orca": "Orca",
                       "opentag_settings": tr("réglage OpenTag3D")}
        for row in data["rows"]:
            key = row["key"]; cells = self.comparison_cells[key]
            reference = row["reference"]
            cells[1].setText(_shown(reference["value"], key))
            cells[1].setAccessibleDescription(_shown(reference["value"], key)+' · '+self._provenance_text(reference))
            cells[1].setToolTip(self._provenance_text(reference))
            if row["orca"] is not None:
                state = tr("appliqué") if row["orca"]["applied"] else (tr("non appliqué à la copie") if orca["status"] == "origin_only" else tr("non appliqué"))
                cells[2].setText(_shown(row["orca"]["value"], key) + ("\n" + state if row["orca"]["value"] is not None else ""))
            else:
                cells[2].setText("—")
            if row["personal"] is not None:
                cells[3].setText(_shown(row["personal"]["value"], key) + "\n" + self._provenance_text(row["personal"]))
            effective = row["effective"]
            marker = "≠ " if row["differs"] else ""
            cells[4].setText(marker + _shown(effective["value"], key))
            cells[4].setAccessibleDescription(_shown(effective["value"], key)+' · '+origin_text.get(effective["origin"], ""))
            cells[4].setToolTip(tr("Diffère de la référence") if row["differs"] else "")
            for column, cell in enumerate(cells):
                if column==0:
                    cell.hide();continue
                cell.setVisible(column != 2 or show_orca)
                if column == 3:
                    cell.setVisible(show_personal)
        self.comparison_heads[2].setVisible(show_orca); self.comparison_heads[3].setVisible(show_personal)
        self.comparison_heads[4].setText("OpenTag3D" if data["format"] == "opentag3d" else "OpenSpool")
        rows={row['key']:row for row in data['rows']}
        for card in self.parameter_cards:card.update_rows(rows,show_orca,show_personal)
        changes=sum(row['differs'] for row in data['rows'])
        self.comparison_summary.setText(tr('{v0} paramètres ajustés par rapport à la référence',v0=changes) if changes
                                        else tr('Les valeurs reprennent la référence.'))
        origins=list(dict.fromkeys(self._provenance_text(row['reference']) for row in data['rows']))
        # Summary from every field's effective origin, not from the first row only.
        effective_origins={}
        for row in data['rows']:
            effective_origins.setdefault(self._effective_origin_text(row),[]).append(row['key'])
        if len(effective_origins)==1:
            self.comparison_origin.setText(tr('Origine effective : {v0}',v0=next(iter(effective_origins))))
        else:
            self.comparison_origin.setText(tr('Origine effective : {v0}',v0=' · '.join(f'{text} ({len(keys)})' for text,keys in effective_origins.items())))
        mixed=len(effective_origins)>1
        for card in self.parameter_cards:
            texts={key:self._effective_origin_text(rows[key]) for key in card.origin_notes}
            uniform=len(set(texts.values()))==1
            for index,(key,note) in enumerate(card.origin_notes.items()):
                # One origin everywhere: the summary already says it; otherwise show it per card/field.
                caption=dict(FIELD_LABELS).get(key,key)
                note.setText(tr('Export : {v0}',v0=texts[key]) if uniform else tr('Export · {v0} : {v1}',v0=tr(caption),v1=texts[key]))
                note.setVisible(mixed and (not uniform or index==0))
            for key,note in card.source_notes.items():
                note.setText(self._provenance_text(rows[key]['reference']))
                note.setVisible(len(origins)>1)
                if len(origins)>1:
                    card.source_rows[key][1].show()
                    self.comparison_cells[key][1].setVisible(rows[key]['differs'])
        self.comparison_alert.setText(tr('Profil Orca inutilisable : contenu invalide.') if orca['status']=='error'
            else tr('Les valeurs à vérifier doivent être confirmées avant export.') if any(row['reference'].get('suspect') for row in data['rows'])
            else tr('Les températures de l’étiquette restent à renseigner avant export.') if data['format']=='opentag3d' and any(v is None for v in data['targets'].values()) else '')
        self.comparison_alert.setVisible(bool(self.comparison_alert.text()))
        notes = []
        # Orca is mentioned only when a profile exists for this filament (or its origin).
        if orca["status"] == "applied":
            if orca.get("completed"):
                notes.append(tr("Profil Orca : complète {v0}, absents de la fiche.", v0=self._field_names(orca["completed"])))
            if orca.get("replaced"):
                notes.append(tr("Profil Orca : remplace {v0} (option « Préférer les valeurs Orca » activée).", v0=self._field_names(orca["replaced"])))
        elif orca["status"] == "unused":
            notes.append(tr("Profil Orca trouvé ; ses valeurs ne remplacent pas celles de la fiche (option désactivée)."))
        elif orca["status"] == "origin_only":
            notes.append(tr("Un profil Orca existe pour la référence d’origine ; l’export de cette copie ne l’utilise pas."))
        elif orca["status"] == "error":
            notes.append(tr("Profil Orca inutilisable : contenu invalide."))
        if data["origin_missing"]:
            notes.append(tr("Référence d’origine absente du catalogue : aucune valeur de comparaison disponible."))
        if data["format"] == "opentag3d":
            targets = data["targets"]
            shown = ", ".join(f"{k} {targets[k]}" for k in ("print_temp", "bed_temp", "chamber_temp") if targets.get(k) is not None)
            notes.append(tr("Cibles OpenTag3D : {v0}.", v0=shown) if shown else tr("Cibles OpenTag3D non renseignées ; aucune n’est calculée."))
        notes.append(tr("Le HEX est la couleur déclarée par la source, pas une mesure de la couleur imprimée."))
        linked = self._colour_references(self.current_sku)
        if linked:
            documented = any(m.get("conditions") for m in linked)
            notes.append(tr("{v0} référence(s) couleur enregistrée(s) associée(s) à ce filament, distincte(s) du HEX exporté ; conditions : {v1}.",
                            v0=len(linked), v1=tr("documentées") if documented else tr("non renseignées")))
        self.comparison_note.setText("\n".join(notes))

    # ── Personal draft ──────────────────────────────────────────────────
    def _persisted_values(self, sku):
        view = core.get_sku_view(self.db, sku)
        if view is None:
            return None
        values = {key: view.product_data.get(key) for key, _ in FIELD_LABELS if key != "hex"}
        values["hex"] = self.db["_skus"][sku].get("hex")
        return values

    def _hex_confirmation(self):
        return not self.draft_confirm_hex.isHidden() and self.draft_confirm_hex.isChecked()

    def _draft_dirty(self):
        draft = getattr(self, "_draft", None)
        return bool(draft) and (any(self.draft_fields[k].text().strip() != draft["initial"][k] for k in self.draft_fields)
                                or self._hex_confirmation())

    def _edit_physical(self, focus_key=None):
        """Open the in-card draft for the current reference (former modal dialog)."""
        if not self.current_sku or self.worker and self.worker.isRunning():
            return
        values = self._persisted_values(self.current_sku)
        if values is None:
            return
        if not self._draft or self._draft["sku"] != self.current_sku:
            entry = self.db["_skus"][self.current_sku]
            view = core.get_sku_view(self.db, self.current_sku)
            self.draft_identity.setText(" · ".join(v for v in (view.product_data.get("brand"), view.display_product,
                                                              entry.get("color_name"), "#" + entry["hex"] if entry.get("hex") else "") if v))
            initial = {key: _text(values[key], key) for key, _ in FIELD_LABELS}
            self._draft = dict(sku=self.current_sku, initial=initial)
            self.draft_suffix.setText(entry.get("_personal_suffix", "Personnel"))
            for key, field in self.draft_fields.items():
                field.setText(initial[key])
            self.draft_confirm_hex.blockSignals(True); self.draft_confirm_hex.setChecked(False); self.draft_confirm_hex.blockSignals(False)
            self.draft_confirm_hex.setVisible(bool(core.validate_hex(entry.get("hex")) and core.db_io.implausible_color(entry)))
            self.draft_error.hide()
        self.provenance_toggle.setChecked(False)
        self.draft_editor.show()
        self._sync_hardware_presentation()
        self.btn_edit_physical.setEnabled(False)
        self._refresh_comparison()  # Draft hints remain available without opening Details.
        self._draft_edited()
        row = next((i for i, e in enumerate(getattr(self, "_rows", [])) if e["sku"] == self.current_sku
                    or any(v["sku"] == self.current_sku for v in e.get("variants", []))), None)
        if row is not None:  # Keep the edited reference visible in the results too.
            self.table.scrollToItem(self.table.item(row, 1)) if self.table.item(row, 1) else None
            self.grid.scrollToItem(self.grid.item(row)) if self.grid.item(row) else None
        target = (self.draft_confirm_hex if focus_key == "confirm_hex" and not self.draft_confirm_hex.isHidden()
                  else self.draft_fields.get(focus_key) or self.draft_fields["min_temp"])
        target.setFocus(Qt.OtherFocusReason)
        QTimer.singleShot(0, lambda: self.detail_scroll.ensureWidgetVisible(self.draft_editor) if self.draft_editor.isVisible() else None)

    def _draft_edited(self, *_):
        if not self._draft:
            return
        changes = 0
        for key, field in self.draft_fields.items():
            changed = field.text().strip() != self._draft["initial"][key] or (key == "hex" and self._hex_confirmation())
            changes += changed
            if field.property("draftChanged") != changed:
                field.setProperty("draftChanged", changed); field.style().unpolish(field); field.style().polish(field)
        self.draft_badge.setText(tr("Brouillon non enregistré : {v0} modification(s)", v0=changes) if changes
                                 else tr("Brouillon : aucune modification"))
        self.draft_save.setEnabled(bool(changes))
        self._refresh_nfc_capacity()  # export state, comparison and reminders of this context

    def _refresh_draft_hints(self, data):
        """Restore buttons and inline reminders; never touches the typed values."""
        rows = {row["key"]: row for row in (data or {}).get("rows", [])}
        origin_text = {"reference": tr("référence"), "personal": tr("copie"), "orca": "Orca", "opentag_settings": tr("réglage OpenTag3D")}
        for key, field in self.draft_fields.items():
            ref = rows.get(key, {}).get("reference", {})
            available = ref.get("value") is not None and not ref.get("suspect") and ref.get("kind") != "absent"
            self.draft_restore[key].setEnabled(available and field.text().strip() != _text(ref.get("value"), key))
            # Inline reminder only when informative: reference differs, is unknown, or export differs.
            effective = rows.get(key, {}).get("effective", {})
            informative = (ref.get("value") is None or _text(ref.get("value"), key) != field.text().strip()
                           or _text(effective.get("value"), key) != self._draft["initial"][key])
            hint = self.draft_hints[key]
            hint.setText(tr("réf. {v0} ({v1}) · export {v2} ({v3})", v0=_shown(ref.get("value"), key), v1=self._provenance_text(ref),
                            v2=_shown(effective.get("value"), key), v3=origin_text.get(effective.get("origin"), "")) if rows else "")
            hint.setVisible(bool(rows) and informative)
            self.draft_restore[key].setToolTip(
                tr("Rétablir {v0} dans la copie personnelle ; la référence source ne change pas.", v0=_shown(ref.get("value"), key)) if available
                else tr("Référence à vérifier : saisissez explicitement la valeur.") if ref.get("suspect")
                else tr("Aucune valeur de référence disponible."))

    def _restore_reference(self, key):
        data = self._comparison()
        row = next((r for r in (data or {}).get("rows", []) if r["key"] == key), None)
        if not row or row["reference"]["value"] is None or row["reference"].get("suspect"):
            return
        self.draft_fields[key].setText(_text(row["reference"]["value"], key))
        self._draft_edited()

    def _draft_values(self):
        """Only explicitly changed fields; inherited frozen values stay unconfirmed."""
        values = {}
        for key, field in self.draft_fields.items():
            raw = field.text().strip()
            if raw == self._draft["initial"][key] and not (key == "hex" and self._hex_confirmation()):
                continue
            label = tr(dict(FIELD_LABELS)[key])
            if key == "hex":
                colour = core.validate_hex(raw)
                if not colour:
                    raise core.ExportValidationError(tr("Couleur invalide : six caractères HEX requis."))
                values[key] = colour
                continue
            if not raw:
                values[key] = None
                continue
            try:
                number = float(raw.replace(",", "."))
            except ValueError as exc:
                raise core.ExportValidationError(tr("Nombre attendu : {v0}.", v0=label)) from exc
            values[key] = int(number) if key.endswith("temp") and number.is_integer() else number
        persisted = self._persisted_values(self._draft["sku"]) or {}
        merged = dict(persisted, **values)
        for low, high, message in PAIRS:
            if merged.get(low) is not None and merged.get(high) is not None and merged[low] > merged[high]:
                raise core.ExportValidationError(tr(message))
        return values

    def _save_draft(self):
        if not self._draft:
            return False
        try:
            values = self._draft_values()
            if not values:
                raise core.ExportValidationError(tr("Aucune modification à enregistrer."))
            created = core.save_personal_filament(self.db, self._draft["sku"], values, self.draft_suffix.text())
        except (ValueError, OSError) as exc:
            # Nothing was written (the storage layer is atomic); the draft stays editable.
            self.draft_error.setText(tr(str(exc))); self.draft_error.show()
            return False
        self._close_draft()
        self.current_sku = created
        self._reload_table()
        self.current_sku = created
        self._show_detail(created)
        self.status.showMessage(tr("Copie personnelle enregistrée ; la référence source est conservée."), 8000)
        self._update_stats()
        return True

    def _close_draft(self):
        self._draft = None
        if hasattr(self, "draft_editor"):
            self.draft_editor.hide(); self.draft_error.hide()
            self.btn_edit_physical.setEnabled(True)
            self._refresh_comparison()
            self._sync_hardware_presentation()

    def _cancel_draft(self):
        """Discard without writing anything; persisted values are shown again."""
        self._close_draft()
        if self.current_sku:
            self._show_detail(self.current_sku)
        self.btn_edit_physical.setFocus(Qt.OtherFocusReason)

    def _ask_draft_decision(self):
        box = QMessageBox(self)
        box.setWindowTitle(tr("Brouillon non enregistré"))
        box.setText(tr("Les modifications de cette fiche ne sont pas enregistrées."))
        save = box.addButton(tr("Enregistrer une copie"), QMessageBox.AcceptRole)
        discard = box.addButton(tr("Abandonner les modifications"), QMessageBox.DestructiveRole)
        keep = box.addButton(tr("Continuer l’édition"), QMessageBox.RejectRole)
        box.setDefaultButton(keep); box.setEscapeButton(keep)
        box.exec()
        clicked = box.clickedButton()
        return "save" if clicked is save else "discard" if clicked is discard else "keep"

    def _confirm_draft_transition(self):
        """True when the current draft may be left; never saves implicitly."""
        if not getattr(self, "_draft", None):
            return True
        if not self._draft_dirty():
            self._close_draft()
            return True
        decision = self._ask_draft_decision()
        if decision == "save":
            return self._save_draft()
        if decision == "discard":
            self._close_draft()
            return True
        return False

    _NAVIGATION_KEYS = {Qt.Key_Down: QAbstractItemView.MoveDown, Qt.Key_Up: QAbstractItemView.MoveUp,
                        Qt.Key_PageDown: QAbstractItemView.MovePageDown, Qt.Key_PageUp: QAbstractItemView.MovePageUp,
                        Qt.Key_Home: QAbstractItemView.MoveHome, Qt.Key_End: QAbstractItemView.MoveEnd,
                        Qt.Key_Left: QAbstractItemView.MoveLeft, Qt.Key_Right: QAbstractItemView.MoveRight}

    def _view_row_sku(self, view, row):
        item = (view.item(row, 1) if view is self.table else view.item(row)) if row >= 0 else None
        return item.data(Qt.UserRole) if item is not None else None

    def _before_view_navigation(self, view, event):
        """Decide once, before Qt moves the selection, for a key leaving a modified draft.

        The target is the index Qt itself would move to, and the selection command
        is the one Qt would apply to it (a modifier such as Ctrl can turn a move
        on the selected row into a deselection). Keeping cancels the key;
        discarding lets Qt proceed; saving then reaches the intended state itself
        (target found by SKU in the filtered results, on its own page, or the
        deselection with the cursor left on the target's reference and column)
        and consumes the original key: no stale row index is used.
        """
        action = self._NAVIGATION_KEYS.get(event.key())
        if action is None or not self._draft_dirty():
            return True
        target = view.moveCursor(action, event.modifiers())
        if not target.isValid() or target == view.currentIndex():
            return True  # Qt applies no selection command when the index does not move.
        command = view.selectionCommand(target, event)
        deselects = bool(command & QItemSelectionModel.Deselect) and view.selectionModel().isSelected(target)
        sku = self._view_row_sku(view, target.row())
        if not deselects and (not sku or self._group_for_sku(sku) is self._group_for_sku(self._draft["sku"])):
            return True
        decision = self._ask_draft_decision()
        if decision == "discard":
            self._close_draft()
            return True
        if decision == "save" and self._save_draft():
            if deselects:
                self._clear_filament()
                self._place_cursor(view, sku, target.column())
            else:
                self._select_result(sku)
        return False

    def _show_result(self, sku):
        """Row of a reference in the filtered results, on its page shown first; None if absent."""
        index = next((i for i, e in enumerate(self._filtered_rows)
                      if e["sku"] == sku or any(v["sku"] == sku for v in e.get("variants", []))), None)
        if index is None:
            return None
        page, row = divmod(index, self._page_size)
        if page != self._page:
            self._page = page
            self._show_page()
        return row

    def _select_result(self, sku):
        """Select a reference in the filtered results, showing its page first.

        A reference no longer in the results is not replaced by another one:
        the current selection (the saved copy) stays.
        """
        row = self._show_result(sku)
        if row is None:
            return False
        self.table.selectRow(row) if self.view_mode == "list" else self.grid.setCurrentRow(row)
        return True

    def _place_cursor(self, view, sku, column):
        """Put the current index on a reference without selecting it, as Qt's deselecting move does.

        Without the reference in the results, the cursor stays where the reload put it,
        with nothing selected and no fiche shown.
        """
        row = self._show_result(sku)
        if row is None:
            return False
        view.selectionModel().setCurrentIndex(view.model().index(row, column), QItemSelectionModel.NoUpdate)
        return True

    def _reselect_draft(self):
        """Put the selection back on the reference being edited."""
        sku = self._draft["sku"] if self._draft else self.current_sku
        row = next((i for i, e in enumerate(getattr(self, "_rows", [])) if e["sku"] == sku or any(v["sku"] == sku for v in e.get("variants", []))), None)
        for widget in (self.table, self.grid):
            previous = widget.blockSignals(True)
            if row is None:
                widget.clearSelection()
            elif widget is self.table:
                widget.selectRow(row)
            else:
                widget.setCurrentRow(row)
            widget.blockSignals(previous)
        self.current_sku = sku

    # ── Export state and primary action ─────────────────────────────────
    def _build_export_explanation(self, layout):
        self.export_journey = QFrame(); self.export_journey.setObjectName("exportJourney")
        card = QVBoxLayout(self.export_journey); card.setContentsMargins(*CARD_MARGINS); card.setSpacing(8)
        # Identity row (photo, name, fold) above the effect and « Configurer »: the
        # button no longer narrows the name's column; the effect row stacks when narrow.
        first = QHBoxLayout(); first.setSpacing(8)
        self.hardware_photo = QLabel(); self.hardware_photo.setFixedSize(40, 44); self.hardware_photo.setAlignment(Qt.AlignCenter); first.addWidget(self.hardware_photo,0,Qt.AlignTop)
        identity = QVBoxLayout(); identity.setSpacing(2)
        self.hardware_name = FlowLabel(); self.hardware_name.setObjectName("guidanceTitle")
        identity.addWidget(self.hardware_name); first.addLayout(identity,1)
        self.hardware_change = QToolButton(); self.hardware_change.setText(tr("Configurer")); self.hardware_change.setFixedHeight(CONTROL_HEIGHT)
        self.hardware_change.setAccessibleName(tr("Configurer l’imprimante et son lecteur"))
        self.hardware_change.clicked.connect(self._open_hardware)
        self._hardware_expanded=True
        self.hardware_fold=QToolButton();self.hardware_fold.setCheckable(True)
        self.hardware_fold.setFixedSize(CONTROL_HEIGHT,CONTROL_HEIGHT)
        self.hardware_fold.toggled.connect(self._choose_hardware_presentation);first.addWidget(self.hardware_fold,0,Qt.AlignTop|Qt.AlignRight)
        card.addLayout(first)
        def effect_row_width():
            words = self.hardware_summary.text().split() or ['']
            return max(self.hardware_summary.fontMetrics().horizontalAdvance(word) for word in words) + 8 + self.hardware_change.width()
        self.hardware_effect_row = ReflowRow(needed=effect_row_width)
        self.hardware_effect_row.addWidget(self.hardware_summary, 1); self.hardware_effect_row.addWidget(self.hardware_change)
        card.addWidget(self.hardware_effect_row)
        self.hardware_body=QWidget()
        body=QVBoxLayout(self.hardware_body);body.setContentsMargins(0,0,0,0);body.setSpacing(8)
        second = QHBoxLayout(); second.setSpacing(8)
        self.tag_summary = WrapLabel(); self.tag_summary.setObjectName("guidanceTitle"); second.addWidget(self.tag_summary, 1)
        self.export_details_button = QToolButton(); self.export_details_button.setText(tr("Détails"))
        self.export_details_button.setAccessibleName(tr("Comprendre la préparation de l’étiquette"))
        self.export_details_button.setFixedHeight(CONTROL_HEIGHT); self.export_details_button.clicked.connect(self._open_export_explanation)
        second.addWidget(self.export_details_button); body.addLayout(second)
        for button in (self.hardware_change,self.export_details_button):button.ensurePolished()
        action_width=max(button.fontMetrics().horizontalAdvance(button.text())+20 for button in (self.hardware_change,self.export_details_button))
        for button in (self.hardware_change,self.export_details_button):button.setFixedWidth(action_width)
        card.addWidget(self.hardware_body)
        card.addWidget(self.nfc_capacity)
        self.capacity_caption = WrapLabel(); self.capacity_caption.hide()
        body.addWidget(self.capacity_caption)
        self.capacity_meter = QProgressBar()
        self.capacity_meter.setFixedHeight(6); self.capacity_meter.setTextVisible(False)
        self.capacity_meter.setAccessibleName(tr("Place disponible sur l’étiquette"))
        self.capacity_meter.hide(); body.addWidget(self.capacity_meter); layout.addWidget(self.export_journey)
        self.export_details = ExportGuidance(self)
        self.export_details.readiness.layout().addWidget(self.btn_opentag_settings)
        self.export_details.archive_button.clicked.connect(self.act_archive.trigger)
        self._export_context = {}; self._hardware_photo_key = None
        self._sync_hardware_presentation()

    def _choose_hardware_presentation(self,expanded):
        if expanded:
            had_draft=bool(getattr(self,'_draft',None))
            if not self._confirm_draft_transition():
                self._sync_hardware_presentation()
                return
            if had_draft and self.current_sku:self._show_detail(self.current_sku)
            self.provenance_toggle.setChecked(False)
        self._hardware_expanded=expanded
        self._sync_hardware_presentation()

    def _sync_hardware_presentation(self):
        """Printer details and filament details form one exclusive accordion."""
        if not hasattr(self,'hardware_body'):return
        busy=bool(getattr(self,'_draft',None)) or self.provenance_toggle.isChecked()
        if busy:self._hardware_expanded=False
        expanded=self._hardware_expanded
        self.hardware_body.setVisible(expanded)
        self.hardware_fold.blockSignals(True);self.hardware_fold.setChecked(expanded);self.hardware_fold.blockSignals(False)
        self.hardware_fold.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        label=tr('Replier la zone imprimante') if expanded else tr('Déplier la zone imprimante')
        self.hardware_fold.setAccessibleName(label)
        self.hardware_fold.setToolTip(label)
        self._align_detail_footer()

    def _fit_hardware_actions(self):
        """Use the polished native metrics, including QSS padding, not startup fonts."""
        buttons=(self.hardware_change,self.export_details_button)
        for button in buttons:button.ensurePolished()
        width=max(max(button.sizeHint().width(),button.fontMetrics().horizontalAdvance(button.text())+24)
                  for button in buttons)
        for button in buttons:button.setFixedWidth(width)

    def _open_export_explanation(self):
        if self.export_details is None:
            self.export_details = ExportGuidance(self)
        self.export_details.update_context(self._export_context)
        self.export_details.show(); self.export_details.raise_(); self.export_details.activateWindow()

    def _reset_export_explanation(self):
        if not hasattr(self, "capacity_meter"):
            return
        self.capacity_caption.hide(); self.capacity_meter.hide()
        self._export_context = {}

    def _explain_export(self, *, budget=None, technical_format="", diagnostic=""):
        """Keep the engine's exact budget available without making it the headline."""
        if not hasattr(self, "capacity_meter"):
            return
        self._export_context.update(budget=budget or {}, technical_format=technical_format, diagnostic=diagnostic)
        if budget:
            remaining, capacity = budget["remaining"], budget["capacity"]
            self.capacity_meter.setRange(0, capacity)
            self.capacity_meter.setValue(remaining)
            percent = remaining * 100 // capacity
            text = (tr("Moins de 1 % de place disponible") if remaining and not percent
                    else tr("{v0} % de place disponible", v0=percent))
            self.capacity_caption.setText(text); self.capacity_caption.show()
            self.capacity_meter.setAccessibleDescription(text)
            self.capacity_meter.show()

    def _refresh_export_journey(self):
        if not hasattr(self, "export_journey"):
            return
        from .printer_presentations import presentation
        printer_id = self.printer.currentData() or printer_profiles.DEFAULT
        profile = PROFILES[printer_id]
        self.hardware_name.setText(tr(profile["label"]))
        # Wraps between words in a narrow panel, never inside one (« Snapmaker » stays whole).
        self.hardware_name.ensurePolished()
        metrics = self.hardware_name.fontMetrics()
        self.hardware_name.setMinimumWidth(max((metrics.horizontalAdvance(word) for word in tr(profile["label"]).split()), default=0) + 2)
        self.hardware_summary.setText(self._configuration_effect())
        dark = getattr(self, '_tok', {}).get('dark', False)
        if self._hardware_photo_key != (printer_id, dark):
            self._hardware_photo_key = (printer_id, dark)
            info = presentation(profile)
            self.hardware_photo.setPixmap(printer_visual(info, 40, dark))
            self.hardware_photo.show()
            self.hardware_photo.setToolTip(info.get('caption', info['title']) if info.get('photo')
                                          else tr('Illustration générique ; photo de ce modèle non disponible.'))
            self.hardware_photo.setAccessibleName(info['title'])
        tag = self.tag_type.currentData()
        format_name = "OpenTag3D" if self._opentag_selected() else "OpenSpool"
        can = self._can_export_for_printer()
        self.tag_summary.setText(f"{tag} · {format_name}" if can else tr("Format d’étiquette à choisir") if self.nfc_format.count()
                                 else tr("Étiquette non utilisable avec cette configuration"))
        ready = bool(self.current_sku and self._primary_kind == "export" and self.btn_generate.isEnabled())
        tone = "ready" if ready else "attention" if can and self.current_sku else "neutral"
        if self.export_journey.property("tone") != tone:
            self.export_journey.setProperty("tone", tone)
            self.export_journey.style().unpolish(self.export_journey); self.export_journey.style().polish(self.export_journey)
        self.export_details_button.setEnabled(bool(self.current_sku))
        if self.export_details is not None:
            self.export_details.archive_button.setEnabled(bool(self.current_sku) and not self._draft_dirty())
        self._export_context.update(printer=tr(profile["label"]), effect=self._configuration_effect(),
            tag=tag, format=format_name if can else tr("Non disponible"),
            configuration=self.hardware_summary.toolTip(),
            writer="",
            reason=self.nfc_capacity.text(), state="ready" if ready else "blocked")
        if self.export_details is not None:
            self.export_details.update_context(self._export_context)

    @staticmethod
    def _friendly_tag_error(message):
        for field, text in (("print_temp", tr("Indiquez la température de buse pour cette bobine.")),
                            ("bed_temp", tr("Indiquez la température du plateau.")),
                            ("chamber_temp", tr("Indiquez la température de l’enceinte.")),
                            ("weight", tr("Indiquez la masse de filament sur la bobine."))):
            if re.search(r"\b" + field + r"\b", message):
                return text
        return tr("Vérifiez les réglages de l’étiquette avant d’exporter.")

    def _configuration_effect(self):
        printer_id, firmware_id = self.printer.currentData(), self.firmware.currentData()
        if firmware_id == "unknown" or printer_id not in PROFILES:
            return tr("Configuration à préciser")
        configuration = printer_profiles.configuration(printer_id, firmware_id)
        if not printer_profiles.can_export(printer_id, firmware_id):
            return tr("Format non exporté par SpoolScribe") if configuration.get("reader_formats") else tr("Consultation des fiches uniquement")
        return {"printer": tr("Lecture possible par l’imprimante"), "inventory": tr("Inventaire externe uniquement"),
                "standalone": tr("Lecture par le lecteur choisi")}[configuration["effect"]]

    def _set_primary(self, kind, text, enabled=True, tip=""):
        self._primary_kind = kind
        self.btn_generate.setText(text)
        self.btn_generate.setEnabled(enabled)
        if hasattr(self,'_arrange_export_actions'):self._arrange_export_actions()
        self.btn_generate.setToolTip(tip or tr("Ctrl+E : exporter pour NFC"))
        if hasattr(self, "btn_qr"):
            # Same verdict as the export itself: no QR for a message that cannot be exported.
            available = kind == "export" and enabled
            self.btn_qr.setEnabled(available)
            self.btn_qr.setToolTip(tr("QR pour le futur SpoolScribe Companion. Android / iOS : bientôt disponible.") if available
                                   else tr("Disponible lorsque l’export NFC est possible."))

    def _primary_action(self, *_):
        kind = getattr(self, "_primary_kind", "export")
        if kind == "export":
            self._generate()
        elif kind == "correct_physical":
            self._edit_physical(getattr(self, "_blocking_field", None))
        elif kind == "confirm_colour":
            self._edit_physical("confirm_hex")
        elif kind == "missing_colour":
            self._generate()  # Historical explicit HEX dialog, then export.
        elif kind == "hardware":
            self._open_hardware()
        elif kind == "opentag_settings":
            self._complete_opentag_settings()

    def _export_bytes(self, mode="nfc"):
        """Bytes the current context would write, or None if export is blocked."""
        try:
            if mode == "nfc" and self._opentag_selected():
                return self._prepare_opentag().data
            payload = self._build_payload()
            if payload is None:
                return None
            options = self._nfc_options() if mode == "nfc" else dict(tag_type=self.tag_type.currentData(), profile="full", reserved_bytes=0)
            return core.serialize_openspool(payload, mode=mode, **options).encode("utf-8")
        except (ValueError, OSError):
            return None

    def _record_export(self, path, mode):
        """Called only with the path returned by a successful write."""
        try:
            digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
        except OSError:
            digest = None
        self._last_export = dict(path=path, sku=self.current_sku, mode=mode,
                                 format="opentag3d" if mode == "nfc" and self._opentag_selected() else "openspool", digest=digest)
        self._refresh_last_export()

    def _last_export_state(self):
        record = getattr(self, "_last_export", None)
        if not record:
            return "none", None
        if not os.path.isfile(record["path"]):
            return "missing", record
        try:
            on_disk = hashlib.sha256(open(record["path"], "rb").read()).hexdigest()
        except OSError:
            return "missing", record
        current = self._export_bytes(record["mode"]) if record["sku"] == self.current_sku and not self._draft_dirty() else None
        same_format = record["format"] == ("opentag3d" if record["mode"] == "nfc" and self._opentag_selected() else "openspool")
        if current is not None and same_format and on_disk == record["digest"] == hashlib.sha256(current).hexdigest():
            return "current", record
        return "other", record

    def _refresh_last_export(self):
        if not hasattr(self, "last_export_label"):
            return
        state, record = self._last_export_state()
        name = os.path.basename(record["path"]) if record else ""
        text = {"none": tr("Aucun fichier exporté pendant cette session."),
                "missing": tr("Dernier fichier introuvable (supprimé ou déplacé) : {v0}", v0=name),
                "current": tr("Fichier exporté : {v0} — identique à l’export actuel.", v0=name),
                "other": tr("Dernier export : {v0} — autre fiche ou réglages différents.", v0=name)}[state]
        self.last_export_label.setText(text)
        self.last_export_label.setVisible(state != "none")  # Stays compact until a file exists.
        self.last_export_label.setToolTip((record["path"] + "\n" if record else "") +
                                          tr("Fichier produit sur ce poste : ni étiquette écrite, ni relue, ni imprimante validée."))
        self.btn_open_out.setEnabled(state in ("current", "other"))
        self.btn_open_out.setToolTip(record["path"] if record and state in ("current", "other") else tr("Disponible après un export réussi."))

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.ActivationChange and self.isActiveWindow():
            self._refresh_last_export()

    def _open_qr(self, *_):
        from .ui_qr import open_qr_window
        return open_qr_window(self)

    def _open_output(self):
        """Reveal the last file actually written; never creates a folder."""
        state, record = self._last_export_state()
        self._refresh_last_export()
        if state not in ("current", "other"):
            self.status.showMessage(tr("Aucun fichier exporté disponible."), 6000)
            return
        path = record["path"]
        try:
            import subprocess
            if sys.platform.startswith("win"):
                subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", path])
            else:
                subprocess.Popen(["xdg-open", os.path.dirname(path)])
        except Exception as e:
            QMessageBox.warning(self, "Ouverture", tr("Impossible d'ouvrir le dossier :\n{v0}", v0=e))

    # ── Colour proximity (CIEDE2000 on declared HEX) ────────────────────
    def _build_colour_filter(self):
        self._colour_query = None
        self._colour_deltas = {}
        self._colour_report = None
        self.colour_guidance = None
        self.colour_panel = QFrame(); self.colour_panel.setObjectName("colourFilter")
        box = QVBoxLayout(self.colour_panel); box.setContentsMargins(0, 2, 0, 2); box.setSpacing(6)
        row = QHBoxLayout(); row.setSpacing(6)
        self.colour_swatch = QToolButton(); self.colour_swatch.setFixedSize(CONTROL_HEIGHT, CONTROL_HEIGHT)
        self.colour_swatch.setAccessibleName(tr("Choisir une couleur")); self.colour_swatch.setToolTip(tr("Choisir une couleur"))
        self.colour_swatch.clicked.connect(self._pick_colour); row.addWidget(self.colour_swatch)
        self.colour_hex = QLineEdit(); self.colour_hex.setObjectName("colourHex"); self.colour_hex.setMaxLength(7)
        self.colour_hex.setPlaceholderText(tr("Code couleur")); self.colour_hex.setFixedHeight(CONTROL_HEIGHT); self.colour_hex.setMinimumWidth(0)
        self.colour_hex.setAccessibleName(tr("Couleur HEX de référence"))
        self.colour_hex.setToolTip(tr("Choisissez une pastille ou saisissez un code couleur."))
        self.colour_hex.returnPressed.connect(lambda: self._start_colour_search(self.colour_hex.text()))
        row.addWidget(self.colour_hex, 1); box.addLayout(row)
        actions = QHBoxLayout(); actions.setSpacing(6)
        self.colour_rank_btn = QToolButton(); self.colour_rank_btn.setText(tr("Comparer")); self.colour_rank_btn.setObjectName("colourAction")
        self.colour_rank_btn.clicked.connect(lambda: self._start_colour_search(self.colour_hex.text()))
        self.colour_exit_btn = QToolButton(); self.colour_exit_btn.setText(tr("Retirer"))
        self.colour_exit_btn.setToolTip(tr("Retirer uniquement la comparaison de couleurs")); self.colour_exit_btn.clicked.connect(self._stop_colour_search)
        self.colour_exit_btn.setEnabled(False)
        self.colour_hex.textChanged.connect(self._refresh_colour_remove)
        self.colour_details_button = QToolButton(); self.colour_details_button.setText(tr("Aide"))
        self.colour_details_button.setAccessibleName(tr("Comment ça marche ?"))
        self.colour_details_button.clicked.connect(self._open_colour_explanation)
        for button in (self.colour_rank_btn, self.colour_exit_btn, self.colour_details_button):
            button.setProperty('colourControl', True)
            button.setFixedHeight(CONTROL_HEIGHT); button.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed); actions.addWidget(button, 1)
        box.addLayout(actions)
        self.colour_measure_btn = QToolButton(); self.colour_measure_btn.setText(tr("Lab, RGB ou fichier…"))
        self.colour_measure_btn.setToolTip(tr("Saisir, coller ou importer une mesure de couleur, puis l’utiliser comme cible ou la lier à une fiche"))
        self.colour_measure_btn.setAccessibleName(tr("Valeurs couleur : Lab, RGB, fichier")); self.colour_measure_btn.setProperty('colourControl', True)
        self.colour_measure_btn.setFixedHeight(CONTROL_HEIGHT); self.colour_measure_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.colour_measure_btn.clicked.connect(self._open_measurements); box.addWidget(self.colour_measure_btn)
        self.measurement_window = None
        self.colour_limit_button = QToolButton(); self.colour_limit_button.setFixedHeight(CONTROL_HEIGHT)
        self._refresh_colour_limit_label()
        self.colour_limit_button.setToolTip(tr("Régler la proximité des couleurs dans les paramètres"))
        self.colour_limit_button.clicked.connect(lambda: self._open_settings(colour_tab=True))
        self.colour_limit_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed); box.addWidget(self.colour_limit_button)
        self.colour_info = FlowLabel(); self.colour_info.hide()
        self.colour_info.setObjectName("guidanceNote"); box.addWidget(self.colour_info)
        self._paint_colour_reference(None)
        self.colour_panel.setMinimumHeight(4*CONTROL_HEIGHT+26)
        return self.colour_panel

    # ── Measurements (registry window) ──────────────────────────────────
    def _open_measurements(self):
        from .ui_colour_measurements import MeasurementWindow
        if self.measurement_window is None:
            self.measurement_window = MeasurementWindow(self, current_sku_provider=lambda: self.current_sku,
                                                        db_provider=lambda: self.db)
            self.measurement_window.search_requested.connect(self._start_measurement_search)
            self.measurement_window.registry_changed.connect(self._measurements_changed)
        self.measurement_window.show(); self.measurement_window.raise_(); self.measurement_window.activateWindow()
        return self.measurement_window

    def _start_measurement_search(self, target):
        """A validated measurement target replaces the HEX query; filters and selection stay."""
        self._set_section_expanded("colours", True)
        query = getattr(self, "_colour_query", None)
        if not colour_targets.query_matches(query, target):
            # A new acquisition is always its own target (identity, name); distances computed for the same values are reused.
            self._colour_query = dict(target, cache=colour_targets.reusable_cache(query, target))
        self.colour_hex.blockSignals(True); self.colour_hex.setText(""); self.colour_hex.blockSignals(False)
        self._paint_colour_reference(target.get("hex"))
        self.colour_info.setText(tr("Cible : {v0}", v0=self._colour_query_label())); self.colour_info.show()
        self._refresh_colour_remove()
        self._apply_filter()
        return True

    def _measurements_changed(self):
        """After an explicit registry action (rename, link, delete, restore…): refresh or withdraw the active target.

        The target is withdrawn when its acquisition no longer exists or can
        no longer be ranked; it is refreshed when its name changed; its
        distances are kept only when values and conditions are unchanged.
        Filters, favourites and selection are untouched.
        """
        query = getattr(self, "_colour_query", None)
        window = self.measurement_window
        if not query or query.get("kind") != "measurement" or window is None or window.registry.load_error is not None:
            return
        identifier = query.get("id")
        if not identifier:
            return
        measurement = window.registry.get(identifier)
        if measurement is None:
            self._stop_colour_search(); return
        try:
            fresh = colour_targets.target_from_measurement(measurement, identifier)
        except (colour_targets.TargetBlocked, colour_measurements.MeasurementError):
            self._stop_colour_search(); return
        if colour_targets.query_matches(query, fresh):
            return
        self._colour_query = dict(fresh, cache=colour_targets.reusable_cache(query, fresh))
        self.colour_info.setText(tr("Cible : {v0}", v0=self._colour_query_label())); self.colour_info.show()
        self._apply_filter()

    def _colour_query_label(self):
        query = getattr(self, "_colour_query", None)
        if not query:
            return ""
        if query.get("kind") == "measurement":
            conditions = colour_measurements.describe_space_conditions(query.get("space"), query.get("conditions_data"), tr)
            return f"{query['name']} — {query['values']} ({conditions})"
        return "#" + query["hex"]

    def _paint_colour_reference(self, value):
        colour = colour_distance.parse_hex(value)
        self.colour_swatch.setStyleSheet(f"QToolButton {{ background:#{colour}; border:2px solid #89949c; border-radius:6px; }}" if colour else "")
        self.colour_swatch.setText("" if colour else "+")

    def _refresh_colour_remove(self, *_):
        self.colour_exit_btn.setEnabled(bool(self._colour_query or self.colour_hex.text()))

    def _pick_colour(self):
        initial = QColor("#" + (colour_distance.parse_hex(self.colour_hex.text()) or "808080"))
        colour = QColorDialog.getColor(initial, self, tr("Choisir une couleur"))
        if colour.isValid():
            self._start_colour_search(colour.name())

    def _open_colour_explanation(self):
        if self.colour_guidance is None:
            self.colour_guidance = ColourGuidance(self)
        report = self._colour_report
        self.colour_guidance.tabs.setTabEnabled(0, report is not None)
        if report:
            self.colour_guidance.update_result(**report)
        else:
            self.colour_guidance.tabs.setCurrentIndex(1)
        self.colour_guidance.show(); self.colour_guidance.raise_(); self.colour_guidance.activateWindow()

    def _open_colour_search(self):
        known = getattr(self, "_cur_hex", None) if self.current_sku and self.stack.currentIndex() == 1 else None
        self._set_section_expanded("colours", True)
        self.colour_hex.setText("#" + known if known else "")
        if known:
            self._start_colour_search(known)
        else:
            self._paint_colour_reference(None)
            self.colour_info.clear(); self.colour_info.hide()
            self.colour_hex.setFocus(Qt.OtherFocusReason)

    def _start_colour_search(self, value):
        self._set_section_expanded("colours", True)
        target = colour_distance.parse_hex(value)
        if target is None:
            self.colour_info.setText(tr("Code couleur invalide.")); self.colour_info.show()
            self.colour_hex.setAccessibleDescription(tr("Saisissez un code à six caractères, par exemple #22F4D3."))
            return False
        self.colour_hex.setText("#" + target); self._paint_colour_reference(target)
        self.colour_info.clear(); self.colour_info.hide(); self.colour_hex.setAccessibleDescription('')
        query = getattr(self, "_colour_query", None)
        if not query or query.get("kind", "hex") != "hex" or query["hex"] != target:
            self._colour_query = dict(kind="hex", hex=target, cache={})
        self._refresh_colour_remove()
        self._apply_filter()
        return True

    def _clear_colour_filter(self):
        self._colour_query = None; self._colour_deltas = {}; self._colour_report = None
        self.colour_hex.clear(); self._paint_colour_reference(None)
        self.colour_info.clear(); self.colour_info.hide(); self.colour_hex.setAccessibleDescription('')
        self._refresh_colour_remove()
        if self.colour_guidance is not None:
            self.colour_guidance.close()

    def _stop_colour_search(self):
        self._clear_colour_filter()
        self._apply_filter()

    def _refresh_colour_limit_label(self):
        limit = core.colour_delta_limit()
        self.colour_limit_button.setText(tr("Écart maximal : {v0}", v0=tr("Sans limite") if limit is None else f"ΔE ≤ {limit:g}"))

    def _rank_by_colour(self, rows):
        query = self._colour_query
        catalogue = getattr(self, "_all_rows", [])
        built = getattr(self, "_colour_index", None)
        if built is None or built[0] is not catalogue:
            # Rebuilt after every reload: the index refers to these row objects only.
            built = self._colour_index = (catalogue, colour_distance.build_index(catalogue))
        if query.get("kind") == "measurement":
            result = colour_targets.rank_measurement(query, rows, index=built[1])
        else:
            result = colour_distance.rank(query["hex"], rows, cache=query["cache"], index=built[1])
        limit = core.colour_delta_limit()
        matched = [item for item in result["items"] if limit is None or item["delta"] <= limit]
        self._colour_deltas = {item["row"]["sku"]: item for item in matched}
        excluded = result["excluded"]
        effects = sum(1 for item in matched if item["effect"])
        self._colour_report = dict(target=query.get("hex"), total=len(matched), excluded=excluded, effects=effects,
                                   limit=limit, outside_limit=len(result["items"])-len(matched))
        if query.get("kind") == "measurement":
            self._colour_report.update(target_label=self._colour_query_label(), basis=query["policy"].get("reference"))
        self._refresh_colour_limit_label()
        if self.colour_guidance is not None:
            self.colour_guidance.tabs.setTabEnabled(0, True)
            self.colour_guidance.update_result(**self._colour_report)
        return [item["row"] for item in matched]

    def _colour_suffix(self, sku):
        item = getattr(self, "_colour_deltas", {}).get(sku) if getattr(self, "_colour_query", None) else None
        if not item:
            return ""
        return f" · ΔE {colour_distance.display_delta(item['delta'])}" + (" ✦" if item["effect"] else "")

"""Catalogue interaction, persistent workspace settings and guided exports."""
from PySide6.QtCore import Qt, QByteArray, QThread, Signal, QUrl, QTimer
from PySide6.QtGui import QDesktopServices, QPixmap, QPainter, QColor, QImage, QKeySequence, QShortcut
from PySide6.QtWidgets import (QTableWidget, QListWidget, QListWidgetItem, QCompleter, QMenu, QDialog, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QToolButton, QCheckBox, QDialogButtonBox, QComboBox,
    QFileDialog, QMessageBox, QPlainTextEdit, QLineEdit, QWidget, QScrollArea, QFrame, QTableWidgetItem, QHeaderView)
import core
import printer_profiles
from printer_profiles import PROFILES


class ClearableTable(QTableWidget):
    def mousePressEvent(self, event):
        index = self.indexAt(event.position().toPoint())
        if event.button() == Qt.LeftButton and (not index.isValid() or self.selectionModel().isRowSelected(index.row(), index.parent())):
            self.clearSelection()
            self.setCurrentCell(-1, -1)
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.clearSelection()
            self.setCurrentCell(-1, -1)
            return
        super().keyPressEvent(event)


class ClearableList(QListWidget):
    """Grille de cartes : reclic sur la carte sélectionnée ou Échap = désélection."""
    def mousePressEvent(self, event):
        item = self.itemAt(event.position().toPoint())
        if event.button() == Qt.LeftButton and (item is None or item.isSelected()):
            self.clearSelection()
            self.setCurrentRow(-1)
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.clearSelection()
            self.setCurrentRow(-1)
            return
        super().keyPressEvent(event)


class ReleaseWorker(QThread):
    ready = Signal(object)
    def run(self):
        from scripts.app_updates import check_release
        try:
            self.ready.emit(check_release(core.APP_VERSION))
        except Exception as exc:
            self.ready.emit({'error': str(exc)})


class CatalogueUx:
    def _install_ux(self):
        self._restoring_ui = True
        self._release_worker = None
        self._last_report = None
        self._sync_before = None
        self.brand_filter.setEditable(True)
        self.brand_filter.setInsertPolicy(QComboBox.NoInsert)
        self.brand_filter.lineEdit().setPlaceholderText('Tapez 3–4 lettres du fabricant…')
        self.brand_filter.lineEdit().setClearButtonEnabled(True)
        self.brand_filter.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.brand_filter.completer().setFilterMode(Qt.MatchContains)
        self.brand_filter.completer().setCaseSensitivity(Qt.CaseInsensitive)
        self.brand_filter.lineEdit().textEdited.connect(self._brand_typed)
        self.brand_filter.activated.connect(lambda *_: self._remember_brand())
        hh = self.table.horizontalHeader()
        hh.setContextMenuPolicy(Qt.CustomContextMenu)
        hh.customContextMenuRequested.connect(self._header_menu)
        hh.setSectionsMovable(True)
        self._prefs_timer = QTimer(self)
        self._prefs_timer.setSingleShot(True)
        self._prefs_timer.setInterval(700)
        self._prefs_timer.timeout.connect(self._save_ui_preferences)
        # Seuls les redimensionnements faits à la souris sont des préférences ;
        # la colonne extensible change aussi de largeur à chaque redimensionnement
        # de fenêtre, sans qu'il y ait rien à enregistrer.
        hh.sectionResized.connect(lambda *_: self._schedule_ui_preferences() if self.app.mouseButtons() & Qt.LeftButton else None)
        hh.sectionMoved.connect(lambda *_: self._schedule_ui_preferences())
        hh.setToolTip('Clic : tri principal, second clic : inverser. Maj + clic ou clic droit : tri secondaire et colonnes.')
        self.columns_btn.clicked.connect(self._columns_menu)
        self.splitter.splitterMoved.connect(lambda *_: self._schedule_ui_preferences())
        self.btn_view_grid.clicked.connect(self._schedule_ui_preferences)
        self.btn_view_list.clicked.connect(self._schedule_ui_preferences)
        # Raccourcis clavier : recherche, export, mise à jour, désélection.
        QShortcut(QKeySequence.Find, self, activated=lambda: (self.search.setFocus(), self.search.selectAll()))
        QShortcut(QKeySequence('Ctrl+E'), self, activated=lambda: self.btn_generate.click() if self.btn_generate.isEnabled() else None)
        QShortcut(QKeySequence('Ctrl+U'), self, activated=lambda: self.update_btn.click() if self.update_btn.isEnabled() else None)
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self._clear_filament)
        self.search.setToolTip('Ctrl+F : rechercher')
        self.btn_generate.setToolTip('Ctrl+E : exporter pour NFC')
        self.update_btn.setToolTip('Ctrl+U : choisir les sources et mettre à jour')
        menu = self.menu_btn.menu()
        menu.addSeparator()
        menu.addAction('Sources de la base…', self._choose_sources)
        menu.addAction('Enregistrer les réglages…', self._export_settings)
        menu.addAction('Charger des réglages…', self._import_settings)
        menu.addAction('Vérifier une mise à jour de l’application…', self._check_app_update)

    def _brand_typed(self, text):
        # The completion popup proposes partial names; the field is never rewritten
        # while typing. An exact name (any case) or an emptied field applies at once.
        typed = text.casefold().strip()
        names = [self.brand_filter.itemText(i).casefold() for i in range(self.brand_filter.count())]
        exact = next((i for i, name in enumerate(names) if typed == name), None)
        partial = [i for i, name in enumerate(names) if i and typed and typed in name]
        if exact is not None:
            if exact != self.brand_filter.currentIndex():
                self.brand_filter.setCurrentIndex(exact)
                self._remember_brand()
        elif not typed:
            if self.brand_filter.currentIndex() != 0:
                self.brand_filter.setCurrentIndex(0)
        elif len(partial) == 1 and partial[0] != self.brand_filter.currentIndex():
            # One candidate: filter on it now, but keep the user's own text so
            # typing and erasing are never fought by the field.
            self.brand_filter.setCurrentIndex(partial[0])
            edit = self.brand_filter.lineEdit()
            edit.blockSignals(True); edit.setText(text); edit.blockSignals(False)

    # ── Barre latérale : fabricants, matières, état ───────────────────
    def _build_sidebar(self):
        side = QWidget(); side.setObjectName('sidebar')
        side.setMinimumWidth(190); side.setMaximumWidth(320)
        lay = QVBoxLayout(side); lay.setContentsMargins(0, 0, 6, 0); lay.setSpacing(6)
        def caption(text):
            label = QLabel(text); label.setObjectName('caption'); self._muted_labels.append(label); return label
        lay.addWidget(caption('FABRICANTS'))
        self.brand_search = QLineEdit(); self.brand_search.setPlaceholderText('Filtrer les fabricants…')
        self.brand_search.setClearButtonEnabled(True); self.brand_search.textChanged.connect(self._filter_brand_list)
        lay.addWidget(self.brand_search)
        self.brand_list = QListWidget(); self.brand_list.setObjectName('facets')
        self.brand_list.setUniformItemSizes(True); self.brand_list.setAlternatingRowColors(False)
        self.brand_list.itemClicked.connect(lambda item: self._choose_brand(item.data(Qt.UserRole) or '', remember=bool(item.data(Qt.UserRole))))
        lay.addWidget(self.brand_list, 3)
        lay.addWidget(caption('MATIÈRES'))
        self.family_list = QListWidget(); self.family_list.setObjectName('facets'); self.family_list.setUniformItemSizes(True)
        self.family_list.itemClicked.connect(lambda item: self._choose_family(item.data(Qt.UserRole) or ''))
        lay.addWidget(self.family_list, 2)
        lay.addWidget(caption('ÉTAT DES DONNÉES'))
        self.state_list = QListWidget(); self.state_list.setObjectName('facets'); self.state_list.setUniformItemSizes(True)
        self.state_list.itemClicked.connect(lambda item: self._choose_state(item.data(Qt.UserRole) or 'all'))
        self.state_list.setFixedHeight(4 * 26 + 6)
        lay.addWidget(self.state_list)
        self.reset_filters = QPushButton('Réinitialiser les filtres'); self.reset_filters.setObjectName('secondary')
        self.reset_filters.clicked.connect(self._reset_filters)
        lay.addWidget(self.reset_filters)
        return side

    def _fill_sidebar(self):
        if not hasattr(self, 'brand_list'): return
        rows = getattr(self, '_all_rows', [])
        brand_counts, family_counts, state_counts = {}, {}, {'all': len(rows), 'ready': 0, 'incomplete': 0, 'suspect': 0}
        for r in rows:
            if r.get('brand'): brand_counts[r['brand']] = brand_counts.get(r['brand'], 0) + 1
            if r.get('family'): family_counts[r['family']] = family_counts.get(r['family'], 0) + 1
            if r.get('ready'): state_counts['ready'] += 1
            else:
                state_counts['incomplete'] += 1
                if 'à vérifier' in r.get('quality', '').casefold(): state_counts['suspect'] += 1
        recent = [b for b in core.load_config().get('recent_brands', []) if b in brand_counts]
        self.brand_list.blockSignals(True); self.brand_list.clear()
        def add_brand(name, count, pinned=False):
            item = QListWidgetItem(('★ ' if pinned else '') + (name or 'Tous les fabricants') + f'  ({core.fmt_int(count)})')
            item.setData(Qt.UserRole, name); item.setToolTip(name or 'Toutes les marques')
            self.brand_list.addItem(item)
        add_brand('', len(rows))
        for name in recent: add_brand(name, brand_counts[name], pinned=True)
        for name in sorted(brand_counts, key=str.casefold):
            if name not in recent: add_brand(name, brand_counts[name])
        self.brand_list.blockSignals(False)
        self.family_list.blockSignals(True); self.family_list.clear()
        item = QListWidgetItem(f'Toutes les matières  ({len(rows)})'); item.setData(Qt.UserRole, ''); self.family_list.addItem(item)
        for name in sorted(family_counts, key=lambda k: (-family_counts[k], k)):
            item = QListWidgetItem(f'{name}  ({family_counts[name]})'); item.setData(Qt.UserRole, name); self.family_list.addItem(item)
        self.family_list.blockSignals(False)
        self.state_list.blockSignals(True); self.state_list.clear()
        for key, label in (('all', 'Toutes les fiches'), ('ready', 'Prêtes à exporter'), ('incomplete', 'À compléter'), ('suspect', 'À vérifier')):
            item = QListWidgetItem(f'{label}  ({state_counts[key]})'); item.setData(Qt.UserRole, key); self.state_list.addItem(item)
        self.state_list.setToolTip('Complétude des champs OpenSpool de la fiche ; ce filtre ne note pas la qualité du filament.')
        self.state_list.blockSignals(False)
        self._filter_brand_list(self.brand_search.text())
        self._sync_sidebar_selection()

    def _filter_brand_list(self, text):
        needle = core._search_key(text)
        for i in range(self.brand_list.count()):
            item = self.brand_list.item(i)
            item.setHidden(bool(needle) and bool(item.data(Qt.UserRole)) and needle not in core._search_key(item.data(Qt.UserRole)))

    def _sync_sidebar_selection(self):
        if not hasattr(self, 'brand_list'): return
        for widget, value in ((self.brand_list, self.brand_filter.currentData() or ''),
                              (self.family_list, self.material_filter.currentData() or ''),
                              (self.state_list, self.quality_filter.currentData() or 'all')):
            widget.blockSignals(True)
            for i in range(widget.count()):
                item = widget.item(i)
                if item.data(Qt.UserRole) == value:
                    widget.setCurrentItem(item); break
            else:
                widget.clearSelection()
            widget.blockSignals(False)

    def _choose_family(self, name):
        self.material_filter.setCurrentIndex(max(0, self.material_filter.findData(name)))

    def _choose_state(self, key):
        self.quality_filter.setCurrentIndex(max(0, self.quality_filter.findData(key)))

    def _choose_brand(self, name, remember=True):
        index = self.brand_filter.findData(name)
        if index >= 0:
            self.brand_filter.setCurrentIndex(index)
            if remember: self._remember_brand()

    def _remember_brand(self):
        name = self.brand_filter.currentData()
        if name:
            cfg = core.load_config()
            recent = list(dict.fromkeys([name] + cfg.get('recent_brands', [])))[:4]
            if recent != cfg.get('recent_brands', []):
                cfg['recent_brands'] = recent
                self._store_config(cfg)
                self._fill_sidebar()

    def _sort_column(self, column):
        key = self._column_keys[column]
        if not key: return
        secondary = bool(self.app.keyboardModifiers() & Qt.ShiftModifier)
        self._set_column_sort(key, secondary)

    def _set_column_sort(self, key, secondary=False):
        combo = self.sort2 if secondary else self.sort1
        direction = self.sort2_direction if secondary else self.sort1_direction
        if combo.currentData() == key:
            direction.setCurrentIndex(1 - direction.currentIndex())
        else:
            direction.blockSignals(True); direction.setCurrentIndex(0); direction.blockSignals(False)
            combo.setCurrentIndex(combo.findData(key))
        # A secondary key identical to the primary one is meaningless; any other
        # secondary key is kept when the primary changes.
        if self.sort2.currentData() and self.sort1.currentData() == self.sort2.currentData():
            self.sort2.setCurrentIndex(0)
        self._header_indicators()
        self._save_ui_preferences()

    def _header_indicators(self):
        labels = ['', 'Référence', 'Produit', 'Couleur', 'Fabricant', 'Matière', 'Ø mm', 'Masse g', 'État des données']
        for i, key in enumerate(self._column_keys):
            for rank, combo, direction in ((1, self.sort1, self.sort1_direction), (2, self.sort2, self.sort2_direction)):
                if key and combo.currentData() == key:
                    labels[i] += f'  {rank}{"↓" if direction.currentData() else "↑"}'
        self.table.setHorizontalHeaderLabels(labels)

    def _add_column_choices(self, menu):
        for col in range(1, self.table.columnCount()):
            action = menu.addAction(self.table.horizontalHeaderItem(col).text())
            action.setCheckable(True); action.setChecked(not self.table.isColumnHidden(col))
            action.triggered.connect(lambda checked, c=col: self._set_column_visible(c, checked))

    def _set_column_visible(self, col, visible):
        if not visible and sum(not self.table.isColumnHidden(i) for i in range(1, self.table.columnCount())) == 1:
            return
        self.table.setColumnHidden(col, not visible)
        self._save_ui_preferences()

    def _header_menu(self, point):
        col = self.table.horizontalHeader().logicalIndexAt(point)
        menu = QMenu(self)
        if col >= 0 and self._column_keys[col]:
            key = self._column_keys[col]
            menu.addAction('Tri principal (1)', lambda: self._set_column_sort(key))
            menu.addAction('Puis trier par cette colonne (2)', lambda: self._set_column_sort(key, True))
            menu.addAction('Retirer le tri secondaire', lambda: self.sort2.setCurrentIndex(0))
            menu.addSeparator()
        self._add_column_choices(menu.addMenu('Colonnes affichées'))
        menu.exec(self.table.horizontalHeader().mapToGlobal(point))

    def _columns_menu(self):
        menu = QMenu(self)
        self._add_column_choices(menu)
        menu.exec(self.columns_btn.mapToGlobal(self.columns_btn.rect().bottomLeft()))

    def _clear_filament(self):
        self.current_sku = None
        for widget in (self.table, self.grid):
            widget.blockSignals(True); widget.clearSelection(); widget.blockSignals(False)
        self._show_empty()
        if hasattr(self, 'inspector'): self.inspector.clear()

    def _store_config(self, cfg):
        try:
            core.save_config(cfg)
        except OSError as exc:
            self.status.showMessage(f'Réglages non enregistrés : {exc}', 10000)

    def _schedule_ui_preferences(self, *_):
        """Group bursts (typing, dragging) into one write a little later."""
        if getattr(self, '_restoring_ui', True) or not hasattr(self, '_all_rows'): return
        self._prefs_timer.start()

    def _save_ui_preferences(self, *_):
        if getattr(self, '_restoring_ui', True) or not hasattr(self, '_all_rows'): return
        if hasattr(self, '_prefs_timer'): self._prefs_timer.stop()
        cfg = core.load_config()
        cfg['ui'] = dict(brand=self.brand_filter.currentData() or '', material=self.material_filter.currentData() or '',
            quality=self.quality_filter.currentData(), search=self.search.text(), sort1=self.sort1.currentData(), sort2=self.sort2.currentData(),
            descending1=self.sort1_direction.currentData(), descending2=self.sort2_direction.currentData(), view=self.view_mode,
            header=bytes(self.table.horizontalHeader().saveState().toHex()).decode(),
            geometry=bytes(self.saveGeometry().toHex()).decode(), splitter=self.splitter.sizes())
        self._store_config(cfg)

    def _restore_ui_preferences(self):
        self._restoring_ui = True
        state = core.load_config().get('ui')
        if not isinstance(state, dict): state = {}
        for combo, key, default in ((self.brand_filter,'brand','Polymaker'),(self.material_filter,'material',''),
                (self.quality_filter,'quality','all'),(self.sort1,'sort1','product'),(self.sort2,'sort2','color_name'),
                (self.sort1_direction,'descending1',False),(self.sort2_direction,'descending2',False)):
            combo.setCurrentIndex(max(0, combo.findData(state.get(key, default))))
        self.search.setText(state.get('search',''))
        try:
            if state.get('header'): self.table.horizontalHeader().restoreState(QByteArray.fromHex(state['header'].encode()))
            if all(self.table.isColumnHidden(i) for i in range(1,9)): self.table.setColumnHidden(2,False)
            if state.get('geometry'): self.restoreGeometry(QByteArray.fromHex(state['geometry'].encode()))
            if state.get('splitter'): self.splitter.setSizes(state['splitter'])
        except (ValueError,TypeError): pass
        self._set_view_mode(state.get('view','list') if state.get('view') in ('list','grid') else 'list')
        self._apply_filter()
        self._restoring_ui = False

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            answer = QMessageBox.question(self, 'Synchronisation en cours',
                'Une synchronisation est en cours. Quitter quand même ?\n'
                'L’étape en cours est interrompue ; la base locale reste celle d’avant.',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                event.ignore(); return
            self.worker.cancel.set()
            self.worker.wait(10000)
        if self._release_worker and self._release_worker.isRunning():
            self._release_worker.wait(3000)
        self._save_ui_preferences()
        super().closeEvent(event)

    def _export_settings(self):
        self._save_ui_preferences()
        path, _ = QFileDialog.getSaveFileName(self, 'Enregistrer les réglages', 'SpoolScribe-reglages.json', 'JSON (*.json)')
        if path:
            try: core.export_settings(path)
            except (OSError,ValueError) as exc: QMessageBox.warning(self,'Réglages',str(exc))

    def _import_settings(self):
        path, _ = QFileDialog.getOpenFileName(self,'Charger des réglages','','JSON (*.json)')
        if path:
            try:
                core.import_settings(path)
                self._restore_ui_preferences()
                cfg=core.load_config()
                for combo,key in ((self.printer,'printer_profile'),(self.tag_type,'nfc_tag_type'),(self.nfc_profile,'nfc_profile')):
                    combo.blockSignals(True);combo.setCurrentIndex(max(0,combo.findData(cfg[key])));combo.blockSignals(False)
                self.tag_choice.blockSignals(True);self.tag_choice.setCurrentIndex(max(0,self.tag_choice.findData(cfg['nfc_tag_type'])));self.tag_choice.blockSignals(False)
                self.nfc_reserve.blockSignals(True);self.nfc_reserve.setMaximum(core.NFC_CAPACITIES[cfg['nfc_tag_type']]);self.nfc_reserve.setValue(cfg['nfc_reserved_bytes']);self.nfc_reserve.blockSignals(False)
                self._refresh_nfc_default_btn()
                self.extra_fields.setChecked(bool(cfg.get('show_extra_fields')))
                self._printer_changed()
                self._fill_sidebar()
                self._refresh_nfc_capacity()
            except (OSError,ValueError) as exc: QMessageBox.warning(self,'Réglages',str(exc))

    def _refresh_database_summary(self):
        if not hasattr(self,'database_btn'):return
        status = self.db.get('_update_status')
        suffix = {'complete':'à jour pour les sources choisies','partial':'mise à jour partielle','failed':'mise à jour échouée'}.get(status,'à synchroniser')
        groups=len(getattr(self,'_all_rows',[]) or [])
        self.database_btn.setText(f'Base : {len(self.db.get("_skus",{})):,} références · {groups:,} filaments · {suffix} ⓘ'.replace(',', '\u202f'))
        self.database_btn.setToolTip('État des sources, dernière synchronisation et corrections conservées')

    def _database_details(self):
        dlg=QDialog(self);dlg.setWindowTitle('Base de données');dlg.resize(640,440)
        lay=QVBoxLayout(dlg);info=QPlainTextEdit();info.setReadOnly(True)
        cfg=core.load_config()
        lines=[self.stats_label.text(),'',f'Dernière tentative : {cfg.get("last_update_attempt") or self.db.get("_last_attempt") or "aucune"}',
               f'Dernière synchronisation complète des sources choisies : {self.db.get("_last_updated","aucune")}',
               f'Fichier local : {core.DB_PATH}','', 'Le filtre « État des données » décrit les champs de la fiche, pas la qualité du filament.']
        for result in self.db.get('_source_results',[]):lines.append(f'\n{result["source"]} : {result["status"]}\n{result.get("message", "")}')
        pending=self.db.get('_pending_source_matches',{})
        lines += [f'\n{source} : {len(rows)} références à rapprocher, non ajoutées au tableau pour éviter les doublons.' for source,rows in pending.items() if rows]
        conflicts=self.stats_label.toolTip()
        if conflicts:lines+=['',conflicts]
        info.setPlainText('\n'.join(lines));lay.addWidget(info)
        close=QPushButton('Fermer');close.clicked.connect(dlg.accept);row=QHBoxLayout();row.addStretch(1);row.addWidget(close);lay.addLayout(row);dlg.exec()

    def _choose_sources(self, checked=False, *, startup=False):
        dlg=QDialog(self);dlg.setWindowTitle('Sources du catalogue');dlg.resize(650,500)
        lay=QVBoxLayout(dlg)
        note=QLabel('La base est téléchargée au premier lancement, puis actualisée au lancement selon la cadence choisie dans Paramètres (quotidienne par défaut).\nLes fabricants ont priorité sur les données communautaires ; vos corrections restent prioritaires.\nDécochez une source pour ne plus la contacter. Ses anciennes données restent disponibles.')
        note.setWordWrap(True);lay.addWidget(note)
        cfg=core.load_config();selected=cfg['selected_sources'];checks={}
        last={r['source']:r for r in self.db.get('_source_results',[])}
        labels={script:label for script,label,_ in core.UPDATE_PIPELINE}
        for key,meta in core.SOURCE_GROUPS.items():
            check=QCheckBox(meta['name']);check.setChecked(key in selected);check.setToolTip(meta['detail']);lay.addWidget(check)
            results=[last[labels[s]] for s in meta['scripts'] if labels.get(s) in last]
            status=''
            if results:
                worst=min(results,key=lambda r:(r.get('ok'),r.get('status')!='unchanged'))
                state={'changed':'mise à jour','unchanged':'inchangée','unavailable':'injoignable','partial':'partielle','error':'en erreur','cancelled':'annulée'}.get(worst.get('status'),worst.get('status') or '—')
                status=f'   ·   dernier résultat : {state}'+(f' — {str(worst.get("message",""))[:90]}' if worst.get('message') and not worst.get('ok') else '')
            detail=QLabel(meta['detail']+status);detail.setWordWrap(True);detail.setObjectName('fieldvalue');lay.addWidget(detail);checks[key]=check
        error=QLabel();lay.addWidget(error)
        if self._last_report:
            report_btn=QPushButton('Voir le rapport de la dernière synchronisation');report_btn.clicked.connect(lambda:self._show_sync_report(*self._last_report));lay.addWidget(report_btn)
        buttons=QDialogButtonBox();run=buttons.addButton('Synchroniser maintenant',QDialogButtonBox.AcceptRole)
        save=buttons.addButton('Enregistrer seulement',QDialogButtonBox.ActionRole)
        cancel=buttons.addButton('Annuler',QDialogButtonBox.RejectRole)
        state={'download':False}
        def accept(download):
            keys=[k for k,c in checks.items() if c.isChecked()]
            if not keys:error.setText('Choisissez au moins une source.');return
            cfg=core.load_config();cfg['selected_sources']=keys;cfg['network_consent']=True;cfg['network_sources_revision']=core.NETWORK_SOURCES_REVISION
            try:core.save_config(cfg)
            except OSError as exc:error.setText(str(exc));return
            state['download']=download;dlg.accept()
        run.clicked.connect(lambda:accept(True));save.clicked.connect(lambda:accept(False));cancel.clicked.connect(dlg.reject);lay.addWidget(buttons)
        if dlg.exec()==QDialog.Accepted and state['download']:self._start_update(manual=True)

    # ── Rapport de synchronisation ────────────────────────────────────
    def _snapshot_stats(self):
        skus=self.db.get('_skus',{})
        by_source={}
        for e in skus.values():by_source[e.get('source') or 'Catalogue historique']=by_source.get(e.get('source') or 'Catalogue historique',0)+1
        conflicts=list(self.db.get('_source_conflicts',[]))
        for values in self.db.get('_source_conflicts_by_source',{}).values():conflicts.extend(values)
        pending=sum(len(v) for v in self.db.get('_pending_source_matches',{}).values())
        return dict(references=len(skus),products=len(self.db.get('_products',{})),brands=len(self.db.get('_brands',{})),
                    by_source=by_source,conflicts=len(set(conflicts)),pending=pending,ready=sum(1 for r in getattr(self,'_sku_rows',[]) if r.get('ready')))

    def _show_sync_report(self,results,before,after=None):
        after=after or self._snapshot_stats()
        self._last_report=(results,before,after)
        dlg=QDialog(self);dlg.setWindowTitle('Rapport de synchronisation');dlg.resize(760,520)
        lay=QVBoxLayout(dlg)
        status=core.update_status(results)
        cancelled=any(r.status=='cancelled' for r in results)
        headline={'complete':'Synchronisation complète','partial':'Synchronisation partielle','failed':'Synchronisation en échec'}[status]
        if cancelled:headline='Synchronisation annulée'
        title=QLabel(headline);font=title.font();font.setPointSize(font.pointSize()+3);font.setBold(True);title.setFont(font);lay.addWidget(title)
        delta=lambda key:after[key]-before[key]
        summary=(f"Références : {core.fmt_int(after['references'])} ({delta('references'):+d}) · "
                 f"filaments prêts à exporter : {core.fmt_int(after['ready'])} ({delta('ready'):+d}) · "
                 f"fabricants : {after['brands']} ({delta('brands'):+d})\n"
                 f"Valeurs locales ou fabricant conservées face à une source : {after['conflicts']} · "
                 f"rapprochements en attente (non ajoutés, pas de doublon) : {after['pending']}\n"
                 'Priorité appliquée : corrections locales > fabricants > Open Filament Database > SpoolmanDB > données anciennes.')
        summary_label=QLabel(summary);summary_label.setWordWrap(True);lay.addWidget(summary_label)
        table=QTableWidget(len(results),4);table.setHorizontalHeaderLabels(['Source','Résultat','Références','Détail'])
        table.verticalHeader().setVisible(False);table.setEditTriggers(QTableWidget.NoEditTriggers);table.setSelectionMode(QTableWidget.NoSelection)
        state_labels={'changed':'✔ mise à jour','unchanged':'✔ inchangée','unavailable':'⚠ injoignable','partial':'⚠ partielle','error':'✖ erreur','cancelled':'— annulée'}
        source_of={label:key for key,meta in core.SOURCE_GROUPS.items() for script,label,_ in core.UPDATE_PIPELINE if script in meta['scripts']}
        source_names={'polymaker':'Polymaker officiel','ofd':'Open Filament Database','spoolman':'SpoolmanDB','bambu':'Bambu Lab officiel','sunlu':'SUNLU officiel'}
        for row,r in enumerate(results):
            key=source_of.get(r.label);name=source_names.get(key)
            count='' if not name else f"{core.fmt_int(after['by_source'].get(name,0))} ({after['by_source'].get(name,0)-before['by_source'].get(name,0):+d})"
            message=(r.stderr or '').strip().replace('\r','')
            for col,text in enumerate((r.label,state_labels.get(r.status,r.status or '—'),count,message.splitlines()[-1][:160] if message else '')):
                item=QTableWidgetItem(text);item.setToolTip(message);table.setItem(row,col,item)
        for col,width in ((0,230),(1,130),(2,120)):table.setColumnWidth(col,width)
        table.horizontalHeader().setSectionResizeMode(3,QHeaderView.Stretch);lay.addWidget(table,1)
        hint=QLabel('Une source injoignable ou trop lente conserve les données locales ; relancez plus tard. '
                    'Les rapprochements incertains restent hors du tableau tant qu’une référence fabricant ne les confirme pas.')
        hint.setWordWrap(True);hint.setObjectName('fieldvalue');lay.addWidget(hint)
        close=QPushButton('Fermer');close.clicked.connect(dlg.accept)
        close_row=QHBoxLayout();close_row.addStretch(1);close_row.addWidget(close);lay.addLayout(close_row)
        dlg.show()

    def _maybe_auto_update(self):
        if not self.isVisible() or core.db_restored_this_session():return
        if core.has_network_consent():
            if not self.db.get('_skus') or core.update_due():
                self._start_update()
            else:
                self.status.showMessage('Base déjà actualisée récemment ; « Mettre à jour » force une synchronisation.',8000)
        elif not core.load_config().get('network_consent') is False:
            self._choose_sources(startup=True)
        else:
            self.status.showMessage('Synchronisation au démarrage désactivée par le refus réseau. Ouvrez « Sources » pour la réactiver.',12000)

    def _build_export_assistant(self, layout):
        """Page « Mon matériel » : imprimante/lecteur, firmware, étiquette."""
        cfg=core.load_config()
        printer_id,firmware_id=printer_profiles.resolve(cfg.get('printer_profile'),cfg.get('printer_firmware'))
        layout.addWidget(QLabel('Imprimante ou lecteur'))
        self.printer=QComboBox();self._fill_printer_combo()
        self.printer.setCurrentIndex(max(0,self.printer.findData(printer_id)));layout.addWidget(self.printer)
        self.reader_info=QLabel();self.reader_info.setWordWrap(True);self.reader_info.setObjectName('fieldvalue');layout.addWidget(self.reader_info)
        fw_row=QHBoxLayout();self.firmware_label=QLabel('Firmware');fw_row.addWidget(self.firmware_label)
        self.firmware=QComboBox();fw_row.addWidget(self.firmware,1);layout.addLayout(fw_row)
        self._fill_firmware_combo(printer_id,firmware_id)
        self.printer_help=QLabel();self.printer_help.setWordWrap(True);layout.addWidget(self.printer_help)
        self.extra_fields=QCheckBox('Afficher aussi les références, la provenance et la masse');self.extra_fields.hide()  # conservé pour les réglages importés
        row=QHBoxLayout();self.tag_label=QLabel('Étiquette achetée');row.addWidget(self.tag_label)
        self.tag_choice=QComboBox();self.tag_choice.addItem('NTAG216 — recommandé','NTAG216');self.tag_choice.addItem('NTAG215 — petit format','NTAG215')
        self.tag_choice.setCurrentIndex(max(0,self.tag_choice.findData(core.nfc_defaults(cfg)['tag_type'])));row.addWidget(self.tag_choice,1)
        self.nfc_default_btn=QToolButton();self.nfc_default_btn.setAccessibleName('Définir ce choix d’étiquette par défaut');row.addWidget(self.nfc_default_btn)
        self.advanced_toggle=QToolButton();self.advanced_toggle.setText('Réglages avancés');self.advanced_toggle.setCheckable(True);row.addWidget(self.advanced_toggle);layout.addLayout(row)

    def _fill_printer_combo(self):
        current=self.printer.currentData()
        self.printer.blockSignals(True);self.printer.clear()
        catalogue=printer_profiles.load_catalogue()
        for group in printer_profiles.GROUP_ORDER:
            members=[(key,p) for key,p in PROFILES.items() if p['group']==group]
            if not members:continue
            self.printer.addItem('— '+catalogue['groups'].get(group,group)+' —',None)
            self.printer.model().item(self.printer.count()-1).setEnabled(False)
            for key,profile in members:self.printer.addItem('    '+profile['label'],key)
        if current:self.printer.setCurrentIndex(max(0,self.printer.findData(current)))
        self.printer.blockSignals(False)

    def _fill_firmware_combo(self,printer_id,firmware_id=None):
        self.firmware.blockSignals(True);self.firmware.clear()
        for fw in PROFILES[printer_id]['firmwares']:
            self.firmware.addItem(fw['label']+(' · lit OpenSpool' if fw['openspool'] else ''),fw['id'])
        self.firmware.setCurrentIndex(max(0,self.firmware.findData(firmware_id)))
        several=self.firmware.count()>1
        self.firmware.setVisible(several);self.firmware_label.setVisible(several)
        self.firmware.blockSignals(False)

    def _build_hardware_dialog(self):
        self.hardware_dialog=QDialog(self);self.hardware_dialog.setWindowTitle('Mon matériel');self.hardware_dialog.setMinimumWidth(560)
        lay=QVBoxLayout(self.hardware_dialog)
        intro=QLabel('Choisissez l’imprimante ou le lecteur qui lira l’étiquette, puis l’étiquette achetée. '
                     'SpoolScribe n’écrit pas le tag : un logiciel d’écriture NFC s’en charge.')
        intro.setWordWrap(True);lay.addWidget(intro)
        lay.addWidget(self.hardware_page)
        foot=QHBoxLayout()
        self.printers_origin=QLabel();self.printers_origin.setObjectName('fieldvalue');foot.addWidget(self.printers_origin,1)
        self.btn_update_printers=QPushButton('Mettre à jour la liste des imprimantes…');self.btn_update_printers.clicked.connect(self._update_printers)
        foot.addWidget(self.btn_update_printers);lay.addLayout(foot)
        close=QPushButton('Fermer');close.clicked.connect(self.hardware_dialog.accept)
        close_row=QHBoxLayout();close_row.addStretch(1);close_row.addWidget(close);lay.addLayout(close_row)
        self._refresh_printers_origin()

    def _refresh_printers_origin(self):
        catalogue=printer_profiles.load_catalogue()
        origin='liste téléchargée' if catalogue.get('_origin')=='user' else 'liste embarquée'
        self.printers_origin.setText(f'Imprimantes : {origin}, version du {catalogue.get("updated","?")}')

    def _open_hardware(self):
        self.hardware_dialog.show();self.hardware_dialog.raise_();self.hardware_dialog.activateWindow()

    def _update_printers(self):
        if core.load_config().get('network_consent') is not True:
            QMessageBox.information(self,'Liste des imprimantes','Accordez d’abord l’autorisation réseau (Synchroniser → sources) pour contacter GitHub.');return
        from scripts import official_sources
        try:
            raw=official_sources.fetch(printer_profiles.PRINTERS_URL,512*1024)
            catalogue=printer_profiles.install_catalogue(raw)
        except Exception as exc:
            QMessageBox.warning(self,'Liste des imprimantes',f'Liste non mise à jour : {exc}');return
        self._fill_printer_combo();self._printer_changed();self._refresh_printers_origin()
        self.status.showMessage(f'Liste des imprimantes du {catalogue.get("updated","?")} installée ({len(catalogue["printers"])} entrées).',8000)

    def _references_text(self,sku):
        rows=[r for r in getattr(self,'_all_rows',[]) if r['sku']==sku]
        variants=rows[0].get('variants') if rows and rows[0].get('variants') else None
        if not variants:
            entry=self.db['_skus'].get(sku,{})
            parts=[sku]
            if entry.get('manufacturer_sku') and entry['manufacturer_sku']!=sku:parts.append(f'réf. fabricant {entry["manufacturer_sku"]}')
            if entry.get('weight'):parts.append(f'{entry["weight"]:g} g')
            return ' · '.join(parts)
        lines=[]
        for v in variants:
            ref=v['reference']
            bits=[ref if not ref.startswith(('OFD-','SMDB-')) else ('source '+ref.split('-')[0])]
            if v.get('weight'):bits.append(f'{v["weight"]:g} g')
            if v.get('diameter'):bits.append(f'Ø {v["diameter"]:g} mm')
            if not v.get('ready'):bits.append('à compléter')
            lines.append(' · '.join(bits))
        hexes={v.get('hex') for v in variants if v.get('hex')}
        text='\n'.join(lines)
        if len(hexes)>1:text+='\n⚠ Teintes différentes selon la source ; la mieux documentée est affichée.'
        return text

    def _wire_export_assistant(self):
        self.advanced_toggle.toggled.connect(self.nfc_advanced.setVisible)
        self.tag_choice.currentIndexChanged.connect(lambda: self.tag_type.setCurrentIndex(self.tag_type.findData(self.tag_choice.currentData())))
        self.tag_type.currentIndexChanged.connect(lambda: self.tag_choice.setCurrentIndex(self.tag_choice.findData(self.tag_type.currentData())))
        self._firmware_printer=None
        self.printer.currentIndexChanged.connect(self._printer_changed)
        self.firmware.currentIndexChanged.connect(self._printer_changed)
        self.nfc_default_btn.clicked.connect(self._save_nfc_default)
        self._printer_changed()
        self._refresh_nfc_default_btn()

    def _current_nfc_choice(self):
        return dict(tag_type=self.tag_type.currentData(),profile=self.nfc_profile.currentData(),reserved_bytes=self.nfc_reserve.value())

    @staticmethod
    def _describe_nfc(choice):
        labels={'auto':'essentiel recommandé','essential':'essentiel','full':'complet'}
        text=f"{choice['tag_type']} · {labels[choice['profile']]}"
        return text+(f" · réserve {choice['reserved_bytes']} o" if choice['reserved_bytes'] else '')

    def _refresh_nfc_default_btn(self):
        if not hasattr(self,'nfc_default_btn') or not hasattr(self,'nfc_reserve'):return
        current,saved=self._current_nfc_choice(),core.nfc_defaults()
        is_default=current==saved
        self.nfc_default_btn.setText('Par défaut ✓' if is_default else 'Définir par défaut')
        self.nfc_default_btn.setEnabled(not is_default)
        self.nfc_default_btn.setToolTip(f'Choix par défaut : {self._describe_nfc(saved)}' if is_default else
            f'Enregistrer {self._describe_nfc(current)} pour les prochains exports et lancements.\n'
            f'Défaut actuel : {self._describe_nfc(saved)}. Sans enregistrement, ce choix ne vaut que pour cette session.')

    def _save_nfc_default(self):
        try:
            saved=core.save_nfc_defaults(**self._current_nfc_choice())
        except (OSError,ValueError) as exc:
            self.status.showMessage(f'Choix par défaut non enregistré : {exc}',8000);return
        self.status.showMessage(f'Choix NFC par défaut : {self._describe_nfc(saved)}.',6000)
        self._refresh_nfc_default_btn()

    def _printer_changed(self,*_):
        printer_id=self.printer.currentData() or printer_profiles.DEFAULT
        if self.sender() is self.printer or self.firmware.count()==0 or self._firmware_printer!=printer_id:
            self._fill_firmware_combo(printer_id,core.load_config().get('printer_firmware') if self._firmware_printer is None else None)
        self._firmware_printer=printer_id
        cfg=core.load_config();cfg['printer_profile']=printer_id;cfg['printer_firmware']=self.firmware.currentData()
        if hasattr(self,'status'):self._store_config(cfg)
        profile=PROFILES[printer_id];fw=printer_profiles.firmware(printer_id,self.firmware.currentData())
        self.reader_info.setText(f'Lecteur : {profile.get("reader") or "aucun"}')
        self.printer_help.setText(profile['help']+(('\n'+fw['notes']) if fw.get('notes') else ''))
        self._printer_field_help()
        if hasattr(self,'btn_generate'):self._refresh_nfc_capacity()

    def _printer_field_help(self):
        if not hasattr(self,'printer'):return
        profile=PROFILES[self.printer.currentData()]
        labels={'Nozzle':'Buse','Bed':'Plateau','Type':'Matière','SKU':'Référence interne'}
        for row in range(self.fields.rowCount()):
            item=self.fields.itemAtPosition(row,0)
            if not item:continue
            label=item.widget();key=label.property('field_key') or label.text();label.setProperty('field_key',key)
            hint=profile.get('fields',{}).get(key,'Information facultative de la fiche')
            label.setText(labels.get(key,key) + (' *' if 'requis' in hint else ''));label.setToolTip(hint)
            if key in self._field_widgets:self._field_widgets[key].setToolTip(hint)
        self.card.setToolTip('Survolez un champ pour connaître son usage pour cette imprimante. Les températures restent à adapter au plateau et au trancheur.')

    def _toggle_extra_fields(self, checked):
        pass  # références et provenance sont toujours visibles dans la fiche

    def _can_export_for_printer(self):
        return printer_profiles.can_export(self.printer.currentData() or printer_profiles.DEFAULT,self.firmware.currentData())

    def _nfc_options(self):
        payload=self._build_payload()
        return core.recommended_nfc(payload,self.tag_type.currentData(),self.nfc_profile.currentData(),self.nfc_reserve.value())

    def _refresh_nfc_capacity(self):
        if not hasattr(self,'printer'):return
        can=self._can_export_for_printer()
        printer_id=self.printer.currentData() or printer_profiles.DEFAULT
        # Without an OpenSpool export, the tag controls are hidden, not merely greyed.
        for widget in (self.tag_label,self.tag_choice,self.nfc_default_btn,self.advanced_toggle):widget.setVisible(can)
        self.nfc_advanced.setVisible(can and self.advanced_toggle.isChecked())
        summary='Pour : '+printer_profiles.describe(printer_id,self.firmware.currentData())
        if can:summary+=f' · {self.tag_choice.currentData()} · {self._describe_nfc(self._current_nfc_choice()).split(" · ",1)[1]}'
        else:summary+=' · pas d’export OpenSpool pour ce matériel'
        if hasattr(self,'hardware_summary'):self.hardware_summary.setText(summary)
        self.btn_generate.setEnabled(can and bool(self.current_sku) and not (self.worker and self.worker.isRunning()))
        if hasattr(self,'btn_inspect'):self.btn_inspect.setEnabled(can and bool(self.current_sku))
        if not can:
            self.nfc_note.setText('Consultez la fiche pour préparer votre profil de trancheur. Aucun tag propriétaire n’est généré.')
            self.nfc_capacity.setText('Export NFC indisponible pour ce système.');return
        if not self.current_sku:return
        try:
            payload=self._build_payload()
            if payload is None:return
            options=self._nfc_options();text=core.serialize_openspool(payload,**options)
            size=core.nfc_size(text,tag_type=options['tag_type'],reserved_bytes=options['reserved_bytes'])
            self.nfc_note.setText('Format complet : descriptifs et logo ajoutés au tag ; plus volumineux, sans effet sur l’impression.' if options['profile']=='full' else
                'Format essentiel : matière, couleurs, températures, diamètre et densité — tout ce que l’imprimante lit. La fiche complète reste dans la base.')
            self.nfc_capacity.setText(f'Compatible avec votre {options["tag_type"]} · marge {size.remaining_bytes} octets. '
                'Le logiciel d’écriture peut ajouter des données : contrôlez sa taille finale avant écriture.')
        except (ValueError,OSError) as exc:
            self.nfc_note.setText('Complétez les données signalées avant l’export.')
            self.nfc_capacity.setText(str(exc))

    def _transparent_logo(self, pixmap):
        # Keep alpha; a subtle contrasting outline makes white/dark logos visible
        # without adding a rectangular background or recoloring their artwork.
        image=pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
        # A uniform white/black raster margin is background, not a contrast
        # plate. Remove only its edge-connected pixels in the rendered copy.
        corners=[image.pixelColor(x,y) for x,y in ((0,0),(image.width()-1,0),(0,image.height()-1),(image.width()-1,image.height()-1))]
        bg=corners[0]
        if all(c==bg and c.alpha()==255 for c in corners) and (bg.lightness()>245 or bg.lightness()<10):
            work=image.copy();todo=[(x,0) for x in range(image.width())]+[(x,image.height()-1) for x in range(image.width())]
            todo += [(0,y) for y in range(image.height())]+[(image.width()-1,y) for y in range(image.height())]
            seen=set();removed=0
            while todo:
                x,y=todo.pop()
                if (x,y) in seen or not 0<=x<image.width() or not 0<=y<image.height():continue
                seen.add((x,y));c=image.pixelColor(x,y)
                if c.alpha()!=255 or max(abs(c.red()-bg.red()),abs(c.green()-bg.green()),abs(c.blue()-bg.blue()))>2:continue
                work.setPixelColor(x,y,QColor(0,0,0,0));removed+=1
                todo.extend(((x-1,y),(x+1,y),(x,y-1),(x,y+1)))
            if 0<removed<image.width()*image.height()*0.98:image=work
        mask=image.copy(); dark=getattr(self,'_tok',{}).get('dark',False)
        ink=QColor('#eeeeee' if dark else '#404040')
        for y in range(mask.height()):
            for x in range(mask.width()):
                c=mask.pixelColor(x,y);ink.setAlpha(round(c.alpha()*0.4));mask.setPixelColor(x,y,ink)
        # Compose in device pixels: the images and the result share the same
        # device pixel ratio, so a Retina logo keeps its full size.
        dpr=pixmap.devicePixelRatio() or 1.0
        pad=max(1,round(2*dpr))
        image.setDevicePixelRatio(1.0);mask.setDevicePixelRatio(1.0)
        result=QPixmap(image.width()+2*pad,image.height()+2*pad);result.fill(Qt.transparent)
        painter=QPainter(result)
        for dx,dy in ((0,pad),(2*pad,pad),(pad,0),(pad,2*pad)):painter.drawImage(dx,dy,mask)
        painter.drawImage(pad,pad,image);painter.end();result.setDevicePixelRatio(dpr);return result

    def _check_app_update(self):
        if self._release_worker and self._release_worker.isRunning():return
        if core.load_config().get('network_consent') is False:
            QMessageBox.information(self,'Mise à jour application','L’autorisation réseau a été retirée. Réactivez-la dans « Sources de la base » pour contacter GitHub.');return
        self.status.showMessage('Vérification de la version publiée sur GitHub…')
        self._release_worker=ReleaseWorker(self);self._release_worker.ready.connect(self._release_result);self._release_worker.start()

    def _release_result(self, result):
        if result.get('error'):QMessageBox.warning(self,'Mise à jour application',result['error']);return
        if not result['newer']:
            QMessageBox.information(self,'Application',f'Version locale : {core.APP_VERSION}\nVersion stable publiée : {result["version"]}\nAucune version plus récente publiée.');return
        box=QMessageBox(self);box.setWindowTitle('Nouvelle version disponible');box.setText(f'SpoolScribe {result["version"]} est disponible.\nTéléchargez le paquet de votre système et remplacez l’application. Vos données et réglages restent dans le dossier utilisateur.')
        download=box.addButton('Ouvrir le téléchargement officiel',QMessageBox.AcceptRole);box.addButton('Plus tard',QMessageBox.RejectRole);box.exec()
        if box.clickedButton()==download:QDesktopServices.openUrl(QUrl(result['url']))

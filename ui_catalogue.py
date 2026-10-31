"""Catalogue interaction, persistent workspace settings and guided exports."""
import json
from pathlib import Path
from PySide6.QtCore import Qt, QByteArray, QThread, Signal, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QPixmap, QPainter, QColor, QImage
from PySide6.QtWidgets import (QTableWidget, QAbstractItemView, QCompleter, QMenu, QDialog, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QToolButton, QCheckBox, QDialogButtonBox, QComboBox,
    QFileDialog, QMessageBox, QPlainTextEdit)
import core
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
        self.brand_filter.setEditable(True)
        self.brand_filter.setInsertPolicy(QComboBox.NoInsert)
        self.brand_filter.lineEdit().setPlaceholderText('Tapez 3–4 lettres du fabricant…')
        self.brand_filter.lineEdit().setClearButtonEnabled(True)
        self.brand_filter.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.brand_filter.completer().setFilterMode(Qt.MatchContains)
        self.brand_filter.completer().setCaseSensitivity(Qt.CaseInsensitive)
        self.brand_filter.lineEdit().textEdited.connect(self._brand_typed)
        self.brand_filter.activated.connect(lambda *_: self._remember_brand())
        self.quick_brands = QHBoxLayout()
        self.quick_brands.addWidget(QLabel('Accès rapides'))
        self.centralWidget().layout().insertLayout(2, self.quick_brands)
        self._fill_quick_brands()
        hh = self.table.horizontalHeader()
        hh.setContextMenuPolicy(Qt.CustomContextMenu)
        hh.customContextMenuRequested.connect(self._header_menu)
        hh.setSectionsMovable(True)
        hh.sectionResized.connect(lambda *_: self._save_ui_preferences())
        hh.sectionMoved.connect(lambda *_: self._save_ui_preferences())
        hh.setToolTip('Clic : croissant/décroissant. Clic droit : tri principal, secondaire et colonnes.')
        self.columns_btn.clicked.connect(self._columns_menu)
        self.splitter.splitterMoved.connect(lambda *_: self._save_ui_preferences())
        self.btn_view_grid.clicked.connect(self._save_ui_preferences)
        self.btn_view_list.clicked.connect(self._save_ui_preferences)
        menu = self.menu_btn.menu()
        menu.addSeparator()
        menu.addAction('Sources de la base…', self._choose_sources)
        menu.addAction('Enregistrer les réglages…', self._export_settings)
        menu.addAction('Charger des réglages…', self._import_settings)
        menu.addAction('Vérifier une mise à jour de l’application…', self._check_app_update)

    def _brand_typed(self, text):
        # The completion popup handles partial names; never add arbitrary brands.
        matches = [i for i in range(self.brand_filter.count()) if text.casefold() in self.brand_filter.itemText(i).casefold()]
        if len(matches) == 1:
            self.brand_filter.setCurrentIndex(matches[0])
        elif not text:
            self.brand_filter.setCurrentIndex(0)

    def _fill_quick_brands(self):
        while self.quick_brands.count() > 1:
            item = self.quick_brands.takeAt(1)
            if item.widget(): item.widget().deleteLater()
        names = list(dict.fromkeys(['Polymaker'] + core.load_config().get('recent_brands', []) + ['Bambu Lab', 'Prusament', 'SUNLU']))[:5]
        for name in names:
            button = QPushButton(name)
            button.setFlat(True)
            button.clicked.connect(lambda checked=False, n=name: self._choose_brand(n))
            self.quick_brands.addWidget(button)
        self.quick_brands.addStretch()

    def _choose_brand(self, name):
        index = self.brand_filter.findData(name)
        if index >= 0:
            self.brand_filter.setCurrentIndex(index)
            self._remember_brand()

    def _remember_brand(self):
        name = self.brand_filter.currentData()
        if name:
            cfg = core.load_config()
            cfg['recent_brands'] = list(dict.fromkeys([name] + cfg.get('recent_brands', [])))[:4]
            self._store_config(cfg)
            self._fill_quick_brands()

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
        if self.sort1.currentData() == self.sort2.currentData():
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

    def _save_ui_preferences(self, *_):
        if getattr(self, '_restoring_ui', True) or not hasattr(self, '_all_rows'): return
        cfg = core.load_config()
        cfg['ui'] = dict(brand=self.brand_filter.currentData() or '', material=self.material_filter.currentData() or '',
            quality=self.quality_filter.currentData(), search=self.search.text(), sort1=self.sort1.currentData(), sort2=self.sort2.currentData(),
            descending1=self.sort1_direction.currentData(), descending2=self.sort2_direction.currentData(), view=self.view_mode,
            header=bytes(self.table.horizontalHeader().saveState().toHex()).decode(),
            geometry=bytes(self.saveGeometry().toHex()).decode(), splitter=self.splitter.sizes())
        self._store_config(cfg)

    def _restore_ui_preferences(self):
        self._restoring_ui = True
        state = core.load_config().get('ui', {})
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
                self.nfc_reserve.setValue(cfg['nfc_reserved_bytes'])
                self._refresh_nfc_capacity()
            except (OSError,ValueError) as exc: QMessageBox.warning(self,'Réglages',str(exc))

    def _refresh_database_summary(self):
        if not hasattr(self,'database_btn'):return
        status = self.db.get('_update_status')
        suffix = {'complete':'à jour pour les sources choisies','partial':'mise à jour partielle','failed':'mise à jour échouée'}.get(status,'à synchroniser')
        self.database_btn.setText(f'Base : {len(self.db.get("_skus",{})):,} références · {suffix} ⓘ')
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
        close=QDialogButtonBox(QDialogButtonBox.Close);close.rejected.connect(dlg.reject);lay.addWidget(close);dlg.exec()

    def _choose_sources(self, checked=False, *, startup=False):
        dlg=QDialog(self);dlg.setWindowTitle('Sources du catalogue');dlg.resize(650,500)
        lay=QVBoxLayout(dlg)
        note=QLabel('La base est téléchargée au premier lancement, puis actualisée au lancement selon la cadence choisie dans Paramètres (quotidienne par défaut).\nLes fabricants ont priorité sur les données communautaires ; vos corrections restent prioritaires.\nDécochez une source pour ne plus la contacter. Ses anciennes données restent disponibles.')
        note.setWordWrap(True);lay.addWidget(note)
        cfg=core.load_config();selected=cfg['selected_sources'];checks={}
        for key,meta in core.SOURCE_GROUPS.items():
            check=QCheckBox(meta['name']);check.setChecked(key in selected);check.setToolTip(meta['detail']);lay.addWidget(check)
            detail=QLabel(meta['detail']);detail.setWordWrap(True);lay.addWidget(detail);checks[key]=check
        error=QLabel();lay.addWidget(error)
        buttons=QDialogButtonBox();run=buttons.addButton('Télécharger et enregistrer',QDialogButtonBox.AcceptRole)
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
        if dlg.exec()==QDialog.Accepted and state['download']:self._start_update()

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
        cfg=core.load_config()
        layout.addWidget(QLabel('Utiliser ce filament avec'))
        self.printer=QComboBox()
        for key,profile in PROFILES.items():self.printer.addItem(profile['label'],key)
        self.printer.setCurrentIndex(max(0,self.printer.findData(cfg.get('printer_profile','u1'))));layout.addWidget(self.printer)
        self.printer_help=QLabel();self.printer_help.setWordWrap(True);layout.addWidget(self.printer_help)
        self.extra_fields=QCheckBox('Afficher aussi les références, la provenance et la masse')
        self.extra_fields.setChecked(cfg.get('show_extra_fields',False))
        self.extra_fields.toggled.connect(self._toggle_extra_fields)
        layout.addWidget(self.extra_fields)
        row=QHBoxLayout();row.addWidget(QLabel('Étiquette achetée'))
        self.tag_choice=QComboBox();self.tag_choice.addItem('NTAG216 — recommandé','NTAG216');self.tag_choice.addItem('NTAG215 — petit format','NTAG215')
        self.tag_choice.setCurrentIndex(max(0,self.tag_choice.findData(cfg.get('nfc_tag_type','NTAG216'))));row.addWidget(self.tag_choice,1)
        self.advanced_toggle=QToolButton();self.advanced_toggle.setText('Réglages avancés');self.advanced_toggle.setCheckable(True);row.addWidget(self.advanced_toggle);layout.addLayout(row)

    def _wire_export_assistant(self):
        self.advanced_toggle.toggled.connect(self.nfc_advanced.setVisible)
        self.tag_choice.currentIndexChanged.connect(lambda: self.tag_type.setCurrentIndex(self.tag_type.findData(self.tag_choice.currentData())))
        self.tag_type.currentIndexChanged.connect(lambda: self.tag_choice.setCurrentIndex(self.tag_choice.findData(self.tag_type.currentData())))
        self.printer.currentIndexChanged.connect(self._printer_changed)
        self._printer_changed()

    def _printer_changed(self):
        cfg=core.load_config();cfg['printer_profile']=self.printer.currentData()
        if hasattr(self,'status'):self._store_config(cfg)
        self.printer_help.setText(PROFILES[self.printer.currentData()]['help'])
        self._printer_field_help()
        self._toggle_extra_fields(self.extra_fields.isChecked())
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
        optional={'Produit','SKU','Source','SKU fabricant','Masse'}
        for row in range(self.fields.rowCount()):
            label=self.fields.itemAtPosition(row,0)
            value=self.fields.itemAtPosition(row,1)
            if label and value:
                key=label.widget().property('field_key') or label.widget().text()
                visible=checked or key not in optional
                label.widget().setVisible(visible);value.widget().setVisible(visible)
        if hasattr(self,'status'):
            cfg=core.load_config();cfg['show_extra_fields']=checked;self._store_config(cfg)

    def _can_export_for_printer(self):
        return PROFILES[self.printer.currentData()]['nfc']

    def _nfc_options(self):
        payload=self._build_payload()
        return core.recommended_nfc(payload,self.tag_type.currentData(),self.nfc_profile.currentData(),self.nfc_reserve.value())

    def _refresh_nfc_capacity(self):
        if not hasattr(self,'printer'):return
        can=self._can_export_for_printer()
        self.printer_help.setText(PROFILES[self.printer.currentData()]['help'] + ('\n* Requis pour identifier le filament. SpoolScribe valide aussi les températures, le diamètre et la densité avant export.' if self.printer.currentData()=='u1' else ''))
        self.tag_choice.setEnabled(can);self.advanced_toggle.setEnabled(can)
        self.btn_generate.setEnabled(can and bool(self.current_sku) and not (self.worker and self.worker.isRunning()))
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
        result=QPixmap(pixmap.width()+4,pixmap.height()+4);result.fill(Qt.transparent)
        painter=QPainter(result)
        for dx,dy in ((0,2),(4,2),(2,0),(2,4)):painter.drawImage(dx,dy,mask)
        painter.drawImage(2,2,image);painter.end();result.setDevicePixelRatio(pixmap.devicePixelRatio());return result

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

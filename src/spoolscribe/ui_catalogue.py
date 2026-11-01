"""Catalogue interaction, persistent workspace settings and guided exports."""
from PySide6.QtCore import Qt, QByteArray, QThread, Signal, QUrl, QTimer, QSize
from PySide6.QtGui import QDesktopServices, QPixmap, QPainter, QColor, QImage, QKeySequence, QShortcut, QIcon
from PySide6.QtWidgets import (QTableWidget, QListWidget, QListWidgetItem, QCompleter, QMenu, QDialog, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QToolButton, QCheckBox, QDialogButtonBox, QComboBox,
    QFileDialog, QMessageBox, QPlainTextEdit, QLineEdit, QWidget, QScrollArea, QFrame, QTableWidgetItem, QHeaderView, QSizePolicy, QStackedWidget, QGridLayout)
from . import core
from .i18n import tr
from . import printer_profiles
from .printer_profiles import PROFILES
from .ui_widgets import WrapLabel, PrinterCard, FavoriteBrandList, PrinterPicker, report_metrics, CONTROL_HEIGHT


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
    favoriteRequested=Signal(str)
    def mousePressEvent(self, event):
        item = self.itemAt(event.position().toPoint())
        if item and event.button()==Qt.LeftButton:
            rect=self.visualItemRect(item)
            if event.position().x()>rect.right()-34 and event.position().y()<rect.top()+32:
                self.favoriteRequested.emit(item.data(Qt.UserRole));return
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
        self.brand_filter.lineEdit().setPlaceholderText(tr('Tapez 3–4 lettres du fabricant…'))
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
        hh.setToolTip(tr('Clic : tri principal, second clic : inverser. Maj + clic ou clic droit : tri secondaire et colonnes.'))
        self.columns_btn.clicked.connect(self._columns_menu)
        self.grid.favoriteRequested.connect(self._toggle_filament_favorite)
        self.splitter.splitterMoved.connect(lambda *_: self._schedule_ui_preferences())
        self.btn_view_grid.clicked.connect(self._schedule_ui_preferences)
        self.btn_view_list.clicked.connect(self._schedule_ui_preferences)
        # Raccourcis clavier : recherche, export, mise à jour, désélection.
        QShortcut(QKeySequence.Find, self, activated=lambda: (self.search.setFocus(), self.search.selectAll()))
        QShortcut(QKeySequence('Ctrl+E'), self, activated=lambda: self.btn_generate.click() if self.btn_generate.isEnabled() else None)
        QShortcut(QKeySequence('Ctrl+U'), self, activated=lambda: self.update_btn.click() if self.update_btn.isEnabled() else None)
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self._clear_filament)
        self.search.setToolTip(tr('Ctrl+F : rechercher'))
        self.btn_generate.setToolTip(tr('Ctrl+E : exporter pour NFC'))
        self.update_btn.setToolTip(tr('Ctrl+U : choisir les sources et mettre à jour'))
        menu = self.menu_btn.menu()
        menu.addSeparator()
        menu.addAction(tr('Enregistrer les réglages…'), self._export_settings)
        menu.addAction(tr('Charger des réglages…'), self._import_settings)
        menu.addAction(tr('Mise à jour de l’application…'), self._check_app_update)
        menu.addSeparator();menu.addAction(self._about_action)

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
        side.setFixedWidth(220)
        lay = QVBoxLayout(side); lay.setContentsMargins(0, 0, 6, 0); lay.setSpacing(6)
        def caption(text):
            label = QLabel(text); label.setObjectName('caption'); self._muted_labels.append(label); return label
        filter_title = QGridLayout();filter_title.setContentsMargins(0,0,0,0);filter_title.setHorizontalSpacing(8)
        filter_title.setColumnStretch(0,1);filter_title.setColumnStretch(1,1);filter_title.addWidget(caption(tr('FILTRES')),0,0)
        self.reset_filters = QToolButton();self.reset_filters.setText(tr('Effacer'));self.reset_filters.setFixedHeight(32)
        self.reset_filters.setToolTip(tr('Effacer les filtres et la sélection. Vos favoris restent enregistrés.'))
        self.reset_filters.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        self.reset_filters.clicked.connect(self._reset_filters);filter_title.addWidget(self.reset_filters,0,1)
        filter_title.addWidget(caption(tr('FAVORIS')),1,0,1,2)
        self.brand_favorites_only=QToolButton();self.brand_favorites_only.setText(tr('Fabricants'));self.brand_favorites_only.setCheckable(True)
        self.favorites_only=QToolButton();self.favorites_only.setText(tr('Filaments'));self.favorites_only.setCheckable(True)
        for column,button in enumerate((self.brand_favorites_only,self.favorites_only)):
            button.setObjectName('favoriteFilter');button.setFixedHeight(CONTROL_HEIGHT);button.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed);filter_title.addWidget(button,2,column)
        self.favorites_only.setToolTip(tr('Afficher mes filaments favoris'));self.brand_favorites_only.setToolTip(tr('Afficher mes fabricants favoris'))
        self.favorites_only.toggled.connect(self._apply_filter);self.brand_favorites_only.toggled.connect(self._brand_favorites_filter)
        lay.addLayout(filter_title)
        brand_title=QHBoxLayout();brand_title.addWidget(caption(tr('FABRICANTS')),1);lay.addLayout(brand_title)
        self.brand_favorite_btn=QToolButton();self.brand_favorite_btn.setParent(side);self.brand_favorite_btn.hide()
        self.brand_search = QLineEdit(); self.brand_search.setPlaceholderText(tr('Filtrer les fabricants…'))
        self.brand_search.setClearButtonEnabled(True); self.brand_search.textChanged.connect(self._filter_brand_list)
        lay.addWidget(self.brand_search)
        self.brand_list = FavoriteBrandList(); self.brand_list.setObjectName('facets')
        self.brand_list.setUniformItemSizes(True); self.brand_list.setAlternatingRowColors(False)
        self.brand_list.itemClicked.connect(lambda item: self._choose_brand(item.data(Qt.UserRole) or '', remember=False))
        self.brand_list.favoriteRequested.connect(self._toggle_brand_favorite)
        self.brand_list.setToolTip(tr('Survolez une ligne pour afficher son étoile, ou utilisez le clic droit. Les favoris gardent une étoile pleine.'))
        self.brand_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.brand_list.customContextMenuRequested.connect(self._brand_context_menu)
        lay.addWidget(self.brand_list, 3)
        lay.addWidget(caption(tr('MATIÈRES')))
        self.material_search=QLineEdit();self.material_search.setPlaceholderText(tr('Filtrer les matières…'));self.material_search.setClearButtonEnabled(True)
        self.material_search.setFixedHeight(CONTROL_HEIGHT);self.material_search.textChanged.connect(self._filter_material_list);lay.addWidget(self.material_search)
        self.family_list = QListWidget(); self.family_list.setObjectName('facets'); self.family_list.setUniformItemSizes(True)
        self.family_list.itemClicked.connect(lambda item: self._choose_family(item.data(Qt.UserRole) or ''))
        lay.addWidget(self.family_list, 2)
        lay.addWidget(caption(tr('ÉTAT DES DONNÉES')))
        self.state_list = QListWidget(); self.state_list.setObjectName('facets'); self.state_list.setUniformItemSizes(True)
        self.state_list.itemClicked.connect(lambda item: self._choose_state(item.data(Qt.UserRole) or 'all'))
        self.state_list.setFixedHeight(4 * 26 + 6)
        lay.addWidget(self.state_list)
        return side

    def _fill_sidebar(self):
        if not hasattr(self, 'brand_list'): return
        rows = getattr(self, '_all_rows', [])
        brand = self.brand_filter.currentData() or ''
        family = self.material_filter.currentData() or ''
        base = core.query_catalogue(rows, text=self.search.text(), quality=self.quality_filter.currentData())
        cfg = core.load_config()
        if self.favorites_only.isChecked():
            favorites=set(cfg.get('favorite_filaments', []))
            base=[row for row in base if self._is_favorite(row, favorites)]
        if self.brand_favorites_only.isChecked():
            favorites=set(cfg.get('favorite_brands', []))
            base=[row for row in base if row.get('brand') in favorites]
        brands = [row for row in base if not family or row.get('family') == family]
        families = [row for row in base if not brand or row.get('brand') == brand]
        brand_counts, family_counts = {}, {}
        for row in brands:
            if row.get('brand'):brand_counts[row['brand']]=brand_counts.get(row['brand'],0)+1
        for row in families:
            if row.get('family'):family_counts[row['family']]=family_counts.get(row['family'],0)+1
        state_counts={'all':len(rows),'ready':0,'incomplete':0,'suspect':0}
        for row in rows:
            state_counts['ready' if row.get('ready') else 'incomplete']+=1
            if not row.get('ready') and 'à vérifier' in row.get('quality','').casefold():state_counts['suspect']+=1
        recent = [b for b in core.load_config().get('favorite_brands', []) if b in brand_counts]
        self.brand_list.blockSignals(True); self.brand_list.clear()
        def add_brand(name, count, pinned=False):
            item = QListWidgetItem((name or tr('Tous les fabricants')) + f'  ({core.fmt_int(count)})')
            item.setData(Qt.UserRole+1,bool(pinned))
            item.setData(Qt.UserRole, name); item.setToolTip(name or tr('Toutes les marques'))
            self.brand_list.addItem(item)
        add_brand('', len(brands))
        for name in recent: add_brand(name, brand_counts[name], pinned=True)
        for name in sorted(brand_counts, key=str.casefold):
            if name not in recent: add_brand(name, brand_counts[name])
        self.brand_list.blockSignals(False)
        self.family_list.blockSignals(True); self.family_list.clear()
        item = QListWidgetItem(tr('Toutes les matières  ({v0})', v0=core.fmt_int(len(families)))); item.setData(Qt.UserRole, ''); self.family_list.addItem(item)
        for name in sorted(family_counts, key=str.casefold):
            item = QListWidgetItem(f'{name}  ({core.fmt_int(family_counts[name])})'); item.setData(Qt.UserRole, name); self.family_list.addItem(item)
        self.family_list.blockSignals(False)
        self._filter_material_list(self.material_search.text())
        self.state_list.blockSignals(True); self.state_list.clear()
        for key, label in (('all', tr('Toutes les fiches')), ('ready', tr('Données complètes')), ('incomplete', tr('À compléter')), ('suspect', tr('À vérifier'))):
            item = QListWidgetItem(f'{label}  ({core.fmt_int(state_counts[key])})'); item.setData(Qt.UserRole, key); self.state_list.addItem(item)
        self.state_list.setToolTip(tr('Complétude des champs OpenSpool de la fiche ; ce filtre ne note pas la qualité du filament.'))
        self.state_list.blockSignals(False)
        self._filter_brand_list(self.brand_search.text())
        self._sync_sidebar_selection()

    def _refresh_facets(self):
        signature=(id(self._all_rows),self.brand_filter.currentData(),self.material_filter.currentData(),
                   self.search.text(),self.quality_filter.currentData(),self.favorites_only.isChecked(),
                   self.brand_favorites_only.isChecked(),tuple(core.load_config().get('favorite_brands',[])),
                   tuple(core.load_config().get('favorite_filaments',[])))
        if signature!=getattr(self,'_facet_signature',None):
            self._facet_signature=signature
            self._fill_sidebar()

    def _filter_brand_list(self, text):
        needle = core._search_key(text)
        favorites=set(core.load_config().get('favorite_brands',[]))
        for i in range(self.brand_list.count()):
            item = self.brand_list.item(i)
            brand=item.data(Qt.UserRole)
            favorite_hidden=self.brand_favorites_only.isChecked() and bool(brand) and brand not in favorites
            item.setHidden(favorite_hidden or (bool(needle) and bool(brand) and needle not in core._search_key(brand)))

    def _filter_material_list(self,text):
        needle=core._search_key(text)
        if not hasattr(self,'family_list'):return
        for i in range(self.family_list.count()):
            item=self.family_list.item(i);name=item.data(Qt.UserRole)
            item.setHidden(bool(name) and bool(needle) and needle not in core._search_key(name))

    def _brand_favorites_filter(self, *_):
        brands=core.load_config().get('favorite_brands',[])
        if self.brand_favorites_only.isChecked() and self.brand_filter.currentData() not in brands:
            self.brand_filter.setCurrentIndex(0)
        self._filter_brand_list(self.brand_search.text());self._apply_filter()

    def _sync_sidebar_selection(self):
        if not hasattr(self, 'brand_list'): return
        for widget, value in ((self.brand_list, self.brand_filter.currentData() or ''),
                              (self.family_list, self.material_filter.currentData() or ''),
                              (self.state_list, self.quality_filter.currentData() or 'all')):
            widget.blockSignals(True)
            for i in range(widget.count()):
                item = widget.item(i)
                if item.data(Qt.UserRole) == value:
                    widget.setCurrentItem(item)
                    widget.scrollToItem(item); break
            else:
                widget.clearSelection()
            widget.blockSignals(False)
        brand = self.brand_filter.currentData()
        self.brand_favorite_btn.setEnabled(bool(brand))
        self.brand_favorite_btn.setText('★' if brand in core.load_config().get('favorite_brands', []) else '☆')

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
        labels = ['', tr('Référence'), tr('Produit'), tr('Couleur'), tr('Fabricant'), tr('Matière'), 'Ø mm', tr('Masse g'), tr('État des données')]
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
            menu.addAction(tr('Tri principal (1)'), lambda: self._set_column_sort(key))
            menu.addAction(tr('Puis trier par cette colonne (2)'), lambda: self._set_column_sort(key, True))
            menu.addAction(tr('Retirer le tri secondaire'), lambda: self.sort2.setCurrentIndex(0))
            menu.addSeparator()
        self._add_column_choices(menu.addMenu(tr('Colonnes affichées')))
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
            self.status.showMessage(tr('Réglages non enregistrés : {v0}', v0=exc), 10000)

    def _schedule_ui_preferences(self, *_):
        """Group bursts (typing, dragging) into one write a little later."""
        if getattr(self, '_restoring_ui', True) or not hasattr(self, '_all_rows'): return
        self._prefs_timer.start()

    def _save_ui_preferences(self, *_):
        if getattr(self, '_restoring_ui', True) or not hasattr(self, '_all_rows'): return
        if hasattr(self, '_prefs_timer'): self._prefs_timer.stop()
        cfg = core.load_config()
        cfg['ui'] = dict(brand=self.brand_filter.currentData() or '', material=self.material_filter.currentData() or '',
            quality=self.quality_filter.currentData(), search=self.search.text(), brand_search=self.brand_search.text(), sort1=self.sort1.currentData(), sort2=self.sort2.currentData(),
            descending1=self.sort1_direction.currentData(), descending2=self.sort2_direction.currentData(), view=self.view_mode,
            header=bytes(self.table.horizontalHeader().saveState().toHex()).decode(),
            geometry=bytes(self.saveGeometry().toHex()).decode(), splitter=self.splitter.sizes(), favorites_only=self.favorites_only.isChecked(), brand_favorites_only=self.brand_favorites_only.isChecked())
        self._store_config(cfg)

    def _restore_ui_preferences(self):
        self._restoring_ui = True
        controls=(self.brand_filter,self.material_filter,self.quality_filter,self.sort1,self.sort2,self.sort1_direction,self.sort2_direction,self.search,self.brand_search,self.favorites_only,self.brand_favorites_only)
        for control in controls:control.blockSignals(True)
        state = core.load_config().get('ui')
        if not isinstance(state, dict): state = {}
        for combo, key, default in ((self.brand_filter,'brand','Polymaker'),(self.material_filter,'material',''),
                (self.quality_filter,'quality','all'),(self.sort1,'sort1','product'),(self.sort2,'sort2','color_name'),
                (self.sort1_direction,'descending1',False),(self.sort2_direction,'descending2',False)):
            combo.setCurrentIndex(max(0, combo.findData(state.get(key, default))))
        self.search.setText(state.get('search',''))
        self.brand_search.setText(state.get('brand_search',''))
        self.favorites_only.setChecked(state.get('favorites_only') is True)
        self.brand_favorites_only.setChecked(state.get('brand_favorites_only') is True)
        self._filter_brand_list(self.brand_search.text())
        try:
            if state.get('header'): self.table.horizontalHeader().restoreState(QByteArray.fromHex(state['header'].encode()))
            if all(self.table.isColumnHidden(i) for i in range(1,9)): self.table.setColumnHidden(2,False)
            if state.get('geometry'): self.restoreGeometry(QByteArray.fromHex(state['geometry'].encode()))
            sizes=state.get('splitter', [])
            if not isinstance(sizes,list) or len(sizes)!=3 or any(type(v) is not int or v<0 for v in sizes): sizes=[220,620,400]
            self.splitter.setSizes([220,max(340,sizes[1]),max(300,min(sizes[2],600))])
        except (ValueError,TypeError): pass
        self._set_view_mode(state.get('view','list') if state.get('view') in ('list','grid') else 'list')
        for control in controls:control.blockSignals(False)
        self._apply_filter()
        self._restoring_ui = False

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            answer = QMessageBox.question(self, tr('Synchronisation en cours'),
                tr('Une synchronisation est en cours. Quitter quand même ?\nL’étape en cours est interrompue ; la base locale reste celle d’avant.'),
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
        path, _ = QFileDialog.getSaveFileName(self, tr('Enregistrer les réglages'), 'SpoolScribe-reglages.json', 'JSON (*.json)')
        if path:
            try: core.export_settings(path)
            except (OSError,ValueError) as exc: QMessageBox.warning(self,tr('Réglages'),str(exc))

    def _import_settings(self):
        path, _ = QFileDialog.getOpenFileName(self,tr('Charger des réglages'),'','JSON (*.json)')
        if path:
            try:
                previous_language=core.load_config().get('language','auto')
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
                if previous_language!=cfg.get('language','auto'):
                    self._offer_language_restart()
            except (OSError,ValueError) as exc: QMessageBox.warning(self,tr('Réglages'),str(exc))

    def _refresh_database_summary(self):
        if not hasattr(self,'database_btn'):return
        status = self.db.get('_update_status')
        suffix = {'complete':tr('actualisée'),'partial':tr('actualisation partielle'),'failed':tr('actualisation échouée')}.get(status,tr('à synchroniser'))
        groups=len(getattr(self,'_all_rows',[]) or [])
        self.database_btn.setText(tr('Base : {v0} filaments · {v1} ⓘ',v0=core.fmt_int(groups),v1=suffix))
        self.database_btn.setToolTip(tr('État des sources, dernière synchronisation et corrections conservées'))

    @staticmethod
    def _report_date(value):
        from datetime import datetime
        try:return datetime.fromisoformat(value).strftime(tr('%d/%m/%Y à %H:%M'))
        except (TypeError,ValueError):return tr('Pas encore effectuée')

    def _report_sources(self,records):
        panel=QWidget();body=QVBoxLayout(panel);body.setContentsMargins(0,0,0,0);body.setSpacing(8)
        names={'Catalogue multi-fabricants OFD':tr('Open Filament Database'),'Fabricants complémentaires SpoolmanDB':'SpoolmanDB',
               'Download profils Orca':tr('Profils Orca · téléchargement'),'Import profils Orca':tr('Profils Orca · import')}
        for record in records:
            card=QFrame();card.setObjectName('sourceCard');layout=QVBoxLayout(card);layout.setContentsMargins(12,10,12,10)
            row=QHBoxLayout();title=WrapLabel(tr(names.get(record['source'],record['source'])));font=title.font();font.setBold(True);title.setFont(font);row.addWidget(title,1)
            ok=bool(record.get('ok'));message=str(record.get('message') or '')
            status=WrapLabel(self._source_status(ok,record.get('status'),message));status.setAlignment(Qt.AlignRight|Qt.AlignVCenter);status.setMaximumWidth(200)
            status.setObjectName('sourceStatus');status.setProperty('success',ok);row.addWidget(status,1);layout.addLayout(row)
            if message:
                more=QToolButton();more.setText(tr('Détail technique'));more.setCheckable(True);more.setFixedHeight(CONTROL_HEIGHT)
                detail=WrapLabel(message);detail.setTextInteractionFlags(Qt.TextSelectableByMouse);detail.hide()
                more.toggled.connect(detail.setVisible);layout.addWidget(more,0,Qt.AlignLeft);layout.addWidget(detail)
            body.addWidget(card)
        if not records:body.addWidget(WrapLabel(tr('Aucune synchronisation enregistrée.')))
        body.addStretch(1)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.NoFrame);scroll.setWidget(panel)
        return scroll

    def _database_details(self):
        dlg=QDialog(self);dlg.setWindowTitle(tr('État du catalogue'));dlg.resize(680,560)
        lay=QVBoxLayout(dlg);lay.setContentsMargins(16,16,16,16);lay.setSpacing(12)
        title=QLabel(tr('Votre catalogue'));font=title.font();font.setPointSizeF(font.pointSizeF()+3);font.setBold(True);title.setFont(font);lay.addWidget(title)
        stats=core.db_stats(self.db);brands=len({p.get('brand') for p in self.db.get('_products',{}).values() if p.get('brand')})
        lay.addWidget(report_metrics([('Références',core.fmt_int(stats['skus'])),('Fabricants',core.fmt_int(brands)),(tr('Couleurs à préciser'),core.fmt_int(stats['missing_hex']))]))
        cfg=core.load_config();attempt=cfg.get('last_update_attempt') or self.db.get('_last_attempt');updated=self.db.get('_last_updated')
        lay.addWidget(WrapLabel(tr('Dernière actualisation complète : ')+self._report_date(updated)))
        if attempt and attempt!=updated:lay.addWidget(WrapLabel(tr('Dernière tentative : ')+self._report_date(attempt)))
        pending=sum(len(rows) for rows in self.db.get('_pending_source_matches',{}).values())
        if pending:lay.addWidget(WrapLabel(tr('{v0} références attendent un rapprochement fiable et restent hors de la liste.', v0=core.fmt_int(pending))))
        report_pages=QStackedWidget();report_pages.setObjectName('catalogueReportPages');report_pages.addWidget(self._report_sources(self.db.get('_source_results',[])));lay.addWidget(report_pages,1)
        technical=QToolButton();technical.setText(tr('Stockage et valeurs conservées'));technical.setCheckable(True);technical.setFixedHeight(CONTROL_HEIGHT)
        detail=QPlainTextEdit();detail.setObjectName('storageDetails');detail.setReadOnly(True);detail.setFixedHeight(140)
        detail.setPlainText(tr('Fichier local : {v0}', v0=core.DB_PATH)+('\n'+self.stats_label.toolTip() if self.stats_label.toolTip() else ''))
        storage=QWidget();storage_layout=QVBoxLayout(storage);storage_layout.setContentsMargins(0,0,0,0);storage_layout.addWidget(detail);storage_layout.addStretch(1);report_pages.addWidget(storage)
        technical.toggled.connect(lambda checked:report_pages.setCurrentIndex(1 if checked else 0))
        technical.toggled.connect(lambda checked:technical.setText(tr('Retour aux sources') if checked else tr('Stockage et valeurs conservées')))
        lay.addWidget(technical,0,Qt.AlignLeft)
        close=QPushButton(tr('Fermer'));close.setFixedHeight(CONTROL_HEIGHT);close.clicked.connect(dlg.accept);row=QHBoxLayout();row.addStretch(1);row.addWidget(close);lay.addLayout(row);dlg.exec()

    @staticmethod
    def _source_status(ok, status, message=''):
        if ok:return tr('À jour') if status=='unchanged' else tr('Actualisée')
        if status=='cancelled':return tr('Annulée')
        if 'timed out' in message or 'timeout' in message.lower():return tr('Délai dépassé — réessayer plus tard')
        if 'CERTIFICATE_VERIFY_FAILED' in message:return tr('Connexion sécurisée impossible')
        if status=='partial':return tr('Certaines données manquent')
        if status=='unavailable':return tr('Source injoignable')
        return tr('Échec de l’actualisation')

    def _sync_catalogue(self):
        if core.has_network_consent():self._start_update(manual=True)
        else:self._choose_sources()

    def _choose_sources(self, checked=False, *, startup=False):
        dlg=QDialog(self);dlg.setWindowTitle(tr('Sources du catalogue'));dlg.resize(660,560)
        lay=QVBoxLayout(dlg)
        note=WrapLabel(tr('Choisissez les sources du catalogue. Vos corrections restent prioritaires.'))
        lay.addWidget(note)
        policy=WrapLabel(tr('Priorité : vos corrections, puis les fabricants. Décocher une source conserve les fiches déjà téléchargées.'))
        note.setToolTip(policy.text()+tr(' Catalogue non exhaustif.'));policy.hide()
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.NoFrame)
        content=QWidget();body=QVBoxLayout(content);body.setSizeConstraint(QVBoxLayout.SetMinimumSize)
        scroll.setWidget(content);lay.addWidget(scroll,1)
        cfg=core.load_config();selected=cfg['selected_sources'];checks={}
        last={r['source']:r for r in self.db.get('_source_results',[])}
        labels={script:label for script,label,_ in core.UPDATE_PIPELINE}
        descriptions={'polymaker':tr('Catalogue et couleurs du fabricant.'), 'ofd':tr('Catalogue de nombreux fabricants.'),
                      'spoolman':tr('Fabricants supplémentaires absents du catalogue principal.'),
                      'bambu':tr('Caractéristiques officielles des fiches Bambu déjà présentes.'),
                      'sunlu':tr('Caractéristiques et couleurs PLA des fiches SUNLU déjà présentes.'),
                      'orca':tr('Paramètres Polymaker pour OrcaSlicer et Snapmaker U1.'),
                      'thefilamentdb':tr('Ancien complément local, sans catalogue ROSA3D.')}
        from pathlib import Path
        for key in ('polymaker','bambu','sunlu','ofd','spoolman','orca','thefilamentdb'):
            meta=core.SOURCE_GROUPS[key]
            frame=QFrame();frame.setObjectName('sourceCard');row=QVBoxLayout(frame)
            row.setContentsMargins(12,10,12,10)
            check=QCheckBox(tr(meta['name']));check.setChecked(key in selected)
            font=check.font();font.setBold(True);check.setFont(font)
            check.setToolTip(meta['detail']);head=QHBoxLayout();head.addWidget(check,1)
            more=QToolButton();more.setText(tr('i'));more.setCheckable(True);more.setToolTip(tr('Portée, compteurs et limites de cette source'));head.addWidget(more);row.addLayout(head)
            available=key!='thefilamentdb' or core.resource_paths.legacy_snapshot_path(core.RESOURCE_DIR, core.DATA_HOME).is_file()
            if not available:check.setChecked(False);check.setEnabled(False)
            results=[last[labels[name]] for name in meta['scripts'] if labels.get(name) in last]
            text=descriptions[key]
            if not available:text=tr('Non disponible dans cette application.')
            elif results:
                worst=min(results,key=lambda r:bool(r.get('ok')))
                text+=' '+self._source_status(worst.get('ok'),worst.get('status'),str(worst.get('message','')))+'.'
            detail=WrapLabel(text);detail.setObjectName('fieldvalue');detail.hide();row.addWidget(detail);more.toggled.connect(detail.setVisible)
            snapshot=self.db.get('_source_snapshots',{}).get(key,{})
            if snapshot.get('references') is not None:
                text=tr('Source analysée : {v0} références', v0=core.fmt_int(snapshot['references']))
                if snapshot.get('brands_imported') is not None:text+=tr(' · {v0} fabricants importés', v0=snapshot['brands_imported'])
                if snapshot.get('incomplete'):text+=tr(' · {v0} fiches incomplètes', v0=snapshot['incomplete'])
                count=QLabel(tr('{v0} réf.', v0=core.fmt_int(snapshot['references'])));head.insertWidget(1,count)
                detail.setText(detail.text()+'\n'+text)
            elif key=='bambu' and snapshot.get('profiles'):
                head.insertWidget(1,QLabel(f"{snapshot['profiles']} profils"))
                detail.setText(detail.text()+tr(' Pas un catalogue complet de couleurs.'))
            body.addWidget(frame);checks[key]=check
        body.addStretch(1)
        error=QLabel();error.setWordWrap(True);lay.addWidget(error)
        report_btn=QToolButton();report_btn.setText(tr('Rapport de synchronisation…'))
        report_btn.clicked.connect(lambda:self._show_sync_report(*self._last_report) if self._last_report else self._database_details())
        lay.addWidget(report_btn,0,Qt.AlignLeft)
        buttons=QDialogButtonBox();run=buttons.addButton(tr('Actualiser maintenant'),QDialogButtonBox.AcceptRole)
        save=buttons.addButton(tr('Enregistrer seulement'),QDialogButtonBox.ActionRole)
        cancel=buttons.addButton(tr('Annuler'),QDialogButtonBox.RejectRole)
        state={'download':False}
        def accept(download):
            keys=[k for k,c in checks.items() if c.isChecked() and c.isEnabled()]
            if not keys:error.setText(tr('Choisissez au moins une source.'));return
            cfg=core.load_config();cfg['selected_sources']=keys;cfg['network_consent']=True;cfg['network_sources_revision']=core.NETWORK_SOURCES_REVISION
            try:core.save_config(cfg)
            except OSError as exc:error.setText(tr(str(exc)));return
            state['download']=download;dlg.accept()
        run.clicked.connect(lambda:accept(True));save.clicked.connect(lambda:accept(False));cancel.clicked.connect(dlg.reject);lay.addWidget(buttons)
        if dlg.exec()==QDialog.Accepted and state['download']:self._start_update(manual=True)

    # ── Rapport de synchronisation ────────────────────────────────────
    def _snapshot_stats(self):
        skus=self.db.get('_skus',{})
        by_source={}
        for e in skus.values():by_source[e.get('source') or tr('Catalogue historique')]=by_source.get(e.get('source') or tr('Catalogue historique'),0)+1
        conflicts=list(self.db.get('_source_conflicts',[]))
        for values in self.db.get('_source_conflicts_by_source',{}).values():conflicts.extend(values)
        pending=sum(len(v) for v in self.db.get('_pending_source_matches',{}).values())
        return dict(references=len(skus),products=len(self.db.get('_products',{})),brands=len({p.get('brand') for p in self.db.get('_products',{}).values() if p.get('brand')}),
                    by_source=by_source,conflicts=len(set(conflicts)),pending=pending,ready=sum(1 for r in getattr(self,'_sku_rows',[]) if r.get('ready')))

    def _show_sync_report(self,results,before,after=None):
        after=after or self._snapshot_stats();self._last_report=(results,before,after)
        dlg=QDialog(self);dlg.setWindowTitle(tr('Actualisation du catalogue'));dlg.resize(680,560)
        lay=QVBoxLayout(dlg);lay.setContentsMargins(16,16,16,16);lay.setSpacing(12)
        status=core.update_status(results);cancelled=any(r.status=='cancelled' for r in results)
        headline={'complete':tr('Votre catalogue est à jour'),'partial':tr('Certaines sources restent à actualiser'),'failed':tr('Actualisation impossible')}[status]
        if cancelled:headline=tr('Actualisation interrompue')
        title=WrapLabel(headline);font=title.font();font.setPointSizeF(font.pointSizeF()+3);font.setBold(True);title.setFont(font);lay.addWidget(title)
        lay.addWidget(report_metrics([(tr('Références conservées'),core.fmt_int(after['references'])),('Fabricants',core.fmt_int(after['brands'])),(tr('Étapes réussies'),f'{sum(r.ok for r in results)} / {len(results)}')]))
        added=after['references']-before['references']
        if added:lay.addWidget(WrapLabel(tr('Évolution : {v0:+,} références.', v0=added).replace(',',' ')))
        if after['conflicts']:lay.addWidget(WrapLabel(tr('{v0} valeurs prioritaires conservées face à une autre source.', v0=core.fmt_int(after['conflicts']))))
        if after['pending']:lay.addWidget(WrapLabel(tr('{v0} rapprochements à confirmer, sans ajout de doublons.', v0=core.fmt_int(after['pending']))))
        lay.addWidget(self._report_sources([dict(source=r.label,status=r.status,ok=r.ok,message=r.stderr) for r in results]),1)
        if status!='complete':lay.addWidget(WrapLabel(tr('Les fiches non actualisées restent disponibles. Vous pouvez réessayer plus tard.')))
        close=QPushButton(tr('Fermer'));close.setFixedHeight(CONTROL_HEIGHT);close.clicked.connect(dlg.accept)
        row=QHBoxLayout();row.addStretch(1);row.addWidget(close);lay.addLayout(row);dlg.show()

    def _maybe_auto_update(self):
        if not self.isVisible() or core.db_restored_this_session():return
        if core.has_network_consent():
            if not self.db.get('_skus') or core.update_due():
                self._start_update()
            else:
                self.status.showMessage(tr('Base déjà actualisée récemment ; « Actualiser le catalogue » permet de la relancer.'),8000)
        elif not core.load_config().get('network_consent') is False:
            self._choose_sources(startup=True)
        else:
            self.status.showMessage(tr('Synchronisation au démarrage désactivée par le refus réseau. Ouvrez « Sources » pour la réactiver.'),12000)

    def _build_export_assistant(self, layout):
        """Page « Mon matériel » : imprimante/lecteur, firmware, étiquette."""
        cfg=core.load_config()
        printer_id,firmware_id=printer_profiles.resolve(cfg.get('printer_profile'),cfg.get('printer_firmware'))
        layout.addWidget(QLabel(tr('1. Quelle imprimante utilisez-vous ?')))
        self.printer=PrinterPicker();self._fill_printer_combo()
        self.printer.setFixedHeight(CONTROL_HEIGHT);self.printer.setAccessibleName(tr('Choisir ou rechercher une imprimante'))
        self.printer.setToolTip(tr('Ouvrir la liste illustrée et rechercher une marque ou un modèle'))
        self.printer.setCurrentIndex(max(0,self.printer.findData(printer_id)));layout.addWidget(self.printer)
        self.printer_card=PrinterCard();layout.addWidget(self.printer_card)
        self.reader_info=QLabel();self.reader_info.setWordWrap(True);self.reader_info.setObjectName('fieldvalue');self.reader_info.hide()
        self.firmware_label=QLabel(tr('2. Logiciel installé'));layout.addWidget(self.firmware_label)
        self.firmware=QComboBox();layout.addWidget(self.firmware)
        self._fill_firmware_combo(printer_id,cfg.get('printer_firmware') if cfg.get('printer_profile')!='u1_stock' else firmware_id)
        self.printer_help=WrapLabel();layout.addWidget(self.printer_help)
        self.extra_fields=QCheckBox(tr('Afficher aussi les références, la provenance et la masse'));self.extra_fields.hide()  # conservé pour les réglages importés
        row=QHBoxLayout();self.tag_label=QLabel(tr('Étiquette NFC'));row.addWidget(self.tag_label)
        self.tag_choice=QComboBox();self.tag_choice.addItem('NTAG216','NTAG216');self.tag_choice.addItem('NTAG215','NTAG215')
        self.tag_choice.setCurrentIndex(max(0,self.tag_choice.findData(core.nfc_defaults(cfg)['tag_type'])));row.addWidget(self.tag_choice,1)
        self.nfc_default_btn=QToolButton();self.nfc_default_btn.setAccessibleName(tr('Définir ce choix d’étiquette par défaut'));row.addWidget(self.nfc_default_btn)
        self.advanced_toggle=QToolButton();self.advanced_toggle.setText(tr('Réglages avancés'));self.advanced_toggle.setCheckable(True);row.addWidget(self.advanced_toggle);layout.addLayout(row)

    def _fill_printer_combo(self):
        current=self.printer.currentData()
        self.printer.blockSignals(True);self.printer.clear()
        # People choose their machine, not a protocol category.
        for key,profile in sorted(PROFILES.items(), key=lambda item:item[1]['label'].casefold()):
            self.printer.addItem(tr(profile['label']),key)
        if current:self.printer.setCurrentIndex(max(0,self.printer.findData(current)))
        self.printer.blockSignals(False)

    def _fill_firmware_combo(self,printer_id,firmware_id=None):
        self.firmware.blockSignals(True);self.firmware.clear()
        if len(PROFILES[printer_id]['firmwares'])>1 and any(f['openspool'] for f in PROFILES[printer_id]['firmwares']):
            self.firmware.addItem(tr('Choisir le logiciel installé…'),'unknown')
        for fw in PROFILES[printer_id]['firmwares']:
            label = {'paxx12':tr('J’ai installé le firmware paxx12'), 'stock':tr('Logiciel d’origine du fabricant')}.get(fw['id'],fw['label'])
            self.firmware.addItem(tr(label),fw['id'])
        self.firmware.setCurrentIndex(max(0,self.firmware.findData(firmware_id)))
        several=self.firmware.count()>1 and any(f['openspool'] for f in PROFILES[printer_id]['firmwares'])
        self.firmware.setVisible(several);self.firmware_label.setVisible(several)
        self.firmware.blockSignals(False)

    def _build_hardware_dialog(self):
        self.hardware_dialog=QDialog(self);self.hardware_dialog.setWindowTitle(tr('Mon imprimante et mes étiquettes'))
        self.hardware_dialog.resize(640,530)
        self.hardware_dialog.setMinimumSize(480,300)
        lay=QVBoxLayout(self.hardware_dialog)
        intro=WrapLabel(tr('Retrouvez votre imprimante, puis vérifiez comment elle reconnaît vos bobines.'))
        lay.addWidget(intro)
        self.hardware_scroll=QScrollArea();self.hardware_scroll.setWidgetResizable(True)
        self.hardware_scroll.setFrameShape(QFrame.NoFrame)
        self.hardware_scroll.setWidget(self.hardware_page);lay.addWidget(self.hardware_scroll,1)
        self.hardware_page.layout().setSizeConstraint(QVBoxLayout.SetMinAndMaxSize)
        self.hardware_page.layout().setAlignment(Qt.AlignTop)
        for control in self.hardware_page.findChildren(QComboBox):
            control.setFixedHeight(CONTROL_HEIGHT);control.setMinimumWidth(0)
            control.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon);control.setMinimumContentsLength(12)
        self.printers_origin=WrapLabel()
        self.printers_origin.setObjectName('fieldvalue');lay.addWidget(self.printers_origin)
        foot=QHBoxLayout()
        self.btn_update_printers=QPushButton(tr('Actualiser la liste'))
        self.btn_update_printers.setFixedHeight(CONTROL_HEIGHT)
        self.btn_update_printers.setToolTip(tr('Télécharger la liste des imprimantes depuis le dépôt SpoolScribe'))
        self.btn_update_printers.clicked.connect(self._update_printers);foot.addWidget(self.btn_update_printers)
        foot.addStretch(1);close=QPushButton(tr('Terminé'));close.setFixedHeight(CONTROL_HEIGHT);close.clicked.connect(self.hardware_dialog.accept);foot.addWidget(close);lay.addLayout(foot)
        self._refresh_printers_origin()

    def _refresh_printers_origin(self):
        catalogue=printer_profiles.load_catalogue()
        origin=tr('liste téléchargée') if catalogue.get('_origin')=='user' else tr('liste embarquée')
        self.printers_origin.setText(tr('Imprimantes : {v0}, version du {v1}', v0=origin, v1=catalogue.get('updated', '?')))

    def _open_hardware(self):
        self._refresh_printer_card()
        self.hardware_dialog.show();self.hardware_dialog.raise_();self.hardware_dialog.activateWindow()

    def _update_printers(self):
        if core.load_config().get('network_consent') is not True:
            QMessageBox.information(self,tr('Liste des imprimantes'),tr('Accordez d’abord l’autorisation réseau (Actualiser le catalogue → sources) pour contacter GitHub.'));return
        from scripts import official_sources
        try:
            catalogue=printer_profiles.refresh_catalogue(official_sources.fetch)
        except Exception as exc:
            self.printers_origin.setText(tr('Vérification impossible. Votre liste actuelle est conservée.'))
            self.printers_origin.setToolTip(str(exc));return
        if catalogue is None:
            self.printers_origin.setText(tr('Aucune nouvelle liste publiée pour cette version. La liste embarquée reste disponible.'))
            self.printers_origin.setToolTip(tr('Le fichier de référence n’est pas encore publié sur la branche main (HTTP 404).'))
            return
        self._fill_printer_combo();self._printer_changed();self._refresh_printers_origin()
        self.status.showMessage(tr('Liste des imprimantes du {v0} installée ({v1} entrées).', v0=catalogue.get('updated', '?'), v1=len(catalogue['printers'])),8000)

    def _references_text(self,sku):
        rows=[r for r in getattr(self,'_all_rows',[]) if r['sku']==sku]
        variants=rows[0].get('variants') if rows and rows[0].get('variants') else None
        if not variants:
            entry=self.db['_skus'].get(sku,{})
            parts=[sku]
            if entry.get('manufacturer_sku') and entry['manufacturer_sku']!=sku:parts.append(tr('réf. fabricant {v0}', v0=entry['manufacturer_sku']))
            if entry.get('weight'):parts.append(f'{entry["weight"]:g} g')
            return ' · '.join(parts)
        lines=[]
        for v in variants:
            ref=v['reference']
            bits=[ref if not ref.startswith(('OFD-','SMDB-')) else ('source '+ref.split('-')[0])]
            if v.get('weight'):bits.append(f'{v["weight"]:g} g')
            if v.get('diameter'):bits.append(f'Ø {v["diameter"]:g} mm')
            if not v.get('ready'):bits.append(tr('à compléter'))
            lines.append(' · '.join(bits))
        hexes={v.get('hex') for v in variants if v.get('hex')}
        text='\n'.join(lines)
        if len(hexes)>1:text+=tr('\n⚠ Teintes différentes selon la source ; la mieux documentée est affichée.')
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
        labels={'auto':tr('essentiel recommandé'),'essential':'essentiel','full':'complet'}
        text=f"{choice['tag_type']} · {labels[choice['profile']]}"
        return text+(tr(' · réserve {v0} o', v0=choice['reserved_bytes']) if choice['reserved_bytes'] else '')

    def _refresh_nfc_default_btn(self):
        if not hasattr(self,'nfc_default_btn') or not hasattr(self,'nfc_reserve'):return
        current,saved=self._current_nfc_choice(),core.nfc_defaults()
        is_default=current==saved
        self.nfc_default_btn.setText(tr('Par défaut ✓') if is_default else tr('Définir par défaut'))
        self.nfc_default_btn.setEnabled(not is_default)
        self.nfc_default_btn.setToolTip(tr('Choix par défaut : {v0}', v0=self._describe_nfc(saved)) if is_default else
            tr('Enregistrer {v0} pour les prochains exports et lancements.\nDéfaut actuel : {v1}. Sans enregistrement, ce choix ne vaut que pour cette session.', v0=self._describe_nfc(current), v1=self._describe_nfc(saved)))

    def _save_nfc_default(self):
        try:
            saved=core.save_nfc_defaults(**self._current_nfc_choice())
        except (OSError,ValueError) as exc:
            self.status.showMessage(tr('Choix par défaut non enregistré : {v0}', v0=exc),8000);return
        self.status.showMessage(tr('Choix NFC par défaut : {v0}.', v0=self._describe_nfc(saved)),6000)
        self._refresh_nfc_default_btn()

    def _printer_changed(self,*_):
        printer_id=self.printer.currentData() or printer_profiles.DEFAULT
        if self.sender() is self.printer or self.firmware.count()==0 or self._firmware_printer!=printer_id:
            self._fill_firmware_combo(printer_id,core.load_config().get('printer_firmware') if self._firmware_printer is None else None)
        self._firmware_printer=printer_id
        cfg=core.load_config();cfg['printer_profile']=printer_id;cfg['printer_firmware']=self.firmware.currentData()
        if hasattr(self,'status'):self._store_config(cfg)
        profile=PROFILES[printer_id];fw=printer_profiles.firmware(printer_id,self.firmware.currentData())
        self.reader_info.setText(tr('Lecteur : {v0}',v0=tr(profile.get('reader') or 'Aucun')))
        if self.firmware.currentData()=='unknown':
            text=tr('Précisez le logiciel installé pour vérifier la lecture des étiquettes. En cas de doute, consultez les informations de votre imprimante.')
        elif fw['openspool']:
            text=tr('Export NFC disponible avec cette configuration. Écrivez ensuite le fichier sur votre étiquette avec une application NFC.')
            if profile['group']=='external':text=tr('Un lecteur externe compatible OpenSpool est nécessaire. Le lecteur d’origine de l’imprimante ne suffit pas.')
        else:
            text=tr('Fiches consultables. Cette configuration ne lit pas les étiquettes créées par SpoolScribe.')
        self.printer_help.setText(text)
        self.printer_help.setVisible(not fw['openspool'] or self.firmware.currentData()=='unknown')
        self.printer_help.setToolTip(tr(profile['help'])+'\n'+tr(fw.get('notes',''))+'\n'+tr(profile.get('reader','')))
        self._refresh_printer_card()
        self.tag_label.setVisible(fw['openspool']);self.tag_choice.setVisible(fw['openspool'])
        self.nfc_default_btn.setVisible(fw['openspool']);self.advanced_toggle.setVisible(fw['openspool'])
        if not fw['openspool'] and hasattr(self,'nfc_advanced'):self.nfc_advanced.hide()
        elif hasattr(self,'nfc_advanced'):self.nfc_advanced.setVisible(self.advanced_toggle.isChecked())
        self._printer_field_help()
        if hasattr(self,'btn_generate'):self._refresh_nfc_capacity()

    def _refresh_printer_card(self):
        profile=PROFILES[self.printer.currentData()]
        fw=printer_profiles.firmware(self.printer.currentData(),self.firmware.currentData())
        badge=tr('Logiciel à préciser') if self.firmware.currentData()=='unknown' else tr('Lecture OpenSpool disponible') if fw['openspool'] else tr('Consultation des fiches uniquement')
        self.printer_card.update_profile(profile,badge,fw['openspool'],getattr(self,'_tok',{}).get('dark',False))

    def _printer_field_help(self):
        if not hasattr(self,'printer'):return
        profile=PROFILES[self.printer.currentData()]
        labels={'Nozzle':'Buse','Bed':'Plateau','Type':tr('Matière'),'SKU':tr('Référence interne')}
        for row in range(self.fields.rowCount()):
            item=self.fields.itemAtPosition(row,0)
            if not item:continue
            label=item.widget();key=label.property('field_key') or label.text();label.setProperty('field_key',key)
            hint=profile.get('fields',{}).get(key,'Information facultative de la fiche')
            label.setText(tr(labels.get(key,key)) + (' *' if 'requis' in hint else ''));label.setToolTip(tr(hint))
            if key in self._field_widgets:self._field_widgets[key].setToolTip(tr(hint))
        for key,label in self.characteristics.labels.items():
            hint=profile.get('fields',{}).get(key,'Paramètre à adapter dans votre trancheur')
            label.setToolTip(tr(hint));self._field_widgets[key].setToolTip(tr(hint))
        self.card.setToolTip(tr('Survolez un champ pour connaître son usage pour cette imprimante. Les températures restent à adapter au plateau et au trancheur.'))

    def _toggle_extra_fields(self, checked):
        pass  # références et provenance sont toujours visibles dans la fiche

    def _can_export_for_printer(self):
        return self.firmware.currentData()!='unknown' and printer_profiles.can_export(self.printer.currentData() or printer_profiles.DEFAULT,self.firmware.currentData())

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
        summary=tr(PROFILES[printer_id]['label'])
        if can:summary+=f' · {self.tag_choice.currentData()}'
        else:summary+=tr(' · consultation des fiches')
        if hasattr(self,'hardware_summary'):self.hardware_summary.setText(summary)
        self.btn_generate.setEnabled(can and bool(self.current_sku) and not self._variant_needs_choice() and not (self.worker and self.worker.isRunning()))
        if hasattr(self,'btn_inspect'):self.btn_inspect.setEnabled(can and bool(self.current_sku))
        if not can:
            self.nfc_note.setText(tr('Utilisez ces informations dans votre logiciel de préparation d’impression.'))
            self.nfc_capacity.setText(tr('Précisez le logiciel de votre imprimante dans « Modifier… ».') if self.firmware.currentData()=='unknown' else tr('Cette configuration ne reconnaît pas les étiquettes SpoolScribe.'));return
        if not self.current_sku:return
        try:
            payload=self._build_payload()
            if payload is None:return
            options=self._nfc_options();text=core.serialize_openspool(payload,**options)
            size=core.nfc_size(text,tag_type=options['tag_type'],reserved_bytes=options['reserved_bytes'])
            self.nfc_note.setText(tr('Fichier avec descriptifs et logo.') if options['profile']=='full' else tr('Fichier compact, adapté à votre étiquette.'))
            self.nfc_capacity.setText(tr('Place suffisante sur l’étiquette.'))
            self.nfc_capacity.setToolTip(tr('Espace restant : {v0} octets. Le logiciel d’écriture peut ajouter des données ; vérifiez sa taille finale.', v0=size.remaining_bytes))
        except (ValueError,OSError) as exc:
            if self._variant_needs_choice(): self.btn_generate.setEnabled(False)
            self.nfc_note.setText(tr('Choisissez la teinte de votre bobine ci-dessus.') if self._variant_needs_choice() else tr('Complétez les données signalées avant l’export.'))
            self.nfc_capacity.setText(tr(str(exc)))

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
        dpr=pixmap.devicePixelRatio() or 1.0;pad=max(1,round(2*dpr))
        background=QColor('#252d34' if getattr(self,'_tok',{}).get('dark',False) else '#ffffff')
        samples=[image.pixelColor(x,y) for y in range(0,image.height(),max(1,image.height()//24)) for x in range(0,image.width(),max(1,image.width()//48))]
        visible=[c for c in samples if c.alpha()>128]
        needs_edge=bool(visible) and sum(abs(c.lightness()-background.lightness())<35 for c in visible)/len(visible)>.85
        image.setDevicePixelRatio(1)
        result=QPixmap(image.width()+2*pad,image.height()+2*pad);result.fill(Qt.transparent);painter=QPainter(result)
        if needs_edge:
            mask=image.copy();ink=QColor('#eeeeee' if background.lightness()<128 else '#404040')
            for y in range(mask.height()):
                for x in range(mask.width()):
                    ink.setAlpha(round(image.pixelColor(x,y).alpha()*.45));mask.setPixelColor(x,y,ink)
            for dx,dy in ((-1,0),(1,0),(0,-1),(0,1)):painter.drawImage(pad+dx,pad+dy,mask)
        painter.drawImage(pad,pad,image);painter.end();result.setDevicePixelRatio(dpr);return result

    def _check_app_update(self):
        if self._release_worker and self._release_worker.isRunning():return
        if core.load_config().get('network_consent') is False:
            QMessageBox.information(self,tr('Mise à jour application'),tr('L’autorisation réseau a été retirée. Réactivez-la dans « Sources de la base » pour contacter GitHub.'));return
        self.status.showMessage(tr('Vérification de la version publiée sur GitHub…'),15000)
        self._release_worker=ReleaseWorker(self);self._release_worker.ready.connect(self._release_result);self._release_worker.start()

    def _release_result(self, result):
        self.status.clearMessage()
        if result.get('error'):QMessageBox.warning(self,tr('Mise à jour application'),result['error']);return
        if not result['newer']:
            QMessageBox.information(self,'Application',tr('Votre version : {v0}\nVersion publique : {v1}\n', v0=core.APP_VERSION, v1=result['version'])+(tr('Vous utilisez une version de développement plus récente.') if core.APP_VERSION != result['version'] else tr('Votre application est à jour.')));return
        box=QMessageBox(self);box.setWindowTitle(tr('Nouvelle version disponible'));box.setText(tr('SpoolScribe {v0} est disponible.\nTéléchargez le paquet de votre système et remplacez l’application. Vos données et réglages restent dans le dossier utilisateur.', v0=result['version']))
        download=box.addButton(tr('Ouvrir le téléchargement officiel'),QMessageBox.AcceptRole);box.addButton(tr('Plus tard'),QMessageBox.RejectRole);box.exec()
        if box.clickedButton()==download:QDesktopServices.openUrl(QUrl(result['url']))

    def _toggle_brand_favorite(self, brand):
        if not brand:return
        cfg=core.load_config();favorites=list(cfg.get('favorite_brands', []))
        if brand in favorites:favorites.remove(brand)
        else:favorites.append(brand)
        cfg['favorite_brands']=favorites;self._store_config(cfg);self._fill_sidebar()
        if self.brand_favorites_only.isChecked():self._brand_favorites_filter()

    def _brand_context_menu(self, point):
        item=self.brand_list.itemAt(point)
        if not item or not item.data(Qt.UserRole):return
        brand=item.data(Qt.UserRole);menu=QMenu(self)
        label=tr('Retirer des favoris') if brand in core.load_config().get('favorite_brands',[]) else tr('Ajouter aux favoris')
        menu.addAction(label,lambda:self._toggle_brand_favorite(brand))
        menu.exec(self.brand_list.viewport().mapToGlobal(point))

    def _group_for_sku(self, sku):
        return next((r for r in getattr(self,'_all_rows',[]) if r['sku']==sku or any(v['sku']==sku for v in r.get('variants',[]))),None)

    def _is_favorite(self, group, saved=None):
        if not group:return False
        if saved is None:saved=set(core.load_config().get('favorite_filaments',[]))
        return bool(saved.intersection([group.get('filament_id',''),group['sku']]+[v['sku'] for v in group.get('variants',[])]))

    def _toggle_filament_favorite(self, sku=None):
        group=self._group_for_sku(sku if isinstance(sku,str) else self.current_sku)
        if not group:return
        cfg=core.load_config();saved=list(cfg.get('favorite_filaments',[]))
        # Stable semantic identity plus source references survives a change of
        # representative, and retains the favorite if an upstream label changes.
        keys=[group.get('filament_id') or group['sku']]+[v['sku'] for v in group.get('variants',[])]
        if self._is_favorite(group):saved=[k for k in saved if k not in keys]
        else:saved=list(dict.fromkeys(saved+keys))
        cfg['favorite_filaments']=saved;self._store_config(cfg)
        self._refresh_favorite_button()
        if self.favorites_only.isChecked():self._apply_filter()
        else:
            saved=set(core.load_config().get('favorite_filaments',[]))
            for index,row in enumerate(self._rows):
                self.grid.itemDelegate().rows[row['sku']]=dict(row,_favorite=self._is_favorite(row,saved))
            self.grid.viewport().update()

    def _refresh_favorite_button(self):
        if not hasattr(self,'favorite_btn'):return
        active=self._is_favorite(self._group_for_sku(self.current_sku))
        self.favorite_btn.blockSignals(True);self.favorite_btn.setChecked(active);self.favorite_btn.blockSignals(False)
        self.favorite_btn.setText(tr('★ Favori') if active else tr('☆ Favori'))
        self.favorite_btn.setToolTip(tr('Retirer ce filament des favoris') if active else tr('Ajouter ce filament aux favoris'))
        self.favorite_btn.setAccessibleName(self.favorite_btn.toolTip())
        self.favorite_btn.setMinimumHeight(28)

    def _detail_packaging(self, sku):
        group=self._group_for_sku(sku)
        if not group or not group.get('variants'):return sku
        identity=group.get('filament_id') or group['sku'];members=group['variants']
        signature=tuple(sorted({r.get('hex') or '' for r in members}))
        signatures=self.__dict__.setdefault('_choice_signatures',{})
        manual=self.__dict__.setdefault('_manual_variants',{})
        if identity in signatures and signatures[identity]!=signature:
            manual.pop(identity,None);self._chosen_variant=None
        signatures[identity]=signature
        chosen=manual.get(identity)
        if chosen and any(r['sku']==chosen for r in members):
            if len(signature)>1:self._chosen_variant=chosen
            return chosen
        if group.get('hex_variants',0)>1:return sku
        return core.preferred_packaging(members,core.load_config(),sku)['sku']

    def _remember_packaging(self, sku):
        group=self._group_for_sku(sku)
        if group:self.__dict__.setdefault('_manual_variants',{})[group.get('filament_id') or group['sku']]=sku

    def _refresh_variant_choice(self, group, sku):
        members=(group or {}).get('variants',[])
        self.variant_choice.blockSignals(True);self.variant_choice.clear()
        conflict=(group or {}).get('hex_variants',0)>1
        chosen=getattr(self,'_chosen_variant',None)
        colors=sorted({r['hex'] for r in members if r.get('hex')}) if conflict else []
        active_hex=next((r.get('hex') for r in members if r['sku']==sku),None) if chosen==sku else None
        # Reuse the controls, including when a theme or filter is refreshed.
        while len(self.shade_buttons)<len(colors):
            button=QToolButton();button.setObjectName('shadeOption');button.setCheckable(True);button.setIconSize(QSize(32,32))
            button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            button.clicked.connect(lambda checked=False,b=button:self._choose_shade(b.property('shade')))
            index=len(self.shade_buttons)
            self.shade_buttons.append(button);self.shade_row.addWidget(button,index//2,index%2)
        for i,button in enumerate(self.shade_buttons):
            button.setVisible(i<len(colors))
            if i>=len(colors):continue
            color=colors[i];button.setProperty('shade',color)
            image=QPixmap(32,32);image.fill(Qt.transparent)
            painter=QPainter(image);painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QColor('#809098'));painter.setBrush(QColor('#'+color));painter.drawRoundedRect(2,2,28,28,7,7);painter.end()
            button.setIcon(QIcon(image));button.setText(tr('Teinte {v0}',v0=i+1))
            button.setChecked(active_hex==color)
            button.setToolTip(tr('Couleur annoncée : #{v0}. Comparez avec votre bobine ; l’écran ne garantit pas une couleur exacte.', v0=color))
        self.shade_panel.setVisible(conflict)
        self.shade_hint.setText(tr('Les sources proposent plusieurs teintes. Laquelle correspond à votre bobine ?'))
        available=[r for r in members if not conflict or not active_hex or r.get('hex')==active_hex]
        available=sorted(available,key=lambda r:(r.get('weight') or 0,r.get('manufacturer_sku') or '',r['sku']))
        if conflict and not active_hex:self.variant_choice.addItem(tr('Choisir d’abord une teinte ci-dessus…'),None)
        for row in available:
            grams=row.get('weight')
            weight=(f'{grams/1000:g} kg' if grams and grams>=1000 else f'{grams:g} g' if grams else tr('Masse non précisée')).replace('.',',')
            ref=row.get('manufacturer_sku')
            package=tr('Recharge') if row.get('spool_refill') is True else tr('Bobine') if row.get('spool_refill') is False else ''
            source='OFD' if row['sku'].startswith('OFD-') else 'SpoolmanDB' if row['sku'].startswith('SMDB-') else ''
            text=' · '.join(v for v in (weight,package,ref) if v)
            self.variant_choice.addItem(text,row['sku'])
            self.variant_choice.setItemData(self.variant_choice.count()-1,row['sku']+'\n'+row.get('quality',''),Qt.ToolTipRole)
        selected=sku if not conflict or chosen==sku else None
        self.variant_choice.setCurrentIndex(max(0,self.variant_choice.findData(selected)))
        self.variant_choice.blockSignals(False)
        visible=len(available)>1 and (not conflict or bool(active_hex))
        single=len(available)==1 and (not conflict or bool(active_hex))
        self.variant_label.setText(self.variant_choice.itemText(0) if single else tr('Bobine'))
        self.variant_label.setVisible(visible or single);self.variant_choice.setVisible(visible)
        preferred=core.load_config().get('preferred_weight_g',1000)
        missing=type(preferred) is int and preferred>0 and bool(available) and not any(v.get('weight')==preferred for v in available) and (not conflict or bool(active_hex))
        self.package_hint.setText(tr('Préférence {v0:g} kg indisponible pour cette fiche.', v0=preferred / 1000) if missing else '')
        self.package_hint.setVisible(missing)

    def _choose_shade(self, color):
        group=self._group_for_sku(self.current_sku)
        members=[r for r in (group or {}).get('variants',[]) if r.get('hex')==color]
        if members:
            current=next((r for r in members if r['sku']==self.current_sku),None)
            row=core.preferred_packaging(members,core.load_config(),current['sku'] if current else members[0]['sku'])
            self._remember_packaging(row['sku'])
            self._chosen_variant=row['sku'];self.current_sku=row['sku'];self._show_detail(row['sku'])

    def _variant_changed(self, *_):
        sku=self.variant_choice.currentData()
        if not sku:return
        self._remember_packaging(sku)
        self._chosen_variant=sku;self.current_sku=sku;self._show_detail(sku)

    def _variant_needs_choice(self):
        group=self._group_for_sku(self.current_sku)
        return bool(group and group.get('hex_variants',0)>1 and getattr(self,'_chosen_variant',None)!=self.current_sku)

    def _toggle_provenance(self, visible):
        self.provenance_box.setVisible(visible)
        if visible and hasattr(self,'detail_scroll'):
            QTimer.singleShot(0,lambda:self.detail_scroll.ensureWidgetVisible(self.provenance_box) if self.provenance_box.isVisible() else None)

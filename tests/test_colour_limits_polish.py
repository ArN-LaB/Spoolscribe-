"""Colour scope and usable controls; all fixtures stay offline."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from tests import test_gui as fixture
from spoolscribe import core


@unittest.skipUnless(fixture.HAS_QT, 'Qt unavailable')
class ColourLimitPolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass()
    def setUp(self):fixture.GuiTests.setUp(self)

    def test_limit_defaults_and_invalid_import_leave_settings_intact(self):
        self.assertEqual(core.colour_delta_limit(),10.0)
        for value in (True,-1,201,'10',float('inf'),float('nan')):
            with self.subTest(value=value):
                source=Path(self.tmp.name)/'settings.json'
                source.write_text(json.dumps(dict(format='spoolscribe-settings',version=1,settings={'colour_delta_max':value})))
                before=Path(core.CONFIG_PATH).read_bytes()
                with self.assertRaises(ValueError):core.import_settings(source)
                self.assertEqual(Path(core.CONFIG_PATH).read_bytes(),before)
        for value in (None,0,3,10.5,200):
            self.assertEqual(core.colour_delta_limit({'colour_delta_max':value}),value)
        self.assertEqual(core.colour_delta_limit({'colour_delta_max':False}),10.0)

    def test_limit_includes_boundary_uses_unrounded_score_and_counts_separately(self):
        w=self.window;w._colour_query=dict(hex='FF0000',cache={})
        rows=[dict(sku=str(i)) for i in range(4)]
        items=[dict(row=row,delta=delta,effect=False) for row,delta in zip(rows,(0,10,10.00001,59.7))]
        fake=dict(items=items,total=4,excluded={'unknown':2})
        with patch('spoolscribe.colour_distance.rank',return_value=fake):
            self.assertEqual(w._rank_by_colour(rows),rows[:2])
            self.assertEqual(w._colour_report['outside_limit'],2)
            self.assertEqual(w._colour_report['excluded'],{'unknown':2})
            cfg=core.load_config();cfg['colour_delta_max']=None;core.save_config(cfg)
            self.assertEqual(w._rank_by_colour(rows),rows)
            cfg['colour_delta_max']=0;core.save_config(cfg)
            self.assertEqual(w._rank_by_colour(rows),rows[:1])

    def test_settings_presets_manual_save_cancel_and_refresh(self):
        from PySide6.QtWidgets import QDialog,QComboBox,QDoubleSpinBox
        w=self.window;w._start_colour_search('070908');raw=Path(core.DB_PATH).read_bytes()
        def choose(dialog):
            presets=dialog.findChild(QComboBox,'colour_delta_preset');number=dialog.findChild(QDoubleSpinBox,'colour_delta_max')
            self.assertIsNotNone(presets);self.assertEqual(number.value(),10)
            presets.setCurrentIndex(presets.findData(3.0));self.assertEqual(number.value(),3)
            number.setValue(7.5);return QDialog.Accepted
        with patch('spoolscribe.app_gui.QDialog.exec',choose):w._open_settings()
        self.assertEqual(core.load_config()['colour_delta_max'],7.5)
        self.assertEqual(w._colour_report['limit'],7.5)
        def cancel(dialog):dialog.findChild(QDoubleSpinBox,'colour_delta_max').setValue(20);return QDialog.Rejected
        with patch('spoolscribe.app_gui.QDialog.exec',cancel):w._open_settings()
        self.assertEqual(core.load_config()['colour_delta_max'],7.5)
        self.assertEqual(Path(core.DB_PATH).read_bytes(),raw)

    def test_splitter_can_actually_drag_and_survives_theme_and_restore(self):
        from PySide6.QtCore import Qt,QPoint
        from PySide6.QtTest import QTest
        w=self.window;w.resize(1500,900);w.show();w.app.processEvents()
        handle=w.splitter.handle(1);before=w.sidebar.width();start=handle.rect().center()
        QTest.mousePress(handle,Qt.LeftButton,pos=start)
        QTest.mouseMove(handle,start+QPoint(90,0),20)
        QTest.mouseRelease(handle,Qt.LeftButton,pos=start+QPoint(90,0));w.app.processEvents()
        self.assertGreater(w.sidebar.width(),before+30)
        changed=w.sidebar.width();w._apply_theme();w.app.processEvents();self.assertEqual(w.sidebar.width(),changed)
        w._save_ui_preferences()
        cfg=core.load_config();cfg['ui'].pop('geometry',None);core.save_config(cfg)  # offscreen desktop clamps restored window geometry
        w.splitter.setSizes([before,650,400]);w._restore_ui_preferences();w.app.processEvents()
        self.assertAlmostEqual(w.sidebar.width(),changed,delta=3)

    def test_progress_card_and_state_arrows(self):
        from PySide6.QtCore import Qt
        w=self.window;w.show();w._show_detail('PB05001');w._choose_hardware_presentation(True)
        self.assertEqual(w.hardware_fold.arrowType(),Qt.DownArrow)
        w.hardware_fold.click();self.assertEqual(w.hardware_fold.arrowType(),Qt.RightArrow)
        w.update_progress_card.show();w.progress.show();w.progress_label.show()
        w._on_update_progress('Polymaker officiel',1,7)
        self.assertEqual(w.progress.value(),0);self.assertIn('1',w.progress_step.text());self.assertIn('7',w.progress_step.text())
        w._on_update_progress('Catalogue multi-fabricants OFD',7,7);self.assertEqual(w.progress.value(),6)
        w._finish_update_ui();self.assertFalse(w.update_progress_card.isVisible())

    def test_grid_score_is_separate_accessible_and_button_pairs_fit(self):
        w=self.window;w.show();w._show_detail('PB05001');w._start_colour_search('070908');w._set_view_mode('grid');w.app.processEvents()
        from PySide6.QtCore import Qt
        item=w.grid.item(0);row=w.grid.itemDelegate().rows[item.data(Qt.UserRole)]
        self.assertIn('_delta',row);self.assertIn('ΔE',item.data(Qt.AccessibleTextRole));self.assertIn('petit',item.toolTip())
        self.assertEqual(w.favorite_btn.width(),w.btn_similar.width())
        for button in (w.favorite_btn,w.btn_similar,w.hardware_change,w.export_details_button):
            self.assertGreaterEqual(button.width(),button.fontMetrics().horizontalAdvance(button.text())+18)

    def test_deeper_reel_stays_transparent_and_unclipped_at_both_sizes(self):
        from spoolscribe.ui_widgets import spool_icon
        for size in (112,256):
            for colour in ('FF8F41','000000',None):
                image=spool_icon(colour,size,1,True).pixmap(size,size).toImage()
                self.assertTrue(any(image.pixelColor(x,size//2).alpha()>0 for x in range(size)))
                for x in range(size):
                    self.assertEqual(image.pixelColor(x,0).alpha(),0)
                    self.assertEqual(image.pixelColor(x,size-1).alpha(),0)
                    self.assertEqual(image.pixelColor(0,x).alpha(),0)
                    self.assertEqual(image.pixelColor(size-1,x).alpha(),0)

    def test_grid_gives_comparison_footer_space_and_restores_compact_size(self):
        w=self.window;w._start_colour_search('070908');self.assertEqual(w.grid.gridSize().height(),232)
        w._stop_colour_search();self.assertEqual(w.grid.gridSize().height(),216)
        self.assertTrue(all(row.get('_delta') is None for row in w.grid.itemDelegate().rows.values()))

    def test_unrestricted_choice_roundtrips_and_updates_inactive_filter_label(self):
        from PySide6.QtWidgets import QDialog,QComboBox,QDoubleSpinBox
        w=self.window
        def choose(dialog):
            combo=dialog.findChild(QComboBox,'colour_delta_preset');combo.setCurrentIndex(combo.findData(None))
            self.assertFalse(dialog.findChild(QDoubleSpinBox,'colour_delta_max').isEnabled())
            return QDialog.Accepted
        with patch('spoolscribe.app_gui.QDialog.exec',choose):w._open_settings()
        self.assertIsNone(core.load_config()['colour_delta_max'])
        target=Path(self.tmp.name)/'prefs.json';core.export_settings(target)
        cfg=core.load_config();cfg['colour_delta_max']=3;core.save_config(cfg)
        core.import_settings(target);w._restore_ui_preferences()
        self.assertIsNone(core.colour_delta_limit());self.assertIn('Sans limite',w.colour_limit_button.text())

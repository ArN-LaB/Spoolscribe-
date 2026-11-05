"""Guided measurement workflow, reusable explicit device settings and narrow layouts."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from tests import test_measurement_ui as existing
from tests import test_gui as fixture
from spoolscribe import core

@unittest.skipUnless(fixture.HAS_QT, 'Qt unavailable')
class MeasurementUxTests(unittest.TestCase):
    setUpClass = classmethod(existing.MeasurementUiTests.setUpClass.__func__)
    setUp = existing.MeasurementUiTests.setUp
    open_window = existing.MeasurementUiTests.open_window

    def test_import_starts_with_file_choice_and_contextual_footer(self):
        d=self.open_window(); d.tabs.setCurrentIndex(2); self.app.processEvents()
        self.assertFalse(d.preview.isVisible())
        self.assertFalse(d.mapping_panel.isVisible())
        self.assertFalse(d.btn_save.isVisible()); self.assertFalse(d.btn_search.isVisible())
        self.assertTrue(d.btn_check.isVisible()); self.assertTrue(d.btn_import.isVisible())
        self.assertFalse(d.btn_check.isEnabled())
        self.assertFalse(d.level_tile.isVisible())

    def test_conditions_and_optional_fields_use_full_width_groups(self):
        d=self.open_window(); d.space.setCurrentIndex(d.space.findData('CIELAB'))
        d.manual_conditions.advanced_toggle.setChecked(True); d.details_toggle.setChecked(True)
        self.app.processEvents()
        self.assertEqual(d.manual_conditions.layout().columnCount(),2)
        self.assertLessEqual(d.manual_conditions.advanced_toggle.text().__len__(),35)
        self.assertEqual(d.details.layout().columnCount(),2)
        self.assertGreater(d.conditions_box.width(),d.width()*.7)
        self.assertNotEqual(d.lab_edits['L'].placeholderText(),d.lab_edits['a'].placeholderText())

    def test_saved_uses_one_search_action_and_preserves_disabled_save(self):
        d=self.open_window(); d.tabs.setCurrentIndex(3); self.app.processEvents()
        self.assertFalse(d.btn_use.isVisible())
        self.assertTrue(d.btn_search.isVisible()); self.assertFalse(d.btn_save.isVisible())

    def test_qr_has_distinct_semantic_action_tone(self):
        self.assertEqual(self.window.btn_qr.property('actionTone'),'companion')

    def test_device_preset_explicit_application_and_no_calibration_or_sample_reuse(self):
        d=self.open_window(); d.space.setCurrentIndex(d.space.findData('CIELAB'))
        d.device_manufacturer.setText('Example'); d.device_model.setText('Meter')
        d.geometry.setText('45/0'); d.calibration.setText('Yesterday'); d.sample_material.setText('PLA')
        d.illuminant.setCurrentIndex(d.illuminant.findData('D65')); d.observer.setCurrentIndex(d.observer.findData(2))
        with patch('spoolscribe.ui_colour_measurements.QInputDialog.getText',return_value=('My meter',True)):
            d.btn_profile_save.click()
        self.assertTrue(d.device_profiles.path.is_file())
        d.profile_default.click()
        d.close()
        from spoolscribe.ui_colour_measurements import MeasurementWindow
        d=MeasurementWindow(self.window,registry=d.registry); self.addCleanup(d.close); d.show(); self.app.processEvents()
        d.space.setCurrentIndex(d.space.findData('CIELAB'))
        self.assertIsNone(d.illuminant.currentData()); self.assertIsNone(d.observer.currentData())
        self.assertEqual(d.device_profile.currentText(),'My meter')
        d.btn_profile_apply.click()
        self.assertEqual(d.illuminant.currentData(),'D65'); self.assertEqual(d.geometry.text(),'45/0')
        self.assertEqual(d.device_model.text(),'Meter'); self.assertEqual(d.calibration.text(),'')
        self.assertEqual(d.sample_material.text(),''); self.assertEqual(d.lab_edits['L'].text(),'')
        self.assertNotIn('Yesterday',d.device_profiles.path.read_text())
        self.assertFalse(d.registry.path.exists())

    def test_profile_write_refuses_concurrent_change_and_corrupt_file(self):
        from spoolscribe.device_profiles import DeviceProfiles
        from scripts import db_io
        path=Path(core.DB_PATH).with_name('test_device_profiles.json')
        a=DeviceProfiles(path); b=DeviceProfiles(path); a.load(); b.load()
        a.add('One',{'illuminant':'D65','observer':2},'Brand','Model')
        before=path.read_bytes()
        with self.assertRaises(db_io.DatabaseError):b.add('Two',{},'','')
        self.assertEqual(path.read_bytes(),before)
        path.write_text('{broken')
        c=DeviceProfiles(path)
        with self.assertRaises(db_io.DatabaseError):c.load()
        with self.assertRaises(db_io.DatabaseError):c.add('Three',{},'','')
        self.assertEqual(path.read_text(),'{broken')

    def test_presets_validate_whitelist_limits_and_default_identity(self):
        from spoolscribe.device_profiles import validate, empty
        from spoolscribe.colour_measurements import MeasurementError
        import copy
        identifier='a'*32
        valid=empty(); valid['profiles'][identifier]={'name':'Meter','manufacturer':'Brand','model':'X','conditions':{'illuminant':'D65','observer':2}}
        self.assertEqual(validate(valid)['profiles'][identifier]['conditions']['observer'],2)
        for change in ('calibration','measurement','unknown_default','too_many','bad_observer'):
            candidate=copy.deepcopy(valid)
            if change=='calibration':candidate['profiles'][identifier]['conditions']['calibration']='yesterday'
            elif change=='measurement':candidate['profiles'][identifier]['L']=50
            elif change=='unknown_default':candidate['default']='b'*32
            elif change=='too_many':candidate['profiles']={f'{i:032x}':valid['profiles'][identifier] for i in range(33)}
            else:candidate['profiles'][identifier]['conditions']['observer']=True
            with self.subTest(change=change), self.assertRaises(MeasurementError):validate(candidate)

    def test_device_name_never_infers_comparison_conditions(self):
        from spoolscribe.device_profiles import DeviceProfiles
        p=DeviceProfiles(Path(core.DB_PATH).with_name('colour_device_profiles.json'))
        identifier=p.add('Meter D65 2 degrees',{},'D65','2 degrees'); p.set_default(identifier)
        d=self.open_window();d.space.setCurrentIndex(d.space.findData('CIELAB'))
        for key,value in [('L','50'),('a','0'),('b','0')]:d.lab_edits[key].setText(value)
        d.btn_profile_apply.click()
        self.assertIsNone(d.observer.currentData());self.assertIsNone(d.illuminant.currentData())
        self.assertFalse(d.btn_search.isEnabled());self.assertTrue(d.btn_save.isEnabled())

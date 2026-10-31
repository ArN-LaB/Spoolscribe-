import json
import unittest

import core
from scripts.db_io import validate_db
from tests.support import ROOT, catalogue


class CatalogueTests(unittest.TestCase):
    def test_every_sku_has_an_export_or_a_reviewed_reason(self):
        db = catalogue()
        validate_db(db)
        reviewed = json.loads((ROOT / "tests/fixtures/catalogue_exceptions.json").read_text())
        exported = 0
        for sku, entry in db["_skus"].items():
            with self.subTest(sku=sku):
                view = core.get_sku_view(db, sku)
                if view is None:
                    self.assertIn(sku, reviewed["orphan_products"])
                    continue
                if not entry.get("hex"):
                    self.assertIn(sku, reviewed["missing_hex"])
                    with self.assertRaises(core.MissingColorError):
                        core.build_openspool(entry, view.product_data, view.brand_meta)
                    continue
                payload = core.build_openspool(dict(entry, sku=sku), view.product_data, view.brand_meta)
                compact = core.serialize_openspool(payload)
                self.assertEqual(json.loads(compact), json.loads(core.serialize_openspool(payload, mode="archive")))
                self.assertTrue(core.nfc_size(compact).fits)
                self.assertEqual(payload["brand"], view.product_data["brand"])
                exported += 1
        self.assertGreater(exported, 1000)

    def test_every_product_has_coherent_physical_values(self):
        for name, product in catalogue()["_products"].items():
            with self.subTest(product=name):
                core._validate_physical(product)

    def test_hardware_references_keep_uncertain_mappings(self):
        data = json.loads((ROOT / "tests/fixtures/observed_filaments.json").read_text())
        observations = data["observations"]
        self.assertEqual([o["color_hex"] for o in observations], ["070908", "A78403", "91C500"])
        self.assertEqual(catalogue()["_skus"]["PB05001"]["hex"], observations[0]["color_hex"])
        self.assertIsNone(observations[1]["candidate_sku"])
        self.assertIsNone(observations[2]["candidate_sku"])
        self.assertTrue(all("density" not in o and "min_temp" not in o for o in observations))

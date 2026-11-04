"""Paste interpretation and CSV/TSV mapping (synthetic fixtures only, no I/O side effects)."""
import hashlib
from pathlib import Path
import unittest

from spoolscribe import colour_import as ci, colour_measurements as cm
from tests.support import ROOT

FIXTURES = ROOT / "tests/fixtures/measurements"


def fixture(name):
    return (FIXTURES / name).read_bytes()


class PasteTests(unittest.TestCase):
    def test_french_and_english_labelled_values(self):
        result = ci.interpret_paste("L*=73,2 ; a*=-25,6 ; b*=-12,4")
        self.assertEqual([c["space"] for c in result["candidates"]], ["CIELAB"])
        self.assertEqual(result["candidates"][0]["components"], {"L": 73.2, "a": -25.6, "b": -12.4})
        self.assertEqual(result["candidates"][0]["lexemes"]["L"], "73,2")
        self.assertFalse(result["needs_decision"])
        english = ci.interpret_paste("Lab: 73.2, -25.6, -12.4 (D65, 2 deg)")
        self.assertEqual(english["candidates"][0]["components"]["a"], -25.6)
        self.assertEqual(english["conditions"], {"illuminant": "D65", "observer": 2})

    def test_hex_and_rgb_consistency_is_reported_not_assumed(self):
        agree = ci.interpret_paste("HEX #74CABF — RGB 116 202 191")
        self.assertTrue(agree["consistent"]); self.assertTrue(agree["needs_decision"])
        disagree = ci.interpret_paste(fixture("synthetic_paste_conflicts.txt").decode("utf-8"))
        self.assertFalse(disagree["consistent"])
        self.assertEqual({c["space"] for c in disagree["candidates"]}, {"sRGB_HEX", "sRGB_RGB8", "CIELAB"})
        self.assertEqual(disagree["conditions"], {"illuminant": "D50", "observer": 10})
        self.assertTrue(disagree["needs_decision"])
        self.assertTrue(any("ne correspondent pas" in e for e in disagree["errors"]))

    def test_unlabelled_numbers_and_partial_sets_are_never_coordinates(self):
        result = ci.interpret_paste("valeurs 73.2 -25.6 -12.4")
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["unlabelled_numbers"], 3)
        self.assertTrue(result["errors"])
        partial = ci.interpret_paste("L*=50 a*=1")
        self.assertEqual(partial["candidates"], [])
        self.assertIn("incomplètes", partial["errors"][0])
        self.assertEqual(ci.interpret_paste("Lab 73.2 -25.6")["candidates"], [])

    def test_conditions_conflicts_and_other_illuminants(self):
        several = ci.interpret_paste("L*=1 a*=2 b*=3 D50 ... D65 2°")
        self.assertIsNone(several["conditions"]["illuminant"]); self.assertTrue(several["needs_decision"])
        other = ci.interpret_paste("L*=1 a*=2 b*=3 TL84 10°")
        self.assertEqual(other["conditions"]["illuminant"], "other")
        self.assertEqual(other["conditions"]["illuminant_note"], "TL84")
        self.assertEqual(other["conditions"]["observer"], 10)

    def test_bounds_bad_values_and_non_text(self):
        self.assertIn("trop long", ci.interpret_paste("x" * (cm.LIMITS["paste_bytes"] + 1))["errors"][0])
        self.assertTrue(ci.interpret_paste(None)["errors"])
        bad_rgb = ci.interpret_paste("RGB 300 0 0")
        self.assertEqual(bad_rgb["candidates"], []); self.assertIn("0–255", bad_rgb["errors"][0])
        bad_lab = ci.interpret_paste("L*=150 a*=0 b*=0")
        self.assertEqual(bad_lab["candidates"], []); self.assertIn("L*", bad_lab["errors"][0])
        ambiguous = ci.interpret_paste("L*=1,234.5 a*=0 b*=0")
        self.assertEqual(ambiguous["candidates"], [])

    def test_candidate_becomes_a_validated_original_keeping_alternatives(self):
        result = ci.interpret_paste("HEX #74CABF RGB 116 202 191")
        chosen = result["candidates"][1]
        original = ci.candidate_to_original(chosen, result["candidates"])
        self.assertEqual(original["space"], "sRGB_RGB8")
        self.assertEqual([a["space"] for a in original["alternatives"]], ["sRGB_HEX"])


class CsvTests(unittest.TestCase):
    def test_semicolon_decimal_comma_crlf_duplicates_and_errors(self):
        data = fixture("synthetic_lab_semicolon_fr.csv")
        preview = ci.preview_csv(data)
        self.assertEqual((preview["encoding"], preview["delimiter"]), ("utf-8", ";"))
        self.assertEqual(preview["header"], ["Sample", "L*", "a*", "b*", "Illuminant", "Observer", "Device"])
        self.assertEqual(preview["records"], 5); self.assertEqual(len(preview["preview"]), 5)
        mapping = ci.propose_mapping(preview["header"])["mapping"]
        self.assertEqual(mapping, {"name": 0, "L": 1, "a": 2, "b": 3, "illuminant": 4, "observer": 5, "device": 6})
        records = ci.read_records(ci.decode_text(data)[0], ";")[1:]
        report = ci.validate_rows(records, mapping, decimal=",", file_name="synthetic_lab_semicolon_fr.csv",
                                  file_sha256=preview["file_sha256"])
        self.assertEqual(len(report["valid"]), 4)
        self.assertEqual(report["errors"], [(5, "Nombre invalide : « abc ».")])
        self.assertEqual(report["duplicates"], [(4, 1)])
        rouge = report["valid"][0]["measurement"]
        self.assertEqual(rouge["name"], "Cible rouge")
        self.assertEqual(rouge["original"]["lexemes"]["L"], "52,3")
        self.assertEqual(rouge["conditions"]["observer"], 2)
        self.assertEqual(rouge["provenance"]["device_model"], "Synthétique A")
        self.assertEqual(rouge["provenance"]["record_number"], 1)
        self.assertEqual(rouge["provenance"]["file_sha256"], hashlib.sha256(data).hexdigest())
        blocked = report["valid"][2]["measurement"]
        self.assertEqual(cm.comparison_policy(blocked)["reason"], "adaptation_unavailable")
        # The confirmed decimal mark is enforced: a point in a comma file is an error, not a guess.
        wrong = ci.validate_rows(records, mapping, decimal=".")
        self.assertEqual(len(wrong["valid"]), 0); self.assertEqual(len(wrong["errors"]), 5)

    def test_comma_separated_rgb_with_point_decimals(self):
        data = fixture("synthetic_rgb_comma.csv")
        preview = ci.preview_csv(data)
        self.assertEqual(preview["delimiter"], ",")
        mapping = ci.propose_mapping(preview["header"])["mapping"]
        self.assertEqual(mapping, {"name": 0, "r": 1, "g": 2, "b_rgb": 3, "note": 4})
        records = ci.read_records(ci.decode_text(data)[0], ",")[1:]
        report = ci.validate_rows(records, mapping, decimal=".")
        self.assertEqual([v["measurement"]["name"] for v in report["valid"]], ["teal", "black"])
        self.assertEqual(cm.hex_of(report["valid"][0]["measurement"]), "74CABF")
        self.assertEqual(report["errors"][0][0], 3)

    def test_bom_tab_quoted_multiline_and_logical_record_numbers(self):
        data = fixture("synthetic_lab_bom_crlf.tsv")
        preview = ci.preview_csv(data)
        self.assertEqual((preview["encoding"], preview["delimiter"]), ("utf-8-sig", "\t"))
        self.assertEqual(preview["records"], 2)   # logical records, not physical lines
        mapping = ci.propose_mapping(preview["header"])["mapping"]
        self.assertEqual(mapping, {"L": 0, "a": 1, "b": 2, "illuminant": 3, "observer": 4, "name": 5})
        records = ci.read_records(ci.decode_text(data)[0], "\t")[1:]
        report = ci.validate_rows(records, mapping, decimal=".")
        self.assertEqual(report["valid"][0]["measurement"]["name"], "first\nsample")
        self.assertEqual(report["valid"][0]["record"], 1)
        self.assertEqual(cm.comparison_policy(report["valid"][1]["measurement"])["reason"], "observer_unsupported")

    def test_duplicate_headers_are_listed_not_resolved(self):
        proposal = ci.propose_mapping(["L", "L", "a", "b", "R", "G", "B"])
        self.assertNotIn("L", proposal["mapping"])
        self.assertEqual(proposal["duplicates"]["L"], [0, 1])
        self.assertEqual(proposal["duplicates"]["b"], [3, 6])
        self.assertEqual(ci.propose_mapping(["Name", "R", "G", "B"])["mapping"], {"name": 0, "r": 1, "g": 2, "b_rgb": 3})
        self.assertEqual(ci.propose_mapping(["LAB_L", "LAB_A", "LAB_B", "Sample", "Device"])["mapping"],
                         {"L": 0, "a": 1, "b": 2, "name": 3, "device": 4})
        self.assertIn(1, ci.propose_mapping(["L*", "=SUM(A1)", "a*", "b*"])["unmapped"])

    def test_encoding_is_explicit_and_never_replaced(self):
        data = fixture("synthetic_latin1.csv")
        with self.assertRaises(ValueError):
            ci.preview_csv(data)
        preview = ci.preview_csv(data, encoding="latin-1")
        self.assertEqual(preview["encoding"], "latin-1")
        records = ci.read_records(ci.decode_text(data, "cp1252")[0], ";")[1:]
        report = ci.validate_rows(records, ci.propose_mapping(preview["header"])["mapping"], decimal=",")
        self.assertEqual(report["valid"][0]["measurement"]["name"], "échantillon")
        with self.assertRaises(ValueError):
            ci.decode_text(data, "utf-16")
        with self.assertRaises(ValueError):
            ci.preview_csv(b"")

    def test_limits_are_enforced_before_any_write(self):
        with self.assertRaises(ValueError):
            ci.decode_text(b"x" * (cm.LIMITS["file_bytes"] + 1))
        wide = (",".join(f"c{i}" for i in range(cm.LIMITS["columns"] + 1)) + "\n").encode()
        with self.assertRaises(ValueError):
            ci.preview_csv(wide)
        big_cell = ("L,a,b\n" + "x" * (cm.LIMITS["cell"] + 1) + ",1,2\n").encode()
        with self.assertRaises(ValueError):
            ci.preview_csv(big_cell)
        many = ("L,a,b\n" + "50,0,0\n" * (cm.LIMITS["records"] + 1)).encode()
        with self.assertRaises(ValueError):
            ci.preview_csv(many)
        exact = ("L,a,b\n" + "50,0,0\n" * cm.LIMITS["records"]).encode()
        self.assertEqual(ci.preview_csv(exact)["records"], cm.LIMITS["records"])

    def test_unmapped_colour_columns_and_blank_or_corrupt_records(self):
        report = ci.validate_rows([["x", "y"], ["", ""], ["1", "2"]], {"name": 0}, decimal=".")
        self.assertEqual(len(report["valid"]), 0)
        self.assertEqual([e[0] for e in report["errors"]], [1, 3])   # the blank record is skipped
        with self.assertRaises(ValueError):
            ci.validate_rows([], {}, decimal=";")
        with self.assertRaises(ValueError):
            ci.read_records('a,"unterminated\n', ",")

    def test_registry_duplicates_are_information_only(self):
        measurement = cm.new_measurement(cm.parse_manual("CIELAB", {"L": "50", "a": "0", "b": "0"}), name="m",
                                         provenance={"method": "csv", "file_sha256": "a" * 64, "record_number": 3})
        registry = {"MEAS-x": measurement}
        report = ci.registry_duplicates([{"record": 3, "measurement": measurement}], registry)
        self.assertEqual(report["similar"][measurement["content_digest"]], ["MEAS-x"])
        self.assertEqual(report["reimported"][("a" * 64, 3)], ["MEAS-x"])

    def test_fixture_bytes_are_never_modified_by_an_import(self):
        for name in ("synthetic_lab_semicolon_fr.csv", "synthetic_rgb_comma.csv", "synthetic_lab_bom_crlf.tsv"):
            path = FIXTURES / name
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            preview = ci.preview_csv(path.read_bytes())
            records = ci.read_records(ci.decode_text(path.read_bytes())[0], preview["delimiter"])[1:]
            ci.validate_rows(records, ci.propose_mapping(preview["header"])["mapping"], decimal="," if preview["delimiter"] == ";" else ".")
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)


if __name__ == "__main__":
    unittest.main()


class CorrectionTests(unittest.TestCase):
    """Regressions of the independent QA (R2/R3): strict tokens, unbalanced sets, explicit principal, strict observer."""

    def test_rgb_tokens_are_whole_and_only_srgb(self):
        unsupported = ci.interpret_paste("Adobe RGB 116 202 191")
        self.assertEqual(unsupported["candidates"], []); self.assertEqual(unsupported["unsupported"], ["Adobe RGB"])
        self.assertIn("non pris en charge", unsupported["errors"][0]); self.assertTrue(unsupported["needs_decision"])
        for text in ("RGB 116 202 191.5", "RGB 116 202 1910", "RGB 116 202 19a"):
            result = ci.interpret_paste(text)
            self.assertEqual(result["candidates"], [], text); self.assertIn("refusé", result["errors"][0])
        for text in ("Display P3 RGB 1 2 3", "ProPhoto RGB 1 2 3", "Rec. 2020 RGB 1 2 3"):
            self.assertEqual(ci.interpret_paste(text)["candidates"], [], text)
        accepted = ci.interpret_paste("Couleur RGB 116 202 191")
        self.assertEqual(accepted["candidates"][0]["components"], {"r": 116, "g": 202, "b": 191})
        self.assertEqual(ci.interpret_paste("sRGB (116, 202, 191)")["candidates"][0]["space"], "sRGB_RGB8")
        self.assertEqual(ci.interpret_paste("HEX #1122334")["candidates"], [])   # seven digits are not a HEX code

    def test_unbalanced_labelled_lab_sets_are_reported_not_truncated(self):
        result = ci.interpret_paste("L*=50 a*=1 b*=2 L*=80 D65 2°")
        self.assertTrue(result["needs_decision"])
        self.assertTrue(any("incomplètes" in e and "L* 80" in e for e in result["errors"]), result["errors"])
        self.assertEqual(len(result["candidates"]), 1)   # the complete set stays a proposal, but a decision is required
        balanced = ci.interpret_paste("L*=50 a*=1 b*=2 ; L*=80 a*=3 b*=4")
        self.assertEqual([c["components"]["L"] for c in balanced["candidates"]], [50.0, 80.0]); self.assertTrue(balanced["needs_decision"])
        reordered = ci.interpret_paste("b*=2 a*=1 L*=50")
        self.assertEqual(reordered["candidates"][0]["components"], {"L": 50.0, "a": 1.0, "b": 2.0})
        self.assertFalse(reordered["needs_decision"])

    def test_signed_observer_is_refused_in_pasted_text(self):
        result = ci.interpret_paste("L*=50 a*=1 b*=2 D65 -2°")
        self.assertIsNone(result["conditions"]["observer"]); self.assertTrue(result["needs_decision"])
        self.assertTrue(any("refusé" in e and "-2°" in e for e in result["errors"]))
        self.assertEqual(ci.interpret_paste("L*=50 a*=1 b*=2 D65 2°")["conditions"]["observer"], 2)

    def test_recognised_context_is_kept_on_every_alternative(self):
        result = ci.interpret_paste(fixture("synthetic_paste_conflicts.txt").decode("utf-8"))
        chosen = next(c for c in result["candidates"] if c["space"] == "sRGB_HEX")
        original = ci.candidate_to_original(chosen, result["candidates"], conditions=result["conditions"])
        self.assertEqual(original["space"], "sRGB_HEX")
        self.assertEqual({a["space"] for a in original["alternatives"]}, {"sRGB_RGB8", "CIELAB"})
        for alternative in original["alternatives"]:
            self.assertEqual((alternative["conditions"]["illuminant"], alternative["conditions"]["observer"]), ("D50", 10))
        measurement = cm.new_measurement(original, name="h", conditions=result["conditions"])
        self.assertEqual(cm.comparison_policy(measurement)["reason"], "srgb_declared")   # context is not a measured illuminant
        self.assertIn("contexte déclaré", cm.describe_conditions(measurement))

    def test_paste_errors_are_translatable_items(self):
        result = ci.interpret_paste("RGB 300 0 0")
        self.assertEqual(len(result["error_items"]), len(result["errors"]))
        self.assertEqual(ci.error_messages(result, lambda t, **v: "EN:" + t.format(**v)), ["EN:" + result["errors"][0]])

    def test_two_colour_spaces_require_an_explicit_principal(self):
        rows = [["50", "1", "2", "FF0000", "D65", "2"]]
        mapping = {"L": 0, "a": 1, "b": 2, "hex": 3, "illuminant": 4, "observer": 5}
        self.assertEqual(ci.mapped_spaces(mapping), ["CIELAB", "sRGB_HEX"])
        with self.assertRaises(cm.MeasurementError) as refused:
            ci.validate_rows(rows, mapping)
        self.assertIn("jeu principal", str(refused.exception))
        with self.assertRaises(cm.MeasurementError):
            ci.validate_rows(rows, mapping, principal="sRGB_RGB8")
        lab_first = ci.validate_rows(rows, mapping, principal="CIELAB")
        original = lab_first["valid"][0]["measurement"]["original"]
        self.assertEqual(original["space"], "CIELAB"); self.assertEqual([a["space"] for a in original["alternatives"]], ["sRGB_HEX"])
        self.assertEqual(original["alternatives"][0]["components"], {"hex": "FF0000"}); self.assertEqual(lab_first["principal"], "CIELAB")
        hex_first = ci.validate_rows(rows, mapping, principal="sRGB_HEX")
        original = hex_first["valid"][0]["measurement"]["original"]
        self.assertEqual(original["space"], "sRGB_HEX"); self.assertEqual([a["space"] for a in original["alternatives"]], ["CIELAB"])
        single = ci.validate_rows(rows, {"L": 0, "a": 1, "b": 2})   # one space: simple path, no principal needed
        self.assertEqual(single["valid"][0]["measurement"]["original"]["alternatives"], [])

    def test_inconsistent_secondary_sets_become_warnings_not_silent_choices(self):
        mapping = {"hex": 0, "r": 1, "g": 2, "b_rgb": 3}
        report = ci.validate_rows([["FF0000", "0", "0", "255"], ["00FF00", "0", "255", "0"], ["0000FF", "x", "0", "0"]], mapping, principal="sRGB_HEX")
        self.assertEqual(len(report["valid"]), 3); self.assertEqual(report["errors"], [])
        self.assertEqual([n for n, _ in report["warnings"]], [1, 3])
        self.assertIn("diffèrent", report["warnings"][0][1]); self.assertIn("ignoré", report["warnings"][1][1])
        self.assertEqual(cm.hex_of(report["valid"][0]["measurement"]), "FF0000")
        self.assertEqual(report["valid"][2]["measurement"]["original"]["alternatives"], [])

    def test_observer_cells_follow_the_allowed_notations_only(self):
        mapping = {"L": 0, "a": 1, "b": 2, "illuminant": 3, "observer": 4}
        refused = ci.validate_rows([["50", "1", "2", "D65", "-2°"], ["50", "1", "2", "D65", "two"], ["50", "1", "2", "D65", "12"]], mapping)
        self.assertEqual(refused["valid"], []); self.assertEqual([n for n, _ in refused["errors"]], [1, 2, 3])
        self.assertIn("observateur inconnu", refused["errors"][0][1]); self.assertIn("-2°", refused["errors"][0][1])
        accepted = ci.validate_rows([["50", "1", "2", "D65", "2°"], ["50", "1", "2", "D65", "2"], ["50", "1", "2", "D65", "10 deg"], ["50", "1", "2", "D65", "10"]], mapping)
        self.assertEqual([v["measurement"]["conditions"]["observer"] for v in accepted["valid"]], [2, 2, 10, 10])
        from unittest.mock import patch
        from spoolscribe import colour_targets as ct
        with patch("spoolscribe.colour_distance.ciede2000") as delta:
            with self.assertRaises(ct.TargetBlocked):
                ct.target_from_measurement(accepted["valid"][2]["measurement"])
        delta.assert_not_called()

    def test_extended_columns_fill_conditions_sample_and_manufacturer(self):
        header = ["Sample", "L*", "a*", "b*", "Geometry", "Specular", "Aperture", "Manufacturer", "Device", "Material", "Finish", "Thickness", "Backing"]
        mapping = ci.propose_mapping(header)["mapping"]
        self.assertEqual(mapping, {"name": 0, "L": 1, "a": 2, "b": 3, "geometry": 4, "specular": 5, "aperture": 6, "manufacturer": 7,
                                   "device": 8, "material": 9, "finish": 10, "thickness": 11, "backing": 12})
        report = ci.validate_rows([["s", "50", "1", "2", "45/0", "SCE", "8 mm", "Acme", "M1", "PLA", "matte", "2 mm", "white"]], mapping)
        measurement = report["valid"][0]["measurement"]
        self.assertEqual((measurement["conditions"]["geometry"], measurement["conditions"]["specular"], measurement["conditions"]["aperture"]), ("45/0", "SCE", "8 mm"))
        self.assertEqual((measurement["provenance"]["device_manufacturer"], measurement["provenance"]["device_model"]), ("Acme", "M1"))
        self.assertEqual({k: measurement["sample"][k] for k in ("material", "finish", "thickness", "backing")}, {"material": "PLA", "finish": "matte", "thickness": "2 mm", "backing": "white"})
        self.assertIsNone(measurement["conditions"]["illuminant"])   # nothing inferred

    def test_local_file_size_is_checked_before_any_read(self):
        import os, tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            big = Path(tmp) / "big.csv"
            with open(big, "wb") as stream:
                stream.truncate(cm.LIMITS["file_bytes"] + 1)   # sparse: the size alone must refuse it
            with patch("spoolscribe.colour_import.open", create=True, side_effect=AssertionError("must not read")):
                with self.assertRaises(cm.MeasurementError) as refused:
                    ci.read_local_file(big)
            self.assertIn("volumineux", str(refused.exception))
            small = Path(tmp) / "small.csv"; small.write_bytes(b"L,a,b\n50,0,0\n")
            self.assertEqual(ci.read_local_file(small), b"L,a,b\n50,0,0\n")
            self.assertEqual(os.stat(big).st_size, cm.LIMITS["file_bytes"] + 1)


class RgbSegmentationTests(unittest.TestCase):
    """R2 after the re-QA 09: an RGB channel is one whole token; a remnant refuses the set, it is never cut off."""

    RGB = {"r": 116, "g": 202, "b": 191}

    def rgb_candidates(self, result):
        return [c for c in result["candidates"] if c["space"] == "sRGB_RGB8"]

    def test_decimal_comma_channel_is_refused_not_truncated(self):
        result = ci.interpret_paste("RGB 116 202 191,5")
        self.assertEqual(result["candidates"], [])   # never RGB8 116/202/191
        self.assertTrue(result["needs_decision"])
        self.assertEqual(result["errors"], ["RGB « 116 202 191,5 » refusé : trois entiers 0–255 sans décimale sont requis."])
        self.assertEqual(len(result["error_items"]), 1)
        from spoolscribe import i18n
        self.addCleanup(i18n.set_language, "fr")
        for language, expected in (("en", "RGB “116 202 191,5” refused: three integers 0–255 without decimals are required."),
                                   ("es", "RGB «116 202 191,5» rechazado: se requieren tres enteros 0–255 sin decimales.")):
            i18n.set_language(language)
            self.assertEqual(ci.error_messages(result, i18n.tr), [expected])

    def test_channel_remnants_never_reappear_as_a_shorter_valid_set(self):
        # (pasted text, the values quoted as typed in the refusal)
        for text, quoted in (("RGB 116 202 191,5", "116 202 191,5"), ("RGB 116 202 191,50", "116 202 191,50"),
                             ("sRGB 116 202 191,5", "116 202 191,5"), ("RVB 116 202 191,5", "116 202 191,5"),
                             ("RGB: 116; 202; 191,5", "116; 202; 191,5"), ("RGB(116, 202, 191,5)", "116, 202, 191,5"),
                             ("RGB 116 202 191 ,5", "116 202 191 ,5"), ("RGB 116 202 191,5 D65 2°", "116 202 191,5"),
                             ("RGB 116,5 202 191", "116,5 202 191"), ("RGB 116 202,5 191", "116 202,5 191"),
                             ("RGB 116, 202,5, 191", "116, 202,5, 191"), ("RGB 116,202,191,5", "116,202,191,5"),
                             ("RGB 116;202;191;5", "116;202;191;5"), ("RGB 116, 202, 191, 5", "116, 202, 191, 5"),
                             ("RGB 116 202 191 255", "116 202 191 255"), ("RGB 116 202 191.5", "116 202 191.5"),
                             ("RGB 116.0 202 191", "116.0 202 191"), ("RGB 116 202 1910", "116 202 1910"),
                             ("RGB 1160 202 191", "1160 202 191"), ("RGB 116 202 19a", "116 202 19a"),
                             ("RGB 116 202 -1", "116 202 -1")):
            with self.subTest(text=text):
                result = ci.interpret_paste(text)
                self.assertEqual(result["candidates"], [])
                self.assertTrue(result["needs_decision"])
                self.assertIn(f"RGB « {quoted} » refusé", " | ".join(result["errors"]))
        for text in ("RGB 256 0 0", "RGB 116 202 300"):
            with self.subTest(text=text):
                result = ci.interpret_paste(text)
                self.assertEqual(result["candidates"], []); self.assertIn("0–255", result["errors"][0])
        for text in ("Adobe RGB 116 202 191,5", "Display P3 RGB 116 202 191"):
            with self.subTest(text=text):
                result = ci.interpret_paste(text)
                self.assertEqual(result["candidates"], []); self.assertTrue(result["unsupported"])

    def test_a_refused_set_does_not_hide_or_replace_the_other_sets(self):
        result = ci.interpret_paste("HEX #74CABF RGB 116 202 191,5")
        self.assertEqual([c["space"] for c in result["candidates"]], ["sRGB_HEX"])
        self.assertTrue(result["needs_decision"])   # the HEX set is not chosen automatically
        self.assertIsNone(result["consistent"])
        several = ci.interpret_paste("RGB 116 202 191,5 ; RGB 10 20 30")
        self.assertEqual([c["components"] for c in self.rgb_candidates(several)], [{"r": 10, "g": 20, "b": 30}])
        self.assertTrue(several["needs_decision"])

    def test_documented_rgb_notations_are_still_accepted(self):
        for text, case in (("RGB 116 202 191", None), ("RGB 116, 202, 191", None), ("RGB 116,202,191", None),
                           ("RGB(116,202,191)", None), ("rgb(116, 202, 191)", None), ("RGB: 116; 202; 191", None),
                           ("sRGB (116, 202, 191)", None), ("RVB 116 202 191", None), ("Couleur RGB 116 202 191", None),
                           ("RGB 116  202  191", None), ("RGB 116, 202, 191, D65 2°", None), ("RGB 116 202 191 D65 10°", None),
                           ("RGB 116 202 191 10°", None), ("RGB 116 202 191 2 deg", None), ("RGB 116, 202, 191.", "refused"),
                           ("RGB 116 202 191\nL*=50 a*=1 b*=2", "lab")):
            with self.subTest(text=text):
                result = ci.interpret_paste(text)
                if case == "refused":   # a trailing full stop stays a remnant: refused, never cut (unchanged since 07)
                    self.assertEqual(self.rgb_candidates(result), []); continue
                self.assertEqual([c["components"] for c in self.rgb_candidates(result)], [self.RGB])
                self.assertEqual(self.rgb_candidates(result)[0]["lexemes"], {"r": "116", "g": "202", "b": "191"})
                if case != "lab":
                    self.assertEqual(result["errors"], []); self.assertFalse(result["needs_decision"])
        zero = ci.interpret_paste("RGB 0 0 255")
        self.assertEqual(self.rgb_candidates(zero)[0]["components"], {"r": 0, "g": 0, "b": 255})
        original = ci.candidate_to_original(self.rgb_candidates(ci.interpret_paste("RGB 116, 202, 191"))[0])
        self.assertEqual((original["components"], original["lexemes"]), (self.RGB, {"r": "116", "g": "202", "b": "191"}))

    # ── R2-SEP-SPACE (re-QA 12): the kind of a separator does not depend on the blanks around it ──
    def test_same_separator_with_varying_spaces_is_one_kind(self):
        for text in ("RGB 116,202, 191", "RGB 116, 202,191", "RGB 116;202; 191", "RGB 116; 202;191",
                     "RGB 116 ,202 , 191", "RGB(116,202, 191)", "RGB: 116 ;202; 191", "RGB 116,202,  191 D65 2°"):
            with self.subTest(text=text):
                result = ci.interpret_paste(text)
                self.assertEqual([c["components"] for c in self.rgb_candidates(result)], [self.RGB])
                self.assertEqual(self.rgb_candidates(result)[0]["lexemes"], {"r": "116", "g": "202", "b": "191"})
                self.assertEqual(result["errors"], []); self.assertFalse(result["needs_decision"])

    def test_varying_spaces_do_not_hide_a_remnant_or_a_true_mix_of_separators(self):
        # (pasted text, the values quoted as typed in the refusal): decimals, remnants and real mixes stay refused.
        for text, quoted in (("RGB 116,202, 191,5", "116,202, 191,5"), ("RGB 116, 202,191,5", "116, 202,191,5"),
                             ("RGB 116;202; 191;5", "116;202; 191;5"), ("RGB 116,202, 191 ,5", "116,202, 191 ,5"),
                             ("RGB 116,5, 202, 191", "116,5, 202, 191"), ("RGB 116, 202,5, 191", "116, 202,5, 191"),
                             ("RGB 116,5 202 191", "116,5 202 191"), ("RGB 116,5 202, 191", "116,5 202, 191"),
                             ("RGB 116 202, 191", "116 202, 191"), ("RGB 116;202, 191", "116;202, 191"),
                             ("RGB 116, 202; 191", "116, 202; 191"), ("RGB 116,202, 191.5", "116,202, 191.5"),
                             ("RGB 116,202, 1910", "116,202, 1910"), ("RGB 116,202, 191, 5", "116,202, 191, 5")):
            with self.subTest(text=text):
                result = ci.interpret_paste(text)
                self.assertEqual(result["candidates"], [])
                self.assertTrue(result["needs_decision"])
                self.assertEqual(result["errors"], [f"RGB « {quoted} » refusé : trois entiers 0–255 sans décimale sont requis."])
        out_of_range = ci.interpret_paste("RGB 116,202, 256")
        self.assertEqual(out_of_range["candidates"], []); self.assertIn("0–255", out_of_range["errors"][0])
        not_srgb = ci.interpret_paste("Adobe RGB 116,202, 191")
        self.assertEqual(not_srgb["candidates"], []); self.assertEqual(not_srgb["unsupported"], ["Adobe RGB"])

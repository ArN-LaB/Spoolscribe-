"""Measurement model: formats, limits, conditions, policies, digests (no Qt, no I/O)."""
import math
import unittest

from spoolscribe import colour_distance, colour_measurements as cm


def lab(L, a, b, **conditions):
    return cm.new_measurement(cm.parse_manual("CIELAB", {"L": L, "a": a, "b": b}), name="t", conditions=conditions)


class ParsingTests(unittest.TestCase):
    def test_hex_and_rgb_are_lossless_and_normalised(self):
        hex_original = cm.parse_manual("sRGB_HEX", {"hex": " #74cabf "})
        self.assertEqual(hex_original["components"], {"hex": "74CABF"})
        self.assertEqual(hex_original["lexemes"], {"hex": "#74cabf"})
        rgb = cm.new_measurement(cm.parse_manual("sRGB_RGB8", {"r": "116", "g": "202", "b": "191"}), name="rgb")
        self.assertEqual(cm.hex_of(rgb), "74CABF")
        self.assertEqual(rgb["original"]["lexemes"], {"r": "116", "g": "202", "b": "191"})
        for bad in ({"hex": "74CABF00"}, {"hex": "GGGGGG"}, {"hex": ""}, {}):
            with self.assertRaises(cm.MeasurementError):
                cm.parse_manual("sRGB_HEX", bad)
        for bad in ({"r": "256", "g": "0", "b": "0"}, {"r": "0.5", "g": "0", "b": "0"}, {"r": "-1", "g": "0", "b": "0"},
                    {"r": "1", "g": "2"}, {"r": "True", "g": "0", "b": "0"}):
            with self.assertRaises(cm.MeasurementError):
                cm.parse_manual("sRGB_RGB8", bad)

    def test_lab_accepts_point_or_comma_but_never_ambiguous_syntax(self):
        original = cm.parse_manual("CIELAB", {"L": "73,2", "a": "-25,6", "b": "-12,4"})
        self.assertEqual(original["components"], {"L": 73.2, "a": -25.6, "b": -12.4})
        self.assertEqual(original["lexemes"]["L"], "73,2")
        self.assertEqual(cm.parse_decimal("12,345"), 12.345)   # a comma is never a thousands separator
        self.assertEqual(cm.parse_decimal(".5"), 0.5)
        for text in ("1,234.5", "1.234,5", "1,2,3", "1 234", "12abc", "", "nan", "inf", "-inf", "1e400"):
            with self.assertRaises(cm.MeasurementError, msg=text):
                cm.parse_decimal(text)
        with self.assertRaises(cm.MeasurementError):
            cm.parse_decimal(True)
        with self.assertRaises(cm.MeasurementError):
            cm.parse_decimal(float("nan"))

    def test_lab_bounds_are_only_the_documented_ones(self):
        self.assertEqual(lab("0", "130", "-140")["original"]["components"], {"L": 0.0, "a": 130.0, "b": -140.0})
        for L in ("-0.1", "100.01"):
            with self.assertRaises(cm.MeasurementError):
                lab(L, "0", "0")
        for missing in ({"L": "50", "a": "0"}, {"L": "50", "b": "0"}, {"a": "0", "b": "0"}):
            with self.assertRaises(cm.MeasurementError):
                cm.parse_manual("CIELAB", missing)

    def test_huge_finite_values_are_stored_but_not_computable(self):
        measurement = lab("50", "1e300", "0", illuminant="D65", observer=2)
        self.assertFalse(cm.computable(measurement))
        self.assertEqual(cm.comparison_policy(measurement)["reason"], "magnitude")
        ordinary = lab("50", "1e3", "0", illuminant="D65", observer=2)
        self.assertTrue(cm.computable(ordinary))
        with self.assertRaises((OverflowError, ValueError)):
            colour_distance.ciede2000(cm.lab_of(measurement), (50, 0, 0))

    def test_summary_text_keeps_lexemes_and_describes_conditions(self):
        measurement = lab("73,2", "-25,6", "-12,4")
        self.assertEqual(cm.summary_values(measurement), "L* 73,2 · a* -25,6 · b* -12,4")
        self.assertEqual(cm.describe_conditions(measurement), "éclairage inconnu / observateur inconnu")
        self.assertEqual(cm.describe_conditions(lab("1", "2", "3", illuminant="D50", observer=10)), "D50 / 10°")
        rgb = cm.new_measurement(cm.parse_manual("sRGB_RGB8", {"r": "1", "g": "2", "b": "3"}), name="x")
        self.assertEqual(cm.summary_values(rgb), "RGB 1, 2, 3")
        self.assertEqual(cm.describe_conditions(rgb), "sRGB")


class ValidationTests(unittest.TestCase):
    def test_measurement_requires_name_timestamp_and_known_enumerations(self):
        base = lab("50", "0", "0")
        for field, value in (("name", ""), ("name", "x" * 121), ("role", "sample"), ("created_at", "yesterday"),
                             ("created_at", None), ("association", {"sku": ""}), ("association", {"id": "X"}),
                             ("sample", {"type": "wood"}), ("provenance", {"method": "usb"}),
                             ("provenance", {"method": "csv", "record_number": 0}), ("provenance", {"method": "csv", "file_sha256": "abc"}),
                             ("conditions", {"illuminant": "D55"}), ("conditions", {"observer": 3}),
                             ("conditions", {"observer": True}), ("conditions", {"illuminant": "other"}),
                             ("conditions", {"geometry": "x" * 257}), ("conditions", {"magic": 1})):
            broken = dict(base, **{field: value})
            with self.assertRaises(cm.MeasurementError, msg=f"{field}={value!r}"):
                cm.validate_measurement(broken)
        documented = dict(base, conditions={"illuminant": "other", "illuminant_note": "TL84", "observer": 10})
        self.assertEqual(cm.validate_measurement(documented)["conditions"]["illuminant_note"], "TL84")
        self.assertIsNone(cm.validate_measurement(base)["conditions"]["illuminant"])
        self.assertIsNone(cm.validate_measurement(base)["measured_at"])

    def test_values_are_never_booleans_nan_or_strings(self):
        for components in ({"L": True, "a": 0, "b": 0}, {"L": float("nan"), "a": 0, "b": 0}, {"L": "50", "a": 0, "b": 0},
                           {"L": 50, "a": float("inf"), "b": 0}, {"L": 50, "a": 0}):
            with self.assertRaises(cm.MeasurementError):
                cm.validate_original({"space": "CIELAB", "components": components})
        with self.assertRaises(cm.MeasurementError):
            cm.validate_original({"space": "sRGB_RGB8", "components": {"r": True, "g": 0, "b": 0}})
        with self.assertRaises(cm.MeasurementError):
            cm.validate_original({"space": "XYZ", "components": {}})

    def test_alternatives_are_validated_and_kept(self):
        original = {"space": "sRGB_HEX", "components": {"hex": "74CABF"},
                    "alternatives": [{"space": "CIELAB", "components": {"L": 1.0, "a": 2.0, "b": 3.0}, "lexemes": {"L": "1"},
                                      "conditions": {"illuminant": "D50", "observer": 2}}]}
        clean = cm.validate_original(original)
        self.assertEqual(clean["alternatives"][0]["conditions"]["illuminant"], "D50")
        original["alternatives"].append({"space": "sRGB_HEX", "components": {"hex": "zz"}})
        with self.assertRaises(cm.MeasurementError):
            cm.validate_original(original)

    def test_registry_document_validation(self):
        measurement = lab("50", "0", "0")
        good = {"schema": cm.SCHEMA, "version": 1, "measurements": {cm.new_id(): measurement}}
        self.assertEqual(len(cm.validate_registry(good)["measurements"]), 1)
        for broken in ({"schema": "other", "version": 1, "measurements": {}}, {"schema": cm.SCHEMA, "version": 2, "measurements": {}},
                       {"schema": cm.SCHEMA, "version": True, "measurements": {}}, {"schema": cm.SCHEMA, "version": 1, "measurements": []},
                       {"schema": cm.SCHEMA, "version": 1, "measurements": {"X": measurement}},
                       {"schema": cm.SCHEMA, "version": 1, "measurements": {"MEAS-not-a-uuid": measurement}}, []):
            with self.assertRaises(cm.MeasurementError):
                cm.validate_registry(broken)
        self.assertTrue(cm.new_id().startswith("MEAS-"))
        self.assertNotEqual(cm.new_id(), cm.new_id())

    def test_digest_depends_on_values_and_conditions_only(self):
        first = lab("73.2", "-25.6", "-12.4", illuminant="D65", observer=2)
        same = lab("73,2", "-25,6", "-12,4", illuminant="D65", observer=2)
        self.assertEqual(first["content_digest"], same["content_digest"])   # lexemes and names do not matter
        renamed = cm.validate_measurement(dict(first, name="autre"))
        self.assertEqual(renamed["content_digest"], first["content_digest"])
        other = lab("73.2", "-25.6", "-12.4", illuminant="D50", observer=2)
        self.assertNotEqual(first["content_digest"], other["content_digest"])
        self.assertNotEqual(first["content_digest"], lab("73.3", "-25.6", "-12.4", illuminant="D65", observer=2)["content_digest"])

    def test_created_at_is_utc_and_measured_at_stays_optional(self):
        measurement = lab("50", "0", "0")
        self.assertTrue(measurement["created_at"].endswith("Z"))
        self.assertIsNone(measurement["measured_at"])
        dated = cm.new_measurement(measurement["original"], name="d", measured_at="2026-10-30")
        self.assertEqual(dated["measured_at"], "2026-10-30")


class PolicyTests(unittest.TestCase):
    def test_srgb_sources_are_indicative_with_a_derived_basis(self):
        hex_measurement = cm.new_measurement(cm.parse_manual("sRGB_HEX", {"hex": "74CABF"}), name="h")
        policy = cm.comparison_policy(hex_measurement)
        self.assertEqual((policy["level"], policy["reason"]), ("indicative", "srgb_declared"))
        self.assertIn("pas une condition mesurée", policy["reference"])
        self.assertIsNone(hex_measurement["conditions"]["illuminant"])  # nothing written as measured

    def test_lab_d65_2_is_indicative_and_everything_else_is_blocked(self):
        self.assertEqual(cm.comparison_policy(lab("50", "0", "0", illuminant="D65", observer=2))["level"], "indicative")
        for conditions, reason in (({"illuminant": "D50", "observer": 2}, "adaptation_unavailable"),
                                   ({"illuminant": "D65", "observer": 10}, "observer_unsupported"),
                                   ({"illuminant": "other", "illuminant_note": "TL84", "observer": 2}, "illuminant_unsupported"),
                                   ({}, "conditions_unknown"), ({"illuminant": "D65"}, "conditions_unknown"),
                                   ({"observer": 2}, "conditions_unknown")):
            policy = cm.comparison_policy(lab("50", "0", "0", **conditions))
            self.assertEqual((policy["level"], policy["reason"]), ("blocked", reason), conditions)
            self.assertIsNone(policy["reference"])

    def test_catalogue_comparison_is_never_called_comparable(self):
        for measurement in (lab("50", "0", "0", illuminant="D65", observer=2, geometry="45/0", specular="SCE"),
                            cm.new_measurement(cm.parse_manual("sRGB_HEX", {"hex": "000000"}), name="h")):
            self.assertNotEqual(cm.comparison_policy(measurement)["level"], "comparable")

    def test_pair_policy_requires_documented_identical_conditions(self):
        full = dict(illuminant="D65", observer=2, geometry="45/0", specular="SCE")
        provenance = {"method": "manual", "device_manufacturer": "Acme", "device_model": "M1"}
        sample = {"type": "printed_sample", "finish": "matte", "backing": "white", "thickness": "2 mm"}
        a = cm.new_measurement(cm.parse_manual("CIELAB", {"L": "50", "a": "0", "b": "0"}), name="a", conditions=full,
                               provenance=provenance, sample=sample)
        b = cm.new_measurement(cm.parse_manual("CIELAB", {"L": "51", "a": "0", "b": "0"}), name="b", conditions=full,
                               provenance=provenance, sample=sample)
        self.assertEqual(cm.pair_policy(a, b)["level"], "comparable")
        missing = cm.new_measurement(b["original"], name="b", conditions=dict(full, geometry=None), provenance=provenance, sample=sample)
        policy = cm.pair_policy(a, missing)
        self.assertEqual((policy["level"], policy["missing"]), ("insufficient", ["geometry"]))
        different = cm.new_measurement(b["original"], name="b", conditions=dict(full, observer=10), provenance=provenance, sample=sample)
        self.assertEqual(cm.pair_policy(a, different)["different"], ["observer"])
        other_device = cm.new_measurement(b["original"], name="b", conditions=full, provenance=dict(provenance, device_model="M2"), sample=sample)
        self.assertEqual(cm.pair_policy(a, other_device)["different"], ["device_model"])
        srgb = cm.new_measurement(cm.parse_manual("sRGB_HEX", {"hex": "000000"}), name="h")
        self.assertEqual(cm.pair_policy(a, srgb)["level"], "blocked")
        self.assertEqual(cm.pair_policy(a, cm.validate_measurement(dict(a, original=lab("50", "1e300", "0")["original"])))["level"], "blocked")

    def test_limits_are_centralised(self):
        self.assertEqual(cm.LIMITS["file_bytes"], 10 * 1024 * 1024)
        self.assertEqual(cm.LIMITS["records"], 10_000)
        self.assertEqual(cm.LIMITS["columns"], 64)
        self.assertEqual(cm.LIMITS["cell"], 4096)
        self.assertEqual(cm.LIMITS["paste_bytes"], 64 * 1024)
        self.assertEqual(cm.LIMITS["name"], 120)
        self.assertEqual(cm.LIMITS["short"], 256)
        self.assertEqual(cm.LIMITS["note"], 4096)
        self.assertEqual(cm.LIMITS["lexeme"], 64)
        self.assertEqual(cm.LIMITS["registry_bytes"], 20 * 1024 * 1024)
        self.assertEqual(cm.LIMITS["registry_count"], 10_000)
        with self.assertRaises(cm.MeasurementError):
            cm.validate_measurement(dict(lab("50", "0", "0"), provenance={"method": "manual", "operator_note": "x" * 4097}))
        self.assertTrue(math.isfinite(cm.COMPUTABLE_MAGNITUDE))


if __name__ == "__main__":
    unittest.main()


class CorrectionTests(unittest.TestCase):
    """Regressions of the independent QA (R5/R6): documented 'other' illuminants, translatable errors and condition texts."""

    def test_other_illuminants_compare_by_their_documented_description(self):
        provenance = {"method": "manual", "device_manufacturer": "Acme", "device_model": "M1"}
        sample = {"type": "printed_sample", "finish": "matte", "backing": "white", "thickness": "2 mm"}

        def other(note, **extra):
            conditions = dict(dict(illuminant="other", illuminant_note=note, observer=2, geometry="45/0", specular="SCE"), **extra)
            return cm.new_measurement(cm.parse_manual("CIELAB", {"L": "50", "a": "0", "b": "0"}), name="o", conditions=conditions,
                                      provenance=provenance, sample=sample)
        policy = cm.pair_policy(other("D55"), other("D75"))
        self.assertEqual((policy["level"], policy["different"]), ("insufficient", ["illuminant_note"]))
        self.assertEqual(cm.pair_policy(other("D55"), other(" d55 "))["level"], "comparable")   # same documented description only
        self.assertEqual(cm.pair_policy(other("D55"), other("TL84"))["level"], "insufficient")
        self.assertEqual(cm.pair_policy(other("D55"), other("D55", geometry="d/8"))["different"], ["geometry"])
        self.assertEqual(cm.pair_policy(other("D55"), other("D55", specular="sce"))["level"], "comparable")   # case only
        for measurement in (other("D55"), other("D75")):
            self.assertEqual(cm.comparison_policy(measurement)["level"], "blocked")   # the catalogue policy is unchanged

    def test_errors_carry_a_template_and_values_for_translation(self):
        error = cm.MeasurementError("Nombre invalide : « {v0} ».", v0="abc")
        self.assertEqual(str(error), "Nombre invalide : « abc »."); self.assertEqual((error.template, error.values), ("Nombre invalide : « {v0} ».", {"v0": "abc"}))
        translate = lambda template, **values: "EN " + template.format(**values)
        self.assertEqual(cm.error_text(error, translate), "EN Nombre invalide : « abc ».")
        with self.assertRaises(cm.MeasurementError) as raised:
            cm.parse_manual("CIELAB", {"L": "150", "a": "0", "b": "0"})
        self.assertEqual(raised.exception.template, "L* doit être compris entre 0 et 100.")
        nested = cm.MeasurementError("{v0} : {v1}", v0="file", v1=error)
        self.assertEqual(cm.error_text(nested, translate), "EN file : EN Nombre invalide : « abc ».")
        self.assertEqual(cm.error_text(ValueError("plain"), translate), "plain")

    def test_condition_texts_are_built_from_translatable_pieces(self):
        wrap = lambda template, **values: "T(" + template.format(**values) + ")"
        self.assertEqual(cm.describe_conditions(lab("1", "2", "3", illuminant="D50", observer=10), wrap), "D50 / T(10°)")
        self.assertEqual(cm.describe_conditions(lab("1", "2", "3"), wrap), "T(éclairage inconnu) / T(observateur inconnu)")
        self.assertEqual(cm.describe_conditions(lab("1", "2", "3", illuminant="other", illuminant_note="TL84", observer=2), wrap), "T(autre éclairage : TL84) / T(2°)")
        rgb = cm.new_measurement(cm.parse_manual("sRGB_RGB8", {"r": "1", "g": "2", "b": "3"}), name="x", conditions={"illuminant": "D50", "observer": 10})
        self.assertEqual(cm.describe_conditions(rgb, wrap), "T(sRGB · contexte déclaré : D50 / T(10°))")
        self.assertEqual(cm.describe_space_conditions("sRGB_HEX", {}, wrap), "T(sRGB)")

    def test_error_templates_and_labels_are_in_the_translation_catalogue(self):
        import json, re
        from tests.support import ROOT
        messages = json.loads((ROOT / "data/translations/messages.json").read_text(encoding="utf-8"))
        pattern = re.compile(r'(?:MeasurementError|RegistryError|InvalidDocument|fail)\(\s*"((?:[^"\\]|\\.)*)"')
        for name in ("src/spoolscribe/colour_measurements.py", "src/spoolscribe/colour_import.py", "src/spoolscribe/measurement_store.py"):
            for match in pattern.finditer((ROOT / name).read_text(encoding="utf-8")):
                self.assertIn(match.group(1), messages, name)
        db_io = (ROOT / "scripts/db_io.py").read_text(encoding="utf-8")
        for match in re.finditer(r'InvalidDocument\("((?:[^"\\]|\\.)*)"', db_io):
            self.assertIn(match.group(1), messages, "db_io")
        for label in (*cm.METHOD_LABELS.values(), *cm.SPACE_LABELS.values(), "autre éclairage : {v0}", "éclairage inconnu", "observateur inconnu",
                      "sRGB · contexte déclaré : {v0}", "{v0}°", "sRGB"):
            self.assertIn(label, messages)
            self.assertEqual(set(messages[label]), {"en", "es", "zh_CN"})

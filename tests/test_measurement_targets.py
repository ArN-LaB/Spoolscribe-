"""Ranking adapter: HEX→HEX results unchanged, Lab D65/2° ranked directly, blocked targets never computed."""
import hashlib
import json
import unittest
from unittest.mock import patch

from spoolscribe import colour_distance as cd, colour_measurements as cm, colour_targets as ct, core
from tests.support import ROOT

DIGESTS = json.loads((ROOT / "tests/fixtures/measurements/hex_baseline_digests.json").read_text(encoding="utf-8"))


def baseline_rows(name):
    """Rebuild the audit's row sets exactly (filename:sku ids, padding, synthetic set)."""
    if name == "synthetic-unique-srgb":
        return [dict(sku=f"SYNTH-{i:05d}", hex=f"{(i * 6173) % 16777216:06X}", brand=f"B{i % 50:02}", product=f"P{i % 125:03}",
                     color_name="Synthetic", material="PLA") for i in range(25000)]
    pool = []
    for filename in ("polymaker_db.json", "catalogue_ofd.json", "catalogue_spoolman.json"):
        db = json.loads((ROOT / "tests/fixtures/catalogues" / filename).read_text(encoding="utf-8"))
        for row in core.list_skus(db):
            row = dict(row); row["sku"] = filename + ":" + row["sku"]; pool.append(row)
    rows = pool[:25000]
    total = len(pool)
    while len(rows) < 25000:
        n = len(rows) - total; row = dict(pool[n % total]); row["sku"] = f"SYNTH-PAD-{n:05d}"; rows.append(row)
    return rows


def digest_of(result):
    packed = [[v["row"]["sku"], v["delta"], v["effect"]] for v in result["items"]]
    return hashlib.sha256(json.dumps(dict(items=packed, excluded=result["excluded"]), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def hex_target(value):
    return ct.target_from_measurement(cm.new_measurement(cm.parse_manual("sRGB_HEX", {"hex": value}), name="h"))


def lab_target(L, a, b, **conditions):
    return ct.target_from_measurement(cm.new_measurement(cm.parse_manual("CIELAB", {"L": str(L), "a": str(a), "b": str(b)}),
                                                         name="lab", conditions=conditions))


class HistoricalRegressionTests(unittest.TestCase):
    def test_the_six_audit_digests_are_reproduced_through_the_measurement_adapter(self):
        for dataset in DIGESTS["datasets"]:
            rows = baseline_rows(dataset["name"])
            self.assertEqual(hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest(), dataset["rows_sha256"])
            index = cd.build_index(rows)
            for case in dataset["targets"]:
                with self.subTest(dataset=dataset["name"], target=case["target"]):
                    direct = cd.rank(case["target"], rows, index=index)
                    self.assertEqual(digest_of(direct), case["digest"])
                    adapted = ct.rank_measurement(hex_target(case["target"]), rows, index=index)
                    self.assertEqual(digest_of(adapted), case["digest"])
                    self.assertEqual(adapted["total"], case["ranked"]); self.assertEqual(adapted["excluded"], case["excluded"])
                    self.assertEqual({str(limit): sum(v["delta"] <= limit for v in adapted["items"]) for limit in (0, 3, 10, 20)}, case["within_limits"])
                    # A Lab target equal to the HEX's own Lab gives the same scores, without any HEX reconstruction.
                    L, a, b = cd.hex_to_lab(case["target"])
                    equivalent = ct.rank_measurement(lab_target(L, a, b, illuminant="D65", observer=2), rows, index=index)
                    self.assertEqual(digest_of(equivalent), case["digest"])
                    self.assertEqual([v["row"]["sku"] for v in equivalent["items"][:5]], [v[0] for v in case["first_five"]])

    def test_the_34_sharma_vectors_still_hold(self):
        self.assertEqual(round(cd.ciede2000((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485)), 4), 2.0425)
        self.assertEqual(round(cd.ciede2000((50.0, 2.5, 0.0), (73.0, 25.0, -18.0)), 4), 27.1492)


class AdapterTests(unittest.TestCase):
    rows = [dict(sku="A", hex="74CABF", brand="x", product="p", color_name="teal"),
            dict(sku="B", hex="000000", brand="x", product="p", color_name="black"),
            dict(sku="C", hex=None, brand="x", product="p", color_name="unknown"),
            dict(sku="D", hex="FFFFFF", brand="x", product="p", color_name="Silk white")]

    def test_rgb_measurement_uses_the_historical_hex_path(self):
        target = ct.target_from_measurement(cm.new_measurement(cm.parse_manual("sRGB_RGB8", {"r": "116", "g": "202", "b": "191"}), name="rgb"))
        self.assertEqual(target["hex"], "74CABF"); self.assertNotIn("lab", target)
        with patch("spoolscribe.colour_distance.rank", wraps=cd.rank) as rank:
            result = ct.rank_measurement(target, self.rows)
        rank.assert_called_once()
        self.assertEqual([v["row"]["sku"] for v in result["items"]], ["A", "D", "B"])
        self.assertEqual(result["items"][0]["delta"], 0.0); self.assertEqual(result["excluded"], {"unknown": 1})
        self.assertTrue(result["items"][1]["effect"])

    def test_lab_measurement_is_compared_directly_with_catalogue_lab(self):
        target = lab_target(50, 10, -20, illuminant="D65", observer=2)
        self.assertNotIn("hex", target)
        with patch("spoolscribe.colour_distance.ciede2000", wraps=cd.ciede2000) as delta:
            result = ct.rank_measurement(target, self.rows)
        for call in delta.call_args_list:
            self.assertEqual(call.args[0], (50.0, 10.0, -20.0))   # the original Lab, never a reconstructed HEX's Lab
        self.assertEqual(result["excluded"], {"unknown": 1})
        self.assertEqual(result["items"][0]["delta"], round(cd.ciede2000((50.0, 10.0, -20.0), cd.hex_to_lab("74CABF")), 6))
        self.assertEqual(len(target["cache"]), 3)

    def test_blocked_targets_never_reach_the_formula(self):
        for conditions in ({}, {"illuminant": "D50", "observer": 2}, {"illuminant": "D65", "observer": 10},
                           {"illuminant": "other", "illuminant_note": "TL84", "observer": 2}):
            with self.assertRaises(ct.TargetBlocked) as raised:
                lab_target(50, 0, 0, **conditions)
            self.assertEqual(raised.exception.policy["level"], "blocked")
        forced = lab_target(50, 0, 0, illuminant="D65", observer=2)
        forced["policy"] = {"level": "blocked", "reason": "test"}
        with patch("spoolscribe.colour_distance.ciede2000") as delta:
            with self.assertRaises(ct.TargetBlocked):
                ct.rank_measurement(forced, self.rows)
        delta.assert_not_called()
        with self.assertRaises(ct.TargetBlocked) as huge:
            lab_target(50, "1e300", 0, illuminant="D65", observer=2)
        self.assertEqual(huge.exception.policy["reason"], "magnitude")

    def test_cache_belongs_to_the_exact_target(self):
        first = lab_target(50, 0, 0, illuminant="D65", observer=2)
        ct.rank_measurement(first, self.rows)
        second = lab_target(50, 0, 0.5, illuminant="D65", observer=2)
        self.assertNotEqual(first["digest"], second["digest"]); self.assertEqual(second["cache"], {})
        self.assertFalse(ct.query_matches(first, second)); self.assertTrue(ct.query_matches(first, dict(first)))
        self.assertFalse(ct.query_matches({"kind": "hex", "hex": "000000"}, first))

    def test_ranking_leaves_rows_and_fixtures_unchanged(self):
        before = json.dumps(self.rows, sort_keys=True)
        ct.rank_measurement(lab_target(10, 0, 0, illuminant="D65", observer=2), self.rows)
        self.assertEqual(json.dumps(self.rows, sort_keys=True), before)


if __name__ == "__main__":
    unittest.main()


class IdentityTests(unittest.TestCase):
    """R1: two acquisitions with equal values are distinct targets; only their distances may be shared."""

    def test_equal_values_never_make_two_acquisitions_the_same_target(self):
        first = cm.new_measurement(cm.parse_manual("sRGB_HEX", {"hex": "112233"}), name="Acquisition A")
        second = cm.new_measurement(cm.parse_manual("sRGB_HEX", {"hex": "112233"}), name="Acquisition B")
        a = ct.target_from_measurement(first, "MEAS-a"); b = ct.target_from_measurement(second, "MEAS-b")
        self.assertEqual(a["digest"], b["digest"])
        self.assertFalse(ct.query_matches(a, b)); self.assertTrue(ct.query_matches(a, ct.target_from_measurement(first, "MEAS-a")))
        ct.rank_measurement(a, AdapterTests.rows)
        self.assertIs(ct.reusable_cache(a, b), a["cache"]); self.assertEqual(ct.reusable_cache(a, ct.target_from_measurement(cm.new_measurement(
            cm.parse_manual("sRGB_HEX", {"hex": "445566"}), name="C"), "MEAS-c")), {})
        self.assertEqual(ct.reusable_cache(None, b), {}); self.assertEqual(ct.reusable_cache({"kind": "hex", "hex": "112233", "cache": {"x": 1}}, b), {})
        unsaved = ct.target_from_measurement(first); renamed = ct.target_from_measurement(dict(first, name="other"))
        self.assertFalse(ct.query_matches(unsaved, renamed)); self.assertFalse(ct.query_matches(unsaved, a))
        self.assertEqual(a["conditions_data"]["illuminant"], None)

import contextlib
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from mona_metrics.__main__ import main
from mona_metrics.analytics import COLUMNS, DataError, analyze, load_config, markdown


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "data/cafes.json"
BASELINE = ROOT / "data/daily.csv"
SCENARIO = ROOT / "data/scenarios/meteor-shower.csv"


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "daily.csv"

    def write_rows(self, rows):
        with self.path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        return self.path

    def row(self, day="2026-09-01", **changes):
        return {
            "date": day, "cafe_id": "luna-paw", "visits": 10, "orders": 6,
            "revenue_credits": 72, "adoptions": 1, "food_waste_g": 250,
            **changes,
        }

    def test_exact_baseline_totals(self):
        report = analyze(BASELINE, CONFIG)
        self.assertTrue(report["synthetic"])
        self.assertEqual(report["records"], 14)
        self.assertEqual(report["totals"], {
            "visits": 658, "orders": 574, "revenue_credits": 6888,
            "adoptions": 19, "food_waste_g": 2260, "conversion": 0.8723,
            "credits_per_order": 12.0,
        })
        self.assertEqual(report["warnings"], [])
        self.assertEqual(report["period"], {"start": "2026-09-01", "end": "2026-09-07"})
        self.assertEqual([cafe["visits"] for cafe in report["cafes"]], [294, 364])

    def test_scenario_has_exact_intentional_warnings(self):
        report = analyze(SCENARIO, CONFIG)
        self.assertEqual(report["records"], 13)
        self.assertEqual(report["totals"]["visits"], 764)
        self.assertEqual(report["totals"]["orders"], 542)
        self.assertEqual(report["totals"]["revenue_credits"], 6504)
        self.assertEqual(report["totals"]["conversion"], 0.7094)
        self.assertEqual(
            [(item["code"], item["cafe_id"], item["date"]) for item in report["warnings"]],
            [("missing_day", "luna-paw", "2026-09-06"),
             ("high_waste", "octocat-outpost", "2026-09-07"),
             ("low_conversion", "octocat-outpost", "2026-09-07"),
             ("traffic_spike", "octocat-outpost", "2026-09-07")],
        )
        self.assertIn("median 53", report["warnings"][-1]["message"])

    def test_output_is_deterministic_and_fingerprinted(self):
        first = analyze(BASELINE, CONFIG)
        self.assertEqual(first, analyze(BASELINE, CONFIG))
        self.assertEqual(markdown(first), markdown(analyze(BASELINE, CONFIG)))
        self.assertEqual(len(first["input_sha256"]), 64)
        self.assertNotEqual(first["input_sha256"], analyze(SCENARIO, CONFIG)["input_sha256"])
        config = Path(self.directory.name) / "cafes.json"
        changed = json.loads(CONFIG.read_text())
        changed["min_conversion"] = 0.5
        config.write_text(json.dumps(changed))
        self.assertNotEqual(first["input_sha256"], analyze(BASELINE, config)["input_sha256"])

    def test_threshold_boundaries_and_history(self):
        rows = [self.row(f"2026-09-0{day}") for day in range(1, 4)]
        rows.append(self.row("2026-09-04", visits=20, orders=12))
        report = analyze(self.write_rows(rows), CONFIG)
        self.assertEqual({item["code"] for item in report["warnings"]}, {"missing_day"})
        rows[-1].update(visits=21, orders=12, food_waste_g=251)
        codes = {item["code"] for item in analyze(self.write_rows(rows), CONFIG)["warnings"]}
        self.assertEqual(codes, {"missing_day", "low_conversion", "high_waste", "traffic_spike"})
        early = analyze(self.write_rows([self.row(), self.row("2026-09-02", visits=100)]), CONFIG)
        self.assertNotIn("traffic_spike", {item["code"] for item in early["warnings"]})

    def test_zero_activity_has_null_rates_and_no_conversion_warning(self):
        row = self.row(visits=0, orders=0, revenue_credits=0, adoptions=0)
        report = analyze(self.write_rows([row]), CONFIG)
        self.assertIsNone(report["totals"]["conversion"])
        self.assertIsNone(report["totals"]["credits_per_order"])
        self.assertNotIn("low_conversion", {item["code"] for item in report["warnings"]})

    def test_reject_invalid_rows_without_partial_metrics(self):
        changes = [
            {"visits": -1}, {"visits": "1.2"}, {"visits": "NaN"},
            {"orders": 11}, {"adoptions": 11},
            {"visits": 0, "orders": 0, "adoptions": 0, "revenue_credits": 1},
            {"cafe_id": "pluto-paws"}, {"date": "2026-02-30"},
            {"date": "20260901"}, {"food_waste_g": ""}, {"orders": " 6"},
            {"visits": "１２"}, {"visits": 1000000001},
        ]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(DataError):
                analyze(self.write_rows([self.row(), self.row("2026-09-02", **change)]), CONFIG)

    def test_reject_duplicate_and_excessive_period(self):
        for rows in (
            [self.row(), self.row()],
            [self.row(), self.row("2027-09-02")],
        ):
            with self.subTest(rows=rows), self.assertRaises(DataError):
                analyze(self.write_rows(rows), CONFIG)

    def test_calendar_handles_maximum_date(self):
        report = analyze(self.write_rows([self.row("9999-12-31")]), CONFIG)
        self.assertEqual(report["period"]["end"], "9999-12-31")

    def test_reject_empty_bad_header_extra_and_missing_fields(self):
        for text in (
            "", ",".join(COLUMNS) + "\n", "bad,header\n1,2\n",
            ",".join(COLUMNS) + "\n2026-09-01,luna-paw,1,1,12,0,2,extra\n",
            ",".join(COLUMNS) + "\n2026-09-01,luna-paw,1\n",
        ):
            with self.subTest(text=text):
                self.path.write_text(text)
                with self.assertRaises(DataError):
                    analyze(self.path, CONFIG)

    def test_reject_invalid_configuration(self):
        original = json.loads(CONFIG.read_text())
        config = Path(self.directory.name) / "config.json"
        cases = [
            [], {}, {**original, "cafes": {}},
            {**original, "min_conversion": float("nan")},
            {**original, "min_conversion": True},
            {**original, "min_conversion": 1.1},
            {**original, "traffic_spike_multiplier": 1},
            {**original, "traffic_spike_multiplier": float("inf")},
            {**original, "cafes": {"luna-paw": {"name": "Mona", "waste_budget_g": -1}}},
        ]
        for value in cases:
            with self.subTest(value=value):
                config.write_text(json.dumps(value))
                with self.assertRaises(DataError):
                    load_config(config)

    def test_unsorted_rows_preserve_metrics(self):
        with BASELINE.open() as handle:
            rows = list(csv.DictReader(handle))
        actual = analyze(self.write_rows(list(reversed(rows))), CONFIG)
        expected = analyze(BASELINE, CONFIG)
        actual.pop("input_sha256")
        expected.pop("input_sha256")
        self.assertEqual(actual, expected)

    def test_record_limit(self):
        rows = [self.row()] * 10001
        # Unique configured cafes keep the duplicate check from hiding the record cap.
        config = json.loads(CONFIG.read_text())
        config["cafes"] = {
            str(index): {"name": str(index), "waste_budget_g": 250}
            for index in range(len(rows))
        }
        config_path = Path(self.directory.name) / "many-cafes.json"
        config_path.write_text(json.dumps(config))
        rows = [dict(row, cafe_id=str(index)) for index, row in enumerate(rows)]
        with self.assertRaisesRegex(DataError, "10000 records"):
            analyze(self.write_rows(rows), config_path)


class CLITests(unittest.TestCase):
    def run_cli(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = main([*args, "--config", str(CONFIG)])
        return status, stdout.getvalue(), stderr.getvalue()

    def test_check_status_and_json_shape(self):
        for data, expected_status in ((BASELINE, 0), (SCENARIO, 1)):
            with self.subTest(data=data):
                status, output, error = self.run_cli("check", "--data", str(data), "--format", "json")
                self.assertEqual(status, expected_status)
                self.assertEqual(error, "")
                self.assertTrue(json.loads(output)["synthetic"])
        status, output, _ = self.run_cli("report", "--data", str(SCENARIO))
        self.assertEqual(status, 0)
        self.assertIn("Quality warnings (4)", output)

    def test_input_failure_returns_two_and_no_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            for content in (None, "broken header\n"):
                if content is not None:
                    path.write_text(content)
                status, output, error = self.run_cli("report", "--data", str(path))
                self.assertEqual(status, 2)
                self.assertEqual(output, "")
                self.assertTrue(error.startswith("mona-metrics:"))


if __name__ == "__main__":
    unittest.main()

"""Checks both the legacy Prime snapshot and the new seven-day comparison."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import update_prime_sets as prime


class TestSevenDayPrimeHistory(unittest.TestCase):
    def setUp(self):
        self.catalog = {f"Item {i} Prime Set": {} for i in range(25)}
        self.latest = {
            "Item 0 Prime Set": [
                {"datetime": "2026-10-27", "order_type": "buy", "median": 1000},
                {"datetime": "2026-10-27", "order_type": "closed", "median": 45.99, "volume": 118},
            ],
            "Item 1 Prime Set": [
                {"datetime": "2026-10-27", "order_type": "closed", "median": 10.5, "volume": 4},
            ],
            "Item 2 Prime Set": [
                {"datetime": "2026-10-27", "order_type": "sell", "median": 100, "volume": 2},
            ],
        }
        self.previous = {
            "Item 0 Prime Set": [
                {"datetime": "2026-10-20", "order_type": "closed", "median": 40, "volume": 20},
            ],
            "Item 1 Prime Set": [
                {"datetime": "2026-10-20", "order_type": "closed", "median": 20, "volume": 7},
            ],
            "Item 2 Prime Set": [
                {"datetime": "2026-10-20", "order_type": "closed", "median": 80, "volume": 7},
            ],
        }

    def test_trend_uses_unrounded_closed_medians(self):
        snapshot = prime.build_snapshot("2026-10-27", self.catalog, self.latest, self.previous)
        self.assertEqual(snapshot["schemaVersion"], 3)
        self.assertEqual(snapshot["comparisonDate"], "2026-10-20")
        rows = {item["name"]: item for item in snapshot["sets"]}
        self.assertEqual(rows["Item 0 Prime Set"]["medianClosedPrice"], 45)
        self.assertEqual(rows["Item 0 Prime Set"]["change7dPct"], 15.0)
        self.assertEqual(rows["Item 1 Prime Set"]["change7dPct"], -47.5)
        self.assertIsNone(rows["Item 2 Prime Set"]["change7dPct"])
        self.assertTrue(prime.reusable_snapshot(snapshot, "2026-10-27"))

    def test_missing_or_invalid_comparison_is_not_zero_percent(self):
        rows = prime.normalize(self.catalog, self.latest, "2026-10-27", {})
        self.assertTrue(all(item["change7dPct"] is None for item in rows))
        self.assertIsNone(prime.percent_change(20, 0))
        self.assertIsNone(prime.percent_change(20, None))

    def test_existing_three_column_callers_still_work(self):
        snapshot = prime.build_snapshot("2026-10-27", self.catalog, self.latest)
        self.assertEqual(snapshot["schemaVersion"], 2)
        self.assertNotIn("comparisonDate", snapshot)
        self.assertNotIn("change7dPct", snapshot["sets"][0])
        self.assertTrue(prime.reusable_snapshot(snapshot, "2026-10-27"))


if __name__ == "__main__":
    unittest.main()

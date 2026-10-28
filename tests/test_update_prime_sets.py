"""Regression tests for Relics.run Prime Set closed-order statistics."""

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import update_prime_sets as prime


class TestPrimeSetClosedOrders(unittest.TestCase):
    def setUp(self):
        self.catalog = {f"Test {index} Prime Set": {} for index in range(25)}
        self.history = {
            "Test 0 Prime Set": [
                {"datetime": "2026-10-26T00:00:00Z", "order_type": "closed", "median": 60, "volume": 4},
                {"datetime": "2026-10-27T00:00:00Z", "order_type": "buy", "median": 1, "volume": 999},
                {"datetime": "2026-10-27T00:00:00Z", "order_type": "sell", "median": 999, "volume": 888},
                {"datetime": "2026-10-27T00:00:00Z", "order_type": "closed", "median": 45, "volume": 118},
            ],
            "Test 1 Prime Set": [
                {"datetime": "2026-10-27T00:00:00Z", "order_type": "buy", "median": 22, "volume": 123},
                {"datetime": "2026-10-27T00:00:00Z", "order_type": "sell", "median": 70, "volume": 456},
            ],
            "Test 2 Prime Set": [
                {"datetime": "2026-10-27T00:00:00Z", "order_type": "closed", "median": 10, "volume": 0},
            ],
        }

    def test_only_newest_closed_order_record_is_used(self):
        rows = {row["name"]: row for row in prime.normalize(self.catalog, self.history, "2026-10-27")}
        self.assertEqual(rows["Test 0 Prime Set"], {
            "name": "Test 0 Prime Set", "medianClosedPrice": 45, "volume": 118,
        })
        self.assertEqual(rows["Test 1 Prime Set"]["medianClosedPrice"], None)
        self.assertEqual(rows["Test 1 Prime Set"]["volume"], None)
        self.assertEqual(rows["Test 2 Prime Set"]["volume"], 0)
        self.assertEqual(len(rows), 25)

    def test_old_snapshots_cannot_be_reused(self):
        snapshot = prime.build_snapshot("2026-10-27", self.catalog, self.history)
        self.assertEqual(snapshot["schemaVersion"], 2)
        self.assertTrue(prime.reusable_snapshot(snapshot, "2026-10-27"))
        self.assertFalse(prime.reusable_snapshot(snapshot, "2026-10-26"))
        self.assertFalse(prime.reusable_snapshot({**snapshot, "schemaVersion": 1}))
        self.assertFalse(prime.reusable_snapshot({**snapshot, "sets": [
            {"name": row["name"], "tradeMedian": None, "volume": None}
            for row in snapshot["sets"]
        ]}))


if __name__ == "__main__":
    unittest.main()

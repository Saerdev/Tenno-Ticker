"""Regression checks for daily Mod and Arcane closed-order snapshots."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import update_mods as mods


class ModSnapshotTests(unittest.TestCase):
    @staticmethod
    def catalog():
        entries = [
            {"slug": f"mod_{i}", "maxRank": 10, "tags": ["mod", "rare"],
             "i18n": {"en": {"name": f"Mod {i}"}}}
            for i in range(510)
        ]
        entries += [
            {"slug": "riven", "tags": ["mod", "riven"], "i18n": {"en": {"name": "Riven"}}},
            {"slug": "relic", "tags": ["relic"], "i18n": {"en": {"name": "Relic"}}},
            {"slug": "part", "tags": ["weapon"], "i18n": {"en": {"name": "Weapon Part"}}},
        ]
        return entries

    def test_mod_catalog_excludes_rivens_relics_and_weapon_parts(self):
        selected = mods.market_items(self.catalog(), "mod")
        self.assertEqual(len(selected), 510)
        self.assertTrue(all(item["name"].startswith("Mod ") for item in selected))

    def test_closed_only_rank_separation_and_precise_change(self):
        latest = {"Mod 0": [
            {"order_type": "sell", "mod_rank": 0, "median": 1000, "volume": 5000},
            {"order_type": "closed", "mod_rank": 0, "median": 45.99, "volume": 12},
            {"order_type": "closed", "mod_rank": 10, "median": 90.5, "volume": 3},
        ]}
        previous = {"Mod 0": [
            {"order_type": "closed", "mod_rank": 0, "median": 40, "volume": 8},
            {"order_type": "closed", "mod_rank": 10, "median": 100, "volume": 8},
        ]}
        rows = mods.build_rows(mods.market_items(self.catalog(), "mod"), latest, previous)
        first = next(item for item in rows if item["name"] == "Mod 0")
        self.assertEqual(first["rank0"]["medianClosedPrice"], 45)
        self.assertEqual(first["rank0"]["volume"], 12)
        self.assertEqual(first["rank0"]["change7dPct"], 15.0)
        self.assertEqual(first["rankMax"]["medianClosedPrice"], 90)
        self.assertEqual(first["rankMax"]["volume"], 3)
        self.assertEqual(first["rankMax"]["change7dPct"], -9.5)
        self.assertIsNone(rows[1]["rank0"]["medianClosedPrice"])

    def test_mod_sources_exclude_wrong_drop_type(self):
        catalog = [
            {"name": "Serration", "tradable": True, "wikiaUrl": "https://wiki.warframe.com/w/Serration",
             "drops": [
                 {"location": "Wrong location", "type": "Spectral Serration", "chance": 12},
                 {"location": "Correct drop", "type": "Serration", "chance": 3.5},
             ]},
            {"name": "Untradable", "tradable": False,
             "drops": [{"location": "Never", "type": "Untradable", "chance": 1}]},
        ]
        result = mods.mod_acquisitions(catalog)
        self.assertEqual(result["serration"]["sources"], [{"location": "Correct drop", "chance": 3.5}])
        self.assertNotIn("untradable", result)

    def test_snapshot_metadata_and_reuse_validation(self):
        items = mods.market_items(self.catalog(), "mod")
        s = mods.snapshot("mod", "2026-10-27", items, {}, {})
        self.assertTrue(mods.reusable(s, "2026-10-27", "mod"))
        self.assertFalse(mods.reusable(s, "2026-10-26", "mod"))
        self.assertFalse(mods.reusable({"schemaVersion": 1, "source": "Relics.run/history",
                                         "category": "mod", "items": [None] * 510}, None, "mod"))


if __name__ == "__main__":
    unittest.main()

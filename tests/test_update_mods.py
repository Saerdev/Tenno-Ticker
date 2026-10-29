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

    def test_mod_effects_show_rank_zero_to_max_rank_ranges(self):
        primed = mods.mod_effects({"levelStats": [
            {"stats": ["+5% Ability Duration"]},
            {"stats": ["+55% Ability Duration"]},
        ]})
        self.assertEqual(primed["rank0"], "+5% Ability Duration")
        self.assertEqual(primed["rankMax"], "+55% Ability Duration")
        self.assertEqual(primed["range"], "+5% → +55% Ability Duration")

        creeping = mods.mod_effects({"levelStats": [
            {"stats": ["+33.3% Critical Chance", "-3.3% Fire Rate"]},
            {"stats": ["+200% Critical Chance", "-20% Fire Rate"]},
        ]})
        self.assertEqual(creeping["range"],
                         "+33.3% → +200% Critical Chance\n-3.3% → -20% Fire Rate")

        adaptation = mods.mod_effects({"levelStats": [
            {"stats": ["When Damaged:\\n+5% Resistance for 10s. Stacks up to 90%."]},
            {"stats": ["When Damaged:\\n+10% Resistance for 20s. Stacks up to 90%."]},
        ]})
        self.assertEqual(adaptation["range"],
                         "When Damaged:\n+5% → +10% Resistance for 10s → 20s. Stacks up to 90%.")

    def test_wording_changes_keep_separate_rank_descriptions(self):
        effects = mods.mod_effects({"levelStats": [
            {"stats": ["On kill: +10% Damage"]},
            {"stats": ["On headshot kill: +50% Damage"]},
        ]})
        self.assertIsNone(effects["range"])
        self.assertEqual(effects["rank0"], "On kill: +10% Damage")
        self.assertEqual(effects["rankMax"], "On headshot kill: +50% Damage")

    def test_snapshot_includes_mod_effects_and_undocumented_fallback(self):
        items = mods.market_items(self.catalog(), "mod")
        descriptions = mods.mod_acquisitions([{
            "name": "Mod 0", "tradable": True, "levelStats": [
                {"stats": ["+5% Strength"]}, {"stats": ["+25% Strength"]},
            ],
        }])
        rows = mods.build_rows(items, {}, {}, descriptions)
        example = next(item for item in rows if item["name"] == "Mod 0")
        missing = next(item for item in rows if item["name"] == "Mod 1")
        self.assertEqual(example["effects"]["range"], "+5% → +25% Strength")
        self.assertIsNone(missing["effects"]["range"])

    def test_all_three_price_boards_share_the_same_banner(self):
        site = Path(__file__).resolve().parents[1] / "site"
        for filename in ("index.html", "prime-sets.html", "mods.html"):
            markup = (site / filename).read_text(encoding="utf-8")
            with self.subTest(filename=filename):
                self.assertIn('class="prime-hero board-hero"', markup)
                self.assertNotIn('class="hero-art"', markup)

    def test_mod_tooltip_includes_effect_and_acquisition_sections(self):
        site = Path(__file__).resolve().parents[1] / "site"
        js = (site / "mods.js").read_text(encoding="utf-8")
        self.assertIn("WHAT IT DOES", js)
        self.assertIn("ACQUISITION", js)
        self.assertIn("effects.range", js)
        self.assertIn("effects.rank0", js)
        self.assertIn("effects.rankMax", js)

    def test_snapshot_metadata_and_reuse_validation(self):
        items = mods.market_items(self.catalog(), "mod")
        s = mods.snapshot("mod", "2026-10-27", items, {}, {})
        self.assertTrue(mods.reusable(s, "2026-10-27", "mod"))
        self.assertFalse(mods.reusable(s, "2026-10-26", "mod"))
        self.assertFalse(mods.reusable({"schemaVersion": 1, "source": "Relics.run/history",
                                         "category": "mod", "items": [None] * 510}, None, "mod"))


if __name__ == "__main__":
    unittest.main()

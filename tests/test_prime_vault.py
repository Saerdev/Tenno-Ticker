"""Regression checks for Wiki-backed Prime relic availability."""

import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import prime_vault


class TestPrimeVault(unittest.TestCase):
    def test_wiki_title_and_acquisition_request(self):
        self.assertEqual(prime_vault.prime_title("Acceltra Prime Set"), "Acceltra Prime")
        self.assertIn("getUnvaultedRelicCountForSet|name=Acceltra Prime",
                      prime_vault.query_text(["Acceltra Prime Set"]))
        with self.assertRaises(ValueError):
            prime_vault.prime_title("Invalid item")

    def test_wiki_relic_count_maps_to_yes_no_or_unavailable(self):
        names = ["Acceltra Prime Set", "Braton Prime Set", "Other Prime Set"]
        def fake_wiki(params):
            self.assertEqual(params["action"], "expandtemplates")
            return {"expandtemplates": {"wikitext": "V000=0\nV001=7\nV002=-1"}}
        results = prime_vault.fetch_vaulted_statuses(names, fetch_json=fake_wiki)
        self.assertEqual(results, dict(zip(names, (True, False, None))))
        self.assertEqual(prime_vault.parse_counts("V000=5", 3), [5, None, None])

    def test_current_catalog_does_not_refresh(self):
        names = ["Acceltra Prime Set", "Braton Prime Set"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_text(json.dumps({
                "checkedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
                "sets": {names[0]: True, names[1]: False},
            }), encoding="utf-8")
            with mock.patch.object(prime_vault, "refresh_catalog") as refresh:
                self.assertFalse(prime_vault.refresh_if_stale(names, path))
                refresh.assert_not_called()
                self.assertTrue(prime_vault.refresh_if_stale(names + ["Other Prime Set"], path))
                refresh.assert_called_once()

    def test_shipped_catalog_covers_published_prime_sets(self):
        root = Path(__file__).resolve().parents[1] / "site/data"
        with (root / "prime-sets.json").open(encoding="utf-8") as handle:
            names = {item["name"] for item in json.load(handle)["sets"]}
        catalog = prime_vault.read_catalog(root / "prime-vault-status.json")
        self.assertTrue(names.issubset(catalog))
        self.assertTrue(all(isinstance(catalog[name], bool) for name in names))

    def test_vault_filter_controls_are_connected(self):
        site = Path(__file__).resolve().parents[1] / "site"
        html = (site / "prime-sets.html").read_text(encoding="utf-8")
        javascript = (site / "prime-sets.js").read_text(encoding="utf-8")
        for control in ("prime-vaulted-only", "prime-unvaulted-only"):
            self.assertIn(f'id="{control}" type="checkbox"', html)
        self.assertIn("item.vaulted === vaultFilter", javascript)
        self.assertIn("els.unvaultedOnly.checked = false", javascript)
        self.assertIn("els.vaultedOnly.checked = false", javascript)

    def test_prime_table_uses_balanced_columns_and_panel_padding(self):
        css = (Path(__file__).resolve().parents[1] / "site/prime-sets.css").read_text(encoding="utf-8")
        self.assertIn(".price-table.prime-table{min-width:1080px;table-layout:fixed}", css)
        self.assertIn(".price-table.prime-table th,.price-table.prime-table td{width:16.6667%;text-align:center}", css)
        self.assertIn("padding:20px 28px 16px", css)
        self.assertIn("padding:12px 28px", css)


if __name__ == "__main__":
    unittest.main()

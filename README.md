# Tenno Ticker

**Website (after renaming the GitHub repository):** https://saerdev.github.io/Tenno-Ticker/

Tenno Ticker is a community-made Warframe price tracker with three boards:

- **Arcanes:** daily median closed-order prices, reported volume, and 7-day change for Rank 0 or Max Rank. Hover for effects and acquisition sources; watchlist and links to Warframe.market and the Warframe Wiki.
- **Prime Sets:** daily median closed-order prices, volume, 7-day change, Wiki-backed vault status, and filters for vaulted/unvaulted sets.
- **Mods:** daily Rank 0 or Max Rank prices, volume, 7-day change, links to Warframe.market and the Wiki, and hover tooltips with documented acquisition sources. Includes market-listed tradable Mods, excluding Rivens, relics, and weapon parts.

Prices are taken only from the **reported closed-order** records in [Relics.run's daily history](https://relics.run/history/). Missing values display as —. These are not active listings or independently verified in-game trades.

The [Warframe.market](https://warframe.market) API supplies the hourly Arcane metadata scan. [WFCD/warframe-items](https://github.com/WFCD/warframe-items) supplies Arcane effect/acquisition data and Mod acquisition locations. Some Mods have no listed location; their tooltip links to the Wiki.

## Publishing and scheduling

The existing `.github/workflows/publish.yaml` is triggered through GitHub's `workflow_dispatch` endpoint from **cron-job.org** once an hour. It runs:

```cmd
python scripts/update_prices.py --output site/data/prices.json
python scripts/update_mods.py --output site/data/mods.json --arcane-output site/data/arcane-daily.json
python scripts/update_prime_sets.py --output site/data/prime-sets.json
```

The Mod/Arcane daily and Prime Set generators reuse the published snapshot when the source day has not changed. The workflow deploys the `site` directory to GitHub Pages. There is no built-in GitHub Actions cron schedule.

### After renaming `Saerdev/Arcane-Atlas` to `Saerdev/Tenno-Ticker`

1. In GitHub, open **Settings → General → Repository name** and set `Tenno-Ticker`.
2. Under **Settings → Pages**, verify **Source: GitHub Actions**.
3. Update the cron-job.org request URL to the renamed GitHub repository:
   `https://api.github.com/repos/Saerdev/Tenno-Ticker/actions/workflows/publish.yaml/dispatches`
   (Keep the existing authorization header, POST body and schedule.)
4. Trigger a workflow run and verify the new Pages URL above. GitHub does **not** automatically redirect the old project Pages URL when its repository is renamed.

## Local testing (Windows CMD)

From the folder containing `scripts` and `site`:

```cmd
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/update_mods.py --no-reuse
python -m http.server 8000 --directory site
```

Open http://localhost:8000/ in your browser. Stop the server with Ctrl+C.

See [third-party notices](site/THIRD_PARTY_NOTICES.md). Tenno Ticker is not affiliated with Digital Extremes, Warframe.market, Relics.run, or WFCD.

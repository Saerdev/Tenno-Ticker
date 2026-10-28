# Tenno Ticker

**Website:** https://saerdev.github.io/Tenno-Ticker/

Tenno Ticker is a community-made Warframe price tracker with three boards:

- **Arcanes:** daily median closed-order prices, reported volume, and 7-day change for Rank 0 or Max Rank. Hover for effects and acquisition sources; watchlist and links to Warframe.market and the Warframe Wiki.
- **Prime Sets:** daily median closed-order prices, volume, 7-day change, Wiki-backed vault status, and filters for vaulted/unvaulted sets.
- **Mods:** daily Rank 0 or Max Rank prices, volume, 7-day change, links to Warframe.market and the Wiki, and hover tooltips with documented acquisition sources. Includes market-listed tradable Mods, excluding Rivens, relics, and weapon parts.

Prices are taken only from the **reported closed-order** records in [Relics.run's daily history](https://relics.run/history/). Missing values display as —. These are not active listings or independently verified in-game trades.

The [Warframe.market](https://warframe.market) API supplies the hourly Arcane metadata scan. [WFCD/warframe-items](https://github.com/WFCD/warframe-items) supplies Arcane effect/acquisition data and Mod acquisition locations. Some Mods have no listed location; their tooltip links to the Wiki.

See [third-party notices](site/THIRD_PARTY_NOTICES.md). Tenno Ticker is not affiliated with Digital Extremes, Warframe.market, Relics.run, or WFCD.

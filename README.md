# Arcane Atlas

**Website:** [Arcane Atlas](https://saerdev.github.io/Arcane-Atlas/)

Arcane Atlas tracks Warframe arcane prices and Prime set prices on separate boards. Arcane prices use Warframe.market; historical Prime set prices use Relics.run.

You can search and sort arcanes, compare 48-hour volume-weighted prices and latest traded-hour medians for rank 0 and max rank, check reported 48-hour trading volume, and hover over an arcane to see its effects and where to get it. Each arcane also links to its Warframe.market listing and Wiki page.

Both prices and volumes use the legacy v1 closed-order 48-hour statistics feed. Warframe.market updates its statistics hourly when volume is nonzero; configure cron-job.org to trigger the GitHub workflow once hourly. These are reported closed orders, not guaranteed completed player-to-player trades. Hours with no trades do not generate a new price.

Prime set prices are shown on the [Prime Sets board](https://saerdev.github.io/Arcane-Atlas/prime-sets.html). They use the newest dated history file published by Relics.run. These are historical daily figures, not live listings. The site shows the source date and warns when the history is old.

This is an unofficial fan project, not affiliated with Digital Extremes, Warframe.market, Relics.run, or WFCD. See [third-party notices](site/THIRD_PARTY_NOTICES.md) for credits.

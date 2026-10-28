"""Read Prime set relic availability from the Warframe Wiki's own Lua module.

The PrimeTable acquisition section on Wiki pages uses Module:Void/data.
Its getUnvaultedRelicCountForSet function returns zero if all of the set's
relics are vaulted (or otherwise outside the normal relic drop tables),
positive if a regular relic remains, and -1 if no relic-based entry exists.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

WIKI_API = "https://wiki.warframe.com/api.php"
DEFAULT_CATALOG = Path(__file__).resolve().parents[1] / "site/data/prime-vault-status.json"
DEFAULT_SNAPSHOT = Path(__file__).resolve().parents[1] / "site/data/prime-sets.json"
USER_AGENT = "TennoTicker/1.0 (+https://github.com/Saerdev/Tenno-Ticker)"
BATCH_SIZE = 20
RESULT_PATTERN = re.compile(r"V(\d{3})=(-?\d+)")


def prime_title(set_name: str) -> str:
    if not isinstance(set_name, str) or not set_name.casefold().endswith(" prime set"):
        raise ValueError(f"Not a Prime set: {set_name!r}")
    title = set_name[:-4].strip()
    if any(char in title for char in ("|", "{", "}", "\n", "\r")):
        raise ValueError(f"Unsupported Wiki title: {title!r}")
    return title


def query_text(names: list[str]) -> str:
    return "\n".join(
        f"V{index:03d}=" + "{{#invoke:Void|getUnvaultedRelicCountForSet|name="
        + prime_title(name) + "}}"
        for index, name in enumerate(names)
    )


def fetch_wiki_json(params: dict[str, str], timeout: int = 35) -> dict:
    url = WIKI_API + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept": "application/json",
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read(1_000_001)
                if len(raw) > 1_000_000:
                    raise ValueError("Wiki API response unexpectedly large")
                return json.loads(raw)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            if isinstance(error, urllib.error.HTTPError) and error.code not in (429, 500, 502, 503, 504):
                raise
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("Warframe Wiki request failed")


def parse_counts(wikitext: str, batch_length: int) -> list[int | None]:
    matches = {int(index): int(count) for index, count in RESULT_PATTERN.findall(wikitext)}
    return [matches.get(index) for index in range(batch_length)]


def statuses_from_counts(counts: list[int | None]) -> list[bool | None]:
    return [None if count is None or count < 0 else count == 0 for count in counts]


def fetch_vaulted_statuses(names: list[str], fetch_json=fetch_wiki_json) -> dict[str, bool | None]:
    """Return a status for every name without mistaking unavailable data for 'No'."""
    statuses: dict[str, bool | None] = {}
    for start in range(0, len(names), BATCH_SIZE):
        batch = names[start:start + BATCH_SIZE]
        response = fetch_json({
            "action": "expandtemplates", "format": "json", "formatversion": "2",
            "prop": "wikitext", "text": query_text(batch),
        })
        text = (response.get("expandtemplates") or {}).get("wikitext")
        if not isinstance(text, str):
            raise ValueError("Warframe Wiki returned no expanded relic data")
        for name, status in zip(batch, statuses_from_counts(parse_counts(text, len(batch)))):
            statuses[name] = status
    return statuses


def read_catalog(path: Path = DEFAULT_CATALOG) -> dict[str, bool | None]:
    if not path.exists():
        return {}
    document = json.loads(path.read_text(encoding="utf-8"))
    statuses = document.get("sets") if isinstance(document, dict) else None
    if not isinstance(statuses, dict):
        raise ValueError("Invalid Wiki vault catalog")
    return {name: status for name, status in statuses.items()
            if isinstance(name, str) and (isinstance(status, bool) or status is None)}


def refresh_catalog(names: list[str], path: Path = DEFAULT_CATALOG) -> dict[str, bool | None]:
    statuses = fetch_vaulted_statuses(names)
    if len(statuses) != len(set(names)):
        raise ValueError("Incomplete Warframe Wiki vault status response")
    document = {
        "source": "Warframe Wiki Module:Void/data via Module:Void",
        "checkedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "sets": statuses,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".prime-vault-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(document, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return statuses


def refresh_if_stale(names: list[str], path: Path = DEFAULT_CATALOG,
                     hours: int = 24) -> bool:
    """Limit routine Wiki traffic while still updating after game changes."""
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            checked_at = dt.datetime.fromisoformat(data["checkedAt"])
            age = dt.datetime.now(dt.timezone.utc) - checked_at
            if (dt.timedelta(0) <= age < dt.timedelta(hours=hours)
                    and isinstance(data.get("sets"), dict)
                    and all(name in data["sets"] for name in names)):
                return False
        except (ValueError, TypeError, KeyError):
            pass
    refresh_catalog(names, path)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_CATALOG)
    args = parser.parse_args()
    data = json.loads(args.snapshot.read_text(encoding="utf-8"))
    names = [row["name"] for row in data["sets"]]
    statuses = refresh_catalog(names, args.output)
    print(f"Wiki vault status: {sum(status is True for status in statuses.values())} vaulted, "
          f"{sum(status is False for status in statuses.values())} unvaulted, "
          f"{sum(status is None for status in statuses.values())} unclassified")
    return 0


if __name__ == "__main__":
    sys.exit(main())

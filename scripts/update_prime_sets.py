#!/usr/bin/env python3
"""Build the Prime Sets snapshot from Relics.run's daily historical statistics."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request

HISTORY_ROOT = "https://relics.run/history/"
CATALOG_URL = HISTORY_ROOT + "item_data/item_ids.json"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "site/data/prime-sets.json"
DEFAULT_REUSE = "https://saerdev.github.io/Tenno-Ticker/data/prime-sets.json"
LEGACY_REUSE = "https://saerdev.github.io/Arcane-Atlas/data/prime-sets.json"
USER_AGENT = os.environ.get(
    "RELICS_USER_AGENT", "TennoTicker/1.0 (+https://github.com/Saerdev/Tenno-Ticker)"
)
DATE_PATTERN = re.compile(r'href=["\']price_history_(\d{4}-\d{2}-\d{2})\.json["\']')


def download(url: str, max_bytes: int = 9_000_000) -> bytes:
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept": "application/json, text/html;q=0.8",
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=35) as response:
                data = response.read(max_bytes + 1)
                if len(data) > max_bytes:
                    raise ValueError(f"Response exceeds {max_bytes} bytes: {url}")
                return data
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            if isinstance(error, urllib.error.HTTPError) and error.code not in (429, 500, 502, 503, 504):
                raise
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Could not download {url}")


def latest_history_date(html: str, today: dt.date | None = None) -> str:
    today = today or dt.datetime.now(dt.timezone.utc).date()
    dates = set()
    for match in DATE_PATTERN.findall(html):
        try:
            day = dt.date.fromisoformat(match)
        except ValueError:
            continue
        if day <= today:
            dates.add(day)
    if not dates:
        raise ValueError("Relics.run directory does not list a usable daily price history")
    return max(dates).isoformat()


def positive_float(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def positive_number(value):
    number = positive_float(value)
    return math.floor(number) if number is not None else None


def percent_change(current, previous):
    current_value = positive_float(current)
    previous_value = positive_float(previous)
    if current_value is None or previous_value is None:
        return None
    change = round((current_value / previous_value - 1) * 100, 1)
    return 0.0 if change == 0 else change


def seven_days_before(source_date: str) -> str:
    return (dt.date.fromisoformat(source_date) - dt.timedelta(days=7)).isoformat()


def count(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return int(number) if math.isfinite(number) and number >= 0 and number.is_integer() else None


def is_prime_set(name: object) -> bool:
    return isinstance(name, str) and name.casefold().endswith(" prime set")


def latest_record(records: object, order_type: str) -> dict | None:
    if not isinstance(records, list):
        return None
    matches = [record for record in records if isinstance(record, dict)
               and record.get("order_type") == order_type]
    if not matches:
        return None
    return max(matches, key=lambda record: str(record.get("datetime") or ""))


def normalize(catalog: object, history: object, source_date: str,
              comparison_history: object | None = None) -> list[dict]:
    # comparison_history is optional to preserve callers of the original
    # three-column snapshot and their existing regression tests.
    if not isinstance(catalog, dict) or not isinstance(history, dict):
        raise ValueError("Relics.run catalog or history has an unsupported format")
    if comparison_history is not None and not isinstance(comparison_history, dict):
        raise ValueError("Relics.run catalog or history has an unsupported format")
    names = {name for name in catalog if is_prime_set(name)}
    names.update(name for name in history if is_prime_set(name))
    if len(names) < 20:
        raise ValueError(f"Only {len(names)} Prime sets found; refusing incomplete snapshot")
    result = []
    for name in sorted(names, key=str.casefold):
        records = history.get(name)
        closed = latest_record(records, "closed")
        row = {
            "name": name,
            "medianClosedPrice": positive_number(closed.get("median")) if closed else None,
            "volume": count(closed.get("volume")) if closed else None,
        }
        if comparison_history is not None:
            previous_closed = latest_record(comparison_history.get(name), "closed")
            row["change7dPct"] = percent_change(
                closed.get("median") if closed else None,
                previous_closed.get("median") if previous_closed else None,
            )
        result.append(row)
    return result


def parse_json(data: bytes, source: str):
    try:
        return json.loads(data)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid JSON from {source}") from error


def reusable_snapshot(data: object, date: str | None = None) -> bool:
    if not isinstance(data, dict):
        return False
    version = data.get("schemaVersion")
    if version not in (2, 3):
        return False
    return (data.get("source") == "Relics.run/history"
            and (date is None or data.get("sourceDate") == date)
            and (version == 2 or isinstance(data.get("comparisonDate"), str))
            and isinstance(data.get("sets"), list) and len(data["sets"]) >= 20
            and all(isinstance(item, dict) and is_prime_set(item.get("name"))
                    and "medianClosedPrice" in item and "volume" in item
                    and (version == 2 or "change7dPct" in item)
                    for item in data["sets"]))


def load_existing(url: str) -> dict | None:
    try:
        data = parse_json(download(url, 1_500_000), url)
        return data if reusable_snapshot(data) else None
    except (ValueError, urllib.error.URLError, TimeoutError, OSError):
        return None


def build_snapshot(source_date: str, catalog: object, history: object,
                   comparison_history: object | None = None) -> dict:
    sets = normalize(catalog, history, source_date, comparison_history)
    snapshot = {
        "schemaVersion": 3 if comparison_history is not None else 2,
        "source": "Relics.run/history",
        "sourceDate": source_date,
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "sets": sets,
    }
    if comparison_history is not None:
        snapshot["comparisonDate"] = seven_days_before(source_date)
    return snapshot


def save_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".prime-sets-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            stream.write("\n")
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def update(output: Path, reuse_url: str | None) -> str:
    previous = load_existing(reuse_url) if reuse_url else None
    # Keep daily reuse working before GitHub's repository/Pages URL is renamed.
    if previous is None and reuse_url == DEFAULT_REUSE:
        previous = load_existing(LEGACY_REUSE)
    # Schema 2 snapshots lack the seven-day comparison and must be rebuilt.
    if previous and previous.get("schemaVersion") != 3:
        previous = None
    try:
        index = download(HISTORY_ROOT, 750_000).decode("utf-8")
        date = latest_history_date(index)
        if previous and reusable_snapshot(previous, date):
            save_atomic(output, previous)
            return f"Reused {len(previous['sets'])} Prime sets from {date} (no new source day)"
        history_url = f"{HISTORY_ROOT}price_history_{date}.json"
        comparison_date = seven_days_before(date)
        comparison_url = f"{HISTORY_ROOT}price_history_{comparison_date}.json"
        catalog = parse_json(download(CATALOG_URL), CATALOG_URL)
        history = parse_json(download(history_url), history_url)
        try:
            comparison_history = parse_json(download(comparison_url), comparison_url)
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            comparison_history = {}  # No exact comparison day: show missing changes.
        snapshot = build_snapshot(date, catalog, history, comparison_history)
        save_atomic(output, snapshot)
        return (f"Updated {len(snapshot['sets'])} Prime sets from Relics.run {date} "
                f"(7-day comparison: {comparison_date})")
    except (ValueError, urllib.error.URLError, TimeoutError, OSError) as error:
        if previous:
            save_atomic(output, previous)
            return f"Source unavailable ({error}); retained {len(previous['sets'])} sets from {previous['sourceDate']}"
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--reuse-url", default=DEFAULT_REUSE,
                        help="Previously published snapshot used to avoid re-downloading unchanged history")
    parser.add_argument("--no-reuse", action="store_true", help="Do not fetch the previous published snapshot")
    parser.add_argument("--skip-vault-refresh", action="store_true",
                        help="Skip refreshing the Warframe Wiki relic availability catalog")
    args = parser.parse_args()
    try:
        print(update(args.output, None if args.no_reuse else args.reuse_url))
        if not args.skip_vault_refresh:
            # Wiki availability has a separate source and cache. A Wiki outage
            # must not fail a successful Relics.run price refresh.
            try:
                from prime_vault import refresh_if_stale
                snapshot = json.loads(args.output.read_text(encoding="utf-8"))
                names = [item["name"] for item in snapshot["sets"]]
                if refresh_if_stale(names):
                    print("Refreshed Prime relic vault status from the Warframe Wiki")
                else:
                    print("Prime relic vault status is current (24-hour cache)")
            except Exception as error:
                print(f"Warning: Wiki vault status refresh skipped ({error})", file=sys.stderr)
        return 0
    except Exception as error:
        print(f"Prime set update failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

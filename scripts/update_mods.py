#!/usr/bin/env python3
"""Build daily closed-order prices for tradable Mods and Arcanes from Relics.run."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
from pathlib import Path
import urllib.error
import urllib.parse

from update_prime_sets import (HISTORY_ROOT, download, latest_history_date,
                               latest_record, parse_json, percent_change,
                               positive_number, count, save_atomic,
                               seven_days_before)

ITEMS_URL = HISTORY_ROOT + "item_data/items.json"
MOD_ACQUISITION_URL = "https://raw.githubusercontent.com/WFCD/warframe-items/master/data/json/Mods.json"
SITE_ROOT = Path(__file__).resolve().parents[1] / "site/data"
DEFAULT_MODS = SITE_ROOT / "mods.json"
DEFAULT_ARCANES = SITE_ROOT / "arcane-daily.json"
PAGES_ROOT = "https://saerdev.github.io/Tenno-Ticker/data/"
LEGACY_PAGES_ROOT = "https://saerdev.github.io/Arcane-Atlas/data/"


def market_items(catalog: object, category: str) -> list[dict]:
    if not isinstance(catalog, list):
        raise ValueError("Relics.run item catalog must be a list")
    selected = {}
    for item in catalog:
        if not isinstance(item, dict) or not isinstance(item.get("slug"), str):
            continue
        tags = item.get("tags") or []
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            continue
        if category == "mod":
            # A category filter, not a name heuristic: includes augments, auras,
            # stances, Primed, Galvanized, and other market-tradable mods.
            if "mod" not in tags or any(t in tags for t in ("arcane_enhancement", "riven", "relic")):
                continue
        else:
            if "arcane_enhancement" not in tags or "mod" in tags:
                continue
        i18n = item.get("i18n") or {}
        english = i18n.get("en") if isinstance(i18n, dict) else None
        name = english.get("name") if isinstance(english, dict) else None
        if not isinstance(name, str) or not name.strip():
            continue
        max_rank = item.get("maxRank")
        if isinstance(max_rank, bool) or not isinstance(max_rank, int) or max_rank < 0:
            max_rank = 0
        selected[item["slug"]] = {
            "name": name.strip(), "slug": item["slug"], "maxRank": max_rank,
        }
    result = sorted(selected.values(), key=lambda item: item["name"].casefold())
    minimum = 500 if category == "mod" else 100
    if len(result) < minimum:
        raise ValueError(f"Only {len(result)} {category} items found; refusing incomplete snapshot")
    return result


def normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


EFFECT_NUMBER = re.compile(r"(?<![a-zA-Z0-9_.])([-+]?\d+(?:\.\d+)?(?:%|ms|s|m|x)?)", re.IGNORECASE)


def effect_range(rank_zero: str | None, max_rank: str | None) -> str | None:
    """Show precise rank-0 → max-rank numbers when the wording is unchanged.

    Never imply a numerical progression if the effect text itself differs.
    In that case the UI shows both full rank descriptions separately.
    """
    if not rank_zero or not max_rank:
        return None
    if rank_zero == max_rank:
        return rank_zero
    low = EFFECT_NUMBER.split(rank_zero)
    high = EFFECT_NUMBER.split(max_rank)
    if len(low) != len(high) or len(low) < 3 or any(
        low[index] != high[index] for index in range(0, len(low), 2)
    ):
        return None
    result = []
    for index, part in enumerate(low):
        if index % 2 == 0:
            result.append(part)
        else:
            result.append(part if part == high[index] else f"{part} → {high[index]}")
    return "".join(result)


def mod_effects(record: dict) -> dict:
    """Extract readable descriptions from WFCD's rank-by-rank mod effect data."""
    def rank_text(rank: object) -> str | None:
        if not isinstance(rank, dict):
            return None
        stats = rank.get("stats")
        if isinstance(stats, str):
            stats = [stats]
        if not isinstance(stats, list):
            return None
        lines = []
        for stat in stats:
            if not isinstance(stat, str):
                continue
            for line in stat.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\r", "\n").split("\n"):
                cleaned = re.sub(r"[ \t]+", " ", line).strip()
                if cleaned and cleaned not in lines:
                    lines.append(cleaned)
        return "\n".join(lines)[:3000] if lines else None

    levels = record.get("levelStats")
    first = rank_text(levels[0]) if isinstance(levels, list) and levels else None
    last = rank_text(levels[-1]) if isinstance(levels, list) and levels else None
    fallback = record.get("description")
    fallback = fallback.strip()[:3000] if isinstance(fallback, str) and fallback.strip() else None
    return {
        "rank0": first,
        "rankMax": last,
        "range": effect_range(first, last),
        "description": fallback,
    }


def mod_acquisitions(records: object) -> dict[str, dict]:
    if not isinstance(records, list):
        raise ValueError("WFCD mod acquisition data must be a list")
    result: dict[str, dict] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("name"), str):
            continue
        if record.get("tradable") is False:
            continue
        name = record["name"]
        key = normalized_name(name)
        details = result.setdefault(key, {"sources": [], "wikiUrl": None, "effects": None})
        if details["effects"] is None or not details["effects"].get("rank0"):
            details["effects"] = mod_effects(record)
        wiki = record.get("wikiaUrl")
        if isinstance(wiki, str) and wiki.startswith("https://wiki.warframe.com/w/"):
            details["wikiUrl"] = wiki
        for drop in record.get("drops") or []:
            if not isinstance(drop, dict) or not isinstance(drop.get("location"), str):
                continue
            # Some WFCD records contain unrelated drops with similar names.
            # Their `type` identifies the mod actually obtained there.
            drop_type = drop.get("type")
            if isinstance(drop_type, str) and normalized_name(drop_type) not in (
                    key, normalized_name(name + " (" + str(record.get("compatName", "")) + ")")):
                continue
            place = drop["location"].strip()
            if not place or len(place) > 180:
                continue
            chance = drop.get("chance")
            if isinstance(chance, bool) or not isinstance(chance, (int, float)) or not math.isfinite(chance):
                chance = None
            else:
                chance = round(float(chance), 3) if 0 <= chance <= 100 else None
            if not any(source["location"] == place for source in details["sources"]):
                details["sources"].append({"location": place, "chance": chance})
    for details in result.values():
        details["sources"].sort(key=lambda s: (s["chance"] is None, -(s["chance"] or 0), s["location"]))
        details["sources"] = details["sources"][:12]
    return result


def rank_statistics(records: object, previous: object, max_rank: int, rank: int) -> dict:
    def rank_closed(rows: object) -> dict | None:
        matching = [r for r in rows if isinstance(r, dict) and r.get("order_type") == "closed"
                    and r.get("mod_rank", 0) == rank] if isinstance(rows, list) else []
        return latest_record(matching, "closed")
    current = rank_closed(records)
    older = rank_closed(previous)
    median = current.get("median") if current else None
    return {
        "medianClosedPrice": positive_number(median),
        "volume": count(current.get("volume")) if current else None,
        "change7dPct": percent_change(median, older.get("median") if older else None),
    }


def build_rows(items: list[dict], current: object, previous: object,
               acquisition: dict[str, dict] | None = None) -> list[dict]:
    if not isinstance(current, dict) or not isinstance(previous, dict):
        raise ValueError("Relics.run daily history must be a mapping")
    result = []
    for item in items:
        row = dict(item)
        records, older = current.get(item["name"]), previous.get(item["name"])
        row["rank0"] = rank_statistics(records, older, item["maxRank"], 0)
        row["rankMax"] = (rank_statistics(records, older, item["maxRank"], item["maxRank"])
                          if item["maxRank"] else row["rank0"])
        if acquisition is not None:
            details = acquisition.get(normalized_name(item["name"]), {})
            row["sources"] = details.get("sources", [])
            row["wikiUrl"] = details.get("wikiUrl") or "https://wiki.warframe.com/w/" + urllib.parse.quote(item["name"].replace(" ", "_"), safe="()")
            row["effects"] = details.get("effects") or {
                "rank0": None, "rankMax": None, "range": None, "description": None,
            }
        result.append(row)
    return result


def snapshot(category: str, date: str, items: list[dict], current: object,
             previous: object, acquisition: dict[str, dict] | None = None) -> dict:
    return {
        "schemaVersion": 1, "source": "Relics.run/history", "category": category,
        "sourceDate": date, "comparisonDate": seven_days_before(date),
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "items": build_rows(items, current, previous, acquisition),
    }


def reusable(data: object, date: str | None, category: str) -> bool:
    return (isinstance(data, dict) and data.get("schemaVersion") == 1
            and data.get("source") == "Relics.run/history" and data.get("category") == category
            and (date is None or data.get("sourceDate") == date)
            and isinstance(data.get("sourceDate"), str)
            and data.get("comparisonDate") == seven_days_before(data["sourceDate"])
            and isinstance(data.get("items"), list)
            and len(data["items"]) >= (500 if category == "mod" else 100))


def optional_previous(url: str, category: str) -> dict | None:
    try:
        data = parse_json(download(url, 2_500_000), url)
        return data if reusable(data, None, category) else None
    except (ValueError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, KeyError):
        return None


def update(mod_output: Path, arcane_output: Path, reuse: bool = True) -> str:
    previous_mods = optional_previous(PAGES_ROOT + "mods.json", "mod") if reuse else None
    previous_arcanes = optional_previous(PAGES_ROOT + "arcane-daily.json", "arcane") if reuse else None
    # The old project Pages URL remains usable until the repository is renamed.
    if reuse and previous_mods is None:
        previous_mods = optional_previous(LEGACY_PAGES_ROOT + "mods.json", "mod")
    if reuse and previous_arcanes is None:
        previous_arcanes = optional_previous(LEGACY_PAGES_ROOT + "arcane-daily.json", "arcane")
    try:
        date = latest_history_date(download(HISTORY_ROOT, 750_000).decode("utf-8"))
        if (previous_mods and previous_arcanes and reusable(previous_mods, date, "mod")
                and reusable(previous_arcanes, date, "arcane")
                and sum(bool(item.get("effects", {}).get("rank0") or
                             item.get("effects", {}).get("description"))
                        for item in previous_mods["items"] if isinstance(item, dict) and
                        isinstance(item.get("effects"), dict)) >= 500):
            save_atomic(mod_output, previous_mods)
            save_atomic(arcane_output, previous_arcanes)
            return f"Reused published daily Mods and Arcanes snapshots from {date}"
        older_date = seven_days_before(date)
        catalog = parse_json(download(ITEMS_URL, 2_500_000), ITEMS_URL)
        current = parse_json(download(f"{HISTORY_ROOT}price_history_{date}.json", 9_000_000), date)
        try:
            previous = parse_json(download(f"{HISTORY_ROOT}price_history_{older_date}.json", 9_000_000), older_date)
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            previous = {}
        try:
            acquisitions = mod_acquisitions(parse_json(download(MOD_ACQUISITION_URL, 11_000_000), MOD_ACQUISITION_URL))
        except (ValueError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as error:
            print(f"Mod acquisition metadata unavailable ({error}); retaining Wiki links and known sources")
            acquisitions = {normalized_name(item["name"]): {"sources": item.get("sources", []), "wikiUrl": item.get("wikiUrl"),
                                                             "effects": item.get("effects")}
                            for item in previous_mods.get("items", [])} if previous_mods else {}
        mods = snapshot("mod", date, market_items(catalog, "mod"), current, previous, acquisitions)
        arcanes = snapshot("arcane", date, market_items(catalog, "arcane"), current, previous)
        save_atomic(mod_output, mods)
        save_atomic(arcane_output, arcanes)
        return f"Updated {len(mods['items'])} mods and {len(arcanes['items'])} arcanes for {date} (7-day baseline: {older_date})"
    except (ValueError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as error:
        if previous_mods and previous_arcanes:
            save_atomic(mod_output, previous_mods)
            save_atomic(arcane_output, previous_arcanes)
            return f"Sources unavailable ({error}); retained previous daily price snapshots"
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_MODS)
    parser.add_argument("--arcane-output", type=Path, default=DEFAULT_ARCANES)
    parser.add_argument("--no-reuse", action="store_true")
    args = parser.parse_args()
    try:
        print(update(args.output, args.arcane_output, not args.no_reuse))
        return 0
    except (ValueError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as error:
        print(f"Mod and Arcane daily update failed: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

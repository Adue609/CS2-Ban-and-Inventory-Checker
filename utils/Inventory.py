import requests
import time
import json
import random
from typing import Optional

from utils.logger import get_logger
from utils.PriceChecker import get_market_price_from_cache
from utils.config import Update_Interval

# Logger
logger = get_logger("Inventory")

INVENTORY_FILE = "inventory_cache.json"
INVENTORY_UPDATE_INTERVAL = Update_Interval

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://steamcommunity.com/",
}

session = requests.Session()
session.headers.update(HEADERS)


def read_cache() -> dict:
    try:
        with open(INVENTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_cache(data: dict) -> None:
    with open(INVENTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def update_cache_entry(steam_id: str, inventory_text: str) -> None:
    cache = read_cache()
    cache[steam_id] = {
        "inventory": inventory_text,
        "last_updated": int(time.time())
    }
    write_cache(cache)


def get_inventory_from_cache(steam_id: str) -> Optional[str]:
    cache = read_cache()
    entry = cache.get(steam_id)
    if not entry:
        return None
    return entry.get("inventory")


def needs_refresh(entry: Optional[dict]) -> bool:
    if not entry or "last_updated" not in entry:
        return True
    return (time.time() - entry["last_updated"]) >= INVENTORY_UPDATE_INTERVAL


def fetch_inventory(steam_id: str, appid: int = 730, contextid: int = 2) -> str:
    url = f"https://steamcommunity.com/inventory/{steam_id}/{appid}/{contextid}"
    for attempt in range(10):
        try:
            time.sleep(1)
            r = session.get(url, timeout=15)
        except requests.exceptions.RequestException:
            logger.exception("HTTP/request error while fetching inventory for %s (attempt=%d)", steam_id, attempt + 1)
            time.sleep(2)
            continue

        if r.status_code == 429:
            backoff = 1.5 * (2 ** attempt) + random.uniform(0, 1)
            logger.warning("Received 429 for inventory %s (attempt=%d). Backing off %.1fs", steam_id, attempt + 1, backoff)
            time.sleep(backoff)
            continue

        if r.status_code != 200:
            logger.warning("Inventory request for %s returned status %s", steam_id, r.status_code)
            time.sleep(5)
            continue

        if not r.text:
            logger.debug("Empty inventory response for %s", steam_id)
            return "Inventory unavailable"

        try:
            data = r.json()
        except ValueError:
            logger.warning("Inventory JSON decode failed for %s", steam_id)
            return "Inventory private or rate-limited"

        if not isinstance(data, dict):
            logger.debug("Inventory response not a dict for %s", steam_id)
            return "Inventory unavailable"

        if data.get("success") != 1:
            logger.debug("Inventory success flag != 1 for %s", steam_id)
            return "Inventory private or unavailable"

        descriptions = data.get("descriptions")
        assets = data.get("assets") or []
        if isinstance(descriptions, dict):
            descriptions = list(descriptions.values())

        if not isinstance(descriptions, list) or not descriptions:
            logger.debug("No descriptions found in inventory for %s", steam_id)
            return "No items found"

        asset_counts = {}
        for asset in assets:
            key = (str(asset.get("classid")), str(asset.get("instanceid", "0")))
            asset_counts[key] = asset_counts.get(key, 0) + 1

        market_totals = {}
        for item in descriptions:
            name = item.get("market_name", "Unknown")
            market_hash = item.get("market_hash_name", name)
            classid = str(item.get("classid"))
            instanceid = str(item.get("instanceid", "0"))
            count = asset_counts.get((classid, instanceid), 1)

            price = get_market_price_from_cache(market_hash)

            tradable = bool(item.get("tradable", 0))
            marketable = bool(item.get("marketable", 0))

            if market_hash in market_totals:
                existing = market_totals[market_hash]
                existing['count'] += count
                existing['price'] = price or existing['price']
                existing['tradable'] = existing['tradable'] or tradable
                existing['marketable'] = existing['marketable'] or marketable
            else:
                market_totals[market_hash] = {
                    'name': name,
                    'count': count,
                    'price': price,
                    'tradable': tradable,
                    'marketable': marketable
                }

        lines = []
        for v in market_totals.values():
            qty_str = f" x{v['count']}" if v['count'] > 1 else ""
            lines.append(f"{v['name']}{qty_str} - {v['price']}")# T={v['tradable']} M={v['marketable']}")

        return "Items:\n" + "\n".join(lines)

    logger.error("Exhausted inventory retries for %s after %d attempts", steam_id, 10)
    return "Inventory rate-limited"


def get_inventory_summary(steam_id: str, appid: int = 730, contextid: int = 2, use_cache: bool = False) -> str:
    cache = read_cache()
    entry = cache.get(steam_id)
    if use_cache and entry and not needs_refresh(entry):
        logger.info("Returning cached inventory for %s", steam_id)
        return entry.get("inventory")

    inventory = fetch_inventory(steam_id, appid=appid, contextid=contextid)
    if inventory and isinstance(inventory, str):
        logger.info("Returning inventory from Steam for %s", steam_id)
        update_cache_entry(steam_id, inventory)
    return inventory


def force_update_all_inventories() -> None:
    cache = read_cache()
    for steam_id in list(cache.keys()):
        inv = fetch_inventory(steam_id)
        cache[steam_id] = {
            "inventory": inv,
            "last_updated": int(time.time())
        }
    write_cache(cache)
import requests
import time
import json
import threading
import re

from utils.logger import get_logger
from utils.config import UPDATE_INTERVAL

# Logger
logger = get_logger("PriceChecker")


PRICE_FILE = "cs_prices.json"
INVENTORY_FILE = "inventory_cache.json"
PRICE_UPDATE_INTERVAL = max(60, UPDATE_INTERVAL * 6)  # 6 times the configured interval
MAX_NON_200_RETRIES = 5
STEAM_429_DELAY_SECONDS = 30

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://steamcommunity.com/market/",
}

session = requests.Session()
session.headers.update(HEADERS)
_CACHE_LOCK = threading.RLock()


def _is_stop_requested() -> bool:
    try:
        from utils.Inventory import is_stop_requested
        return is_stop_requested()
    except Exception:
        return False


def read_cache():
    with _CACHE_LOCK:
        try:
            with open(PRICE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.debug("Loaded %d cached price entries from %s", len(data) if isinstance(data, dict) else 0, PRICE_FILE)
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            logger.debug("Price cache missing/invalid, using empty cache: %s", PRICE_FILE)
            return {}

def write_cache(data):
    with _CACHE_LOCK:
        with open(PRICE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.debug("Wrote %d price cache entries to %s", len(data) if isinstance(data, dict) else 0, PRICE_FILE)

def update_cache_entry(item, price):
    with _CACHE_LOCK:
        cache = read_cache()
        cache[item] = {
            "price": price,
            "last_updated": int(time.time())
        }
        write_cache(cache)
    logger.debug("Updated price cache for item=%s value=%s", item, price)

def steam_price(item, ignore_stop: bool = False):
    """Query Steam priceoverview using requests params so names are URL-encoded."""
    url = "https://steamcommunity.com/market/priceoverview/"
    params = {
        "currency": 1,
        "appid": 730,
        "market_hash_name": item
    }
    logger.debug("Priceoverview URL: %s params=%r", url, params)
    for attempt in range(MAX_NON_200_RETRIES):
        if not ignore_stop and _is_stop_requested():
            logger.info("Stop requested; aborting price fetch for %s", item)
            return "Request Restricted"
        try:
            logger.debug("Querying market for item: %s", item)
            r = session.get(url, params=params, timeout=30)
            logger.debug("Market request URL: %s", r.url)
        except requests.exceptions.RequestException:
            logger.exception("Error fetching market data for %s; retry later", item)
            time.sleep(10)
            return "Request Restricted"

        if r.status_code == 429:
            logger.warning(
                "Rate-limited HTTP 429 for item=%s (attempt=%d/%d); sleeping %ss then retrying",
                item,
                attempt + 1,
                MAX_NON_200_RETRIES,
                STEAM_429_DELAY_SECONDS,
            )
            time.sleep(STEAM_429_DELAY_SECONDS)
            continue

        if r.status_code != 200:
            logger.warning(
                "Blocked HTTP %s for item=%s (attempt=%d/%d); retrying",
                r.status_code,
                item,
                attempt + 1,
                MAX_NON_200_RETRIES,
            )
            time.sleep(3)
            continue

        try:
            data = r.json()
        except ValueError:
            logger.exception("Invalid JSON returned for item=%s", item)
            time.sleep(10)
            return "Invalid JSON"

        if data.get("success") and data.get("lowest_price"):
            logger.debug("Found price for %s -> %s", item, data.get("lowest_price"))
            logger.info("Found price for %s -> %s from steam", item, data.get("lowest_price"))
            return data.get("lowest_price")

        logger.info("Item %s not listed", item)
        return "Not Listed"

    logger.warning("Exhausted retries fetching market price for item=%s", item)
    return "Request Restricted"


def needs_refresh(entry):
    if not entry or "last_updated" not in entry:
        logger.debug("Price cache refresh required: missing entry or timestamp")
        return True
    age = time.time() - entry["last_updated"]
    refresh = age >= PRICE_UPDATE_INTERVAL
    logger.debug("Price cache age=%.1fs refresh=%s threshold=%ss", age, refresh, PRICE_UPDATE_INTERVAL)
    return refresh

def get_market_price_from_cache(market_hash_name):
    cache = read_cache()
    entry = cache.get(market_hash_name)

    # force refresh if 7 days passed
    if needs_refresh(entry):
        logger.debug("Refreshing price from Steam for %s", market_hash_name)
        price = steam_price(market_hash_name)
        update_cache_entry(market_hash_name, price)
        return price

    # valid cached price
    cached_price = entry.get("price")
    if cached_price and cached_price.lower() not in ("n/a", "not listed"):
        logger.info("Found price for %s -> %s from cache", market_hash_name, cached_price)
        return cached_price

    # fallback fetch
    logger.debug("Cached price not usable for %s, fetching fallback from Steam", market_hash_name)
    price = steam_price(market_hash_name)
    update_cache_entry(market_hash_name, price)
    return price


def _extract_item_name_from_inventory_line(line: str) -> str:
    if not isinstance(line, str):
        return ""

    line = line.strip()
    if not line or " - " not in line:
        return ""

    name_part = line.split(" - ", 1)[0].strip()
    name_part = re.sub(r"\s+x\d+$", "", name_part)
    return name_part.strip()


def _collect_inventory_items_from_cache() -> set[str]:
    try:
        with open(INVENTORY_FILE, "r", encoding="utf-8") as f:
            inventory_cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return set()
    except Exception:
        logger.exception("Failed reading %s while collecting inventory item names", INVENTORY_FILE)
        return set()

    if not isinstance(inventory_cache, dict):
        return set()

    result = set()
    for entry in inventory_cache.values():
        if not isinstance(entry, dict):
            continue

        summary = entry.get("inventory")
        if not isinstance(summary, str) or not summary.startswith("Items:\n"):
            continue

        for line in summary.splitlines()[1:]:
            item_name = _extract_item_name_from_inventory_line(line)
            if item_name:
                result.add(item_name)

    return result


def force_update_all_prices():
    cache = read_cache()
    inventory_items = _collect_inventory_items_from_cache()
    all_items = set(cache.keys()) | inventory_items
    logger.info(
        "Force updating prices for %d items (price_cache=%d, inventory_cache=%d)",
        len(all_items),
        len(cache),
        len(inventory_items),
    )

    for item in all_items:
        price = steam_price(item, ignore_stop=True)
        cache[item] = {
            "price": price,
            "last_updated": int(time.time())
        }
    write_cache(cache)
import requests
import time
import json
import threading
from typing import Optional

from utils.logger import get_logger
from utils.PriceChecker import get_market_price_from_cache
from utils.config import UPDATE_INTERVAL

# Logger
logger = get_logger("Inventory")

INVENTORY_FILE = "inventory_cache.json"
UNCHANGED_INVENTORY_FILE = "unchanged_inventory.json"
INVENTORY_UPDATE_INTERVAL = max(60, UPDATE_INTERVAL)
CACHE_DISCARD_SECONDS = 24 * 60 * 60
INVENTORY_MAX_RETRIES = 10
INVENTORY_RESPONSE_COUNT_LIMIT = 2000
INVENTORY_COUNT_POLL_INTERVAL = 2.0
INVENTORY_COUNT_POLL_MAX_ATTEMPTS = 1
STEAM_429_DELAY_SECONDS = 30
TRANSIENT_INVENTORY_STATES = {
    "Inventory rate-limited",
    "Inventory unavailable",
    "Inventory private or rate-limited",
    "Inventory fetch stopped",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://steamcommunity.com/",
}

session = requests.Session()
session.headers.update(HEADERS)
_CACHE_LOCK = threading.RLock()
_STOP_EVENT = threading.Event()


def set_stop_requested(value: bool) -> None:
    if value:
        _STOP_EVENT.set()
    else:
        _STOP_EVENT.clear()


def is_stop_requested() -> bool:
    return _STOP_EVENT.is_set()


def read_cache() -> dict:
    with _CACHE_LOCK:
        try:
            with open(INVENTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    logger.debug("Inventory cache content is not dict, using empty cache: %s", INVENTORY_FILE)
                    return {}

                now = int(time.time())
                changed = False
                for steam_id, entry in list(data.items()):
                    if not isinstance(entry, dict):
                        data[steam_id] = {}
                        changed = True
                        continue

                    last_updated = entry.get("last_updated")
                    try:
                        age = now - int(last_updated)
                    except (TypeError, ValueError):
                        age = None

                    if age is not None and age >= CACHE_DISCARD_SECONDS:
                        item_count = entry.get("item_count")
                        data[steam_id] = {"item_count": item_count}
                        changed = True

                if changed:
                    with open(INVENTORY_FILE, "w", encoding="utf-8") as wf:
                        json.dump(data, wf, indent=2)
                    logger.info("Discarded stale inventory cache payloads older than %ss (kept item_count only)", CACHE_DISCARD_SECONDS)

                logger.debug("Loaded %d inventory cache entries from %s", len(data) if isinstance(data, dict) else 0, INVENTORY_FILE)
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            logger.debug("Inventory cache missing/invalid, using empty cache: %s", INVENTORY_FILE)
            return {}


def write_cache(data: dict) -> None:
    with _CACHE_LOCK:
        with open(INVENTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.debug("Wrote %d inventory cache entries to %s", len(data) if isinstance(data, dict) else 0, INVENTORY_FILE)


def read_unchanged_inventory() -> dict:
    with _CACHE_LOCK:
        try:
            with open(UNCHANGED_INVENTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return {}


def write_unchanged_inventory(data: dict) -> None:
    with _CACHE_LOCK:
        with open(UNCHANGED_INVENTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


def mark_inventory_unchanged(steam_id: str, item_count: int) -> None:
    unchanged = read_unchanged_inventory()
    unchanged[steam_id] = {
        "item_count": item_count,
        "last_checked": int(time.time()),
    }
    write_unchanged_inventory(unchanged)


def remove_unchanged_inventory(steam_id: str) -> bool:
    unchanged = read_unchanged_inventory()
    if steam_id not in unchanged:
        return False
    unchanged.pop(steam_id, None)
    write_unchanged_inventory(unchanged)
    return True


def get_unchanged_inventory_ids() -> list[str]:
    unchanged = read_unchanged_inventory()
    return [str(x) for x in unchanged.keys()]


def update_cache_entry(steam_id: str, inventory_text: str) -> None:
    count = extract_item_count_from_summary(inventory_text)
    with _CACHE_LOCK:
        cache = read_cache()
        cache[steam_id] = {
            "inventory": inventory_text,
            "last_updated": int(time.time()),
            "item_count": count,
        }
        write_cache(cache)
    logger.debug(
        "Updated inventory cache for steam_id=%s item_count=%s",
        steam_id,
        count,
    )


def extract_item_count_from_summary(inventory_text: str) -> Optional[int]:
    if not inventory_text or not isinstance(inventory_text, str):
        return None

    if not inventory_text.startswith("Items:\n"):
        return 0 if inventory_text.strip() == "No items found" else None

    total = 0
    lines = inventory_text.splitlines()[1:]
    for line in lines:
        if not line.strip():
            continue
        qty = 1
        marker_idx = line.rfind(" - ")
        name_part = line if marker_idx < 0 else line[:marker_idx]
        qty_idx = name_part.rfind(" x")
        if qty_idx >= 0:
            qty_raw = name_part[qty_idx + 2:].strip()
            if qty_raw.isdigit():
                qty = int(qty_raw)
        total += qty

    return total


def fetch_inventory_item_count(steam_id: str, appid: int = 730, contextid: int = 2) -> Optional[int]:
    if is_stop_requested():
        logger.info("Stop requested; skipping inventory count poll for %s", steam_id)
        return None
    url = f"https://steamcommunity.com/inventory/{steam_id}/{appid}/{contextid}"
    logger.debug("Polling inventory count for steam_id=%s appid=%s contextid=%s", steam_id, appid, contextid)

    for attempt in range(INVENTORY_MAX_RETRIES):
        if is_stop_requested():
            logger.info("Stop requested; aborting inventory count poll for %s", steam_id)
            return None
        logger.debug(
            "Inventory count poll attempt %d/%d for steam_id=%s",
            attempt + 1,
            INVENTORY_MAX_RETRIES,
            steam_id,
        )
        try:
            r = session.get(url, params={"count": INVENTORY_RESPONSE_COUNT_LIMIT}, timeout=15)
        except requests.exceptions.RequestException:
            logger.exception("HTTP/request error while polling inventory count for %s (attempt=%d)", steam_id, attempt + 1)
            time.sleep(1)
            continue

        if r.status_code == 429:
            logger.warning(
                "Received 429 while polling count for %s (attempt=%d/%d). Sleeping %.1fs before retry",
                steam_id,
                attempt + 1,
                INVENTORY_MAX_RETRIES,
                STEAM_429_DELAY_SECONDS,
            )
            time.sleep(STEAM_429_DELAY_SECONDS)
            continue

        if r.status_code in (401, 403):
            logger.warning("Inventory count unauthorized/forbidden for %s (status=%d)", steam_id, r.status_code)
            return None

        if r.status_code != 200:
            logger.warning("Inventory count request for %s returned status %s", steam_id, r.status_code)
            time.sleep(1)
            continue

        try:
            data = r.json()
        except ValueError:
            logger.warning("Inventory count JSON decode failed for %s", steam_id)
            return None

        if not isinstance(data, dict):
            return None

        if data.get("success") != 1:
            return None

        assets = data.get("assets") or []
        if not isinstance(assets, list):
            return None

        count = 0
        for asset in assets:
            amount_raw = asset.get("amount", "1")
            try:
                amount = int(str(amount_raw))
            except ValueError:
                amount = 1
            if amount < 1:
                amount = 1
            count += amount

        logger.debug("Inventory count poll success for steam_id=%s count=%d", steam_id, count)
        return count

    logger.warning("Inventory count polling failed after %d attempts for steam_id=%s", INVENTORY_MAX_RETRIES, steam_id)
    return None


def wait_for_inventory_count_change(
    steam_id: str,
    previous_count: int,
    appid: int = 730,
    contextid: int = 2,
) -> Optional[int]:
    logger.info(
        "Start monitoring inventory count for steam_id=%s previous_count=%d interval=%.1fs max_attempts=%s",
        steam_id,
        previous_count,
        INVENTORY_COUNT_POLL_INTERVAL,
        "infinite" if INVENTORY_COUNT_POLL_MAX_ATTEMPTS == 0 else INVENTORY_COUNT_POLL_MAX_ATTEMPTS,
    )
    attempts = 0
    while True:
        if is_stop_requested():
            logger.info("Stop requested; aborting inventory monitor for %s", steam_id)
            return None
        current_count = fetch_inventory_item_count(steam_id, appid=appid, contextid=contextid)
        if current_count is not None and current_count != previous_count:
            logger.info(
                "Inventory count changed for %s: %d -> %d",
                steam_id,
                previous_count,
                current_count,
            )
            return current_count

        if current_count is not None:
            logger.debug(
                "Inventory count still unchanged for %s (attempt=%d current=%d expected_change_from=%d)",
                steam_id,
                attempts + 1,
                current_count,
                previous_count,
            )
        else:
            logger.debug(
                "Inventory count poll returned no usable value for %s (attempt=%d)",
                steam_id,
                attempts + 1,
            )

        attempts += 1
        if INVENTORY_COUNT_POLL_MAX_ATTEMPTS > 0 and attempts >= INVENTORY_COUNT_POLL_MAX_ATTEMPTS:
            break

        time.sleep(INVENTORY_COUNT_POLL_INTERVAL)

    logger.debug(
        "Inventory count unchanged for %s after %d poll attempts (count=%d)",
        steam_id,
        attempts,
        previous_count,
    )
    return None


def remove_cache_entry(steam_id: str) -> bool:
    with _CACHE_LOCK:
        cache = read_cache()
        if steam_id not in cache:
            return False
        cache.pop(steam_id, None)
        write_cache(cache)
    logger.info("Removed inventory cache entry for steam_id=%s", steam_id)
    return True


def needs_refresh(entry: Optional[dict]) -> bool:
    if not entry or "last_updated" not in entry:
        logger.debug("Inventory cache refresh required: missing entry or timestamp")
        return True
    age = time.time() - entry["last_updated"]
    refresh = age >= INVENTORY_UPDATE_INTERVAL
    logger.debug("Inventory cache age=%.1fs refresh=%s threshold=%ss", age, refresh, INVENTORY_UPDATE_INTERVAL)
    return refresh


def fetch_inventory(steam_id: str, appid: int = 730, contextid: int = 2) -> str:
    if is_stop_requested():
        logger.info("Stop requested; skipping inventory fetch for %s", steam_id)
        return "Inventory fetch stopped"
    url = f"https://steamcommunity.com/inventory/{steam_id}/{appid}/{contextid}"
    logger.debug("Fetching inventory for steam_id=%s appid=%s contextid=%s", steam_id, appid, contextid)
    while True:
        if is_stop_requested():
            logger.info("Stop requested; aborting inventory fetch loop for %s", steam_id)
            return "Inventory fetch stopped"
        try:
            r = session.get(url, params={"count": INVENTORY_RESPONSE_COUNT_LIMIT}, timeout=15)
        except requests.exceptions.RequestException:
            logger.exception("HTTP/request error while fetching inventory for %s", steam_id)
            time.sleep(1)
            continue

        if r.status_code == 429:
            logger.warning(
                "Received 429 for inventory %s. Sleeping %.1fs before retry",
                steam_id,
                STEAM_429_DELAY_SECONDS,
            )
            time.sleep(STEAM_429_DELAY_SECONDS)
            continue

        if r.status_code in (401, 403):
            logger.warning("Inventory unauthorized/forbidden for %s (status=%d). Skipping retries.", steam_id, r.status_code)
            return "Inventory private or unauthorized"

        if r.status_code != 200:
            logger.warning("Inventory request for %s returned status %s", steam_id, r.status_code)
            time.sleep(1)
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
        market_hashes = {
            item.get("market_hash_name", item.get("market_name", "Unknown"))
            for item in descriptions
        }
        price_by_hash = {}
        for market_hash in market_hashes:
            if is_stop_requested():
                logger.info("Stop requested; aborting price aggregation for %s", steam_id)
                return "Inventory fetch stopped"
            try:
                price_by_hash[market_hash] = get_market_price_from_cache(market_hash)
            except Exception:
                logger.exception("Price lookup failed for %s", market_hash)
                price_by_hash[market_hash] = "Request Restricted"

        logger.debug(
            "Resolved %d/%d inventory item prices for steam_id=%s",
            len(price_by_hash),
            len(market_hashes),
            steam_id,
        )

        for item in descriptions:
            name = item.get("market_name", "Unknown")
            market_hash = item.get("market_hash_name", name)
            classid = str(item.get("classid"))
            instanceid = str(item.get("instanceid", "0"))
            count = asset_counts.get((classid, instanceid), 1)

            price = price_by_hash.get(market_hash, "Request Restricted")

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
            lines.append(f"{v['name']}{qty_str} - {v['price']}")

        logger.info("Built inventory summary for steam_id=%s with %d unique market items", steam_id, len(market_totals))
        return "Items:\n" + "\n".join(lines)


def _get_inventory_summary_internal(steam_id: str, appid: int = 730, contextid: int = 2, use_cache: bool = False) -> tuple[str, bool]:
    cache = read_cache()
    entry = cache.get(steam_id)
    logger.debug(
        "Inventory summary requested for steam_id=%s use_cache=%s cache_entry_exists=%s",
        steam_id,
        use_cache,
        bool(entry),
    )
    if use_cache and entry:
        cached_inventory = entry.get("inventory")

        if not needs_refresh(entry):
            cached_count = entry.get("item_count")
            if isinstance(cached_count, int):
                mark_inventory_unchanged(steam_id, cached_count)
            logger.info("Returning cached inventory for %s", steam_id)
            return cached_inventory, False

        remove_unchanged_inventory(steam_id)
        logger.info("Inventory cache for %s reached refresh threshold; refreshing from Steam", steam_id)
    elif use_cache:
        logger.info("No cache entry for %s. Performing first-time inventory fetch.", steam_id)

    logger.debug("Refreshing inventory from Steam for %s (use_cache=%s)", steam_id, use_cache)
    inventory = fetch_inventory(steam_id, appid=appid, contextid=contextid)
    if inventory and isinstance(inventory, str):
        logger.info("Returning inventory from Steam for %s", steam_id)
        if inventory in TRANSIENT_INVENTORY_STATES:
            logger.debug("Skipping cache for transient inventory state for %s: %s", steam_id, inventory)
        else:
            update_cache_entry(steam_id, inventory)
    return inventory, False


def get_inventory_summary(steam_id: str, appid: int = 730, contextid: int = 2, use_cache: bool = False) -> str:
    inventory, _ = _get_inventory_summary_internal(steam_id, appid=appid, contextid=contextid, use_cache=use_cache)
    return inventory


def get_inventory_summary_with_status(steam_id: str, appid: int = 730, contextid: int = 2, use_cache: bool = False) -> tuple[str, bool]:
    return _get_inventory_summary_internal(steam_id, appid=appid, contextid=contextid, use_cache=use_cache)


def force_update_all_inventories() -> None:
    cache = read_cache()
    for steam_id in list(cache.keys()):
        inv = fetch_inventory(steam_id)
        cache[steam_id] = {
            "inventory": inv,
            "last_updated": int(time.time()),
            "item_count": extract_item_count_from_summary(inv),
        }
    write_cache(cache)

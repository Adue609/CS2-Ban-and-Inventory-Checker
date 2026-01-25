import logging
import requests
import time
import json

from utils.logger import get_logger
from utils.config import Update_Interval

# Logger
logger = get_logger("PriceChecker")


PRICE_FILE = "cs_prices.json"
UPDATE_INTERVAL = Update_Interval * 6 # 6 times the configured interval

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://steamcommunity.com/market/",
}

session = requests.Session()
session.headers.update(HEADERS)


def read_cache():
    try:
        with open(PRICE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def write_cache(data):
    with open(PRICE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def update_cache_entry(item, price):
    cache = read_cache()
    cache[item] = {
        "price": price,
        "last_updated": int(time.time())
    }
    write_cache(cache)

def steam_price(item):
    """Query Steam priceoverview using requests params so names are URL-encoded."""
    url = "https://steamcommunity.com/market/priceoverview/"
    params = {
        "currency": 1,
        "appid": 730,
        "market_hash_name": item
    }
    logger.debug("Priceoverview URL: %s params=%r", url, params)
    while True:
        try:
            logger.debug("Querying market for item: %s", item)
            r = session.get(url, params=params, timeout=30)
            logger.debug("Market request URL: %s", r.url)
        except requests.exceptions.RequestException:
            logger.exception("Error fetching market data for %s; retry later", item)
            time.sleep(10)
            return "Request Restricted"

        if r.status_code != 200:
            logger.warning("Blocked HTTP %s for item=%s; sleeping 30s then retrying", r.status_code, item)
            time.sleep(30)
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


def needs_refresh(entry):
    if not entry or "last_updated" not in entry:
        return True
    return (time.time() - entry["last_updated"]) >= UPDATE_INTERVAL

def get_market_price_from_cache(market_hash_name):
    cache = read_cache()
    entry = cache.get(market_hash_name)

    # force refresh if 7 days passed
    if needs_refresh(entry):
        price = steam_price(market_hash_name)
        update_cache_entry(market_hash_name, price)
        return price

    # valid cached price
    cached_price = entry.get("price")
    if cached_price and cached_price.lower() not in ("n/a", "not listed"):
        logger.info("Found price for %s -> %s from cache", market_hash_name, cached_price)
        return cached_price

    # fallback fetch
    price = steam_price(market_hash_name)
    update_cache_entry(market_hash_name, price)
    return price

def force_update_all_prices():
    cache = read_cache()
    for item in cache.keys():
        price = steam_price(item)
        cache[item] = {
            "price": price,
            "last_updated": int(time.time())
        }
    write_cache(cache)
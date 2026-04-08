import json
import os
from typing import List

from utils.logger import get_logger

logger = get_logger("config")

CONFIG_FILE = os.environ.get("CONFIG_FILE", "config.json")


def _load_config_file(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("Config file not found: %s. Creating template.", path)
        default = {
            "steam_api_key": "",
            "bot_token": "",
            "channel_ids": [],
            "Update_Interval": 3600
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=2)
        return default
    except json.JSONDecodeError:
        logger.exception("Invalid JSON in config file: %s", path)
        raise SystemExit(1)


_cfg = _load_config_file(CONFIG_FILE)


def _parse_positive_int(raw_value, default: int, field_name: str) -> int:
    try:
        value = int(raw_value)
        if value <= 0:
            raise ValueError
        return value
    except (TypeError, ValueError):
        logger.warning("Invalid %s in %s. Using default=%d", field_name, CONFIG_FILE, default)
        return default


def _parse_channel_ids(raw_value) -> List[int]:
    if not isinstance(raw_value, list):
        logger.warning("Invalid channel_ids in %s. Expected list.", CONFIG_FILE)
        return []

    parsed: List[int] = []
    for idx, item in enumerate(raw_value):
        try:
            parsed.append(int(item))
        except (TypeError, ValueError):
            logger.warning("Ignoring invalid channel_ids[%d]=%r in %s", idx, item, CONFIG_FILE)
    return parsed

STEAM_API_KEY: str = (_cfg.get("steam_api_key") or "").strip()
BOT_TOKEN: str = (_cfg.get("bot_token") or "").strip()
CHANNEL_IDS: List[int] = _parse_channel_ids(_cfg.get("channel_ids"))
UPDATE_INTERVAL: int = _parse_positive_int(_cfg.get("Update_Interval", 3600), 3600, "Update_Interval")
# Backward-compatible alias for existing imports
Update_Interval: int = UPDATE_INTERVAL

if not STEAM_API_KEY:
    logger.error("Missing steam_api_key in %s", CONFIG_FILE)
    raise SystemExit(1)

if not BOT_TOKEN:
    logger.error("Missing bot_token in %s", CONFIG_FILE)
    raise SystemExit(1)
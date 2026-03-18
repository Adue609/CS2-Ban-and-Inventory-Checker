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

STEAM_API_KEY: str = (_cfg.get("steam_api_key") or "").strip()
BOT_TOKEN: str = (_cfg.get("bot_token") or "").strip()
CHANNEL_IDS: List[int] = [int(x) for x in (_cfg.get("channel_ids") or [])]
Update_Interval: int = int(_cfg.get("Update_Interval", 3600))

if not STEAM_API_KEY:
    logger.error("Missing steam_api_key in config.json")
    raise SystemExit(1)

if not BOT_TOKEN:
    logger.error("Missing bot_token in config.json")
    raise SystemExit(1)
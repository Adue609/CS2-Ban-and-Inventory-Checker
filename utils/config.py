import json
import os
from typing import List, Any

from utils.logger import get_logger

logger = get_logger("config")

CONFIG_FILE = os.environ.get("CONFIG_FILE", "config.json")


# def _load_config_file(path: str) -> dict:
#     try:
#         with open(path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#             logger.debug("Loaded configuration file %s", path)
#             return data
#     except FileNotFoundError:
#         logger.warning("Config file %s not found; creating default template", path)
#         default = {
#             "steam_api_key": "",
#             "bot_token": "",
#             "channel_ids": [],
#             "Update_Interval": 1 * 1 * 60 * 60  # 1 days (epoch seconds)
#         }
#         try:
#             with open(path, "w", encoding="utf-8") as f:
#                 json.dump(default, f, indent=2, ensure_ascii=False)
#             logger.info("Wrote default config template to %s; please fill in values", path)
#         except Exception:
#             logger.exception("Failed to write default config template to %s", path)
#         return default
#     except json.JSONDecodeError:
#         logger.exception("Config file %s is not valid JSON", path)
#         raise SystemExit(1)
#     except Exception:
#         logger.exception("Unexpected error while loading config file %s", path)
#         raise SystemExit(1)


# _cfg = _load_config_file(CONFIG_FILE)

# # Steam API key
# STEAM_API_KEY: str = _cfg.get("steam_api_key") or os.environ.get("STEAM_API_KEY")
# # Discord bot token
# BOT_TOKEN: str = _cfg.get("bot_token") or os.environ.get("DISCORD_BOT_TOKEN")

# # Channel IDs: prefer config file, fall back to env/CSV or JSON in env
# _channel_ids: Any = _cfg.get("channel_ids") or os.environ.get("CHANNEL_IDS")
# CHANNEL_IDS: List[int] = []
# if _channel_ids:
#     if isinstance(_channel_ids, list):
#         CHANNEL_IDS = [int(x) for x in _channel_ids]
#     else:
#         # try parse JSON list first, then CSV
#         try:
#             parsed = json.loads(_channel_ids)
#             if isinstance(parsed, list):
#                 CHANNEL_IDS = [int(x) for x in parsed]
#         except Exception:
#             try:
#                 CHANNEL_IDS = [int(x.strip()) for x in str(_channel_ids).split(",") if x.strip()]
#             except Exception:
#                 logger.exception("Failed to parse CHANNEL_IDS from env/config: %r", _channel_ids)

Update_Interval: int = int(_cfg.get("Update_Interval", 3600))

# Basic validation
if not STEAM_API_KEY:
    try:
        os.getenv("steam_api_key")
    except:
        logger.error("Missing Steam API key. Set 'steam_api_key' in %s or STEAM_API_KEY env var", CONFIG_FILE)
        raise SystemExit(1)

if not BOT_TOKEN:
    try:
        os.getenv("bot_token")
    except:
        logger.error("Missing Discord bot token. Set 'bot_token' in %s or DISCORD_BOT_TOKEN env var", CONFIG_FILE)
        raise SystemExit(1)

if not CHANNEL_IDS:
    try:
        CHANNEL_IDS = [int(x) for x in os.getenv("channel_ids", "").split(",") if x]
    except:
        logger.warning("No channel IDs configured (CONFIG_FILE=%s). CHANNEL_IDS is empty.", CONFIG_FILE)
        pass


#logger.info("Configuration loaded: Update_Interval=%d seconds, CHANNEL_IDS=%r", Update_Interval, CHANNEL_IDS)
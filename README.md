# CS2 Ban and Inventory Checker

A Discord bot that checks Steam account ban status (VAC/community/game bans), summarizes CS2 inventory values, and posts grouped results as embeds.

## Features

- Reads Steam profile links and optional group tags.
- Resolves custom Steam vanity URLs to SteamID64.
- Checks ban status through Steam Web API:
  - `VACBanned`
  - `CommunityBanned`
  - `NumberOfGameBans`
- Fetches inventory summaries with cache support.
- Retrieves market prices with cache support.
- Sends grouped Discord embeds with chunking to respect Discord field limits.
- Supports runtime input collection and JSON input fallback.

## Project Structure

- `BanChecker.py` — bot entrypoint and main workflow.
- `utils/config.py` — config loading and validation.
- `utils/Inventory.py` — inventory fetch/cache logic.
- `utils/PriceChecker.py` — market price fetch/cache logic.
- `utils/logger.py` — logging setup.
- `input_messages.json` — persisted input list fallback.
- `build_exe.bat` — one-click EXE build script.

## Requirements

Install with:

    pip install -r requirements.txt

Current `requirements.txt`:

- `discord.py==2.3.2`
- `requests==2.31.0`
- `pyinstaller==6.16.0`
- `audioop-lts>=0.2.1; python_version >= "3.13"`

## Configuration

Create `config.json` in the project root:

```json
{
  "steam_api_key": "YOUR_STEAM_API_KEY",
  "bot_token": "YOUR_DISCORD_BOT_TOKEN",
  "channel_ids": ["YOUR_DISCORD_CHANNEL_ID"],
  "Update_Interval": 3600
}
```

### Fields

- `steam_api_key` — Steam Web API key.
- `bot_token` — Discord bot token.
- `channel_ids` — channel IDs to process and post results into.
- `Update_Interval` — cache refresh interval in seconds (used by utility modules).

## Input Sources

The bot supports two sources:

1. **Runtime input** (interactive console), multiple lines.
2. **JSON fallback** from `input_messages.json` when runtime input is not provided in time.

### `input_messages.json` format

```json
[
  "https://steamcommunity.com/profiles/76561198000000000/GROUPA",
  "https://steamcommunity.com/id/somecustomid/GROUPB"
]
```

Each item should be a Steam profile link in the same format expected from Discord chat parsing.

## Run (Python)

To start the bot, run:

    python BanChecker.py

## Build EXE (one click)

Double-click:

- `build_exe.bat`

or run:

    build_exe.bat

This script:

- Reuses active/local virtual environment (`%VIRTUAL_ENV%`, `.venv`, or `env`).
- Installs dependencies from `requirements.txt`.
- Builds `dist/CS2BanChecker.exe` with PyInstaller.
- Includes helper modules under `utils`.

Optional:

    build_exe.bat --freeze

Regenerates `requirements.txt` from the same active environment before build.

## Troubleshooting

### `TypeError: expected token to be a str, received NoneType`

- `bot_token` is missing/empty in `config.json`.

### Steam API `403 Forbidden` on ban check

- Verify `steam_api_key` has no trailing spaces or extra text.
- Confirm key is valid and active.

### Inventory `401/403`

- Inventory endpoint can reject requests for private/restricted profiles.
- Current logic skips retry loops for `401/403` and continues.

### No results posted

- Ensure `channel_ids` are correct and bot has permission to read history/send embeds.
- Ensure input contains valid Steam links.

## Notes

- Cache files are generated at runtime (`inventory_cache.json`, `cs_prices.json`).
- Do not commit secrets (`config.json`, bot token, API keys) to source control.

## Runtime Behavior

- `check_steam` runs every **90 minutes**.
- Runtime input is accepted first (interactive console).
- If no runtime input is provided in time, the bot falls back to `input_messages.json`.
- Input entries can include optional group suffixes in URL form:
  - `https://steamcommunity.com/profiles/<steamid>/<GROUP>`
  - `https://steamcommunity.com/id/<vanity>/<GROUP>`

## Discord Setup

Enable these in Discord Developer Portal:

- **MESSAGE CONTENT INTENT** (required)
- Bot permissions in target channel:
  - Read Message History
  - Read Messages/View Channels
  - Send Messages
  - Embed Links
  - Manage Messages (for cleanup of previous bot messages)

## First Run Notes

- If `config.json` does not exist, the app creates a template file.
- You must fill valid values in `config.json` before the bot can start.

## EXE Notes

- JSON/cache files (`config.json`, `inventory_cache.json`, `cs_prices.json`, `input_messages.json`) are runtime files.
- They are expected/created in the same directory as the executable (or working directory).

## Error Handling Notes

- Steam inventory `401/403` responses are treated as private/unauthorized and retries are skipped.
- Ban API `403` usually indicates an invalid or malformed Steam API key.

## Security

- Do not commit `config.json` with real keys/tokens.
- If a Discord token was ever exposed, regenerate it immediately in the Discord Developer Portal.

## License

[MIT](https://choosealicense.com/licenses/mit/)


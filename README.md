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

The app uses `config.json` in the project root.

Example:

```json
{
  "steam_api_key": "YOUR_STEAM_API_KEY",
  "bot_token": "YOUR_DISCORD_BOT_TOKEN",
  "channel_ids": [1458480444579254272],
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

## Screenshots

![App Screenshot](https://via.placeholder.com/468x300?text=App+Screenshot+Here)

## Documentation

[Documentation](https://linktodocumentation)

## FAQ

#### Question 1

Answer 1

#### Question 2

Answer 2

## Roadmap

- Add a compiled version of the script with CLI terminal.
- Add GUI to the script.
- Add support for different apps like Telegram and WhatsApp.

## 🚀 About Me

I'm a full stack developer...

## License

[MIT](https://choosealicense.com/licenses/mit/)


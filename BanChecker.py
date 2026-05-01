import discord
from discord.ext import commands, tasks
import re
import requests
import time
import asyncio
import random
import json
import tkinter as tk
import threading

from utils.logger import get_logger
from utils.Inventory import get_inventory_summary_with_status, remove_cache_entry, get_unchanged_inventory_ids, remove_unchanged_inventory, set_stop_requested, is_stop_requested
from utils.config import STEAM_API_KEY, BOT_TOKEN, CHANNEL_IDS
from utils.gui import create_gui_window, setup_gui_logging, reset_inventory_progress, mark_inventory_processed
from utils.PriceChecker import force_update_all_prices

logger = get_logger("BanChecker")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

STEAM_SESSION = requests.Session()

STEAM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://steamcommunity.com/",
    "Connection": "keep-alive",
}
STEAM_SESSION.headers.update(STEAM_HEADERS)

BAN_API_MAX_RETRIES = 5
BAN_API_BACKOFF_BASE = 1.5
BAN_API_BACKOFF_CAP = 6.0
STEAM_429_DELAY_SECONDS = 30

# @tasks.loop(seconds=UPDATE_INTERVAL)
# async def refresh_inventories_task():
#     await asyncio.to_thread(force_update_all_inventories)

EMBED_FIELD_VALUE_LIMIT = 1024
EMBED_FIELD_NAME_LIMIT = 256
EMBED_TOTAL_CHAR_LIMIT = 6000
EMBED_MAX_FIELDS = 25
MAX_CONCURRENT_PROFILE_CHECKS = 4
CHECK_LOOP_INTERVAL_SECONDS = 60 * 60

_runtime_input_bootstrapped = False
_runtime_input_messages_cache = []
_continuous_worker_started = False
_bot_paused = False
_bot_running = False
_bot_started_by_gui = False
_gui_window: tk.Tk = None
_gui_ready = False
_bot_ready = asyncio.Event()  # Signal when bot event loop is ready
_active_tasks = set()  # Track active profile processing tasks

@bot.event
async def on_ready():
    global _continuous_worker_started, _bot_started_by_gui, _gui_ready, _bot_ready
    logger.info("Bot ready. Logged in as %s", bot.user)
    
    # Signal that bot event loop is ready
    if not _bot_ready.is_set():
        _bot_ready.set()
    
    # Only auto-start if GUI isn't managing the bot
    if not _continuous_worker_started and not _gui_ready:
        logger.info("GUI not active, auto-starting check loop")
        check_steam.start()
        _continuous_worker_started = True
        _bot_running = True
        logger.info(
            "Started continuous check loop interval=%ss",
            CHECK_LOOP_INTERVAL_SECONDS,
        )
    elif not _continuous_worker_started and _gui_ready:
        logger.info("GUI is active, waiting for GUI commands to start check loop")
        _continuous_worker_started = True

def check_steam_profile(steam_id):
    if is_stop_requested():
        logger.info("Stop requested; skipping ban check for SteamID=%s", steam_id)
        return None
    api_key = (STEAM_API_KEY or "").strip()
    url = "https://api.steampowered.com/ISteamUser/GetPlayerBans/v1/"
    params = {"key": api_key, "steamids": steam_id}

    for attempt in range(BAN_API_MAX_RETRIES):
        if is_stop_requested():
            logger.info("Stop requested; aborting ban check for SteamID=%s", steam_id)
            return None
        try:
            logger.debug("Checking bans for SteamID=%s via %s params=%s", steam_id, url, {"steamids": steam_id})
            response = STEAM_SESSION.get(url, params=params, timeout=10)
        except requests.exceptions.RequestException:
            wait_s = min(BAN_API_BACKOFF_CAP, BAN_API_BACKOFF_BASE * (2 ** attempt) + random.uniform(0, 1))
            logger.warning(
                "Request error checking bans for SteamID=%s (attempt=%d/%d). Retrying in %.1fs",
                steam_id,
                attempt + 1,
                BAN_API_MAX_RETRIES,
                wait_s,
            )
            time.sleep(wait_s)
            continue

        if response.status_code == 200:
            try:
                data = response.json()
            except ValueError:
                logger.warning("Invalid JSON in ban response for SteamID=%s", steam_id)
                return None

            if data.get("players"):
                return data["players"][0]
            return None

        if response.status_code == 429:
            logger.warning(
                "Steam ban API rate-limited for SteamID=%s (attempt=%d/%d). Sleeping %ss",
                steam_id,
                attempt + 1,
                BAN_API_MAX_RETRIES,
                STEAM_429_DELAY_SECONDS,
            )
            time.sleep(STEAM_429_DELAY_SECONDS)
            continue

        if response.status_code in (420, 500, 502, 503, 504):
            retry_after = response.headers.get("Retry-After")
            try:
                retry_after_s = float(retry_after) if retry_after is not None else 0.0
            except ValueError:
                retry_after_s = 0.0

            wait_s = min(
                BAN_API_BACKOFF_CAP,
                max(retry_after_s, BAN_API_BACKOFF_BASE * (2 ** attempt) + random.uniform(0, 1)),
            )
            logger.warning(
                "Steam ban API throttled/unavailable for SteamID=%s (status=%d, attempt=%d/%d). Retrying in %.1fs",
                steam_id,
                response.status_code,
                attempt + 1,
                BAN_API_MAX_RETRIES,
                wait_s,
            )
            time.sleep(wait_s)
            continue

        logger.warning(
            "Non-retryable ban API status for SteamID=%s: status=%d",
            steam_id,
            response.status_code,
        )
        return None

    logger.warning("Exhausted ban API retries for SteamID=%s", steam_id)
    return None

def normalize_steam_profile_link(link):
    if is_stop_requested():
        logger.info("Stop requested; skipping profile normalization for link=%s", link)
        return None, None
    specific_profile_link = 'https://steamcommunity.com/profiles/76561198063578000/'
    specific_profile_id = '71111111111111111'
    specific_custom_id = 'MehdiCRisH'

    if link in [specific_profile_link, f'https://steamcommunity.com/id/{specific_custom_id}/']:
        logger.debug("Matched hardcoded profile mapping for link=%s", link)
        return specific_profile_id, specific_custom_id
    else:
        match = re.match(r'https?://steamcommunity\.com/(profiles|id)/(\w+)/?', link)
        if match:
            profile_type, profile_id = match.groups()
            if profile_type == 'id':
                try:
                    if is_stop_requested():
                        logger.info("Stop requested; aborting vanity resolve for %s", profile_id)
                        return None, None
                    vanity_url = f"http://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/?key={STEAM_API_KEY}&vanityurl={profile_id}"
                    logger.debug("Resolving vanity URL for %s via %s", profile_id, vanity_url)
                    response = requests.get(vanity_url, timeout=10)
                    if response.status_code == 429:
                        logger.warning("Vanity resolve rate-limited for %s. Sleeping %ss", profile_id, STEAM_429_DELAY_SECONDS)
                        time.sleep(STEAM_429_DELAY_SECONDS)
                        return None, None
                    response.raise_for_status()
                    data = response.json()
                    if data.get('response', {}).get('success') == 1:
                        logger.debug("Resolved vanity id=%s to steamid=%s", profile_id, data['response']['steamid'])
                        return data['response']['steamid'], profile_id
                except Exception:
                    logger.exception("Failed to resolve vanity URL for %s", profile_id)
            else:
                logger.debug("Direct numeric profile id detected: %s", profile_id)
                return profile_id, profile_id
    logger.debug("Could not normalize link: %s", link)
    return None, None

def chunk_list(data_list, chunk_size=EMBED_FIELD_VALUE_LIMIT):
    chunks = []
    current_chunk = []
    current_length = 0
    current_count = 0

    def flush_current():
        nonlocal current_chunk, current_length, current_count
        if current_chunk:
            chunks.append(('\n'.join(current_chunk), current_count))
            current_chunk = []
            current_length = 0
            current_count = 0

    for item in data_list:
        item_str = str(item)
        item_length = len(item_str) + 1

        if item_length > chunk_size:
            lines = item_str.splitlines() or [item_str]
            sub_buf = []
            sub_len = 0
            sub_count = 0
            for line in lines:
                line_len = len(line) + 1
                if sub_len + line_len > chunk_size:
                    if sub_buf:
                        flush_current() if current_chunk else None
                        chunks.append(('\n'.join(sub_buf), sub_count))
                        sub_buf = []
                        sub_len = 0
                        sub_count = 0
                    if line_len > chunk_size:
                        start = 0
                        while start < len(line):
                            part = line[start:start + chunk_size - 1]
                            chunks.append((part, 1))
                            start += len(part)
                    else:
                        sub_buf = [line]
                        sub_len = line_len
                        sub_count = 1
                else:
                    sub_buf.append(line)
                    sub_len += line_len
                    sub_count += 1
            if sub_buf:
                chunks.append(('\n'.join(sub_buf), sub_count))
            continue

        if current_length + item_length > chunk_size:
            flush_current()

        current_chunk.append(item_str)
        current_length += item_length
        current_count += 1

    if current_chunk:
        flush_current()

    return chunks

async def send_grouped_embeds(channel, title, grouped_accounts, total):
    for group, accounts in grouped_accounts.items():
        await send_embed(channel, f"{title} - {group}", accounts, total)

async def send_embed(channel, title, accounts, total_accounts_found):
    if not accounts:
        logger.debug("No accounts to send for embed title=%s", title)
        return

    chunks = chunk_list(accounts)
    embed = discord.Embed(title=title, color=0x1e90ff)
    fields_in_current = 0
    part_index = 1
    printed_in_current = 0

    def estimate_embed_size(e: discord.Embed) -> int:
        size = 0
        size += len(e.title or "")
        size += len(e.description or "")
        if e.footer and e.footer.text:
            size += len(e.footer.text)
        if e.author and e.author.name:
            size += len(e.author.name)
        for f in e.fields:
            size += len(f.name or "") + len(f.value or "")
        return size

    async def send_and_reset(current_embed, printed_so_far):
        try:
            # Use footer instead of summary field (safer for 6000-char limit)
            current_embed.set_footer(
                text=f"Printed in this embed: {printed_so_far} / Found: {total_accounts_found}"
            )
            await channel.send(embed=current_embed)
            logger.info(
                "Sent embed '%s' to channel %s (printed=%d, found=%d)",
                title,
                channel.id if channel else "unknown",
                printed_so_far,
                total_accounts_found
            )
        except Exception:
            logger.exception(
                "Failed to send embed '%s' to channel %s",
                title,
                channel.id if channel else "unknown"
            )

    for chunk_str, count in chunks:
        value = chunk_str
        field_name = f"{title} (Part {part_index})"

        if len(field_name) > EMBED_FIELD_NAME_LIMIT:
            field_name = field_name[:EMBED_FIELD_NAME_LIMIT - 3] + "..."
        if len(value) > EMBED_FIELD_VALUE_LIMIT:
            value = value[:EMBED_FIELD_VALUE_LIMIT - 3] + "..."

        # Field count hard limit
        if fields_in_current >= EMBED_MAX_FIELDS:
            await send_and_reset(embed, printed_in_current)
            embed = discord.Embed(title=title, color=0x1e90ff)
            fields_in_current = 0
            printed_in_current = 0

        # Total char hard limit (reserve space for footer text)
        footer_reserved = 80
        projected = estimate_embed_size(embed) + len(field_name) + len(value) + footer_reserved
        if projected > EMBED_TOTAL_CHAR_LIMIT and fields_in_current > 0:
            await send_and_reset(embed, printed_in_current)
            embed = discord.Embed(title=title, color=0x1e90ff)
            fields_in_current = 0
            printed_in_current = 0

        embed.add_field(name=field_name, value=value, inline=False)
        fields_in_current += 1
        printed_in_current += count
        part_index += 1

    if fields_in_current > 0:
        await send_and_reset(embed, printed_in_current)
    else:
        logger.debug("No fields were added to embed for title=%s even though accounts exist", title)

async def send_totals_embed(channel, group_totals):
    if not group_totals:
        logger.debug("No group totals to send for channel %s", channel.id if channel else "unknown")
        return

    embed = discord.Embed(title="Group Inventory Totals", color=0x1e90ff)
    total_all = 0.0
    for group, total in group_totals.items():
        embed.add_field(name=group, value=f"${total:.2f}", inline=True)
        total_all += total

    embed.add_field(name="Grand Total", value=f"${total_all:.2f}", inline=False)
    try:
        await channel.send(embed=embed)
        logger.info("Sent totals embed to channel %s: %s", channel.id if channel else "unknown", {g: f"${t:.2f}" for g, t in group_totals.items()})
    except Exception:
        logger.exception("Failed to send totals embed to channel %s", channel.id if channel else "unknown")

def add_to_group(container, group, value):
    if group not in container:
        container[group] = []
    container[group].append(value)

async def delete_previous_bot_messages(channel):
    deleted = 0
    try:
        async for message in channel.history(limit=100):
            if message.author == bot.user:
                try:
                    await message.delete()
                    deleted += 1
                except discord.NotFound:
                    pass
        logger.info("Deleted %d previous bot messages in channel %s", deleted, channel.id if channel else "unknown")
    except Exception:
        logger.exception("Failed while deleting previous bot messages in channel %s", channel.id if channel else "unknown")
             
def parse_inventory_total(inventory_text):

    if not inventory_text or not isinstance(inventory_text, str):
        return 0.0

    totals = {}
    for m in re.finditer(r'^(.*?)\s*(?:x(\d+))?\s*-\s*\$([0-9,]+\.\d{2})', inventory_text, flags=re.MULTILINE):
        name = m.group(1).strip()
        qty = int(m.group(2)) if m.group(2) else 1
        try:
            price = float(m.group(3).replace(',', ''))
        except Exception:
            logger.debug("Failed to parse price fragment %r for item %s", m.group(3), name)
            continue

        if name in totals:
            prev_price, prev_count = totals[name]
            if abs(prev_price - price) > 0.001:
                logger.debug("Conflicting unit prices for %s: %.2f vs %.2f — using latest %.2f", name, prev_price, price, price)
                prev_price = price
            totals[name] = (prev_price, prev_count + qty)
        else:
            totals[name] = (price, qty)

    total = sum(p * c for p, c in totals.values())
    return total

INPUT_FILE = "input_messages.json"
RUNTIME_INPUT_TIMEOUT_SECONDS = 30
STEAM_LINK_PATTERN = re.compile(r'https?://steamcommunity\.com/(profiles|id)/(\w+)(?:/(\w+))?')
INPUT_FILE_CANDIDATE_NAMES = {"input_message.json", "input_messages.json"}


def _normalize_messages(messages: list[str]) -> list[str]:
    seen = set()
    result = []
    for m in messages:
        if not isinstance(m, str):
            continue
        value = m.strip()
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def save_input_messages(messages: list[str], file_path: str = INPUT_FILE) -> None:
    new_items = _normalize_messages(messages)
    if not new_items:
        return

    existing_items = load_input_messages(file_path)
    merged = _normalize_messages(existing_items + new_items)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2)
        logger.info("Saved %d new input message(s), total=%d in %s", len(new_items), len(merged), file_path)
    except Exception:
        logger.exception("Failed to save input messages to %s", file_path)


def _extract_messages_from_json_payload(data) -> list[str]:
    messages: list[str] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                messages.append(item)
            elif isinstance(item, dict) and isinstance(item.get("content"), str):
                messages.append(item["content"])
    elif isinstance(data, dict):
        raw = data.get("messages", [])
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, str):
                    messages.append(item)
                elif isinstance(item, dict) and isinstance(item.get("content"), str):
                    messages.append(item["content"])
    return _normalize_messages(messages)


def load_input_messages(file_path: str = INPUT_FILE) -> list[str]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.warning("Input file not found: %s", file_path)
        return []
    except json.JSONDecodeError:
        logger.exception("Invalid JSON in input file: %s", file_path)
        return []
    except Exception:
        logger.exception("Failed to read input file: %s", file_path)
        return []

    messages = _extract_messages_from_json_payload(data)
    logger.info("Loaded %d input message(s) from %s", len(messages), file_path)
    return messages


async def hydrate_input_messages_from_discord(channel, file_path: str = INPUT_FILE) -> list[str]:
    local_messages = load_input_messages(file_path)
    if local_messages:
        return local_messages

    if channel is None:
        logger.warning("Cannot hydrate %s from Discord: channel is None", file_path)
        return []

    logger.info("Local %s is empty/missing. Trying to fetch from Discord channel %s", file_path, channel.id)
    try:
        async for message in channel.history(limit=200):
            for attachment in message.attachments:
                if attachment.filename.lower() not in INPUT_FILE_CANDIDATE_NAMES:
                    continue

                try:
                    payload = await attachment.read()
                    data = json.loads(payload.decode("utf-8"))
                    messages = _extract_messages_from_json_payload(data)
                    if not messages:
                        logger.warning("Attachment %s found but no valid messages inside", attachment.filename)
                        continue

                    save_input_messages(messages, file_path)
                    logger.info(
                        "Hydrated %d input message(s) from Discord attachment %s",
                        len(messages),
                        attachment.filename
                    )
                    return messages
                except Exception:
                    logger.exception("Failed reading/parsing Discord attachment %s", attachment.filename)
    except Exception:
        logger.exception("Failed to scan channel history for %s", file_path)

    logger.warning("No usable %s attachment found in Discord history", file_path)
    return []


async def collect_runtime_messages_and_save(timeout_seconds: int = RUNTIME_INPUT_TIMEOUT_SECONDS) -> list[str]:
    logger.info("Runtime CLI input is disabled. Skipping interactive terminal input.")
    return []
            
async def process_profile_entry(profile_type: str, profile_id: str, group: str, semaphore: asyncio.Semaphore) -> dict:
    full_link = f'https://steamcommunity.com/{profile_type}/{profile_id}'
    logger.debug("Processing profile entry link=%s group=%s", full_link, group)

    try:
        async with semaphore:
            steam_id, _ = await asyncio.to_thread(normalize_steam_profile_link, full_link)
            logger.debug("Normalized %s -> steam_id=%s", full_link, steam_id)

            if not steam_id:
                logger.warning("Invalid/unresolvable Steam link: %s", full_link)
                return {
                    "steam_id": None,
                    "group": group,
                    "inv_total": 0.0,
                    "inventory_details": "",
                    "entries": [("invalid", f"Invalid or unresolvable Steam link: {full_link}")],
                }

            profile_status = await asyncio.to_thread(check_steam_profile, steam_id)
            if not profile_status:
                logger.warning("Could not retrieve profile status for steam_id=%s", steam_id)
                return {
                    "steam_id": steam_id,
                    "group": group,
                    "inv_total": 0.0,
                    "inventory_details": "Could not retrieve inventory/profile data",
                    "entries": [(
                        "not_banned",
                        f"Original ID: {full_link} (Steam ID: {steam_id}) - Could not retrieve data",
                    )],
                }

            vac_banned = profile_status['VACBanned']
            community_banned = profile_status['CommunityBanned']
            game_ban_count = profile_status['NumberOfGameBans']
            inventory_info, _ = await asyncio.to_thread(get_inventory_summary_with_status, steam_id, 730, 2, True)
            inventory_state_line = "`Inventory:` " + inventory_info[:20] + "\n"

            inv_total = parse_inventory_total(inventory_info)
            logger.debug("Calculated $%.2f for group %s (profile=%s)", inv_total, group, steam_id)

            profile_info = (
                f"Original ID: {full_link}\n"
                f"`Steam ID:` {steam_id}\n"
                f"{inventory_state_line}"
                f"```{inventory_info}```"
            )

            profile_info_not_banned = (
                f"Original ID: {full_link}\n"
                f"{inventory_state_line}"
                f"```{inventory_info}```"
            )

            entries = []
            if vac_banned:
                entries.append(("vac", profile_info))
            if community_banned:
                entries.append(("community", profile_info))
            if game_ban_count > 0:
                entries.append(("game", f"{profile_info} - {game_ban_count} Game Ban(s)"))
            if not (vac_banned or community_banned or game_ban_count > 0):
                entries.append(("not_banned", profile_info_not_banned))

            logger.debug(
                "Completed profile entry steam_id=%s group=%s flags(vac=%s,community=%s,game_bans=%s)",
                steam_id,
                group,
                vac_banned,
                community_banned,
                game_ban_count,
            )

            return {
                "steam_id": steam_id,
                "group": group,
                "inv_total": inv_total,
                "inventory_details": inventory_info,
                "entries": entries,
            }
    except asyncio.CancelledError:
        logger.debug("Profile processing for link=%s was cancelled", full_link)
        return {
            "steam_id": None,
            "group": group,
            "inv_total": 0.0,
            "inventory_details": "",
            "entries": [],
        }


async def process_profile_entry_with_label(
    profile_type: str,
    profile_id: str,
    group: str,
    target_label: str,
    semaphore: asyncio.Semaphore,
) -> tuple[str, dict | Exception]:
    try:
        result = await process_profile_entry(profile_type, profile_id, group, semaphore)
        return target_label, result
    except Exception as e:
        return target_label, e

@tasks.loop(seconds=CHECK_LOOP_INTERVAL_SECONDS)
async def check_steam():
    global _runtime_input_bootstrapped, _runtime_input_messages_cache, _bot_paused, _bot_running, _active_tasks

    # Check if paused or stopped
    if _bot_paused or not _bot_running:
        logger.debug("Bot is paused or stopped, skipping check_steam iteration")
        return

    if not _runtime_input_bootstrapped:
        _runtime_input_messages_cache = []
        _runtime_input_bootstrapped = True
        logger.info("Runtime CLI input disabled. Using %s and Discord attachment hydration only.", INPUT_FILE)

    for channel_id in CHANNEL_IDS:
        channel = bot.get_channel(channel_id)
        logger.debug("Processing channel %s", channel_id)
        vac_banned_accounts = {}
        community_banned_accounts = {}
        game_banned_accounts = {}
        not_banned_accounts = {}
        invalid_accounts = {}
        group_totals = {}
        total_accounts_found = 0

        if channel is None:
            logger.warning("Channel %s not found", channel_id)
            continue

        input_messages = _runtime_input_messages_cache or load_input_messages()
        if not input_messages:
            input_messages = await hydrate_input_messages_from_discord(channel, INPUT_FILE)

        if not input_messages:
            input_messages = load_input_messages()

        if not input_messages:
            logger.warning("No input messages found from runtime input or %s", INPUT_FILE)
            continue

        targets = []
        target_labels = []
        for msg_idx, content in enumerate(input_messages, start=1):
            steam_links = re.findall(r'https?://steamcommunity\.com/(profiles|id)/(\w+)(?:/(\w+))?', content)
            if not steam_links:
                continue

            logger.debug("Found %d steam links in input message #%d", len(steam_links), msg_idx)
            for profile_type, profile_id, group in steam_links:
                resolved_group = group or "UNGROUPED"
                targets.append((profile_type, profile_id, resolved_group))
                target_labels.append(f"{profile_type}/{profile_id} [{resolved_group}]")

        if not targets:
            logger.warning("No Steam links found in loaded input messages for channel %s", channel_id)
            continue

        reset_inventory_progress(target_labels)
        total_accounts_found = len(targets)

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_PROFILE_CHECKS)
        logger.debug(
            "Processing %d Steam profiles for channel %s with concurrency=%d",
            len(targets),
            channel_id,
            MAX_CONCURRENT_PROFILE_CHECKS,
        )
        tasks_batch = [
            asyncio.create_task(
                process_profile_entry_with_label(
                    profile_type,
                    profile_id,
                    group,
                    f"{profile_type}/{profile_id} [{group}]",
                    semaphore,
                )
            )
            for profile_type, profile_id, group in targets
        ]
        
        # Track tasks so we can cancel them if needed
        for task in tasks_batch:
            _active_tasks.add(task)
        
        results = []
        try:
            for completed_task in asyncio.as_completed(tasks_batch):
                target_label, result = await completed_task
                if isinstance(result, dict):
                    details = str(result.get("inventory_details", ""))
                mark_inventory_processed(target_label, details)
                results.append(result)
        finally:
            # Remove completed tasks
            for task in tasks_batch:
                _active_tasks.discard(task)

        active_steam_ids = set()

        for result in results:
            if isinstance(result, Exception):
                logger.error("Profile processing task failed: %r", result)
                continue

            if result.get("steam_id"):
                active_steam_ids.add(str(result.get("steam_id")))

            group = result.get("group", "UNGROUPED")
            group_totals[group] = group_totals.get(group, 0.0) + float(result.get("inv_total", 0.0))

            for category, value in result.get("entries", []):
                if category == "vac":
                    add_to_group(vac_banned_accounts, group, value)
                elif category == "community":
                    add_to_group(community_banned_accounts, group, value)
                elif category == "game":
                    add_to_group(game_banned_accounts, group, value)
                elif category == "not_banned":
                    add_to_group(not_banned_accounts, group, value)
                elif category == "invalid":
                    add_to_group(invalid_accounts, group, value)

        unchanged_ids = set(await asyncio.to_thread(get_unchanged_inventory_ids))
        stale_unchanged_ids = [sid for sid in unchanged_ids if sid not in active_steam_ids]
        if stale_unchanged_ids:
            logger.info("Removing %d unchanged entries not present in current item list", len(stale_unchanged_ids))
        for stale_sid in stale_unchanged_ids:
            await asyncio.to_thread(remove_unchanged_inventory, stale_sid)
            await asyncio.to_thread(remove_cache_entry, stale_sid)

        logger.info(
            "Channel %s summary: total_found=%d vac_groups=%d community_groups=%d game_groups=%d not_banned_groups=%d invalid_groups=%d",
            channel_id, total_accounts_found,
            len(vac_banned_accounts), len(community_banned_accounts),
            len(game_banned_accounts), len(not_banned_accounts),
            len(invalid_accounts)
        )

        await delete_previous_bot_messages(channel)

        await send_grouped_embeds(channel, "VAC Banned Accounts", vac_banned_accounts, total_accounts_found)
        await send_grouped_embeds(channel, "Community Banned Accounts", community_banned_accounts, total_accounts_found)
        await send_grouped_embeds(channel, "Game Banned Accounts", game_banned_accounts, total_accounts_found)
        await send_grouped_embeds(channel, "Not Banned Accounts", not_banned_accounts, total_accounts_found)
        await send_grouped_embeds(channel, "Invalid Accounts", invalid_accounts, total_accounts_found)

        if group_totals:
            await send_totals_embed(channel, group_totals)

logger.info("Entrypoint: starting bot")

# Initialize GUI logging
setup_gui_logging()

# Create GUI window with callbacks
def on_start_bot():
    global _bot_running, _bot_paused
    logger.info("Bot start requested via GUI")
    set_stop_requested(False)
    _bot_running = True
    _bot_paused = False
    logger.info("Starting check_steam loop from GUI")
    try:
        # Wait for bot event loop to be ready, then schedule the task
        if _bot_ready.is_set():
            asyncio.run_coroutine_threadsafe(
                _start_check_steam(),
                bot.loop
            )
        else:
            logger.warning("Bot event loop not ready yet, retrying...")
    except Exception as e:
        logger.error("Failed to start check_steam: %s", e)

async def _start_check_steam():
    """Helper coroutine to start the check_steam task."""
    try:
        loop_task = getattr(check_steam, "_task", None)
        if loop_task is not None and not loop_task.done() and not check_steam.is_running():
            logger.info("Previous check_steam task still shutting down; waiting before start")
            try:
                await loop_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

        check_steam.start()
        logger.info("check_steam loop started successfully")
    except RuntimeError as e:
        if "already launched" in str(e).lower() or "already running" in str(e).lower():
            logger.info("check_steam loop already running")
        else:
            logger.error("Error starting check_steam: %s", e)
    except Exception as e:
        logger.error("Error starting check_steam: %s", e)

def on_stop_bot():
    global _bot_running, _bot_paused
    logger.info("Bot stop requested via GUI")
    set_stop_requested(True)
    _bot_running = False
    _bot_paused = False
    if check_steam.is_running():
        logger.info("Stopping check_steam loop from GUI")
        try:
            # Schedule the stop on the bot's event loop
            if _bot_ready.is_set():
                asyncio.run_coroutine_threadsafe(
                    _stop_check_steam(),
                    bot.loop
                )
            else:
                logger.warning("Bot event loop not ready yet")
        except Exception as e:
            logger.error("Failed to stop check_steam: %s", e)
    else:
        logger.info("check_steam loop not running")

async def _stop_check_steam():
    """Helper coroutine to stop the check_steam task."""
    global _active_tasks, _bot_running
    try:
        set_stop_requested(True)
        # Cancel all active profile processing tasks
        tasks_to_cancel = list(_active_tasks)
        logger.info("Cancelling %d active profile processing tasks", len(tasks_to_cancel))
        for task in tasks_to_cancel:
            if not task.done():
                task.cancel()
                
        # Wait for all tasks to be cancelled
        if tasks_to_cancel:
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
                
        _active_tasks.clear()
                
        # Stop the check_steam loop
        loop_task = getattr(check_steam, "_task", None)
        if loop_task is not None and not loop_task.done():
            check_steam.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
        else:
            check_steam.stop()

        _bot_running = False
        logger.info("check_steam loop stopped successfully, all worker tasks cancelled")
    except Exception as e:
        logger.error("Error stopping check_steam: %s", e)

def on_pause_bot():
    global _bot_paused
    logger.info("Bot pause requested via GUI")
    _bot_paused = True

def on_resume_bot():
    global _bot_paused
    logger.info("Bot resume requested via GUI")
    _bot_paused = False


def on_restart_bot():
    logger.info("Bot restart requested via GUI")
    set_stop_requested(False)
    try:
        if _bot_ready.is_set():
            asyncio.run_coroutine_threadsafe(
                _restart_check_steam(),
                bot.loop
            )
        else:
            logger.warning("Bot event loop not ready yet")
    except Exception as e:
        logger.error("Failed to restart check_steam: %s", e)


async def _restart_check_steam():
    global _bot_running, _bot_paused
    try:
        if check_steam.is_running():
            await _stop_check_steam()
        set_stop_requested(False)
        _bot_paused = False
        _bot_running = True
        await _start_check_steam()
        if check_steam.is_running():
            logger.info("check_steam loop restarted successfully")
        else:
            logger.warning("check_steam restart requested but loop is not running")
    except Exception as e:
        logger.error("Error restarting check_steam: %s", e)

def on_force_update_prices():
    logger.info("Force update prices requested via GUI")
    try:
        force_update_all_prices()
        logger.info("Force update prices completed")
    except Exception as e:
        logger.error("Force update prices failed: %s", e)


def on_reset_updated_flags():
    logger.info("Reset updated flags requested via GUI (no-op)")
    pass


# Start GUI in a separate thread
def run_gui():
    global _gui_window, _gui_ready
    logger.info("GUI thread starting")
    _gui_window = create_gui_window(
        on_start_bot=on_start_bot,
        on_stop_bot=on_stop_bot,
        on_pause_bot=on_pause_bot,
        on_resume_bot=on_resume_bot,
        on_restart_bot=on_restart_bot,
        on_force_update_prices=on_force_update_prices,
    )
    _gui_ready = True
    logger.info("GUI thread ready, mainloop starting")
    _gui_window.mainloop()

gui_thread = threading.Thread(target=run_gui, daemon=False)
gui_thread.start()

# Give GUI a moment to initialize before Discord connects
logger.info("Waiting for GUI to initialize...")
time.sleep(1)

# Run the bot
logger.info("Starting Discord bot connection")
bot.run(BOT_TOKEN)
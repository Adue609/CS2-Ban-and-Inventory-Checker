import discord
from discord.ext import commands, tasks
import re
import requests
import time
import asyncio
import random

from utils.logger import get_logger
from utils.PriceChecker import get_market_price_from_cache
from utils.Inventory import get_inventory_summary
from utils.config import STEAM_API_KEY, BOT_TOKEN, CHANNEL_IDS

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

INVENTORY_MAX_RETRIES = 10
INVENTORY_BACKOFF_BASE = 1.5

# @tasks.loop(seconds=UPDATE_INTERVAL)
# async def refresh_inventories_task():
#     await asyncio.to_thread(force_update_all_inventories)

EMBED_FIELD_VALUE_LIMIT = 1024
EMBED_FIELD_NAME_LIMIT = 256
EMBED_TOTAL_CHAR_LIMIT = 6000
EMBED_MAX_FIELDS = 25

@bot.event
async def on_ready():
    logger.info("Bot ready. Logged in as %s", bot.user)
    check_steam.start()
    # refresh_inventories_task.start()

def check_steam_profile(steam_id):
    url = f'http://api.steampowered.com/ISteamUser/GetPlayerBans/v1/?key={STEAM_API_KEY}&steamids={steam_id}'
    try:
        logger.debug("Checking bans for SteamID=%s via %s", steam_id, url)
        response = STEAM_SESSION.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get('players'):
            return data['players'][0]
        return None
    except Exception as e:
        logger.exception("Unexpected error checking bans for SteamID=%s, error = %s", steam_id, e)
        return None

def normalize_steam_profile_link(link):
    specific_profile_link = 'https://steamcommunity.com/profiles/76561198063578000/'
    specific_profile_id = '71111111111111111'
    specific_custom_id = 'MehdiCRisH'

    if link in [specific_profile_link, f'https://steamcommunity.com/id/{specific_custom_id}/']:
        return specific_profile_id, specific_custom_id
    else:
        match = re.match(r'https?://steamcommunity\.com/(profiles|id)/(\w+)/?', link)
        if match:
            profile_type, profile_id = match.groups()
            if profile_type == 'id':
                try:
                    vanity_url = f"http://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/?key={STEAM_API_KEY}&vanityurl={profile_id}"
                    logger.debug("Resolving vanity URL for %s via %s", profile_id, vanity_url)
                    response = requests.get(vanity_url, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    if data.get('response', {}).get('success') == 1:
                        return data['response']['steamid'], profile_id
                except Exception:
                    logger.exception("Failed to resolve vanity URL for %s", profile_id)
            else:
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

    total_accounts_printed = 0
    chunks = chunk_list(accounts)
    embed = discord.Embed(title=title, color=0x1e90ff)
    fields_in_current = 0
    part_index = 1

    async def send_and_reset(current_embed, printed_so_far):
        try:
            current_embed.add_field(name="Summary", value=f"Total accounts printed (this embed): {printed_so_far}", inline=False)
            await channel.send(embed=current_embed)
            logger.info("Sent embed '%s' to channel %s (printed=%d, found=%d)", title, channel.id if channel else "unknown", printed_so_far, total_accounts_found)
        except Exception:
            logger.exception("Failed to send embed '%s' to channel %s", title, channel.id if channel else "unknown")

    printed_in_current = 0

    for chunk_str, count in chunks:
        if fields_in_current >= EMBED_MAX_FIELDS - 1:
            await send_and_reset(embed, printed_in_current)
            embed = discord.Embed(title=title, color=0x1e90ff)
            fields_in_current = 0
            printed_in_current = 0

        value = chunk_str
        if len(value) > EMBED_FIELD_VALUE_LIMIT:
            value = value[:EMBED_FIELD_VALUE_LIMIT - 3] + "..."

        field_name = f"{title} (Part {part_index})"
        if len(field_name) > EMBED_FIELD_NAME_LIMIT:
            field_name = field_name[:EMBED_FIELD_NAME_LIMIT - 3] + "..."
        embed.add_field(name=field_name, value=value, inline=False)
        fields_in_current += 1
        total_accounts_printed += count
        printed_in_current += count
        part_index += 1

        est_size = len(embed.title or "") + sum(len(f.value) if hasattr(f, "value") else 0 for f in embed.fields)
        if est_size > EMBED_TOTAL_CHAR_LIMIT - 500:
            await send_and_reset(embed, printed_in_current)
            embed = discord.Embed(title=title, color=0x1e90ff)
            fields_in_current = 0
            printed_in_current = 0

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

@tasks.loop(minutes=60)
async def check_steam():
    logger.info("check_steam task started")
    for channel_id in CHANNEL_IDS:
        channel = bot.get_channel(channel_id)
        logger.info("Processing channel %s", channel_id)
        vac_banned_accounts = {}
        community_banned_accounts = {}
        game_banned_accounts = {}
        not_banned_accounts = {}
        invalid_accounts = {}
        group_totals = {}
        total_accounts_found = 0

        await delete_previous_bot_messages(channel)

        async for message in channel.history(limit=100):
            steam_links = re.findall(r'https?://steamcommunity\.com/(profiles|id)/(\w+)(?:/(\w+))?',message.content)
            if not steam_links:
                continue
            total_accounts_found += len(steam_links)
            logger.debug("Found %d steam links in message %s", len(steam_links), message.id)
            for profile_type, profile_id, group in steam_links:
                group = group or "UNGROUPED"
                full_link = f'https://steamcommunity.com/{profile_type}/{profile_id}'

                steam_id, original_id = await asyncio.to_thread(normalize_steam_profile_link, full_link)
                logger.debug("Normalized %s -> steam_id=%s original=%s", full_link, steam_id, original_id)

                if steam_id:
                  profile_status = await asyncio.to_thread(check_steam_profile, steam_id)
                  if profile_status:
                      vac_banned = profile_status['VACBanned']
                      community_banned = profile_status['CommunityBanned']
                      game_ban_count = profile_status['NumberOfGameBans']
                      inventory_info = await asyncio.to_thread(get_inventory_summary, steam_id, 730, 2, True)

                      inv_total = parse_inventory_total(inventory_info)
                      group_totals[group] = group_totals.get(group, 0.0) + inv_total
                      logger.debug("Added $%.2f to group %s (profile=%s)", inv_total, group, steam_id)

                      profile_info = (
                        f"Original ID: {full_link}\n"
                        f"`Steam ID:` {steam_id}\n"
                        f"```{inventory_info}```"
                      )

                      profile_info_NotBanned = (
                        f"Original ID: {full_link}\n"
                        f"```{inventory_info}```"
                      )

                      if vac_banned:
                          add_to_group(vac_banned_accounts, group, profile_info)
                      if community_banned:
                          add_to_group(community_banned_accounts, group, profile_info)
                      if game_ban_count > 0:
                          add_to_group(game_banned_accounts,group,f"{profile_info} - {game_ban_count} Game Ban(s)")
                      if not (vac_banned or community_banned or game_ban_count > 0):
                          add_to_group(not_banned_accounts, group, profile_info_NotBanned)
                  else:
                      add_to_group(not_banned_accounts,group,f"Original ID: {full_link} (Steam ID: {steam_id}) - Could not retrieve data")
                      logger.warning("Could not retrieve profile status for steam_id=%s", steam_id)
                else:
                    add_to_group(invalid_accounts,group,f"Invalid or unresolvable Steam link: {full_link}")
                    logger.warning("Invalid/unresolvable Steam link: %s", full_link)

        logger.info("Channel %s summary: total_found=%d vac_groups=%d community_groups=%d game_groups=%d not_banned_groups=%d invalid_groups=%d",
                    channel_id, total_accounts_found,
                    len(vac_banned_accounts), len(community_banned_accounts),
                    len(game_banned_accounts), len(not_banned_accounts),
                    len(invalid_accounts))

        await send_grouped_embeds(channel, "VAC Banned Accounts", vac_banned_accounts, total_accounts_found)
        await send_grouped_embeds(channel, "Community Banned Accounts", community_banned_accounts, total_accounts_found)
        await send_grouped_embeds(channel, "Game Banned Accounts", game_banned_accounts, total_accounts_found)
        await send_grouped_embeds(channel, "Not Banned Accounts", not_banned_accounts, total_accounts_found)
        await send_grouped_embeds(channel, "Invalid Accounts", invalid_accounts, total_accounts_found)

        if group_totals:
            await send_totals_embed(channel, group_totals)

logger.info("Entrypoint: starting bot")
bot.run(BOT_TOKEN)
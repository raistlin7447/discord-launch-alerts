import json
import sys
import asyncio
from typing import List, Union, Dict, Sequence
import backoff
import pytz
from discord import DMChannel, TextChannel, Emoji
from discord.abc import GuildChannel
from discord.ext import commands, tasks
import discord
import aiohttp
from datetime import datetime, timedelta
from logbook import Logger, StreamHandler, FileHandler

from acronym_utils import acronym_lookup, get_acronym_embed
from config import ChannelConfig, UserConfig
from launch_monitor import LaunchMonitor, ISOFORMAT
from launch_monitor_utils import LAUNCH_MONITORS_KEY, db
from utils import get_config_from_message, get_launch_embed, is_today_launch, \
    get_config_from_channel, get_config_from_db_key, get_server_name_from_channel, convert_quoted_string_in_list, \
    new_aiohttp_connector, get_launch_win_open, get_live_url, get_server_id_from_channel, has_tc_integration
from local_config import *

SUB_EMOJI = "🔔"


def get_prefix(client, message):
    """
    This is a mostly undocumented feature of Discord.py v0.16.12
    If you pass a callable into `commands.Bot(command_prefix=<value>)`
    then the function will be called on message receipt to dynamically
    determine the prefix

    :param client: The bot object
    :param message: The message being received
    :return: A string or collection of strings denoting acceptable prefixes
    """
    if message.guild and message.guild.id in DISCORD_BOT_PREFIXES.keys():
        return DISCORD_BOT_PREFIXES[message.guild.id]
    else:
        return DEFAULT_BOT_PREFIX


description = "Rocket launch lookup and alert bot.\n" \
              "Valid prefixes: {}".format(", ".join(DEFAULT_BOT_PREFIX))

loop = asyncio.get_event_loop()
connector = loop.run_until_complete(new_aiohttp_connector())

bot = commands.Bot(command_prefix=get_prefix, description=description, loop=loop, connector=connector)
bot.session = aiohttp.ClientSession(connector=connector)

StreamHandler(sys.stdout).push_application()
FileHandler('discord-launch-alert.log', bubble=True).push_application()
bot.log = Logger('Launch Alerts Bot')


async def save_launch_alerts(upcoming_launches: List[dict], alert_sent_lms: List[LaunchMonitor]) -> None:
    """Get all configurations with launch alerts turned on.  Update with last alert times and save to DB."""
    db_keys = db.keys()

    launch_monitors_to_save = []
    for key in db_keys:
        if key.startswith(ChannelConfig.KEY_PREFIX) or key.startswith(UserConfig.KEY_PREFIX):
            config = get_config_from_db_key(str(key))
            if config.receive_alerts == "true":
                for upcoming_launch in upcoming_launches:
                    # Create clean list for all launch monitors
                    if not get_launch_win_open(upcoming_launch):
                        continue
                    new_lm = LaunchMonitor()
                    new_lm.load({
                        "server": config.server_id if hasattr(config, "server_id") else None,
                        "channel": config.channel_id if hasattr(config, "channel_id") else config.user_id,
                        "launch_slug": upcoming_launch["slug"],
                        "launch_win_open": get_launch_win_open(upcoming_launch).strftime(ISOFORMAT),
                        "last_alert": None
                    }, config.alert_times)

                    # Update last_alert from times in the DB
                    for current_lm in await get_launch_alerts(due_only=False):
                        if new_lm == current_lm:
                            new_lm.last_alert = current_lm.last_alert
                            # TODO check for launch_win_open change here and send alert that the window has moved
                            # if new_lm.launch_win_open != current_lm.launch_win_open:
                            #     "[mission name] has been moved to [time].  Go to [link] to find out more.

                    # Update last_alert for messages we just sent
                    for alert_sent_lm in alert_sent_lms:
                        if new_lm == alert_sent_lm:
                            new_lm.last_alert = alert_sent_lm.last_alert
                    launch_monitors_to_save.append(new_lm.dump())
    db.set(LAUNCH_MONITORS_KEY, json.dumps(launch_monitors_to_save))


async def get_launch_alerts(due_only=True) -> List[LaunchMonitor]:
    launch_monitors_from_db = db.get(LAUNCH_MONITORS_KEY)
    if launch_monitors_from_db:
        launch_monitors_from_db = json.loads(launch_monitors_from_db)
    else:
        launch_monitors_from_db = []

    monitors = []
    for launch_monitor in launch_monitors_from_db:
        if launch_monitor["server"]:
            config = ChannelConfig(launch_monitor["server"], launch_monitor["channel"])
        else:
            config = UserConfig(launch_monitor["channel"])

        lm = LaunchMonitor()
        lm.load(launch_monitor, config.alert_times)
        if not due_only or lm.is_alert_due():
            monitors.append(lm)

    return monitors


@tasks.loop(seconds=60)
async def process_alerts():
    bot.log.info("Process Alerts")
    lms = await get_launch_alerts()
    for lm in lms:
        bot.log.info(f"[channel={lm.channel}, slug={lm.launch}] sending launch alert")
        try:
            lm.last_alert = datetime.now(pytz.utc)
            await send_launch_alert(lm)
        except Exception as e:
            bot.log.exception("Error sending launch alert: {}".format(e))
    upcoming_launches = await get_multiple_launches(("5",))
    if upcoming_launches:
        await save_launch_alerts(upcoming_launches, lms)


@process_alerts.before_loop
async def before_process_alerts():
    print('process alerts waiting for bot to start')
    await bot.wait_until_ready()


async def send_launch_alert(lm: LaunchMonitor) -> None:
    if lm.server:
        channel = bot.get_channel(int(lm.channel))
        if channel:
            config = get_config_from_channel(channel)
        else:
            bot.log.error(f"[channel={lm.channel}, slug={lm.launch}] channel does not exist")
            return
    else:  # User configs are different
        user = bot.get_user(int(lm.channel))
        if not user.dm_channel:
            await user.create_dm()
        channel = user.dm_channel
        config = UserConfig(lm.channel)
    launch = await get_launch_by_slug(lm.launch)

    # OffNom send Starship tests to #boca-chica
    if isinstance(channel, GuildChannel) and channel.guild.id == 360523650912223253 and launch["vehicle"]["id"] == 115:
        channel = bot.get_channel(int(754432168293433354))

    asyncio.ensure_future(send_launch_panel(channel, launch, config.timezone, message="There's a launch coming up!"))

    async for msg in channel.history(limit = 3):
        if msg.embeds and msg.author == bot.user:
            if msg.embeds[0].title == launch["name"]:
                launch_window = get_launch_win_open(launch)
                if int(launch_window.timestamp()) == int(msg.embeds[0].fields[0].name.split(":")[1]):
                    #Skip alerting everyone
                    return


@backoff.on_exception(backoff.expo,
                      Exception,
                      max_tries=10)
async def get_multiple_launches(args: Sequence):
    headers = {"Authorization": "Bearer 44bd6b60-5002-4866-be8f-09cee79c92f7"}
    # Uses slash to separate parameters
    params = "/".join(args)
    async with bot.session.get('https://fdo.rocketlaunch.live/json/launch/next/{}'.format(params), headers=headers) as response:
        if response.status == 200:
            js = await response.json()
            return js["result"]


@backoff.on_exception(backoff.expo,
                      Exception,
                      max_tries=10)
async def get_launch_by_slug(slug: str):
    # TODO: Add caching for launch data so that we don't retrieve it too often
    #     Safe to redis key, perhaps "cache-slug" with 60 second expiry.  If not there, fetch, then save to redis
    headers = {"Authorization": "Bearer 44bd6b60-5002-4866-be8f-09cee79c92f7"}
    async with bot.session.get('https://fdo.rocketlaunch.live/json/launch/{}'.format(slug), headers=headers) as response:
        if response.status == 200:
            js = await response.json()
            if js["result"]:
                return js["result"][0]
            else:
                return None


async def send_launch_panel(channel: Union[TextChannel, DMChannel], launch: Dict, timezone: str, message: str=None) -> None:
    server = get_server_name_from_channel(channel)
    server_id = get_server_id_from_channel(channel)
    with_tc = has_tc_integration(server_id)
    bot.log.info("[server={}, channel={}, slug={}] launch panel sent".format(server, channel, launch["slug"]))
    launch_message = await channel.send(message, embed=get_launch_embed(launch, timezone, with_tc=with_tc))
    if with_tc:
        await launch_message.add_reaction(SUB_EMOJI)


@bot.event
async def on_reaction_add(reaction, user):
    if user == bot.user:
        return

    if reaction.emoji != SUB_EMOJI:
        return

    message = reaction.message
    server = message.guild

    if server.id not in SERVERS_WITH_TC_INTEGRATION:
        return

    if message.author == bot.user:
        footer_text = message.embeds[0].footer.text
        slug = footer_text.split("|")[1].strip()
        launch = await get_launch_by_slug(slug)
        live_url = get_live_url(launch) or ""
        win_open = get_launch_win_open(launch) or ""
        expire = win_open + timedelta(days=1)
        name = launch["name"]

        if launch["provider"]["slug"] == "spacex":
            tc_parent_id = 6
        else:
            tc_parent_id = 17

        tc_sub_message = f'{TERMINAL_COUNT_COMMAND} botsub "{server.id}" "{slug}" {tc_parent_id} "{live_url}" "{expire}" "{user.id}" "{name}"'

        tc_channel = bot.get_channel(TERMINAL_COUNT_CHANNEL_ID)
        await tc_channel.send(tc_sub_message)


@bot.event
async def on_reaction_remove(reaction, user):
    if user == bot.user:
        return

    if reaction.emoji != SUB_EMOJI:
        return

    message = reaction.message
    server = message.guild

    if server.id not in SERVERS_WITH_TC_INTEGRATION:
        return

    if message.author == bot.user:
        footer_text = message.embeds[0].footer.text
        slug = footer_text.split("|")[1].strip()

        tc_sub_message = f'{TERMINAL_COUNT_COMMAND} botunsub "{server.id}" "{slug}" "{user.id}"'

        tc_channel = bot.get_channel(TERMINAL_COUNT_CHANNEL_ID)
        await tc_channel.send(tc_sub_message)


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(type=0, name="{}help".format(DEFAULT_BOT_PREFIX[0])))
    bot.log.info('Logged in as')
    bot.log.info(f'Name: {bot.user.name}')
    bot.log.info(f'ID: {bot.user.id}')
    bot.log.info(f'Lib Ver: {discord.__version__}')
    bot.log.info('------')
    if not hasattr(bot, 'uptime'):
        bot.uptime = datetime.utcnow()


@bot.command(pass_context=True, aliases=['n'])
async def next(ctx, *args):
    """Get next launch with optional filtering.
    Examples:
    !launch next 2 (get next two launches)
    !launch next crs (get next CRS launch)
    !launch next 2 crs (get next two CRS launches)
    !launch next 3 falcon 9 (get next three Falcon 9 launches)
    !launch next falcon heavy (get next Falcon Heavy launch)"""
    message = ctx.message
    channel = message.channel
    server = get_server_name_from_channel(channel)
    bot.log.info("[server={}, channel={}, command={}, args={}] command called"
                 .format(server, channel, "next", args))

    async with channel.typing():
        channel_config = get_config_from_message(message)
        args = convert_quoted_string_in_list(args)

        launches = await get_multiple_launches(args)
        if launches:
            for launch in launches:
                asyncio.ensure_future(send_launch_panel(channel, launch, channel_config.timezone))
        else:
            if args[0].isnumeric():
                filter_arg = " ".join(args[1:])
            else:
                filter_arg = " ".join(args)

            await channel.send("No launches found with filter `{}`.".format(filter_arg))


@bot.command(pass_context=True, aliases=['t'])
async def today(ctx):
    """Get today's launches."""
    message = ctx.message
    channel = message.channel
    server = get_server_name_from_channel(channel)
    bot.log.info("[server={}, channel={}, command={}] command called"
                 .format(server, channel, "today"))
    async with channel.typing():
        channel_config = get_config_from_message(message)
        launches = await get_multiple_launches(('5',),)
        found_launches = False

        for launch in launches:
            if is_today_launch(launch, channel_config.timezone):
                found_launches = True
                await send_launch_panel(channel, launch, channel_config.timezone)

        if not found_launches:
            bot.log.info("[[server={}, channel={}, command={}] no launches today"
                         .format(server, channel, "today"))
            await channel.send("There are no launches today. \u2639")


@bot.command(pass_context=True, aliases=['c'])
async def config(ctx, option=None, *, value=None):
    """Configure settings for this channel.
    !launch config - View current config
    !launch config option - View option
    !launch config option value - Set option"""
    message = ctx.message
    channel = message.channel
    server = get_server_name_from_channel(channel)
    bot.log.info("[server={}, channel={}, command={}, option={}, value={}] command called"
                 .format(server, channel, "config", option, value))
    config = get_config_from_message(message)

    if option is None:  # Send Options
        bot.log.info("[server={}, channel={}, command={}, option={}, value={}] options sent"
                     .format(server, channel, "config", option, value))
        embed_message = await channel.send(embed=config.config_options_embed())
        config.record_embed_message(embed_message)
    elif value is None:  # Get Value of Option
        bot.log.info("[server={}, channel={}, command={}, option={}, value={}] value sent"
                     .format(server, channel, "config", option, value))
        await channel.send("{} is currently set to {}".format(option, config.__getattr__(option)))
    else:  # Set Value of Option
        config.__setattr__(option, value)
        bot.log.info("[server={}, channel={}, command={}, option={}, value={}] option set"
                     .format(server, channel, "config", option, value))
        old_embed_id = config.get_embed_message()

        if old_embed_id:
            embed_message = await ctx.message.channel.fetch_message(old_embed_id)
            await embed_message.edit(embed=config.config_options_embed())
        await channel.send("{} is now set to {}".format(option, config.__getattr__(option)))


@bot.command(pass_context=True, aliases=['s'])
async def slug(ctx, slug):
    """Retrieve data for a specific launch."""
    message = ctx.message
    channel = message.channel
    server = get_server_name_from_channel(channel)
    bot.log.info("[server={}, channel={}, command={}, slug={}] command called"
                 .format(server, channel, "slug", slug))
    message_config = get_config_from_message(message)

    async with channel.typing():
        launch = await get_launch_by_slug(slug)
        if launch:
            await send_launch_panel(channel, launch, message_config.timezone)
        else:
            bot.log.warning("[server={}, channel={}, command={}, slug={}] slug not found called"
                            .format(server, channel, "slug", slug))
            await channel.send("No launch found with slug `{}`.".format(slug))


@bot.command(pass_context=True, aliases=['a'])
async def acronym(ctx, acronym):
    """Try to find definition for an acronym."""
    message = ctx.message
    channel = message.channel
    server = get_server_name_from_channel(channel)
    bot.log.info("[server={}, channel={}, command={}, acronym={}] command called"
                 .format(server, channel, "acronym", acronym))

    async with channel.typing():
        definitions = await acronym_lookup(bot.session, acronym)
        if definitions:
            embed = get_acronym_embed(acronym, definitions)
            await channel.send(embed=embed)
        else:
            await channel.send("No definitions found for `{}`.".format(acronym))

process_alerts.start()
bot.run(DISCORD_BOT_TOKEN)

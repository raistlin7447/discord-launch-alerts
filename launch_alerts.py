import json
import sys
import asyncio
from typing import List, Union, Dict
import pytz
from dateutil.parser import parse
from discord import User, PrivateChannel, Channel
from discord.ext import commands
import discord
import aiohttp
from datetime import datetime, timedelta
from logbook import Logger, StreamHandler, FileHandler

from acronym_utils import acronym_lookup, get_acronym_embed
from config import ChannelConfig, UserConfig
from launch_monitor import LaunchMonitor, ISOFORMAT
from launch_monitor_utils import LAUNCH_MONITORS_KEY, db
from utils import get_config_from_message, get_launch_embed, is_today_launch, is_launching_soon, \
    get_config_from_channel, get_config_from_db_key, get_server_name_from_channel
from local_config import *

description = "Rocket launch lookup and alert bot."
description = "Rocket launch lookup and alert bot.\n" \
              "Valid prefixes: {}".format(", ".join(DISCORD_BOT_PREFIX))

# TODO Make bot prefix configurable per server instead of installation
bot = commands.Bot(command_prefix=DISCORD_BOT_PREFIX, description=description)
bot.session = aiohttp.ClientSession(loop=bot.loop)

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
                    if not upcoming_launch["win_open"]:
                        continue
                    new_lm = LaunchMonitor()
                    new_lm.load({
                        "server": config.server_id if hasattr(config, "server_id") else None,
                        "channel": config.channel_id if hasattr(config, "channel_id") else config.user_id,
                        "launch_slug": upcoming_launch["slug"],
                        "launch_win_open": parse(upcoming_launch["win_open"]).strftime(ISOFORMAT),
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


async def process_alerts():
    await bot.wait_until_ready()
    while not bot.is_closed:
        lms = await get_launch_alerts()
        for lm in lms:
            bot.log.info("[slug={}] sending launch alert".format(lm.launch))
            await send_launch_alert(lm)
        upcoming_launches = await get_multiple_launches(("5",))
        if upcoming_launches:
            await save_launch_alerts(upcoming_launches, lms)
        await asyncio.sleep(60)


async def send_launch_alert(lm: LaunchMonitor) -> None:
    if lm.server:
        channel = bot.get_channel(lm.channel)
        config = get_config_from_channel(channel)
    else:  # User configs are different
        channel = User(id=lm.channel)
        config = UserConfig(lm.channel)
    launch = await get_launch_by_slug(lm.launch)
    asyncio.ensure_future(send_launch_panel(channel, launch, config.timezone, message="There's a launch coming up!"))
    lm.last_alert = datetime.now(pytz.utc)


async def get_multiple_launches(args: tuple):
    # Uses slash to separate parameters
    params = "/".join(args)
    async with bot.session.get('https://www.rocketlaunch.live/json/launch/next/{}'.format(params)) as response:
        if response.status == 200:
            js = await response.json()
            return js["result"]


async def get_launch_by_slug(slug: str):
    # TODO: Add caching for launch data so that we don't retrieve it too often
    #     Safe to redis key, perhaps "cache-slug" with 60 second expiry.  If not there, fetch, then save to redis
    async with bot.session.get('https://www.rocketlaunch.live/json/launch/{}'.format(slug)) as response:
        if response.status == 200:
            js = await response.json()
            if js["result"]:
                return js["result"][0]
            else:
                return None


async def send_launch_panel(channel: Union[Channel, PrivateChannel], launch: Dict, timezone: str, message: str=None) -> None:
    server = get_server_name_from_channel(channel)
    bot.log.info("[server={}, channel={}, slug={}] launch panel sent".format(server, channel, launch["slug"]))
    now = datetime.now()
    if is_launching_soon(launch):
        seconds_to_keep_updated = 60 * 15
    else:
        seconds_to_keep_updated = 1
    update_until = now + timedelta(seconds=seconds_to_keep_updated)
    launch_message = None
    # TODO find a better way to keep panels updated.  Time doesn't seem the best idea.  Maybe after a certain number
    #     message have passed by in the channel?
    while True:
        if not launch_message:
            launch_message = await bot.send_message(channel, message, embed=get_launch_embed(launch, timezone))
        else:
            await bot.edit_message(launch_message, message, embed=get_launch_embed(launch, timezone))
        await asyncio.sleep(1)
        now = datetime.now()
        if now > update_until:
            bot.log.info("[server={}, channel={}, slug={}] done updating".format(server, channel, launch["slug"]))
            break


@bot.event
async def on_ready():
    await bot.change_presence(game=discord.Game(type=0, name="{}help".format(DISCORD_BOT_PREFIX[0])))
    bot.log.info('Logged in as')
    bot.log.info(f'Name: {bot.user.name}')
    bot.log.info(f'ID: {bot.user.id}')
    bot.log.info(f'Lib Ver: {discord.__version__}')
    bot.log.info('------')
    if not hasattr(bot, 'uptime'):
        bot.uptime = datetime.utcnow()


@bot.command(pass_context=True, aliases=['n'])
async def next(ctx, *args):
    """Get next launch with optional filtering.  Be sure to use quotes if your filters contain spaces.
    Examples:
    !launch next 2 (get next two launches)
    !launch next crs (get next CRS launch)
    !launch next 2 crs (get next two CRS launches)
    !launch next 3 "falcon 9" (get next three Falcon 9 launches)
    !launch next "falcon heavy" (get next Falcon Heavy launch)"""
    message = ctx.message
    channel = message.channel
    server = get_server_name_from_channel(channel)
    bot.log.info("[server={}, channel={}, command={}, args={}] command called".format(server, channel, "next", args))
    config = get_config_from_message(message)
    await bot.send_typing(channel)
    launches = await get_multiple_launches(args)
    if launches:
        for launch in launches:
            asyncio.ensure_future(send_launch_panel(channel, launch, config.timezone))
    else:
        if args[0].isnumeric():
            filter_arg = " ".join(args[1:])
        else:
            filter_arg = " ".join(args)

        await bot.send_message(channel, "No launches found with filter `{}`.".format(filter_arg))


@bot.command(pass_context=True, aliases=['t'])
async def today(ctx):
    """Get today's launches."""
    message = ctx.message
    channel = message.channel
    server = get_server_name_from_channel(channel)
    bot.log.info("[server={}, channel={}, command={}] command called".format(server, channel, "today"))
    config = get_config_from_message(message)
    await bot.send_typing(channel)
    launches = await get_multiple_launches(('5',),)
    found_launches = False

    for launch in launches:
        if is_today_launch(launch, config.timezone):
            found_launches = True
            await send_launch_panel(channel, launch, config.timezone)

    if not found_launches:
        bot.log.info("[[server={}, channel={}, command={}] no launches today".format(server, channel, "today"))
        await bot.send_message(channel, "There are no launches today. \u2639")


@bot.command(pass_context=True, aliases=['c'])
async def config(ctx, option=None, value=None):
    """Configure settings for this channel.
    !launch config - View current config
    !launch config option - View option
    !launch config option value - Set option"""
    message = ctx.message
    channel = message.channel
    server = get_server_name_from_channel(channel)
    bot.log.info("[server={}, channel={}, command={}, option={}, value={}] command called".format(server, channel, "config", option, value))
    config = get_config_from_message(message)

    if option is None:  # Send Options
        bot.log.info("[server={}, channel={}, command={}, option={}, value={}] options sent".format(server, channel, "config", option, value))
        await bot.send_message(channel, embed=config.config_options_embed())
    elif value is None:  # Get Value of Option
        bot.log.info("[server={}, channel={}, command={}, option={}, value={}] value sent".format(server, channel, "config", option, value))
        await bot.send_message(channel,
                               "{} is currently set to {}".format(option, config.__getattr__(option)))
    else:  # Set Value of Option
        config.__setattr__(option, value)
        bot.log.info("[server={}, channel={}, command={}, option={}, value={}] option set".format(server, channel, "config", option, value))
        await bot.send_message(channel,
                               "{} is now set to {}".format(option, config.__getattr__(option)))


@bot.command(pass_context=True, aliases=['s'])
async def slug(ctx, slug):
    """Retrieve data for a specific launch."""
    message = ctx.message
    channel = message.channel
    server = get_server_name_from_channel(channel)
    bot.log.info("[server={}, channel={}, command={}, slug={}] command called".format(server, channel, "slug", slug))
    config = get_config_from_message(message)
    await bot.send_typing(channel)
    launch = await get_launch_by_slug(slug)
    if launch:
        await send_launch_panel(channel, launch, config.timezone)
    else:
        bot.log.warning("[server={}, channel={}, command={}, slug={}] slug not found called".format(server, channel, "slug", slug))
        await bot.send_message(channel, "No launch found with slug `{}`.".format(slug))

@bot.command(pass_context=True, aliases=['a'])
async def acronym(ctx, acronym):
    """Try to find definition for an acronym."""
    message = ctx.message
    channel = message.channel
    server = get_server_name_from_channel(channel)
    bot.log.info("[server={}, channel={}, command={}, acronym={}] command called".format(server, channel, "acronym", acronym))
    await bot.send_typing(channel)

    definitions = await acronym_lookup(bot.session, acronym)
    if definitions:
        embed = get_acronym_embed(acronym, definitions)
        await bot.send_message(channel, embed=embed)
    else:
        await bot.send_message(channel, "No definitions found for `{}`.".format(acronym))


bot.loop.create_task(process_alerts())
bot.run(DISCORD_BOT_TOKEN)

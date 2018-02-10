import sys

import asyncio
from discord.ext import commands
import discord
import aiohttp
from datetime import datetime
from logbook import Logger, StreamHandler
from utils import get_config_from_message, get_launch_embed, is_today_launch, is_launching_soon
from local_config import *

description = "Rocket launch lookup and alert bot."
bot = commands.Bot(command_prefix=DISCORD_BOT_PREFIX, description=description)
bot.session = aiohttp.ClientSession(loop=bot.loop)

StreamHandler(sys.stdout).push_application()
bot.log = Logger('Launch Alerts Bot')


async def get_multiple_launches(args: list):
    # Uses slash to separate parameters
    params = "/".join(args)
    async with bot.session.get('https://www.rocketlaunch.live/json/launch/next/{}'.format(params)) as response:
        if response.status == 200:
            js = await response.json()
            return js["result"]


async def get_launch_by_slug(slug: str):
    async with bot.session.get('https://www.rocketlaunch.live/json/launch/{}'.format(slug)) as response:
        if response.status == 200:
            js = await response.json()
            if js["result"]:
                return js["result"][0]
            else:
                return None


async def send_launch_panel(channel, launch, timezone):
    bot.log.info("[slug={}] launch panel sent".format(launch["slug"]))
    if is_launching_soon(launch):
        seconds_to_keep_updated = 60 * 15
    else:
        seconds_to_keep_updated = 1
    launch_message = None
    for i in range(seconds_to_keep_updated):
        if not launch_message:
            launch_message = await bot.send_message(channel, embed=get_launch_embed(launch, timezone))
        else:
            await bot.edit_message(launch_message, embed=get_launch_embed(launch, timezone))
        await asyncio.sleep(1)


@bot.event
async def on_ready():
    await bot.change_presence(game=discord.Game(type=0, name="{}help".format(DISCORD_BOT_PREFIX)))
    bot.log.info('Logged in as')
    bot.log.info(f'Name: {bot.user.name}')
    bot.log.info(f'ID: {bot.user.id}')
    bot.log.info(f'Lib Ver: {discord.__version__}')
    bot.log.info('------')
    if not hasattr(bot, 'uptime'):
        bot.uptime = datetime.utcnow()


@bot.command(pass_context=True)
async def next(ctx, *args):
    """Get next launch with optional filtering.  Be sure to use quotes if your filters contain spaces.
    Examples:
    !launch next 2 (get next two launches)
    !launch next crs (get next CRS launch)
    !launch next 2 crs (get next two CRS launches)
    !launch next 3 "falcon 9" (get next three Falcon 9 launches)
    !launch next "falcon heavy" (get next Falcon Heavy launch)"""
    bot.log.info("[command={}, num_launches={}] command called".format("next", args))
    message = ctx.message
    config = get_config_from_message(message)
    await bot.send_typing(message.channel)
    launches = await get_multiple_launches(args)
    for launch in launches:
        asyncio.ensure_future(send_launch_panel(message.channel, launch, config.timezone))


@bot.command(pass_context=True)
async def today(ctx):
    """Get today's launches."""
    bot.log.info("[command={}] command called".format("today"))
    message = ctx.message
    config = get_config_from_message(message)
    await bot.send_typing(message.channel)
    launches = await get_multiple_launches(5)
    found_launches = False

    for launch in launches:
        if is_today_launch(launch, config.timezone):
            found_launches = True
            await send_launch_panel(message.channel, launch, config.timezone)

    if not found_launches:
        bot.log.info("[command={}] no launches today".format("today"))
        await bot.send_message(message.channel, "There are no launches today. \u2639")


@bot.command(pass_context=True)
async def config(ctx, option=None, value=None):
    """Configure settings for this channel."""
    bot.log.info("[command={}, option={}, value={}] command called".format("config", option, value))
    message = ctx.message
    config = get_config_from_message(message)

    if option is None:  # Send Options
        bot.log.info("[command={}, option={}, value={}] options sent".format("config", option, value))
        await bot.send_message(message.channel, embed=config.config_options_embed())
    elif value is None:  # Get Value of Option
        bot.log.info("[command={}, option={}, value={}] value sent".format("config", option, value))
        await bot.send_message(message.channel,
                               "{} is currently set to {}".format(option, config.__getattr__(option)))
    else:  # Set Value of Option
        config.__setattr__(option, value)
        bot.log.info("[command={}, option={}, value={}] option set".format("config", option, value))
        await bot.send_message(message.channel,
                               "{} is now set to {}".format(option, config.__getattr__(option)))


@bot.command(pass_context=True)
async def slug(ctx, slug):
    """Retrieve data for a specific launch."""
    bot.log.info("[command={}, slug={}] command called".format("slug", slug))
    message = ctx.message
    config = get_config_from_message(message)
    await bot.send_typing(message.channel)
    launch = await get_launch_by_slug(slug)
    if launch:
        await send_launch_panel(message.channel, launch, config.timezone)
    else:
        bot.log.warning("[command={}, slug={}] slug not found called".format("slug", slug))
        await bot.send_message(message.channel, "No launch found with slug `{}`.".format(slug))


bot.run(DISCORD_BOT_TOKEN)

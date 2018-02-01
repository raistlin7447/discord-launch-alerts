import sys
from discord.ext import commands
import discord
import aiohttp
from datetime import datetime
from logbook import Logger, StreamHandler
from utils import get_config_from_message, get_launch_embed
from local_config import *

description = "Rocket launch lookup and alert bot."
bot = commands.Bot(command_prefix="!launch ", description=description)
bot.session = aiohttp.ClientSession(loop=bot.loop)

StreamHandler(sys.stdout).push_application()
bot.log = Logger('Launch Alerts Bot')


async def get_multiple_launches(num_launches: int):
    async with bot.session.get('https://www.rocketlaunch.live/json/launch/next/{}'.format(num_launches)) as response:
        if response.status == 200:
            js = await response.json()
            return js["result"]


@bot.event
async def on_ready():
    await bot.change_presence(game=discord.Game(type=0, name="!launch help"))
    bot.log.info('Logged in as')
    bot.log.info(f'Name: {bot.user.name}')
    bot.log.info(f'ID: {bot.user.id}')
    bot.log.info(f'Lib Ver: {discord.__version__}')
    bot.log.info('------')
    if not hasattr(bot, 'uptime'):
        bot.uptime = datetime.utcnow()


@bot.command(pass_context=True)
async def next(ctx, num_launches: int = 1):
    """Get next launch.  Specify an integer to get more than one."""
    message = ctx.message
    config = get_config_from_message(message)
    await bot.send_typing(message.channel)
    launches = await get_multiple_launches(num_launches)
    for launch in launches:
        await bot.send_message(message.channel, embed=get_launch_embed(launch, config.timezone))


@bot.command(pass_context=True)
async def config(ctx, option=None, value=None):
    """Configure settings for this channel."""
    message = ctx.message
    config = get_config_from_message(message)

    if option is None:  # Send Options
        await bot.send_message(message.channel, embed=config.config_options_embed())
    elif value is None:  # Get Value of Option
        await bot.send_message(message.channel,
                               "{} is currently set to {}".format(option, config.__getattr__(option)))
    else:  # Set Value of Option
        config.__setattr__(option, value)
        await bot.send_message(message.channel,
                               "{} is now set to {}".format(option, config.__getattr__(option)))


@bot.command(pass_context=True)
async def slug(ctx, slug):
    """Retrieve data for a specific launch."""
    message = ctx.message
    config = get_config_from_message(message)

bot.run(DISCORD_BOT_TOKEN)

from typing import Union, List, Tuple, Any

import aiohttp
import discord
import pytz
from datetime import datetime
from dateutil.parser import parse
from discord import Message, DMChannel, TextChannel
from pytz import UnknownTimeZoneError

from config import UserConfig, ChannelConfig
from local_config import SERVERS_WITH_TC_INTEGRATION


async def new_aiohttp_connector(*args, **kwargs) -> aiohttp.TCPConnector:
    """*Yes, it's just a coro to instantiate a class.*"""
    return aiohttp.TCPConnector(*args, **kwargs)


def get_config_from_message(message: Message):
    if isinstance(message.channel, DMChannel):
        config = UserConfig(message.author.id)
    else:
        config = ChannelConfig(message.channel.guild.id, message.channel.id)
    return config


def get_config_from_channel(channel: Union[TextChannel, DMChannel]):
    if isinstance(channel, DMChannel):
        config = UserConfig(channel.recipient.id)
    else:
        config = ChannelConfig(channel.guild.id, channel.id)
    return config


def get_config_from_db_key(db_key: str):
    if db_key.startswith(UserConfig.KEY_PREFIX):
        _, _, user_id = db_key.split("-")
        return UserConfig(user_id)
    elif db_key.startswith(ChannelConfig.KEY_PREFIX):
        _, _, server_id, channel_id = db_key.split("-")
        return ChannelConfig(server_id, channel_id)
    raise Exception("Can't match to KEY_PREFIX")


def get_friendly_string_from_seconds(seconds: int):
    if seconds > 0:
        sign = "-"
    else:
        sign = "+"

    seconds = abs(seconds)
    hours = seconds // 3600
    minutes = round(seconds % 3600 // 60)
    s = seconds % 60

    return "L{}{:02}:{:02}:{:02}".format(sign, hours, minutes, s)


def get_seconds_to_launch(launch):
    window_open = get_launch_win_open(launch)
    if window_open:
        seconds_to_launch = int((window_open - datetime.now(pytz.utc)).total_seconds())
        return seconds_to_launch


def is_launching_soon(launch, seconds=24 * 60 * 60):
    seconds_to_launch = get_seconds_to_launch(launch)
    if seconds_to_launch:
        if seconds_to_launch < 0:
            return False
        else:
            return seconds_to_launch <= seconds
    else:
        return False


def has_launched_recently(launch, seconds=24 * 60 * 60):
    seconds_to_launch = get_seconds_to_launch(launch)
    if seconds_to_launch:
        if seconds_to_launch > 0:
            return False
        else:
            seconds_since_launch = -seconds_to_launch
            return seconds_since_launch <= seconds
    else:
        return False


def get_launch_embed(launch, timezone, show_countdown=True, with_tc=False):
    slug = launch["slug"]

    embed = discord.Embed()
    embed.title = "{}".format(launch["name"])

    description = ""
    if get_live_url(launch):
        description += f"Live URL: {get_live_url(launch)}"
    if get_mission_desc(launch):
        description += f'\n{get_mission_desc(launch)}'
    if description:
        embed.description = description

    embed.url = "https://www.rocketlaunch.live/launch/{}".format(slug)
    embed.colour = 0x073349
    footer = f"Data by rocketlaunch.live | {slug}"
    if with_tc:
        footer = f"🔔 Subscribe to TerminalCount\n" + footer
    embed.set_footer(text=footer)

    #  Date Embed Field
    if get_launch_win_open(launch):
        launch_window = get_launch_win_open(launch)
        try:
            timezone = pytz.timezone(timezone)
        except UnknownTimeZoneError:
            timezone = pytz.UTC
        launch_window_local = launch_window.astimezone(timezone)
        launch_window_date_display = launch_window_local.strftime("%I:%M %p %Z").lstrip("0")
        if is_launching_soon(launch) or has_launched_recently(launch):
            seconds_to_launch = get_seconds_to_launch(launch)
            launch_window_display = f"{launch_window_date_display}"
            if show_countdown:
                friendly_time_to_go = get_friendly_string_from_seconds(seconds_to_launch)
                launch_window_display += f"\n{friendly_time_to_go}"
        else:
            launch_window_display = launch_window_date_display

        if get_seconds_to_launch(launch) < 0:   # Launch in the past needs the year to not be confusing
            date_display = launch_window_local.strftime("%b %d, %Y").upper()
        else:
            date_display = launch_window_local.strftime("%b %d").upper()
        embed.add_field(name=date_display, value=launch_window_display)
    else:
        date_display = launch["date_str"].upper()
        embed.add_field(name=date_display, value="Estimated")

    vehicle_name = launch["vehicle"]["name"]
    provider_name = launch["provider"]["name"]
    pad_name = launch["pad"]["name"]
    location_name = launch["pad"]["location"]["name"]
    embed.add_field(name=vehicle_name, value=f'{provider_name}\n{pad_name}, {location_name}')

    return embed


def is_today_launch(launch, timezone):
    launch_window = get_launch_win_open(launch)
    if not launch_window:
        return False

    timezone = pytz.timezone(timezone)

    today_date = datetime.now(timezone).date()
    launch_window_date = launch_window.date()

    return today_date == launch_window_date


def get_server_name_from_channel(channel: Union[TextChannel, DMChannel]) -> Union[str, None]:
    if isinstance(channel, TextChannel):
        return channel.guild.name
    elif isinstance(channel, DMChannel):
        return channel.recipient.name


def get_server_id_from_channel(channel: Union[TextChannel, DMChannel]) -> Union[int, None]:
    if isinstance(channel, TextChannel):
        return channel.guild.id
    elif isinstance(channel, DMChannel):
        return channel.recipient.id


def has_tc_integration(server_id: int) -> bool:
    return True if server_id in SERVERS_WITH_TC_INTEGRATION else False


def convert_quoted_string_in_list(args: Tuple[Any]) -> List:
    new_list = []
    if len(args) == 0:
        pass
    elif args[0].isnumeric():
        new_list.append(args[0])
        if len(args) > 2:
            new_list.append(" ".join(args[1:]))
        elif len(args) > 1:
            new_list += args[1:]
    elif len(args) > 1:
        new_list.append(" ".join(args))
    else:
        new_list = args
    return new_list


def get_launch_win_open(launch: dict) -> datetime:
    if launch["t0"]:
        win_open = launch["t0"]
    else:
        win_open = launch["win_open"]
    if win_open:
        return parse(win_open)


def get_live_url(launch: dict) -> str:
    for media in launch["media"]:
        if media["ldfeatured"]:
            if media["media_url"]:
                return media["media_url"]
            elif media["youtube_vidid"]:
                return f'https://youtu.be/{media["youtube_vidid"]}'


def get_mission_desc(launch: dict) -> str:
    if launch["missions"]:
        if launch["missions"][0]["description"]:
            return launch["missions"][0]["description"]

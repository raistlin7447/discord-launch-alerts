import discord
import pytz
from datetime import datetime
from dateutil.parser import parse
from discord import Message
from config import UserConfig, ChannelConfig


def get_config_from_message(message: Message):
    if message.channel.is_private:
        config = UserConfig(message.author)
    else:
        config = ChannelConfig(message.server)
    return config


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
    window_open = launch["win_open"]
    if window_open:
        launch_window = parse(window_open)
        seconds_to_launch = int((launch_window - datetime.now(pytz.utc)).total_seconds())
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


def get_launch_embed(launch, timezone):
    slug = launch["slug"]

    embed = discord.Embed()
    embed.title = "{}".format(launch["name"])
    if launch["mission_description"]:
        embed.description = launch["mission_description"]
    embed.url = "https://www.rocketlaunch.live/launch/{}".format(slug)
    embed.colour = 0x073349
    embed.set_footer(text="Data by rocketlaunch.live | {}".format(slug))

    #  Date Embed Field
    if launch["win_open"]:
        launch_window = parse(launch["win_open"])
        timezone = pytz.timezone(timezone)
        launch_window_local = launch_window.astimezone(timezone)
        launch_window_date_display = launch_window_local.strftime("%I:%M %p %Z").lstrip("0")
        if is_launching_soon(launch) or has_launched_recently(launch):
            seconds_to_launch = get_seconds_to_launch(launch)
            friendly_time_to_go = get_friendly_string_from_seconds(seconds_to_launch)
            launch_window_display = "{}\n{}".format(launch_window_date_display, friendly_time_to_go)
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

    embed.add_field(name=launch["vehicle"], value="{}\n{}".format(launch["provider"], launch["location"]["name"]))

    return embed


def is_today_launch(launch, timezone):
    if not launch["win_open"]:
        return False

    timezone = pytz.timezone(timezone)

    today_date = datetime.now(timezone).date()
    launch_window = parse(launch["win_open"])
    launch_window_date = launch_window.date()

    return today_date == launch_window_date

import re
from datetime import datetime, timedelta
from typing import List, Optional

import pytz

SECONDS_PER_UNIT = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
ISOFORMAT = "%Y-%m-%dT%H:%M:%S%z"


class InvalidAlertTimeFormat(Exception): pass


class LaunchMonitor:
    def __init__(self):
        self.launch = None
        self.launch_win_open = None
        self.last_alert = None
        self.alert_datetimes = None

    def load(self, data: dict, alert_times: str) -> None:
        self.launch = data["launch_slug"]
        self.launch_win_open = datetime.strptime(data["launch_win_open"], ISOFORMAT)
        self.last_alert = datetime.strptime(data["last_alert"], ISOFORMAT)
        self.alert_datetimes = self._get_alert_datetimes(alert_times)

    def dump(self) -> dict:
        data = {
            "launch_slug": self.launch,
            "launch_win_open": self.launch_win_open.strftime(ISOFORMAT),
            "last_alert": self.last_alert.strftime(ISOFORMAT)
        }
        return data

    @property
    def next_alert_datetime(self) -> Optional[datetime]:
        """
        Get time for next alert.  Return only the most recent past due, or if no past due, return the next due.
        """
        now = datetime.now(pytz.utc)

        past_due_alert = None
        for alert_datetime in self.alert_datetimes:
            if self.last_alert < alert_datetime < now:
                past_due_alert = alert_datetime

        if past_due_alert:
            return past_due_alert

        for alert_datetime in self.alert_datetimes:
            if alert_datetime > now:
                return alert_datetime

    def is_alert_due(self) -> bool:
        alert_datetime = self.next_alert_datetime
        if alert_datetime:
            return alert_datetime < datetime.now(tz=pytz.utc)
        else:
            return False

    def _get_alert_datetimes(self, alert_times: str) -> List[datetime]:
        datetimes_list = []
        alert_times = alert_times.split(',')
        for alert_time in alert_times:
            alert_time = alert_time.strip()
            td = self.get_time_delta_from_str(alert_time)
            datetimes_list.append(self.launch_win_open - td)
        return sorted(datetimes_list)

    @staticmethod
    def is_valid_alert_time_format(alert_time: str) -> bool:
        available_units = "".join(SECONDS_PER_UNIT.keys())
        if re.match(r"^(\d{1,5}[" + available_units + "])+$", alert_time):
            return True
        else:
            return False

    @staticmethod
    def get_time_delta_from_str(alert_time: str) -> timedelta:
        if not LaunchMonitor.is_valid_alert_time_format(alert_time):
            raise InvalidAlertTimeFormat
        available_units = "".join(SECONDS_PER_UNIT.keys())
        split_by_unit = re.findall(r"\d{1,5}[" + available_units + "]", alert_time)

        seconds = 0
        for unit in split_by_unit:
            numeral = int(unit[:-1])
            letter = unit[-1:]
            seconds += numeral * SECONDS_PER_UNIT[letter]
        return timedelta(seconds=seconds)

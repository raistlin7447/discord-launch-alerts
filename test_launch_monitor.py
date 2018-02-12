import unittest
from datetime import timedelta, datetime

import pytz
from freezegun import freeze_time

from launch_monitor import LaunchMonitor


class TestLaunchMonitor(unittest.TestCase):

    def test_get_time_delta_from_str(self):
        self.assertEqual(LaunchMonitor.get_time_delta_from_str("1s"), timedelta(seconds=1))
        self.assertEqual(LaunchMonitor.get_time_delta_from_str("1m"), timedelta(seconds=60))
        self.assertEqual(LaunchMonitor.get_time_delta_from_str("1h"), timedelta(seconds=3600))
        self.assertEqual(LaunchMonitor.get_time_delta_from_str("1d"), timedelta(seconds=86400))
        self.assertEqual(LaunchMonitor.get_time_delta_from_str("1w"), timedelta(seconds=604800))

        self.assertEqual(LaunchMonitor.get_time_delta_from_str("1h1s"), timedelta(seconds=3601))
        self.assertEqual(LaunchMonitor.get_time_delta_from_str("3h"), timedelta(seconds=10800))
        self.assertEqual(LaunchMonitor.get_time_delta_from_str("1d3h2s"), timedelta(seconds=97202))
        self.assertEqual(LaunchMonitor.get_time_delta_from_str("2s3h1d"), timedelta(seconds=97202))

    def test_is_valid_alert_time_format(self):
        self.assertEqual(LaunchMonitor.is_valid_alert_time_format("1s"), True)
        self.assertEqual(LaunchMonitor.is_valid_alert_time_format("1m"), True)
        self.assertEqual(LaunchMonitor.is_valid_alert_time_format("1h"), True)
        self.assertEqual(LaunchMonitor.is_valid_alert_time_format("1d"), True)
        self.assertEqual(LaunchMonitor.is_valid_alert_time_format("152w"), True)
        self.assertEqual(LaunchMonitor.is_valid_alert_time_format("15w3d1s"), True)

        self.assertEqual(LaunchMonitor.is_valid_alert_time_format("1ss"), False)
        self.assertEqual(LaunchMonitor.is_valid_alert_time_format("2hh1s"), False)
        self.assertEqual(LaunchMonitor.is_valid_alert_time_format("23df12f"), False)
        self.assertEqual(LaunchMonitor.is_valid_alert_time_format("fail"), False)
        self.assertEqual(LaunchMonitor.is_valid_alert_time_format("123456h"), False)

    def test_dump(self):
        lm = LaunchMonitor()
        data = {
            "server": "360523650912223253",
            "channel": "general",
            "launch_slug": "test-slug",
            "launch_win_open": "2018-02-12T14:00:00+0000",
            "last_alert": "2018-02-12T02:00:00+0000"
        }
        lm.load(data, "24h, 12h, 6h, 3h, 1h, 15m")
        self.assertEqual(lm.dump(), data)

    @freeze_time("2018-02-12 08:10:00+00:00")
    def test_next_alert_datetime(self):
        # No alerts yet
        lm = LaunchMonitor()
        data = {
            "server": "360523650912223253",
            "channel": "general",
            "launch_slug": "test-slug",
            "launch_win_open": "2018-02-12T14:00:00+0000",
            "last_alert": None
        }
        lm.load(data, "24h, 12h, 6h, 3h, 1h, 15m")
        self.assertEqual(lm.next_alert_datetime, datetime(2018, 2, 12, 8, 0, 0, tzinfo=pytz.utc))

        # One missed alert, should choose the 6h
        lm = LaunchMonitor()
        data = {
            "server": "360523650912223253",
            "channel": "general",
            "launch_slug": "test-slug",
            "launch_win_open": "2018-02-12T14:00:00+0000",
            "last_alert": "2018-02-12T02:00:00+0000"
        }
        lm.load(data, "24h, 12h, 6h, 3h, 1h, 15m")
        self.assertEqual(lm.next_alert_datetime, datetime(2018, 2, 12, 8, 0, 0, tzinfo=pytz.utc))

        # Multiple missed alerts, should choose the 15m
        lm = LaunchMonitor()
        data = {
            "server": "360523650912223253",
            "channel": "general",
            "launch_slug": "test-slug",
            "launch_win_open": "2018-02-12T08:17:00+0000",
            "last_alert": "2018-02-12T02:00:00+0000"
        }
        lm.load(data, "24h, 12h, 6h, 3h, 1h, 15m")
        self.assertEqual(lm.next_alert_datetime, datetime(2018, 2, 12, 8, 2, 0, tzinfo=pytz.utc))

        # No missed alerts, one left, should choose the 15m
        lm = LaunchMonitor()
        data = {
            "server": "360523650912223253",
            "channel": "general",
            "launch_slug": "test-slug",
            "launch_win_open": "2018-02-12T09:05:00+0000",
            "last_alert": "2018-02-12T08:09:00+0000"
        }
        lm.load(data, "24h, 12h, 6h, 3h, 1h, 15m")
        self.assertEqual(lm.next_alert_datetime, datetime(2018, 2, 12, 8, 50, 0, tzinfo=pytz.utc))

        # No missed alerts, none left, should return None
        lm = LaunchMonitor()
        data = {
            "server": "360523650912223253",
            "channel": "general",
            "launch_slug": "test-slug",
            "launch_win_open": "2018-02-12T08:15:00+0000",
            "last_alert": "2018-02-12T08:05:00+0000"
        }
        lm.load(data, "24h, 12h, 6h, 3h, 1h, 15m")
        self.assertEqual(lm.next_alert_datetime, None)

    @freeze_time("2018-02-12 08:10:00+00:00")
    def test_is_alert_due(self):
        # No alerts sent yet
        lm = LaunchMonitor()
        data = {
            "server": "360523650912223253",
            "channel": "general",
            "launch_slug": "test-slug",
            "launch_win_open": "2018-02-12T14:00:00+0000",
            "last_alert": None
        }
        lm.load(data, "24h, 12h, 6h, 3h, 1h, 15m")
        self.assertEqual(lm.is_alert_due(), True)

        # One missed alert
        lm = LaunchMonitor()
        data = {
            "server": "360523650912223253",
            "channel": "general",
            "launch_slug": "test-slug",
            "launch_win_open": "2018-02-12T14:00:00+0000",
            "last_alert": "2018-02-12T02:00:00+0000"
        }
        lm.load(data, "24h, 12h, 6h, 3h, 1h, 15m")
        self.assertEqual(lm.is_alert_due(), True)

        # Multiple missed alerts
        lm = LaunchMonitor()
        data = {
            "server": "360523650912223253",
            "channel": "general",
            "launch_slug": "test-slug",
            "launch_win_open": "2018-02-12T08:17:00+0000",
            "last_alert": "2018-02-12T02:00:00+0000"
        }
        lm.load(data, "24h, 12h, 6h, 3h, 1h, 15m")
        self.assertEqual(lm.is_alert_due(), True)

        # No missed alerts, one left
        lm = LaunchMonitor()
        data = {
            "server": "360523650912223253",
            "channel": "general",
            "launch_slug": "test-slug",
            "launch_win_open": "2018-02-12T09:05:00+0000",
            "last_alert": "2018-02-12T08:09:00+0000"
        }
        lm.load(data, "24h, 12h, 6h, 3h, 1h, 15m")
        self.assertEqual(lm.is_alert_due(), False)

        # No missed alerts, none left
        lm = LaunchMonitor()
        data = {
            "server": "360523650912223253",
            "channel": "general",
            "launch_slug": "test-slug",
            "launch_win_open": "2018-02-12T08:15:00+0000",
            "last_alert": "2018-02-12T08:05:00+0000"
        }
        lm.load(data, "24h, 12h, 6h, 3h, 1h, 15m")
        self.assertEqual(lm.is_alert_due(), False)

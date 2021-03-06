import unittest
from freezegun import freeze_time
from utils import get_friendly_string_from_seconds, get_seconds_to_launch, is_launching_soon, has_launched_recently, \
    convert_quoted_string_in_list


class TestUtils(unittest.TestCase):
    def test_get_friendly_string_from_seconds(self):
        self.assertEqual(get_friendly_string_from_seconds(1), "L-00:00:01")
        self.assertEqual(get_friendly_string_from_seconds(0), "L+00:00:00")
        self.assertEqual(get_friendly_string_from_seconds(60), "L-00:01:00")
        self.assertEqual(get_friendly_string_from_seconds(61), "L-00:01:01")
        self.assertEqual(get_friendly_string_from_seconds(3600), "L-01:00:00")
        self.assertEqual(get_friendly_string_from_seconds(86400), "L-24:00:00")
        self.assertEqual(get_friendly_string_from_seconds(3820), "L-01:03:40")
        self.assertEqual(get_friendly_string_from_seconds(-65), "L+00:01:05")
        self.assertEqual(get_friendly_string_from_seconds(77431), "L-21:30:31")
        self.assertEqual(get_friendly_string_from_seconds(77430), "L-21:30:30")
        self.assertEqual(get_friendly_string_from_seconds(77429), "L-21:30:29")

    @freeze_time("2018-02-06 08:46:23+00:00")
    def test_get_seconds_to_launch(self):
        launch = {"win_open": None, "t0": None}
        self.assertEqual(get_seconds_to_launch(launch), None)
        launch = {"win_open": "2018-02-06T18:30:00+00:00", "t0": None}
        self.assertEqual(get_seconds_to_launch(launch), 35017)
        launch = {"win_open": "2018-02-06T18:30:00+00:00", "t0": "2018-02-06T18:40:00+00:00"}
        self.assertEqual(get_seconds_to_launch(launch), 35617)
        launch = {"win_open": "2018-02-06T08:46:25+00:00", "t0": None}
        self.assertEqual(get_seconds_to_launch(launch), 2)
        launch = {"win_open": "2018-02-06T08:46:25+00:00", "t0": "2018-02-06T08:46:26+00:00"}
        self.assertEqual(get_seconds_to_launch(launch), 3)
        launch = {"win_open": "2018-02-06T08:46:21+00:00", "t0": None}  # Past
        self.assertEqual(get_seconds_to_launch(launch), -2)

    @freeze_time("2018-02-06 08:46:23+00:00")
    def test_is_launching_soon(self):
        launch = {"win_open": None, "t0": None}
        self.assertEqual(is_launching_soon(launch), False)
        launch = {"win_open": "2018-02-06T18:30:00+00:00", "t0": None}
        self.assertEqual(is_launching_soon(launch), True)
        launch = {"win_open": "2018-02-06T18:30:00+00:00", "t0": "2018-02-06T18:31:00+00:00"}
        self.assertEqual(is_launching_soon(launch), True)
        launch = {"win_open": "2018-02-06T08:46:25+00:00", "t0": None}
        self.assertEqual(is_launching_soon(launch), True)
        launch = {"win_open": "2018-02-06T08:46:25+00:00", "t0": "2018-02-08T08:46:25+00:00"}
        self.assertEqual(is_launching_soon(launch), False)
        launch = {"win_open": "2018-02-06T08:46:21+00:00", "t0": None}  # Past
        self.assertEqual(is_launching_soon(launch), False)
        launch = {"win_open": "2018-03-06T08:46:21+00:00", "t0": None}
        self.assertEqual(is_launching_soon(launch), False)

    @freeze_time("2018-02-06 08:46:23+00:00")
    def test_has_launched_recently(self):
        launch = {"win_open": None, "t0": None}
        self.assertEqual(has_launched_recently(launch), False)
        launch = {"win_open": "2018-02-06T18:30:00+00:00", "t0": None}
        self.assertEqual(has_launched_recently(launch), False)
        launch = {"win_open": "2018-02-06T08:46:25+00:00", "t0": None}
        self.assertEqual(has_launched_recently(launch), False)
        launch = {"win_open": "2018-02-06T08:46:25+00:00", "t0": "2018-02-06T08:46:26+00:00"}
        self.assertEqual(has_launched_recently(launch), False)
        launch = {"win_open": "2018-02-06T08:46:25+00:00", "t0": "2018-02-06T08:46:21+00:00"}
        self.assertEqual(has_launched_recently(launch), True)
        launch = {"win_open": "2018-02-06T08:46:21+00:00", "t0": None}  # Past
        self.assertEqual(has_launched_recently(launch), True)
        launch = {"win_open": "2018-02-06T08:40:23+00:00", "t0": None}  # Past
        self.assertEqual(has_launched_recently(launch), True)
        launch = {"win_open": "2018-02-06T08:40:23+00:00", "t0": "2018-02-06T08:41:23+00:00"}  # Past
        self.assertEqual(has_launched_recently(launch), True)
        launch = {"win_open": "2018-02-01T08:40:23+00:00", "t0": None}  # Past
        self.assertEqual(has_launched_recently(launch), False)
        launch = {"win_open": "2018-03-06T08:46:21+00:00", "t0": None}
        self.assertEqual(has_launched_recently(launch), False)

    def test_convert_quoted_string_in_list(self):
        self.assertEqual(convert_quoted_string_in_list([]), [])
        self.assertEqual(convert_quoted_string_in_list(['3']), ['3'])
        self.assertEqual(convert_quoted_string_in_list(['3', 'falcon']), ['3', 'falcon'])
        self.assertEqual(convert_quoted_string_in_list(['falcon']), ['falcon'])
        self.assertEqual(convert_quoted_string_in_list(['3', 'falcon', '9']), ['3', 'falcon 9'])
        self.assertEqual(convert_quoted_string_in_list(['3', 'falcon 9']), ['3', 'falcon 9'])
        self.assertEqual(convert_quoted_string_in_list(['falcon', '9']), ['falcon 9'])
        self.assertEqual(convert_quoted_string_in_list(['falcon 9']), ['falcon 9'])
        self.assertEqual(convert_quoted_string_in_list(['5', 'united', 'launch', 'alliance']), ['5', 'united launch alliance'])
        self.assertEqual(convert_quoted_string_in_list(['5', 'united launch', 'alliance']), ['5', 'united launch alliance'])
        self.assertEqual(convert_quoted_string_in_list(['5', 'united launch alliance']), ['5', 'united launch alliance'])

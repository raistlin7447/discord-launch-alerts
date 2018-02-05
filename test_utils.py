import unittest

from utils import get_friendly_string_from_seconds


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

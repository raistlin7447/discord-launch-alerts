import unittest
from utils import convert_quoted_string_in_list


class TestUtils(unittest.TestCase):
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

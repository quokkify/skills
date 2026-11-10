import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import ids  # noqa: E402


class IdsTest(unittest.TestCase):
    def test_slugify_cyrillic(self):
        self.assertEqual(ids.slugify("Как это работает"), "kak-eto-rabotaet")

    def test_slugify_limits_length(self):
        s = ids.slugify("word " * 30)
        self.assertLessEqual(len(s), 40)
        self.assertFalse(s.endswith("-"))

    def test_spot_id_stable_on_whitespace(self):
        a = ids.spot_id("ch", "p", "hello   world\n", set())
        b = ids.spot_id("ch", "p", "  hello world", set())
        self.assertEqual(a, b)
        self.assertRegex(a, r"^ch-p-[0-9a-f]{6}$")

    def test_spot_id_collision_suffix(self):
        seen = set()
        first = ids.spot_id("ch", "li", "same", seen)
        second = ids.spot_id("ch", "li", "same", seen)
        third = ids.spot_id("ch", "li", "same", seen)
        self.assertEqual([second, third], [first + "-2", first + "-3"])

    def test_node_spot_id(self):
        self.assertEqual(ids.node_spot_id("how", "A1"), "how-A1")


if __name__ == "__main__":
    unittest.main()

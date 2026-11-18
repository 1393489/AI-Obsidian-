"""Title hygiene.

Two failures people actually saw: a page H1 ending on a dangling bracket
(``…DSH(De``) because the cut landed mid-token, and conversation text turning
into a wikilink to a page that will never exist.
"""

import unittest

from memloom.render import _neutralize_links
from memloom.util import settle, tighten


class TightenTest(unittest.TestCase):
    def test_short_enough_is_untouched(self):
        self.assertEqual(tighten("short", 40), "short")

    def test_breaks_on_a_space_not_mid_word(self):
        got = tighten("alpha beta gamma delta epsilon zeta", 20)
        self.assertTrue(got.endswith("…"))
        self.assertEqual(got, "alpha beta gamma…")

    def test_drops_a_dangling_opener(self):
        got = tighten("把一份 DSH(DeepSeek Harness) 的会话", 20)
        self.assertNotIn("(", got)
        self.assertEqual(got, "把一份 DSH…")

    def test_never_exceeds_limit_plus_ellipsis(self):
        self.assertLessEqual(len(tighten("x" * 200, 30)), 31)

    def test_survives_a_string_that_is_only_brackets(self):
        self.assertTrue(tighten("((((((", 4))


class SettleTest(unittest.TestCase):
    def test_repairs_an_archive_truncated_title(self):
        # Exactly what one DSH archive stores as its own session title.
        self.assertEqual(settle("你是资料提炼员。把一份 DSH(De"), "你是资料提炼员。把一份 DSH")

    def test_leaves_a_balanced_title_alone(self):
        title = "修好 fix(a, b) 的边界"
        self.assertEqual(settle(title), title)

    def test_trims_a_trailing_separator(self):
        self.assertEqual(settle("出错了： -"), "出错了")


class NeutralizeTest(unittest.TestCase):
    def test_escapes_a_quoted_wikilink(self):
        self.assertEqual(_neutralize_links("看看 [[双链]]"), "看看 \\[[双链]]")

    def test_leaves_ordinary_brackets(self):
        self.assertEqual(_neutralize_links("[1] 列表"), "[1] 列表")

"""The whole pipeline against the fixtures: build, idempotency, and safe cleaning."""
import os
import shutil
import unittest

from memloom.render import GENERATED_MARK, GUIDE_NAME, INDEX_NAME
from memloom.vault import build

from ._helpers import FIX, mktemp

HAVE_FIXTURES = os.path.isdir(FIX) and any(n.endswith(".jsonl") for n in os.listdir(FIX))


@unittest.skipUnless(HAVE_FIXTURES, "fixtures missing")
class BuildTest(unittest.TestCase):
    def setUp(self):
        self.out = mktemp()

    def tearDown(self):
        shutil.rmtree(self.out, ignore_errors=True)

    def run_build(self, **kw):
        return build(self.out, roots=[("", FIX)], quiet=True, **kw)

    def test_vault_layout(self):
        res = self.run_build()
        self.assertGreaterEqual(res["sessions"], 2)
        self.assertGreater(res["pages"], 5)
        self.assertTrue(os.path.isfile(os.path.join(self.out, INDEX_NAME + ".md")))
        self.assertTrue(os.path.isfile(os.path.join(self.out, GUIDE_NAME + ".md")))
        self.assertTrue(os.path.isdir(os.path.join(self.out, "20-会话")))
        self.assertEqual(res["problems"], [])

    def test_second_run_writes_nothing(self):
        self.run_build()
        again = self.run_build()
        self.assertEqual(again["written"], 0)
        self.assertEqual(again["pruned"], 0)

    def test_hand_written_notes_survive(self):
        self.run_build()
        mine = os.path.join(self.out, "20-会话", "我的笔记.md")
        with open(mine, "w", encoding="utf-8") as fh:
            fh.write("# 手写的\n")
        self.run_build()
        self.assertTrue(os.path.isfile(mine), "a file without the generated marker must be kept")

    def test_stale_generated_pages_are_pruned(self):
        self.run_build()
        stale = os.path.join(self.out, "20-会话", "过期.md")
        with open(stale, "w", encoding="utf-8") as fh:
            fh.write(GENERATED_MARK + " v0.0.0 -->\n# 过期\n")
        res = self.run_build()
        self.assertFalse(os.path.isfile(stale))
        self.assertGreaterEqual(res["pruned"], 1)

    def test_dry_run_writes_nothing(self):
        res = self.run_build(dry_run=True)
        self.assertGreater(res["files"], 0)
        self.assertEqual(os.listdir(self.out), [])

    def test_empty_source_is_reported(self):
        empty = mktemp()
        try:
            res = build(self.out, roots=[("", empty)], quiet=True)
            self.assertEqual(res["sessions"], 0)
        finally:
            shutil.rmtree(empty, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

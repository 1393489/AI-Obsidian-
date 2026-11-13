"""Incremental-scan cache: serialisation round-trip and rebuild behaviour."""

import json
import os
import shutil
import time
import unittest

from memloom.adapters import get_adapter
from memloom.state import Cache, session_from_dict, session_to_dict
from memloom.vault import build

from ._helpers import FIX, mktemp

FIXTURES = ("dsh-session.jsonl", "claude-session.jsonl", "codex-rollout.jsonl")


class _SessionRoundTripTest(unittest.TestCase):
    def test_roundtrip_keeps_everything(self):
        s = get_adapter("dsh").load(os.path.join(FIX, "dsh-session.jsonl"))
        self.assertIsNotNone(s)
        back = session_from_dict(json.loads(json.dumps(session_to_dict(s), default=str)))
        self.assertEqual(back.id, s.id)
        self.assertEqual(back.source, s.source)
        self.assertEqual(back.adapter, s.adapter)
        self.assertEqual(back.title, s.title)
        self.assertEqual(back.cwd, s.cwd)
        self.assertEqual(back.started_at, s.started_at)
        self.assertEqual(back.ended_at, s.ended_at)
        self.assertEqual(len(back.turns), len(s.turns))
        self.assertEqual(back.n_tools, s.n_tools)
        for a, b in zip(s.turns, back.turns):
            self.assertEqual(b.index, a.index)
            self.assertEqual(b.prompt, a.prompt)
            self.assertEqual(b.reply, a.reply)
            self.assertEqual([t.name for t in b.tools], [t.name for t in a.tools])
            self.assertEqual([t.ok for t in b.tools], [t.ok for t in a.tools])
        self.assertEqual(back.errors, s.errors)


class _CacheUnitTest(unittest.TestCase):
    def setUp(self):
        self.dir = mktemp()
        self.src = os.path.join(self.dir, "a.jsonl")
        shutil.copy2(os.path.join(FIX, "claude-session.jsonl"), self.src)
        self.out = os.path.join(self.dir, "vault")

    def test_miss_then_hit(self):
        s = get_adapter("claude-code").load(self.src)
        cache = Cache(self.out).load()
        self.assertIsNone(cache.lookup(self.src, "claude-code"))
        cache.store(self.src, "claude-code", s)
        cache.save()

        fresh = Cache(self.out).load()
        got = fresh.lookup(self.src, "claude-code")
        self.assertIsNotNone(got)
        self.assertEqual(got.id, s.id)
        self.assertEqual(fresh.reused, 1)

    def test_adapter_change_invalidates(self):
        s = get_adapter("claude-code").load(self.src)
        cache = Cache(self.out).load()
        cache.store(self.src, "claude-code", s)
        cache.save()
        self.assertIsNone(Cache(self.out).load().lookup(self.src, "codex"))

    def test_touch_invalidates(self):
        s = get_adapter("claude-code").load(self.src)
        cache = Cache(self.out).load()
        cache.store(self.src, "claude-code", s)
        cache.save()
        st = os.stat(self.src)
        os.utime(self.src, (st.st_atime, st.st_mtime + 5))
        self.assertIsNone(Cache(self.out).load().lookup(self.src, "claude-code"))

    def test_stale_entries_are_dropped(self):
        s = get_adapter("claude-code").load(self.src)
        cache = Cache(self.out).load()
        cache.store(self.src, "claude-code", s)
        cache.save()
        blob = os.path.join(self.out, ".memloom", "cache")
        self.assertTrue(os.listdir(blob))

        os.remove(self.src)
        fresh = Cache(self.out).load()      # holds the entry, but no file touches it
        fresh.save()                        # nothing used -> blob pruned
        self.assertFalse(os.listdir(blob))


class _IncrementalBuildTest(unittest.TestCase):
    def setUp(self):
        self.dir = mktemp()
        self.src = os.path.join(self.dir, "archives")
        os.makedirs(self.src)
        for fn in FIXTURES:
            shutil.copy2(os.path.join(FIX, fn), os.path.join(self.src, fn))
        self.out = os.path.join(self.dir, "vault")

    def run_build(self, **kw):
        return build(self.out, roots=[("", self.src)], quiet=True, **kw)

    def test_first_build_parses_everything(self):
        res = self.run_build()
        self.assertTrue(res["ok"])
        self.assertFalse(res["full"])
        self.assertEqual(res["parsed"], len(FIXTURES))
        self.assertEqual(res["reused"], 0)

    def test_second_build_reuses_and_writes_nothing(self):
        first = self.run_build()
        second = self.run_build()
        self.assertEqual(second["reused"], len(FIXTURES))
        self.assertEqual(second["parsed"], 0)
        self.assertEqual(second["written"], 0)
        self.assertEqual(second["pages"], first["pages"])
        self.assertEqual(second["sessions"], first["sessions"])

    def test_changed_file_is_reparsed_alone(self):
        first = self.run_build()
        target = os.path.join(self.src, "claude-session.jsonl")
        with open(target, "a", encoding="utf-8") as fh:
            fh.write('\n{"type":"system","subtype":"notice","text":"extra"}\n')
        now = time.time() + 3
        os.utime(target, (now, now))

        second = self.run_build()
        self.assertEqual(second["parsed"], 1)
        self.assertEqual(second["reused"], len(FIXTURES) - 1)
        self.assertEqual(second["sessions"], first["sessions"])

    def test_full_flag_ignores_cache(self):
        self.run_build()
        res = self.run_build(full=True)
        self.assertEqual(res["reused"], 0)
        self.assertEqual(res["parsed"], len(FIXTURES))
        self.assertTrue(res["full"])
        # --full still refreshes the cache, so the next plain build is fast again
        again = self.run_build()
        self.assertEqual(again["reused"], len(FIXTURES))

    def test_dry_run_does_not_write_cache(self):
        self.run_build(dry_run=True)
        self.assertFalse(os.path.exists(os.path.join(self.out, ".memloom")))


class _WriterTest(unittest.TestCase):
    def test_crlf_page_is_not_rewritten_forever(self):
        from memloom.vault import _uniq_page_names, _write

        d = mktemp()
        body = "line one\r\nline two\r\n"
        self.assertEqual(_write(d, "a.md", body), 1)
        self.assertEqual(_write(d, "a.md", body), 0)
        self.assertEqual(_write(d, "a.md", "line one\nline two\n"), 0)
        with open(os.path.join(d, "a.md"), "rb") as fh:
            self.assertNotIn(b"\r", fh.read())

        pages = [("t/A.md", "one"), ("t/A.md", "two")]
        names = [rel for rel, _ in _uniq_page_names(pages)]
        self.assertEqual(len(names), 2)
        self.assertNotEqual(names[0], names[1])
        self.assertTrue(all(n.startswith("t/A-") or n == "t/A.md" for n in names))
        self.assertEqual(len(_uniq_page_names([("t/A.md", "same"), ("t/A.md", "same")])), 1)
        self.assertEqual([n for n, _ in _uniq_page_names([("t/B.md", "b")])], ["t/B.md"])


if __name__ == "__main__":
    unittest.main()

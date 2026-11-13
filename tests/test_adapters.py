"""Adapters: each archive dialect is recognised and parsed without third-party code."""
import json
import os
import shutil
import unittest

from memloom.adapters import detect_adapter, get_adapter

from ._helpers import FIX, fixture, mktemp

HAVE = set(os.listdir(FIX)) if os.path.isdir(FIX) else set()


class DetectTest(unittest.TestCase):
    def test_each_fixture_is_recognised(self):
        for name, adapter in (
            ("dsh-session.jsonl", "dsh"),
            ("claude-session.jsonl", "claude-code"),
            ("codex-rollout.jsonl", "codex"),
        ):
            if name not in HAVE:
                continue
            a = detect_adapter(fixture(name))
            self.assertIsNotNone(a, name)
            self.assertEqual(a.name, adapter, name)

    def test_minified_dsh_events_are_recognised(self):
        """Real DSH archives are one compact JSON object per line, not pretty-printed."""
        rows = [
            {"type": "session", "version": 4, "seq": 0, "id": "session-x",
             "createdAt": 1793446721580, "cwd": "C:\\work\\proj"},
            {"type": "user/message", "seq": 1, "time": 1793446722000,
             "data": {"role": "user", "content": [{"type": "text", "text": "hi"}]}},
        ]
        d = mktemp()
        try:
            p = os.path.join(d, "s.jsonl")
            with open(p, "w", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r, separators=(",", ":")) + "\n")
            a = detect_adapter(p)
            self.assertIsNotNone(a)
            self.assertEqual(a.name, "dsh")
            s = a.load(p)
            self.assertIsNotNone(s)
            self.assertEqual(s.id, "session-x")
            self.assertEqual(len(s.turns), 1)
            self.assertEqual(s.turns[0].prompt, "hi")
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_unknown_json_is_not_claimed(self):
        d = mktemp()
        try:
            p = os.path.join(d, "notes.jsonl")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write('{"hello": "world"}\n')
            self.assertIsNone(detect_adapter(p))
        finally:
            shutil.rmtree(d, ignore_errors=True)


class DshLoadTest(unittest.TestCase):
    @unittest.skipUnless("dsh-session.jsonl" in HAVE, "fixture missing")
    def test_session_shape(self):
        s = get_adapter("dsh").load(fixture("dsh-session.jsonl"))
        self.assertIsNotNone(s)
        self.assertTrue(s.id)
        self.assertTrue(s.turns, "should parse at least one turn")
        self.assertTrue(s.started_at, "should know when it started")
        self.assertEqual(os.path.abspath(s.source),
                         os.path.abspath(fixture("dsh-session.jsonl")))
        for t in s.turns:
            self.assertNotIn("tool-call", t.reply or "")

    @unittest.skipUnless("dsh-session.jsonl" in HAVE, "fixture missing")
    def test_tool_calls_are_not_double_counted(self):
        s = get_adapter("dsh").load(fixture("dsh-session.jsonl"))
        calls = sum(len(t.tools) for t in s.turns)
        self.assertGreater(calls, 0)
        self.assertEqual(calls, s.n_tools)


class ClaudeLoadTest(unittest.TestCase):
    @unittest.skipUnless("claude-session.jsonl" in HAVE, "fixture missing")
    def test_session_shape(self):
        s = get_adapter("claude-code").load(fixture("claude-session.jsonl"))
        self.assertIsNotNone(s)
        self.assertTrue(s.turns)
        self.assertTrue(any(t.prompt or t.reply for t in s.turns))


class CodexLoadTest(unittest.TestCase):
    @unittest.skipUnless("codex-rollout.jsonl" in HAVE, "fixture missing")
    def test_synthetic_rollout(self):
        s = get_adapter("codex").load(fixture("codex-rollout.jsonl"))
        self.assertIsNotNone(s)
        self.assertEqual(len(s.turns), 1)
        self.assertIn("测试", s.turns[0].prompt)
        self.assertEqual([tu.name for tu in s.turns[0].tools], ["shell"])
        self.assertFalse(s.turns[0].tools[0].ok)


if __name__ == "__main__":
    unittest.main()

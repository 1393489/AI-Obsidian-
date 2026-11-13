"""Naming and grouping: the part users judge first, and the easiest to get wrong."""
import unittest

from memloom.group import analyze, group_projects, group_topics
from memloom.model import Session, ToolUse, Turn
from memloom.util import clip_text, safe_name, slug


def mk(sid, cwd, prompt, tools=(), reply="好的，已经改完。"):
    s = Session(id=sid, source="/tmp/" + sid, adapter="dsh", cwd=cwd, title=sid)
    s.started_at = 1793446721580
    turn = Turn(index=1)
    turn.prompt = prompt
    turn.reply = reply
    turn.tools = [ToolUse(name=n, summary=a, ok=True) for n, a in tools]
    s.turns = [turn]
    return s


class SafeNameTest(unittest.TestCase):
    def test_path_separators_become_fullwidth(self):
        self.assertEqual(safe_name("C:/work/app"), "C：／work／app")
        self.assertNotIn("/", safe_name("a/b/c"))

    def test_long_names_are_cut_at_a_boundary(self):
        out = safe_name("Error: cannot read path- file has not been rea", 24)
        self.assertLessEqual(len(out), 25)
        self.assertNotIn("rea…", out.replace("read…", ""))

    def test_empty_becomes_untitled(self):
        self.assertEqual(safe_name(""), "untitled")
        self.assertEqual(safe_name("///"), "untitled")

    def test_slug_is_ascii(self):
        self.assertEqual(slug("Hello World 你好"), "hello-world")
        self.assertTrue(slug(""))


class ClipTest(unittest.TestCase):
    def test_short_text_is_untouched(self):
        self.assertEqual(clip_text("abc", 10), "abc")

    def test_long_text_gets_an_ellipsis(self):
        out = clip_text("word " * 100, 40)
        self.assertLess(len(out), 60)
        self.assertTrue(out.endswith("…"))


class ProjectNamingTest(unittest.TestCase):
    def test_sessions_sharing_a_folder_and_files_form_one_project(self):
        sessions = {
            "a": mk("a", "D:/w/alpha", "改 D:/w/alpha/src/app.ts"),
            "b": mk("b", "D:/w/alpha", "再看 D:/w/alpha/src/app.ts 的测试"),
            "c": mk("c", "D:/w/alpha", "顺手 D:/w/alpha/src/app.ts 格式化"),
        }
        facts = {sid: analyze(s) for sid, s in sessions.items()}
        projects = group_projects(sessions, facts)
        self.assertEqual(len(projects), 1)
        self.assertIn("alpha", projects[0].name)
        self.assertEqual(projects[0].n_sessions, 3)

    def test_different_cwds_stay_apart(self):
        sessions = {
            "a": mk("a", "D:/w/alpha", "改 D:/w/alpha/main.py"),
            "b": mk("b", "D:/w/beta", "改 D:/w/beta/main.py"),
        }
        facts = {sid: analyze(s) for sid, s in sessions.items()}
        names = [p.name for p in group_projects(sessions, facts)]
        self.assertEqual(len(names), 2)
        self.assertEqual(len(set(names)), 2, names)

    def test_no_duplicate_names_after_split(self):
        sessions = {}
        for i in range(8):
            cwd = "D:/w/big" if i < 4 else "D:/w/big/sub{}".format(i)
            sessions["s%d" % i] = mk(
                "s%d" % i, cwd, "改 D:/w/big/shared%d/file%d.ts" % (i % 2, i)
            )
        facts = {sid: analyze(s) for sid, s in sessions.items()}
        names = [p.name for p in group_projects(sessions, facts, split_threshold=2)]
        self.assertEqual(len(names), len(set(names)), names)

    def test_unnamed_cwd_is_labelled(self):
        sessions = {"a": mk("a", None, "改 C:/w/x/main.py")}
        facts = {sid: analyze(s) for sid, s in sessions.items()}
        projects = group_projects(sessions, facts)
        self.assertEqual(len(projects), 1)
        self.assertTrue(projects[0].name)


class TopicTest(unittest.TestCase):
    def test_shared_failure_becomes_a_pitfall(self):
        sessions = {
            "a": mk("a", "D:/w/a", "跑测试", reply="Error: cannot read C:/w/a.ts — not found"),
            "b": mk("b", "D:/w/b", "跑测试", reply="Error: cannot read D:/w/b.ts — not found"),
        }
        facts = {sid: analyze(s) for sid, s in sessions.items()}
        topics = group_topics(sessions, facts)
        pitfalls = [t for t in topics if t.category == "踩坑"]
        self.assertEqual(len(pitfalls), 1)
        self.assertEqual(len(pitfalls[0].sessions), 2)

    def test_one_off_failure_is_not_a_topic(self):
        sessions = {"a": mk("a", "D:/w/a", "跑测试", reply="Error: boom in C:/w/a.ts")}
        facts = {sid: analyze(s) for sid, s in sessions.items()}
        self.assertEqual([t for t in group_topics(sessions, facts) if t.category == "踩坑"], [])

    def test_generic_folders_do_not_become_code_topics(self):
        sessions = {
            sid: mk(sid, "D:/w/p", "改 D:/w/p/shared/x{}.ts".format(sid))
            for sid in ("a", "b", "c")
        }
        facts = {sid: analyze(s) for sid, s in sessions.items()}
        code = [t for t in group_topics(sessions, facts) if t.category == "代码"]
        self.assertEqual([t.title for t in code if t.title.lower() == "shared"], [])


if __name__ == "__main__":
    unittest.main()

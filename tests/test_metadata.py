"""The version is written in two places; a drift between them ships a release
whose ``--version`` disagrees with its own tag (and with the generated-file
marker in render.py, which stamps every page)."""

import os
import re
import unittest

import memloom

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class VersionSyncTest(unittest.TestCase):
    def test_pyproject_and_package_agree(self):
        with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as fh:
            text = fh.read()
        found = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
        self.assertIsNotNone(found, "pyproject.toml has no version line")
        self.assertEqual(memloom.__version__, found.group(1))

    def test_version_is_dotted(self):
        self.assertRegex(memloom.__version__, r"^\d+\.\d+\.\d+$")

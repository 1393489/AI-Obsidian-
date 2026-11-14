"""Release preflight: run every green gate for a public release in one command.

Zero dependencies, same as the package itself. Exits non-zero if any gate fails.

    python tools/preflight.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BINARY_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".zstd"}
LEAK_NEEDLES = ("Administrator", "\u77e5\u8bc6\u5e93", "_tw/", "_tw\\")  # local user, private vault, scratch dirs

# This file names the needles it looks for, so it can never pass its own scan.
SKIP = {"tools/preflight.py"}

RESULTS = []  # type: list


def _run(args, cwd=REPO):
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    return proc.returncode, (proc.stdout or ""), (proc.stderr or "")


def tracked_files():
    # core.quotepath=false keeps non-ASCII paths as real UTF-8 instead of
    # octal-escaped quoted strings (every page name here is Chinese).
    code, out, err = _run(["git", "-c", "core.quotepath=false", "ls-files"])
    if code != 0:
        raise AssertionError("git ls-files failed: " + err.strip()[:200])
    return [line.strip() for line in out.splitlines() if line.strip()]


def text_files():
    return [rel for rel in tracked_files()
            if rel not in SKIP
            and os.path.splitext(rel)[1].lower() not in BINARY_EXT]


def _read_bytes(rel):
    with open(os.path.join(REPO, rel), "rb") as f:
        return f.read()


def check_clean_encoding():
    files = text_files()
    bom = [rel for rel in files if _read_bytes(rel)[:3] == b"\xef\xbb\xbf"]
    assert not bom, "BOM in: " + ", ".join(bom)
    crlf = [rel for rel in files if b"\r\n" in _read_bytes(rel)]
    assert not crlf, "CRLF in: " + ", ".join(crlf)
    return "%d tracked text files, all UTF-8 without BOM, LF endings" % len(files)


def check_no_local_paths():
    hits = []
    for rel in text_files():
        text = _read_bytes(rel).decode("utf-8", "replace")
        for needle in LEAK_NEEDLES:
            if needle in text:
                hits.append("%s -> %s" % (rel, needle))
    assert not hits, "; ".join(hits)
    return "no local user name or local vault path"


def check_pyproject():
    path = os.path.join(REPO, "pyproject.toml")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    needed = ['name = "memloom"', "version", "description", "readme", "license",
              "requires-python", "[project.scripts]", 'memloom = "memloom.cli:main"']
    missing = [key for key in needed if key not in text]
    assert not missing, "pyproject.toml missing: " + ", ".join(missing)
    return "name/version/readme/license/requires-python/scripts all declared"


def check_version():
    code, out, err = _run([sys.executable, "-m", "memloom", "--version"])
    assert code == 0, (err or out).strip()[:300]
    line = out.strip()
    assert line.startswith("memloom "), "unexpected --version output: " + line[:80]
    return line


def check_tests():
    code, out, err = _run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."])
    body = (err or out).strip().splitlines()
    assert code == 0, "unittest failed:\n" + "\n".join(body[-12:])
    ran = [line for line in body if line.startswith("Ran ")]
    return (ran[0] if ran else "tests ok") + ", all green"


def check_build_idempotent():
    outdir = os.path.join(REPO, "out", ".preflight")
    shutil.rmtree(outdir, ignore_errors=True)
    fixtures = os.path.join("tests", "fixtures")
    cmd = [sys.executable, "-m", "memloom", "build", "--out", outdir,
           "--root", "dsh=" + fixtures, "--root", "claude-code=" + fixtures,
           "--root", "codex=" + fixtures, "--quiet", "--json"]

    code, first_out, first_err = _run(cmd)
    assert code == 0, "first build failed: " + (first_err or first_out).strip()[:300]
    first = json.loads(first_out)

    code, second_out, second_err = _run(cmd)
    assert code == 0, "second build failed: " + (second_err or second_out).strip()[:300]
    second = json.loads(second_out)

    assert first.get("written", 0) > 0, "first build wrote nothing: %r" % (first,)
    assert second.get("written") == 0, "second build rewrote pages: %r" % (second,)
    assert second.get("parsed") == 0, "second build re-parsed archives: %r" % (second,)
    assert second.get("reused", 0) > 0, "second build reused no cache: %r" % (second,)
    return "first %d pages written, second 0 written / 0 parsed / %d reused" % (
        first.get("written", 0), second.get("reused", 0))


def check_examples():
    root = os.path.join(REPO, "examples", "sample-vault")
    pages = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name.endswith(".md"):
                pages.append(os.path.join(dirpath, name))
    assert len(pages) >= 5, "examples/sample-vault has only %d markdown pages" % len(pages)
    empty = [p for p in pages if os.path.getsize(p) < 200]
    assert not empty, "suspiciously empty sample page: " + ", ".join(os.path.basename(p) for p in empty)
    return "%d sample pages, none empty" % len(pages)


CHECKS = [
    ("tracked files are clean UTF-8/LF", check_clean_encoding),
    ("no local paths leaked", check_no_local_paths),
    ("pyproject metadata complete", check_pyproject),
    ("memloom --version", check_version),
    ("unit tests", check_tests),
    ("second build is a no-op", check_build_idempotent),
    ("examples present", check_examples),
]


def main():
    print("memloom preflight  (%s)" % REPO)
    print("-" * 66)
    failed = 0
    for label, fn in CHECKS:
        try:
            detail = fn()
            print("[PASS] %-32s %s" % (label, detail))
        except AssertionError as exc:
            failed += 1
            print("[FAIL] %-32s %s" % (label, exc))
        except Exception as exc:  # noqa: BLE001 - a broken gate must not hide others
            failed += 1
            print("[FAIL] %-32s %s: %s" % (label, type(exc).__name__, exc))
    print("-" * 66)
    if failed:
        print("%d gate(s) failed - do not tag yet." % failed)
        return 1
    print("all gates green - tag and push.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

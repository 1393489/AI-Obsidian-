"""Shared test paths.

Temp dirs live inside the repo (out/_tmp): the OS temp directory is outside the sandbox
on this machine, and ``tempfile.mkdtemp`` itself produces a directory that a sandboxed
process cannot write into — ``os.makedirs`` with a random name does work.
"""
import os
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
FIX = os.path.join(HERE, "fixtures")
TMP_ROOT = os.path.join(REPO, "out", "_tmp")


def fixture(name):
    return os.path.join(FIX, name)


def mktemp():
    os.makedirs(TMP_ROOT, exist_ok=True)
    d = os.path.join(TMP_ROOT, "t-" + uuid.uuid4().hex[:10])
    os.makedirs(d, exist_ok=True)
    return d

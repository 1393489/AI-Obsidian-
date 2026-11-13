"""Adapter protocol: one file format, one module, nothing else changes."""

from __future__ import annotations

import json
import os
import re
from typing import Iterator, Optional

from ..model import Session

__all__ = ["Adapter", "read_jsonl", "texts_of", "clip", "first_line", "guess_kind", "squash"]

# Tool names whose arguments we can summarise nicely.
_SUMMARY_KEYS = (
    "description",
    "command",
    "cmd",
    "path",
    "file_path",
    "query",
    "pattern",
    "url",
    "prompt",
    "text",
    "name",
)


class Adapter:
    """Base class. Subclasses implement :meth:`load`."""

    name = "base"
    label = "Base"
    #: file suffixes this adapter can read
    suffixes = (".jsonl",)

    def default_roots(self) -> list:
        """Where this tool normally keeps its archives."""
        return []

    def match(self, path: str) -> bool:
        """Cheap path-based guess. Used only when ``--adapter auto``."""
        return False

    def sniff(self, head: str) -> bool:
        """Cheap content-based guess for files that live somewhere unusual.

        ``head`` is the first few KB of the file as text; parse defensively because the
        last line is usually truncated.
        """
        return False

    def load(self, path: str) -> Optional[Session]:  # pragma: no cover - abstract
        raise NotImplementedError

    # -- helpers shared by subclasses -------------------------------------
    @staticmethod
    def tool_summary(name: str, arguments) -> str:
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except Exception:
                return clip(arguments, 120)
        if not isinstance(arguments, dict):
            return ""
        for k in _SUMMARY_KEYS:
            v = arguments.get(k)
            if isinstance(v, str) and v.strip():
                return clip(re.sub(r"\s+", " ", v).strip(), 140)
        return ""


def read_jsonl(path: str) -> Iterator[dict]:
    """Yield dict records; skip blank/garbage lines instead of dying on them."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line[0] not in "{[":
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                yield obj


#: block types that are machinery, not conversation
_NOISE_BLOCKS = frozenset(
    {
        "thinking",
        "redacted_thinking",
        "reasoning",  # DSH / OpenAI-style chain of thought
        "tool_use",
        "tool_call",
        "tool-call",
        "tool_result",
        "tool-result",
        "image",
        "file",
    }
)


def texts_of(content) -> str:
    """Flatten the many ``content`` shapes into plain text.

    Handles: ``"str"``, ``[{"type": "text", "text": ...}]``, ``[{"text": ...}]``.
    Reasoning / tool blocks are dropped on purpose — memloom summarises what was *said*,
    not how the model thought, and leaking chain-of-thought into a vault page is both
    noise and a privacy foot-gun.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        content = [content]
    if not isinstance(content, list):
        return ""
    out = []
    for b in content:
        if isinstance(b, str):
            out.append(b)
            continue
        if not isinstance(b, dict):
            continue
        if b.get("type") in _NOISE_BLOCKS:
            continue
        val = b.get("text") or b.get("content") or b.get("input_text") or b.get("output_text")
        if isinstance(val, str) and val:
            out.append(val)
    return "\n".join(out)


def clip(s: str, n: int) -> str:
    s = re.sub(r"\n{3,}", "\n\n", (s or "").strip())
    return s if len(s) <= n else s[:n].rstrip() + " …"


def first_line(s: str, n: int = 300) -> str:
    for line in (s or "").splitlines():
        if line.strip():
            return clip(line.strip(), n)
    return ""


def guess_kind(path: str) -> str:
    """Best-effort hint from the path alone (used by ``scan``/``doctor``)."""
    p = path.replace("/", os.sep)
    if ".dsh" in p and "sessions" in p:
        return "dsh"
    if ".claude" in p and "projects" in p:
        return "claude-code"
    if ".codex" in p and "sessions" in p:
        return "codex"
    return ""


def squash(s: str) -> str:
    """Strip all whitespace so sniffers stop caring about json.dumps separators."""
    return re.sub(r"\s+", "", s or "").lower()

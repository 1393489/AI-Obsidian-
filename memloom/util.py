"""Small helpers shared across memloom. No third-party imports, ever."""

from __future__ import annotations

import datetime
import hashlib
import os
import re
from typing import Iterable, Optional

__all__ = [
    "safe_name",
    "slug",
    "short_id",
    "sha1",
    "utc_now",
    "to_local",
    "fmt_dt",
    "parse_iso",
    "from_ms",
    "human_size",
    "clip_text",
    "ensure_dir",
    "within_days",
    "uniq_keep_order",
    "is_informative_error",
    "short_tool_name",
]


_TZ = datetime.timezone(datetime.timedelta(hours=8))


def safe_name(s: str, limit: int = 60) -> str:
    """Make a string safe as a Windows *and* POSIX filename.

    Obsidian wiki links also dislike ``[ ] # ^ |``, so those go too.
    """
    s = s or ""
    for a, b in (
        ("/", "／"),
        ("\\", "＼"),
        (":", "："),
        ("*", ""),
        ("?", ""),
        ('"', ""),
        ("<", ""),
        (">", ""),
        ("|", "｜"),
        ("[", "("),
        ("]", ")"),
        ("#", ""),
        ("^", ""),
        ("\r", " "),
        ("\n", " "),
        ("\t", " "),
    ):
        s = s.replace(a, b)
    s = re.sub(r"\s+", " ", s).strip(" .·-／＼：｜")
    if not s:
        s = "untitled"
    if len(s) > limit:
        cut = s[:limit]
        for sep in (" ", "·", "、", "，", "：", ",", "."):
            i = cut.rfind(sep)
            if i > limit * 0.6:
                cut = cut[:i]
                break
        s = cut.rstrip(" -·、，：.,") + "…"
    return s


def slug(s: str, limit: int = 24) -> str:
    """Stable file-name fragment. Keeps CJK: a Chinese title that slugs to "x"
    makes every session page indistinguishable in the file list."""
    s = re.sub(r"[^\w]+", "-", (s or "").lower(), flags=re.UNICODE).strip("-")
    return (s or "x")[:limit].strip("-") or "x"


def short_id(sid: str, n: int = 8) -> str:
    """Last 8 hex chars of a session id (uuids share nothing useful up front)."""
    tail = re.sub(r"[^A-Za-z0-9]", "", sid or "")
    return (tail[-n:] if len(tail) >= n else tail) or "00000000"


def sha1(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()


def utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def to_local(dt: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(_TZ)


def fmt_dt(dt: Optional[datetime.datetime], fmt: str = "%Y-%m-%d %H:%M") -> str:
    local = to_local(dt)
    return local.strftime(fmt) if local else "—"


def parse_iso(s: Optional[str]) -> Optional[datetime.datetime]:
    """Parse the ISO-8601 dialects the various tools emit (with/without Z etc.)."""
    if not s or not isinstance(s, str):
        return None
    t = s.strip()
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    try:
        dt = datetime.datetime.fromisoformat(t)
    except ValueError:
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.datetime.strptime(s, fmt)
                break
            except ValueError:
                continue
        else:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def from_ms(ms) -> Optional[datetime.datetime]:
    try:
        return datetime.datetime.fromtimestamp(float(ms) / 1000.0, datetime.timezone.utc)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024 or unit == "GB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}GB"


def clip_text(s: str, n: int) -> str:
    """Trim to ``n`` chars on a word-ish boundary, marking the cut."""
    s = (s or "").strip()
    if len(s) <= n:
        return s
    cut = s[:n]
    for sep in ("\n", "。", ". ", " "):
        i = cut.rfind(sep)
        if i > n * 0.6:
            return cut[:i].rstrip() + " …"
    return cut.rstrip() + " …"


def ensure_dir(p: str) -> str:
    os.makedirs(p, exist_ok=True)
    return p


def within_days(dt: Optional[datetime.datetime], days: Optional[int]) -> bool:
    if days is None:
        return True
    if dt is None:
        return True
    return (utc_now() - dt.astimezone(datetime.timezone.utc)).days <= days


def uniq_keep_order(items: Iterable[str]) -> list:
    out, seen = [], set()
    for x in items:
        k = (x or "").strip()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(k)
    return out


# ---- topic titles -------------------------------------------------------

# ``fingerprint()`` already strips a leading "Error: ", so what survives can be the bare
# word "Error" — and with 26 sessions behind it that becomes the biggest page in 踩坑
# while its only evidence is "Error: {". A repeatable signal needs a subject.
_GENERIC_ERRORS = frozenset(
    {
        "error", "errors", "err", "failed", "fail", "failure", "exception",
        "traceback", "timeout", "timed out", "undefined", "unknown",
        "unknown error", "exit 1", "exit code 1", "command failed",
        "error failed", "operation failed",
    }
)


def is_informative_error(fp: str) -> bool:
    """True when an error fingerprint names *what* failed, not just *that* it failed."""
    s = (fp or "").strip().strip(".:;!?，。：；！？").lower()
    if len(s) < 6:
        return False
    return s not in _GENERIC_ERRORS


def short_tool_name(raw: str) -> str:
    """``tool:mcp__douyin__douyin_status`` -> ``douyin_status``.

    The MCP server prefix is plumbing; the reader only needs the verb.
    """
    s = (raw or "").replace("tool:", "")
    if "__" in s:
        s = s.rsplit("__", 1)[-1]
    return s

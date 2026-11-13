"""Incremental scan cache.

Decompressing zstd is the only slow part of a build: on a 113-session corpus it is ~90%
of the wall clock. So every parsed session is cached next to the *output* (never next to
the archives -- sources are read-only) and restored when the source file's size and
mtime are unchanged.

Cache layout::

    <out>/.memloom/state.json            # path -> {size, mtime_ns, adapter, key}
    <out>/.memloom/cache/<sha1>.json     # one serialised Session per source file

Deleting the directory is always safe; the next build just parses everything again.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Set

from .model import Session, ToolUse, Turn
from .util import ensure_dir, sha1

STATE_VERSION = 1
DIR_NAME = ".memloom"


# ------------------------------------------------------------------ serialise

def _dump_dt(value: Any) -> Any:
    return value.isoformat() if isinstance(value, datetime) else value


def _load_dt(value: Any) -> Any:
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return value


def _tool_to_dict(t: ToolUse) -> Dict[str, Any]:
    return {"n": t.name, "s": t.summary, "ok": t.ok, "e": t.error}


def _tool_from_dict(d: Dict[str, Any]) -> ToolUse:
    return ToolUse(name=d.get("n", ""), summary=d.get("s", ""), ok=d.get("ok"), error=d.get("e"))


def session_to_dict(s: Session) -> Dict[str, Any]:
    return {
        "id": s.id,
        "source": s.source,
        "adapter": s.adapter,
        "title": s.title,
        "cwd": s.cwd,
        "model": s.model,
        "started_at": _dump_dt(s.started_at),
        "ended_at": _dump_dt(s.ended_at),
        "cost_usd": s.cost_usd,
        "meta": s.meta,
        "turns": [
            {
                "i": t.index,
                "at": _dump_dt(t.at),
                "p": t.prompt,
                "r": t.reply,
                "tools": [_tool_to_dict(x) for x in t.tools],
            }
            for t in s.turns
        ],
    }


def session_from_dict(d: Dict[str, Any]) -> Session:
    turns: List[Turn] = []
    for raw in d.get("turns") or ():
        turns.append(
            Turn(
                index=raw.get("i", 0),
                at=_load_dt(raw.get("at")),
                prompt=raw.get("p", ""),
                reply=raw.get("r", ""),
                tools=[_tool_from_dict(x) for x in (raw.get("tools") or ())],
            )
        )
    return Session(
        id=d.get("id", ""),
        source=d.get("source", ""),
        adapter=d.get("adapter", ""),
        title=d.get("title", ""),
        cwd=d.get("cwd"),
        model=d.get("model"),
        started_at=_load_dt(d.get("started_at")),
        ended_at=_load_dt(d.get("ended_at")),
        turns=turns,
        cost_usd=d.get("cost_usd"),
        meta=d.get("meta") or {},
    )


# ------------------------------------------------------------------ cache

class Cache:
    """Per-output-dir cache of parsed sessions."""

    def __init__(self, out_dir: str) -> None:
        self.root = os.path.join(out_dir, DIR_NAME)
        self.cache_dir = os.path.join(self.root, "cache")
        self.state_path = os.path.join(self.root, "state.json")
        self._state: Dict[str, Dict[str, Any]] = {}
        self._used: Set[str] = set()
        self.reused = 0
        self.parsed = 0
        self.read_only = False
        self._dirty = False

    # -- loading ---------------------------------------------------------

    def load(self) -> "Cache":
        try:
            with open(self.state_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return self
        if isinstance(data, dict) and data.get("version") == STATE_VERSION:
            files = data.get("files")
            if isinstance(files, dict):
                self._state = {k: v for k, v in files.items() if isinstance(v, dict)}
        return self

    def _entry(self, path: str, adapter: str) -> Optional[Dict[str, Any]]:
        ent = self._state.get(path)
        if not ent or ent.get("adapter") != adapter:
            return None
        try:
            st = os.stat(path)
        except OSError:
            return None
        if ent.get("size") != st.st_size or ent.get("mtime_ns") != st.st_mtime_ns:
            return None
        return ent

    # -- public ----------------------------------------------------------

    def lookup(self, path: str, adapter: str) -> Optional[Session]:
        """Return the cached session for an unchanged file, else ``None``."""
        ent = self._entry(path, adapter)
        if not ent:
            return None
        blob = os.path.join(self.cache_dir, str(ent.get("key", "")) + ".json")
        try:
            with open(blob, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            session = session_from_dict(data)
        except (OSError, ValueError, TypeError, KeyError):
            return None
        if not session.id:
            return None
        self._used.add(blob)
        self.reused += 1
        return session

    def store(self, path: str, adapter: str, session: Session) -> None:
        self.parsed += 1
        if self.read_only:
            return
        try:
            st = os.stat(path)
        except OSError:
            return
        key = sha1(path.encode("utf-8", "replace"))[:16]
        blob = os.path.join(self.cache_dir, key + ".json")
        ensure_dir(self.cache_dir)
        tmp = blob + ".tmp"
        try:
            payload = session_to_dict(session)
            with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"), default=str)
            os.replace(tmp, blob)
        except (OSError, TypeError, ValueError):
            try:
                os.remove(tmp)
            except OSError:
                pass
            return
        self._used.add(blob)
        self._state[path] = {
            "size": st.st_size,
            "mtime_ns": st.st_mtime_ns,
            "adapter": adapter,
            "key": key,
        }
        self._dirty = True

    def forget(self, path: str) -> None:
        if self._state.pop(path, None) is not None:
            self._dirty = True

    def save(self) -> None:
        """Persist state and drop cache entries that no longer map to a source file."""
        if self.read_only:
            return
        stale = [
            os.path.join(self.cache_dir, f)
            for f in self._iter_cache_files()
            if os.path.join(self.cache_dir, f) not in self._used
        ]
        for p in stale:
            try:
                os.remove(p)
            except OSError:
                pass
        if not (self._dirty or stale):
            return
        ensure_dir(self.root)
        payload = {"version": STATE_VERSION, "files": self._state}
        tmp = self.state_path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            os.replace(tmp, self.state_path)
        except OSError:
            pass

    def clear(self) -> None:
        for f in self._iter_cache_files():
            try:
                os.remove(os.path.join(self.cache_dir, f))
            except OSError:
                pass
        self._state = {}
        self._used = set()
        self._dirty = True

    def _iter_cache_files(self) -> Iterable[str]:
        try:
            names = os.listdir(self.cache_dir)
        except OSError:
            return []
        return [n for n in names if n.endswith(".json")]

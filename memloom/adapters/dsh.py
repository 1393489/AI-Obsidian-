"""DeepSeek Harness session archives.

Format: line-delimited JSON events ``{"type": ..., "seq": ..., "time": <ms>, "data": {...}}``,
optionally zstd-compressed as *concatenated frames* (one frame per record).

Events we care about::

    session            -> id, createdAt, cwd, agentPreset
    session/title      -> data.title
    model/selection    -> data.provider + data.model
    turn/start         -> data.turn
    user/message       -> data.content (blocks), data.source.kind == "user"
    assistant/message  -> data.message.content (blocks)
    tool/call          -> data.name, data.arguments (JSON *string*), data.callId
    tool/result        -> data.message.isError, data.message.content, toolCallId
"""

from __future__ import annotations

import os
import re
from typing import Optional

from .. import zstd_frames
from ..model import Session, ToolUse, Turn
from ..util import from_ms, parse_iso
from .base import Adapter, clip, fallback_title, looks_like_brief, squash, texts_of

__all__ = ["DshAdapter"]


class DshAdapter(Adapter):
    name = "dsh"
    label = "DeepSeek Harness"
    suffixes = (".jsonl", ".jsonl.zstd")

    def default_roots(self) -> list:
        return [os.path.join(os.path.expanduser("~"), ".dsh", "sessions")]

    def match(self, path: str) -> bool:
        p = path.replace("/", os.sep)
        return (".dsh" in p and "sessions" in p) and p.endswith(self.suffixes)

    def sniff(self, head: str) -> bool:
        sq = squash(head)
        return '"type":"session"' in sq and '"seq"' in sq

    def load(self, path: str) -> Optional[Session]:
        if path.endswith(".zstd"):
            payload, _backend = zstd_frames.decompress(path)
            events = _parse_events(payload.decode("utf-8", "replace").splitlines())
        else:
            events = _parse_events_file(path)
        if not events:
            return None
        return _build(path, events)


def _parse_events_file(path: str):
    import json

    events = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line[0] != "{":
                continue
            try:
                events.append(json.loads(line))
            except Exception:
                continue
    return events


def _parse_events(lines):
    import json

    events = []
    for line in lines:
        line = line.strip()
        if not line or line[0] != "{":
            continue
        try:
            events.append(json.loads(line))
        except Exception:
            continue
    return events


def _build(path: str, events) -> Optional[Session]:
    meta = {}
    for e in events:
        if e.get("type") == "session":
            meta = e
            break

    sid = meta.get("id") or os.path.basename(path).replace(".jsonl.zstd", "").replace(".jsonl", "")
    title = ""
    model = None
    times = []
    turns = {}  # index -> Turn
    order = []
    by_call = {}  # callId -> ToolUse
    pending_prompt = None

    def new_turn(idx):
        if idx not in turns:
            turns[idx] = Turn(index=idx)
            order.append(idx)
        return turns[idx]

    cur = 0
    for e in events:
        t = e.get("type")
        d = e.get("data") or {}
        tm = e.get("time")
        if isinstance(tm, (int, float)):
            times.append(tm)

        if t == "session/title":
            # A scheduler run stamps the same standing instruction as its title every
            # time; keep it only if it actually names the work.
            if d.get("title") and not looks_like_brief(str(d["title"])):
                title = d["title"]
        elif t == "model/selection":
            if d.get("model"):
                model = f'{d.get("provider")}/{d.get("model")}'
        elif t == "turn/start":
            cur = d.get("turn") or cur
            new_turn(cur)
        elif t == "user/message":
            src = d.get("source") or {}
            if src.get("kind") not in (None, "user"):
                continue
            text = texts_of(d.get("content"))
            if not text.strip():
                continue
            turn = new_turn(cur)
            if turn.prompt:
                cur = cur + 1
                turn = new_turn(cur)
            turn.prompt = clip(text, 4000)
            turn.at = from_ms(tm)
            pending_prompt = turn
        elif t == "assistant/message":
            text = texts_of((d.get("message") or {}).get("content"))
            if not text.strip():
                continue
            turn = new_turn(cur)
            turn.reply = (turn.reply + "\n\n" + clip(text, 4000)).strip() if turn.reply else clip(text, 4000)
            if turn.at is None:
                turn.at = from_ms(tm)
        elif t == "tool/call":
            name = d.get("name") or "?"
            tu = ToolUse(name=name, summary=Adapter.tool_summary(name, d.get("arguments")))
            new_turn(cur).tools.append(tu)
            cid = d.get("callId")
            if cid:
                by_call[cid] = tu
        elif t == "tool/result":
            msg = d.get("message") or {}
            cid = msg.get("toolCallId") or d.get("toolCallId")
            tu = by_call.get(cid)
            if tu is None:
                continue
            is_err = bool(msg.get("isError"))
            tu.ok = not is_err
            if is_err:
                tu.error = clip(_text_of_result(msg), 300)

    turns_list = [turns[i] for i in order]
    if not any(tt.prompt or tt.reply or tt.tools for tt in turns_list):
        return None

    return Session(
        id=sid,
        source=os.path.abspath(path),
        adapter="dsh",
        title=title or _fallback_title(turns_list),
        cwd=meta.get("cwd"),
        model=model,
        started_at=from_ms(meta.get("createdAt") or (times[0] if times else None)),
        ended_at=from_ms(times[-1] if times else None),
        turns=turns_list,
        meta={
            "events": len(events),
            "agentPreset": meta.get("agentPreset"),
            "version": meta.get("version"),
        },
    )


def _text_of_result(msg: dict) -> str:
    txt = texts_of(msg.get("content"))
    return txt or ""


def _fallback_title(turns) -> str:
    return fallback_title(turns)

"""Normalised session model shared by every adapter.

Every tool (Claude Code, Codex, DeepSeek Harness, ...) stores something different.
Adapters translate their private format into these four dataclasses and nothing
downstream ever looks at a raw event again.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Optional

__all__ = ["ToolUse", "Turn", "Session"]


@dataclass
class ToolUse:
    """One tool invocation, kept as light as possible."""

    name: str
    summary: str = ""  # short, human readable: e.g. "pwsh: Get-ChildItem _tw"
    ok: Optional[bool] = None
    error: str = ""  # first line of the failure, if any


@dataclass
class Turn:
    """One user prompt and everything the agent did in response."""

    index: int = 0
    at: Optional[datetime.datetime] = None
    prompt: str = ""
    reply: str = ""
    tools: list = field(default_factory=list)  # list[ToolUse]

    @property
    def tool_names(self) -> list:
        return [t.name for t in self.tools if t.name]


@dataclass
class Session:
    """A whole conversation file."""

    id: str
    source: str  # absolute path of the file it came from
    adapter: str
    title: str = ""
    cwd: Optional[str] = None
    model: Optional[str] = None
    started_at: Optional[datetime.datetime] = None
    ended_at: Optional[datetime.datetime] = None
    turns: list = field(default_factory=list)  # list[Turn]
    cost_usd: Optional[float] = None
    meta: dict = field(default_factory=dict)

    # ---- derived, cheap, used a lot by rendering ----
    @property
    def date(self) -> str:
        d = self.started_at or self.ended_at
        return d.strftime("%Y-%m-%d") if d else "0000-00-00"

    @property
    def n_prompts(self) -> int:
        return sum(1 for t in self.turns if t.prompt)

    @property
    def n_tools(self) -> int:
        return sum(len(t.tools) for t in self.turns)

    @property
    def tool_histogram(self) -> dict:
        h = {}
        for t in self.turns:
            for tu in t.tools:
                if tu.name:
                    h[tu.name] = h.get(tu.name, 0) + 1
        return h

    @property
    def errors(self) -> list:
        out = []
        for t in self.turns:
            for tu in t.tools:
                if tu.error:
                    out.append(tu.error)
        return out

    def is_empty(self) -> bool:
        return not any(t.prompt or t.reply or t.tools for t in self.turns)

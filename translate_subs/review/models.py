"""Review domain models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ReviewLine(BaseModel):
    """A source line paired with its translation, keyed by the stable unit ID."""

    id: str
    event_index: int  # position in the translated document, for applying fixes
    speaker: str | None = None
    source: str
    target: str


class Finding(BaseModel):
    scope: Literal["line", "global"] = "line"
    id: str | None = None  # line ID for scope="line"
    kind: str  # glossary | proper_name | gender | pronoun | formality | literal | ...
    message: str
    current: str | None = None
    suggested: str | None = None
    auto: bool = False  # True only for vetted safe corrections

    @property
    def has_fix(self) -> bool:
        return self.suggested is not None and self.suggested != self.current


class ReviewReport(BaseModel):
    episode: str
    findings: list[Finding] = []

    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if not f.has_fix]

    def fixes(self) -> list[Finding]:
        return [f for f in self.findings if f.has_fix]

    def auto_fixes(self) -> list[Finding]:
        return [f for f in self.findings if f.has_fix and f.auto and f.id]

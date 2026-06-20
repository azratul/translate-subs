"""Translation job schema (strict JSON in/out).

The core writes `*.in.json` and expects `*.out.json` with the SAME IDs. Validating
against these models catches malformed responses so a block can be retried. The models
reject unknown keys (`extra="forbid"`) so a stale or hand-edited file fails loudly.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class JobLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    speaker: str | None = None
    text: str


class TranslationJobIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_id: str
    target: str
    rules: list[str] = Field(default_factory=list)
    context_before: list[JobLine] = Field(default_factory=list)
    translate: list[JobLine]
    context_after: list[JobLine] = Field(default_factory=list)


class TranslationJobOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_id: str
    translations: dict[str, str]  # id -> translated text

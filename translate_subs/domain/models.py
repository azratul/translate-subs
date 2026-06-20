"""Shared domain models."""

from __future__ import annotations

from pydantic import BaseModel


class TranslatableUnit(BaseModel):
    """A translatable subtitle line with a stable ID.

    `text` is the visible text (ASS tags stripped, line breaks as '\\n').
    `event_index` maps back to the originating event in the SSAFile.
    `lead_tags` holds the leading override block (e.g. `{\\an8\\pos(..)}`) that applies
    to the whole line; it is restored ahead of the translated text on reinsertion.
    """

    id: str
    event_index: int
    start: int  # ms
    end: int  # ms
    style: str
    speaker: str | None = None
    text: str
    lead_tags: str = ""

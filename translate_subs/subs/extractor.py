"""Extract translatable units from an SSAFile.

Separates visible text from ASS tags and assigns a stable per-line ID.
"""

from __future__ import annotations

import re

import pysubs2

from translate_subs.domain.models import TranslatableUnit

# {\p1} or higher marks a vector drawing, not text.
_DRAWING_RE = re.compile(r"\\p[1-9]")

# The run of override blocks at the very start of an event (e.g. {\an8}{\pos(..)}).
# These apply to the whole line and don't depend on its text, so they can be restored
# after translation. Inline tags further inside the text are tied to the original
# wording and are dropped. Karaoke (\k) is per-syllable, so such leads are not restored.
_LEADING_TAGS_RE = re.compile(r"^(?:\{[^}]*\})+")
_KARAOKE_RE = re.compile(r"\\[kK]")


def is_translatable(event: pysubs2.SSAEvent) -> bool:
    if event.is_comment:
        return False
    if _DRAWING_RE.search(event.text or ""):
        return False
    return bool(event.plaintext.strip())


def leading_tags(event: pysubs2.SSAEvent) -> str:
    match = _LEADING_TAGS_RE.match(event.text or "")
    if match is None:
        return ""
    block = match.group(0)
    return "" if _KARAOKE_RE.search(block) else block


def extract_units(subs: pysubs2.SSAFile) -> list[TranslatableUnit]:
    units: list[TranslatableUnit] = []
    n = 1
    for index, event in enumerate(subs.events):
        if not is_translatable(event):
            continue
        units.append(
            TranslatableUnit(
                id=f"{n:04d}",
                event_index=index,
                start=event.start,
                end=event.end,
                style=event.style,
                speaker=event.name or None,
                text=event.plaintext,
                lead_tags=leading_tags(event),
            )
        )
        n += 1
    return units

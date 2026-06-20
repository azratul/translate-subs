"""Compact per-series memory: drop dead glossary entries and redundant characters.

Memory only ever grows as episodes are analyzed. This prunes entries that carry no
instruction so prompts and files stay small: glossary mappings where source == target,
case-insensitive duplicate terms/characters, and characters with no usable information.
"""

from __future__ import annotations

from dataclasses import dataclass

from translate_subs.memory.models import CharacterMemory
from translate_subs.memory.store import ProjectMemory


@dataclass
class CompactReport:
    removed_identity_terms: int = 0
    removed_duplicate_terms: int = 0
    merged_characters: int = 0
    removed_empty_characters: int = 0


def compact_project_memory(pm: ProjectMemory) -> CompactReport:
    """Prune `pm` in place; return what was removed."""
    report = CompactReport()

    cleaned: dict[str, str] = {}
    seen: set[str] = set()
    for src, dst in pm.glossary.items():
        if src == dst:
            report.removed_identity_terms += 1
            continue
        key = src.casefold()
        if key in seen:
            report.removed_duplicate_terms += 1
            continue
        seen.add(key)
        cleaned[src] = dst
    pm.glossary = cleaned

    merged: dict[str, CharacterMemory] = {}
    order: list[str] = []
    for ch in pm.memory.characters:
        key = ch.name.casefold()
        base = merged.get(key)
        if base is None:
            merged[key] = ch
            order.append(key)
            continue
        report.merged_characters += 1
        if base.gender == "unknown" and ch.gender in ("male", "female"):
            base.gender = ch.gender
        if not base.speech_style and ch.speech_style:
            base.speech_style = ch.speech_style
        for other, rel in ch.relationships.items():
            base.relationships.setdefault(other, rel)

    kept = []
    for key in order:
        ch = merged[key]
        if ch.gender == "unknown" and not ch.speech_style and not ch.relationships:
            report.removed_empty_characters += 1
            continue
        kept.append(ch)
    pm.memory.characters = kept

    return report

"""Group translatable units into blocks (jobs) with surrounding context."""

from __future__ import annotations

from collections.abc import Callable

from translate_subs.ai.job_protocol import JobLine, TranslationJobIn
from translate_subs.domain.models import TranslatableUnit

# Given a block's translatable lines, return the rules to send with it. Used to keep
# only the memory relevant to each block so prompts don't grow with series history.
RulesFor = Callable[[list[JobLine]], list[str]]


def _line(unit: TranslatableUnit) -> JobLine:
    return JobLine(id=unit.id, speaker=unit.speaker, text=unit.text)


def build_jobs(
    units: list[TranslatableUnit],
    *,
    target: str,
    rules: list[str] | None = None,
    rules_for: RulesFor | None = None,
    block_size: int = 40,
    context: int = 3,
) -> list[TranslationJobIn]:
    """Build translation jobs. `rules_for` (per-block) takes precedence over `rules`."""
    jobs: list[TranslationJobIn] = []
    for block_no, start in enumerate(range(0, len(units), block_size), start=1):
        chunk = units[start : start + block_size]
        before = units[max(0, start - context) : start]
        after_start = start + len(chunk)
        after = units[after_start : after_start + context]
        translate = [_line(u) for u in chunk]
        block_rules = rules_for(translate) if rules_for is not None else list(rules or [])
        jobs.append(
            TranslationJobIn(
                block_id=f"{block_no:04d}",
                target=target,
                rules=block_rules,
                context_before=[_line(u) for u in before],
                translate=translate,
                context_after=[_line(u) for u in after],
            )
        )
    return jobs

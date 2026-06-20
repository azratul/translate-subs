"""Deterministic source/target structure checks used before linguistic review."""

from __future__ import annotations

from collections import Counter

from translate_subs.review.models import Finding, ReviewLine

ALIGN_TOLERANCE_MS = 10


def _style_signature(subs, event) -> tuple[str, dict | None]:
    style = subs.styles.get(event.style)
    return event.style, style.as_dict() if style is not None else None


def pair_lines(
    units,
    target_subs,
    *,
    source_subs=None,
    compare_styles: bool = False,
) -> tuple[list[ReviewLine], list[Finding]]:
    """Pair source/target events and report structural mismatches."""
    events = target_subs.events
    n = min(len(units), len(events))
    lines = [
        ReviewLine(
            id=units[i].id,
            event_index=i,
            speaker=units[i].speaker,
            source=units[i].text,
            target=events[i].plaintext,
        )
        for i in range(n)
    ]
    findings: list[Finding] = [
        Finding(
            id=units[i].id,
            kind="missing_id",
            message="No translated line at this position.",
            current="",
        )
        for i in range(n, len(units))
    ]
    findings.extend(
        Finding(
            id=f"T{i + 1:04d}",
            kind="extra_event",
            message="Translated file contains an event with no source line at this position.",
            current=events[i].plaintext,
        )
        for i in range(n, len(events))
    )

    duplicate_ids = sorted(
        unit_id for unit_id, count in Counter(unit.id for unit in units).items() if count > 1
    )
    if duplicate_ids:
        findings.append(
            Finding(
                scope="global",
                kind="duplicate_id",
                message=f"Source contains duplicate stable IDs: {duplicate_ids[:5]}.",
            )
        )

    for i in range(n):
        unit = units[i]
        event = events[i]
        if (
            abs(unit.start - event.start) > ALIGN_TOLERANCE_MS
            or abs(unit.end - event.end) > ALIGN_TOLERANCE_MS
        ):
            findings.append(
                Finding(
                    id=unit.id,
                    kind="timing_mismatch",
                    message=(
                        f"Timing differs: source {unit.start}-{unit.end} ms, "
                        f"target {event.start}-{event.end} ms."
                    ),
                    current=event.plaintext,
                )
            )
        if (
            compare_styles
            and source_subs is not None
            and _style_signature(source_subs, source_subs.events[unit.event_index])
            != _style_signature(target_subs, event)
        ):
            findings.append(
                Finding(
                    id=unit.id,
                    kind="style_mismatch",
                    message=f"ASS style differs: source '{unit.style}', target '{event.style}'.",
                    current=event.plaintext,
                )
            )

    source_is_chronological = all(
        units[i].start >= units[i - 1].start for i in range(1, len(units))
    )
    out_of_order = (
        [i for i in range(1, len(events)) if events[i].start < events[i - 1].start]
        if source_is_chronological
        else []
    )
    if out_of_order:
        findings.append(
            Finding(
                scope="global",
                kind="out_of_order",
                message=(
                    "Translated events are not in chronological order "
                    f"near positions {[i + 1 for i in out_of_order[:5]]}."
                ),
            )
        )
    return lines, findings

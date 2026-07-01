"""Property-based invariants for the deterministic extraction/reinsertion core.

These exercise the central round-trip guarantee (§"Never send the raw subtitle file to an LLM")
against generated events — mixing plain text, whole-line ASS override blocks, CJK/accented Unicode,
speakers and overlapping timings — rather than a handful of hand-written cases. The core is the
part that must never corrupt a file, so it is where generated inputs earn their keep.
"""

from __future__ import annotations

import pysubs2
from hypothesis import given, settings
from hypothesis import strategies as st

from translate_subs.subs.extractor import extract_units, is_translatable
from translate_subs.subs.reinserter import apply_translations, flatten_overlaps

# No braces or backslashes: visible text never accidentally forms an ASS override block, so the
# only tags in an event are the leading block we prepend deliberately.
_ALPHABET = "abcdefghijklmnopqrstuvwxyz ABCDEFG 0123 あ日本語 éüñ"
_VISIBLE = st.text(alphabet=_ALPHABET, min_size=1, max_size=40).filter(lambda s: s.strip())
_LEAD = st.sampled_from(["", "{\\an8}", "{\\i1}", "{\\pos(10,20)}", "{\\an8\\i1}", "{\\b1}"])
_SPEAKER = st.sampled_from(["", "Akane", "Kyosuke", "?"])


@st.composite
def _event(draw: st.DrawFn) -> pysubs2.SSAEvent:
    start = draw(st.integers(min_value=0, max_value=100_000))
    duration = draw(st.integers(min_value=1, max_value=5_000))
    event = pysubs2.SSAEvent(start=start, end=start + duration)
    event.text = draw(_LEAD) + draw(_VISIBLE)
    event.name = draw(_SPEAKER)
    return event


@st.composite
def _subs(draw: st.DrawFn) -> pysubs2.SSAFile:
    subs = pysubs2.SSAFile()
    subs.events = draw(st.lists(_event(), min_size=0, max_size=12))
    return subs


@settings(max_examples=200)
@given(_subs())
def test_extract_assigns_sequential_unique_ids(subs: pysubs2.SSAFile) -> None:
    ids = [unit.id for unit in extract_units(subs)]
    assert ids == [f"{i:04d}" for i in range(1, len(ids) + 1)]


@settings(max_examples=200)
@given(_subs())
def test_one_unit_per_translatable_event(subs: pysubs2.SSAFile) -> None:
    units = extract_units(subs)
    translatable = [event for event in subs.events if is_translatable(event)]
    assert len(units) == len(translatable)
    assert [unit.event_index for unit in units] == [
        index for index, event in enumerate(subs.events) if is_translatable(event)
    ]


@settings(max_examples=200)
@given(_subs())
def test_identity_round_trip_preserves_text_and_speaker(subs: pysubs2.SSAFile) -> None:
    units = extract_units(subs)
    before = [(unit.speaker, unit.text) for unit in units]
    apply_translations(subs, units, {unit.id: unit.text for unit in units})
    after = [(unit.speaker, unit.text) for unit in extract_units(subs)]
    assert after == before


@settings(max_examples=200)
@given(_subs())
def test_flatten_overlaps_leaves_no_timed_overlap(subs: pysubs2.SSAFile) -> None:
    flatten_overlaps(subs)
    timed = sorted(
        (event for event in subs.events if event.end > event.start), key=lambda e: e.start
    )
    for earlier, later in zip(timed, timed[1:], strict=False):
        assert later.start >= earlier.end

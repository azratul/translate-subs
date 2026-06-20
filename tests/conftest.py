from __future__ import annotations

import pysubs2
import pytest


@pytest.fixture
def sample_ass() -> pysubs2.SSAFile:
    """ASS with tagged dialogue, a multiline cue, a comment, a drawing and an empty line."""
    subs = pysubs2.SSAFile()
    subs.styles["White"] = pysubs2.SSAStyle()
    subs.styles["Sign"] = pysubs2.SSAStyle()

    subs.events.append(
        pysubs2.SSAEvent(
            start=1000, end=3000, text=r"{\i1}I won't forgive you!{\i0}", style="White"
        )
    )
    subs.events.append(
        pysubs2.SSAEvent(
            start=3100, end=5000, text=r"{\pos(640,690)}First line\NSecond line", style="White"
        )
    )
    subs.events.append(pysubs2.SSAEvent(start=5200, end=7000, text="SHADOW CORE", style="Sign"))

    comment = pysubs2.SSAEvent(start=7100, end=8000, text="staff note")
    comment.is_comment = True
    subs.events.append(comment)

    drawing = pysubs2.SSAEvent(
        start=8100, end=9000, text=r"{\p1}m 0 0 l 10 0 10 10 0 10{\p0}", style="White"
    )
    subs.events.append(drawing)

    subs.events.append(pysubs2.SSAEvent(start=9100, end=9500, text="", style="White"))
    return subs

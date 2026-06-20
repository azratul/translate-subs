"""Subtitle loading and saving (any input format -> .ass or .srt)."""

from __future__ import annotations

from pathlib import Path

import pysubs2


def load(path: str | Path) -> pysubs2.SSAFile:
    return pysubs2.load(str(path))


def save(subs: pysubs2.SSAFile, path: str | Path, *, fmt: str | None = None) -> None:
    """Save `subs`; the format is `fmt` or, if None, inferred from the suffix."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    subs.save(str(path), format_=fmt)

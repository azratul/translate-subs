"""Per-subtitle readability metrics and limits."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReadabilityLimits:
    max_chars_per_line: int = 42
    max_lines: int = 2
    max_chars_per_second: float = 18.0


@dataclass(frozen=True)
class LineMetrics:
    chars_total: int  # visible chars, excluding line breaks
    max_line_chars: int
    n_lines: int
    duration_ms: int
    cps: float  # chars per second

    def char_budget(self, limits: ReadabilityLimits) -> int:
        """Max chars that fit the cps limit for this line's duration."""
        return int(limits.max_chars_per_second * self.duration_ms / 1000)


def measure(text: str, start_ms: int, end_ms: int) -> LineMetrics:
    lines = text.split("\n")
    chars_total = sum(len(line) for line in lines)
    duration_ms = max(0, end_ms - start_ms)
    seconds = duration_ms / 1000
    cps = chars_total / seconds if seconds > 0 else float("inf")
    return LineMetrics(
        chars_total=chars_total,
        max_line_chars=max((len(line) for line in lines), default=0),
        n_lines=len(lines),
        duration_ms=duration_ms,
        cps=cps,
    )


def exceeds(metrics: LineMetrics, limits: ReadabilityLimits) -> list[str]:
    """Human-readable reasons the line breaks the limits (empty if it passes)."""
    reasons = []
    if metrics.max_line_chars > limits.max_chars_per_line:
        reasons.append(f"line too long ({metrics.max_line_chars} > {limits.max_chars_per_line})")
    if metrics.n_lines > limits.max_lines:
        reasons.append(f"too many lines ({metrics.n_lines} > {limits.max_lines})")
    if metrics.cps > limits.max_chars_per_second:
        reasons.append(f"too fast ({metrics.cps:.1f} > {limits.max_chars_per_second} cps)")
    return reasons

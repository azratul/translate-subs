"""Automatic review (Phase 4): a second quality pass after translation.

Pairs each source line with its translation and produces findings — deterministic
checks (glossary respected, name consistency, empty target, line length) plus an
optional LLM pass (gender/pronoun/formality/naturalness/meaning). Findings are
written to `episode.review.md`; only *safe* fixes may be auto-applied.
"""

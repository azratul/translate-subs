"""Per-series memory (Phase 3): glossary, characters and style guide.

Persisted under `data/projects/<serie>/` so episode 10 respects decisions made in
earlier episodes. Updates never silently overwrite a stored decision; contradicting
suggestions are flagged as conflicts (see `merge`).
"""

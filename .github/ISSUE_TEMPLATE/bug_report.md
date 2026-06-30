---
name: Bug report
about: Something the CLI does wrong (a crash, bad output, wrong behaviour)
title: ""
labels: bug
---

## What happened

A clear description of the bug.

## Steps to reproduce

The exact command(s) you ran, e.g.:

```bash
llm-subs translate "Episode 01.mkv" --project "Show" --target es-latam --provider ollama
```

If the input matters, attach a **minimal** subtitle that triggers it (a few cues is enough).
Do not attach copyrighted media.

## Expected vs actual

- Expected:
- Actual (paste the error / wrong output):

## Environment

- `llm-subs --version`:
- OS and Python version:
- Provider and model (`claude`/`codex`/`ollama`/…):
- Output of `llm-subs doctor` (and `llm-subs doctor --provider <name>` if provider-related):

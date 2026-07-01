# Contributing

Thanks for your interest in improving `llm-subs`. This is a focused command-line tool;
see the **Scope, non-goals and limitations** section of the [README](README.md) before
proposing large features, so effort isn't spent on things that are intentionally out of scope.

## Development setup

Requires Python ≥ 3.11, [`uv`](https://docs.astral.sh/uv/), and `ffmpeg`/`ffprobe` on PATH.

```bash
uv sync                 # install deps (incl. dev tools) into the project venv
uv run llm-subs --help
```

## Before opening a pull request

All must pass; CI enforces them on Python 3.11–3.14:

```bash
uv run ruff check translate_subs/ tests/
uv run ruff format --check translate_subs/ tests/   # run `ruff format` (no --check) to fix
uv run mypy translate_subs/
uv run pytest -q
```

New behaviour needs tests. Bug fixes should come with a test that fails without the fix.

## Conventions

- **All code is in English** — identifiers, CLI strings, comments and docstrings. (Issues and
  discussion may be in any language; the code is not.)
- **Comments explain the *why*** (non-obvious decisions, invariants, edge cases), never the
  *what* the code already states. No commented-out code.
- **Never send the raw subtitle file to an LLM.** Parse it, extract visible text with stable
  IDs, send `[ID] text`, and reinsert by ID. This invariant drives the whole design — keep the
  deterministic core (parsing/reinsertion/validation) free of any provider's quirks.
- Adding a translation backend means adding a runner (`prompt -> text`) behind
  `CliTranslationProvider`; it must not leak into parsing or reinsertion.

## Architecture in one screen

The flow, end to end: **resolve** a source (sidecar or an embedded track demuxed with ffmpeg,
`translate_subs/io/`) → **parse** with `pysubs2` and **extract** only each event's visible text
with a stable id, keeping the whole-line leading override block aside
(`translate_subs/subs/extractor.py`) → **build blocks** of `[ID] Speaker: text` with before/after
context, folding in relevance-filtered series memory and episode context
(`translate_subs/ai/blocks.py`, `translate_subs/memory/`) → **translate** through a provider,
checkpointed per block so a crash resumes (`translate_subs/ai/`) → **reinsert** by id, restore the
leading override block, prune non-translatable events, and **export** `.ass` (keeps positioning and
style) or `.srt` (flat; overlapping cues merged, `translate_subs/subs/reinserter.py`) →
**validate** before writing — nothing is written if validation fails
(`translate_subs/subs/validator.py`).

Layering: use-case orchestration lives in `translate_subs/workflows/`, Typer callbacks in
`translate_subs/commands/`, and `pipeline.py`/`cli.py` are **stable public facades** — keep their
imports, signatures and command/option names stable.

## How to add a translation provider

A provider is a callable `runner(prompt: str) -> str` behind the same abstraction.

1. **Implement** a small dataclass: a subprocess CLI goes in `translate_subs/ai/cli_adapters.py`
   (model an existing one like `CodexCli`), an HTTP/model API in
   `translate_subs/ai/api_adapters.py`. It only turns a prompt into text — the caller builds the
   prompt and parses the reply.
2. **Harden it.** Subtitle text is **untrusted**: launch any agent CLI from the empty throwaway
   `cwd` that `_run` provides and deny its tools/filesystem/network with the tool's own switches
   (see how `claude`/`codex`/`opencode` are locked down). A runner that can be talked into reading
   local files is not acceptable.
3. **Register** it in the `_RUNNERS` map so `make_runner` builds it, and add it to the provider
   help strings.
4. **Wire diagnostics** in `translate_subs/diagnostics.py` so `doctor --provider <name>` verifies
   the backend (binary on PATH / reachable server / installed package).
5. **Test** argv/behaviour with a fake `subprocess.run` (see `tests/test_phase6.py`) — no live
   calls; live-verify by hand and note it in the PR.

## Troubleshooting by provider

Run `llm-subs doctor --provider <name>` first; it checks each backend without an LLM call.

- **claude / codex / antigravity / opencode** — `… CLI not found on PATH`: install the agent CLI
  and put it on `PATH`; auth lives in the CLI's own config (run it once to log in). `antigravity`
  (`agy`) has the weakest isolation (terminal-only sandbox) — prefer `claude`/`codex` for untrusted
  input.
- **ollama** — `no server at …`: `ollama serve` or set `$OLLAMA_HOST`. `model '…' not installed`:
  `ollama pull <model>` (verify with `llm-subs doctor --provider ollama --model <model>`).
- **litellm** — `package not installed`: `uv sync --extra litellm` (or
  `pip install 'llm-subs[litellm]'`). The model id carries the provider prefix, e.g.
  `ollama/qwen3:4b`.
- **Embedded track issues** — `llm-subs probe <media>` to list tracks, then `--track <n>` or pass a
  sidecar directly. Image tracks (PGS/VobSub) are unsupported (they need OCR).

## Deliberate design decisions — please don't re-report these

The items below are recurring review findings that are **intentional** and have been audited. They
are listed here so a reviewer (human or automated) can tell a settled trade-off from a fresh bug.
If you believe one is actually wrong, open an issue with a concrete reproducing case rather than a
general "this looks unsafe" — the reasoning is what a PR needs to overturn.

- **`opencode` keeps `--pure` *and* an inline deny-all permission config.** `--pure` only drops
  external plugins; built-in tools (read/bash/webfetch) stay allowed, so the deny-all is what
  actually contains an untrusted cue. Do not "simplify" it to `--pure` alone.
- **Every agent CLI runs from an empty throwaway `cwd` with its own tool/sandbox switches.**
  `claude` denies all tools + `--strict-mcp-config`, `codex` is `--sandbox read-only`,
  `antigravity` gets `--sandbox` (terminal-only — the weakest, hence discouraged for untrusted
  input). No extra container is required beyond these.
- **Internal state is written owner-only (0600); the final subtitle is widened to the umask.**
  State can carry subtitle text and stays private; the output must be readable by a media server
  running as another user (Jellyfin/Plex). The two modes are intentionally different.
- **Series memory is segmented by the *full* target** (`es-latam` ≠ `es-es`), so variants of one
  language never share glossary/characters/conflicts.
- **Per-episode batch failures are recorded and skipped; `ProviderError` aborts the run.** A parse
  error is per-episode; exhausted quota / broken auth is systemic, so it stops everything.
- **The stale-output fingerprint hashes translation-relevant content (id/speaker/text), not timing
  or styles.** A timing-only source edit does not change the translation, so it deliberately does
  not flag the output as stale. `--strict-lang` stays translation-only (not on `analyze`/`review`).
- **`.ass` output preserves non-translatable events verbatim** (drawings, comments, empty cues);
  only `.srt` prunes them, because SRT has no positioning.

## Known limitations — already tracked

Real gaps we know about. Don't silently close them, and don't re-file them as new:

- **`review --apply` replaces the whole line** for a "glossary"/"proper_name" safe fix; the guard
  confirms the suggestion contains the expected rendering but doesn't diff-limit the change to just
  that term. Treat `--apply` as suggestion-acceptance and review the diff.
- **`tighten --apply` writes compactions without semantic validation** — it checks the result fits
  the character budget, not that meaning was preserved.
- **`flatten_overlaps` has a quadratic worst case** on pathologically dense `.srt` files; ordinary
  subtitles are unaffected.
- **The `litellm` extra isn't exercised in CI** (`uv sync` runs without extras), so that adapter is
  covered only by argv tests, not an install-path run.

## Support and compatibility

Maintained on a best-effort basis. See the **Versioning and compatibility policy** in the
[README](README.md) for what a patch/minor release may change and how deprecations work. By
participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## Commit messages

Write clear, imperative one-line summaries in English (e.g. "Add --strict-lang to translate").
Keep unrelated changes in separate commits.

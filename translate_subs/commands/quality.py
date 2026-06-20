"""Review and readability command callbacks."""

from __future__ import annotations

from pathlib import Path

import typer

from translate_subs.readability.metrics import ReadabilityLimits

_AI_PROVIDER_HELP = "claude | codex | gemini | opencode"


def _runtime():
    from translate_subs import cli

    return cli


def review(
    source: Path = typer.Argument(..., help="Original source (subtitle/video)."),
    translated: Path = typer.Argument(..., help="Translated .ass/.srt to review."),
    target: str = typer.Option(
        "es-latam", help="Target language/variant, e.g. es-latam, en, fr-FR, ja."
    ),
    track: int | None = typer.Option(None, help="Embedded track index (when several exist)."),
    lang: str = typer.Option("en", help="Preferred source language when picking a track."),
    project: str | None = typer.Option(None, help="Project/series name."),
    max_chars: int = typer.Option(42, help="Max characters per visual line."),
    provider: str = typer.Option("claude", help=_AI_PROVIDER_HELP),
    model: str | None = typer.Option(None, "--model", help="Model id for the chosen CLI provider."),
    reasoning: str | None = typer.Option(None, "--reasoning", help="Codex reasoning effort."),
    retries: int = typer.Option(2, "--retries", min=0, help="Retries after an agent/JSON failure."),
    no_llm: bool = typer.Option(False, "--no-llm", help="Deterministic checks only."),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Apply only the safe auto-fixes to the translated subtitle.",
    ),
    non_interactive: bool = typer.Option(
        False, "--non-interactive", "--yes", "-y", help="Do not prompt; resolve by heuristic/flags."
    ),
):
    """Review a translation and write episode.review.md (optionally apply safe fixes)."""
    runtime = _runtime()
    try:
        result = runtime.review_translation(
            source,
            translated,
            target=target,
            track_index=track,
            lang=lang,
            project=project,
            interactive=not non_interactive,
            max_chars=max_chars,
            use_llm=not no_llm,
            apply=apply,
            provider=provider,
            model=model,
            reasoning=reasoning,
            max_retries=retries,
        )
    except runtime._EXPECTED_ERRORS as exc:
        runtime.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    report = result.report
    runtime.console.print(
        f"Reviewed [bold]{result.n_lines}[/bold] lines: "
        f"{len(report.warnings())} warning(s), {len(report.fixes())} suggested fix(es)."
    )
    if result.context_stale:
        runtime.console.print(
            "[yellow]Warning:[/yellow] episode.context.json was analyzed from a different "
            "version of this source; re-run `analyze` to refresh it."
        )
    if apply and not result.mapping_aligned:
        runtime.console.print(
            "[yellow]Skipped --apply:[/yellow] the translated file does not map 1:1 to the "
            "source (merged .srt). Review and apply fixes on the .ass output instead."
        )
    elif apply:
        runtime.console.print(f"Applied [green]{result.n_applied}[/green] safe fix(es).")
    runtime.console.print(f"Report: [green]{result.report_path}[/green]")


def tighten(
    translated: Path = typer.Argument(..., help="Translated .ass/.srt to check for readability."),
    project: str | None = typer.Option(None, help="Project/series name."),
    max_chars_per_line: int = typer.Option(42, help="Max characters per visual line."),
    max_lines: int = typer.Option(2, help="Max lines per subtitle."),
    max_cps: float = typer.Option(18.0, help="Max characters per second."),
    provider: str = typer.Option("claude", help=_AI_PROVIDER_HELP),
    model: str | None = typer.Option(None, "--model", help="Model id for the chosen CLI provider."),
    reasoning: str | None = typer.Option(None, "--reasoning", help="Codex reasoning effort."),
    retries: int = typer.Option(2, "--retries", min=0, help="Retries after an agent/JSON failure."),
    no_llm: bool = typer.Option(False, "--no-llm", help="Only measure/flag, no compaction."),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Write the compacted lines back to the subtitle file.",
    ),
):
    """Flag subtitles that break readability limits and compact them via the LLM."""
    runtime = _runtime()
    limits = ReadabilityLimits(
        max_chars_per_line=max_chars_per_line,
        max_lines=max_lines,
        max_chars_per_second=max_cps,
    )
    try:
        result = runtime.tighten_subtitle(
            translated,
            project=project,
            limits=limits,
            use_llm=not no_llm,
            apply=apply,
            provider=provider,
            model=model,
            reasoning=reasoning,
            max_retries=retries,
        )
    except runtime._EXPECTED_ERRORS as exc:
        runtime.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    runtime.console.print(
        f"Checked [bold]{result.n_subs}[/bold] subtitles: "
        f"{result.n_flagged} over limit, {result.n_compacted} compacted."
    )
    if apply:
        runtime.console.print(f"Applied [green]{result.n_applied}[/green] compaction(s).")
    if result.n_residual:
        runtime.console.print(
            f"[yellow]{result.n_residual} still over limit after compaction.[/yellow]"
        )
    runtime.console.print(f"Report: [green]{result.report_path}[/green]")

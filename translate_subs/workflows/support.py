"""Provider, project-path and transactional-file helpers for workflows."""

from __future__ import annotations

import contextlib
import os
import tempfile
from collections.abc import Callable
from pathlib import Path

from translate_subs import config
from translate_subs.ai.cli_adapters import CLI_PROVIDERS, make_runner
from translate_subs.ai.provider import (
    CliTranslationProvider,
    FileHandoffProvider,
    IdentityProvider,
    TranslationProvider,
)
from translate_subs.io.source_resolver import ResolvedSource
from translate_subs.naming import base_stem
from translate_subs.subs import document
from translate_subs.subs.validator import ValidationResult
from translate_subs.workflows.models import PipelineError


def make_provider(
    name: str,
    jobs_dir: Path,
    *,
    model: str | None = None,
    reasoning: str | None = None,
    max_retries: int = 2,
) -> TranslationProvider:
    if name == "identity":
        return IdentityProvider()
    if name == "file-handoff":
        return FileHandoffProvider(jobs_dir)
    if name in CLI_PROVIDERS:
        return CliTranslationProvider(make_runner(name, model, reasoning), max_retries=max_retries)
    raise PipelineError(f"Unknown provider: {name}")


def make_ai_runner(provider: str, *, model: str | None = None, reasoning: str | None = None):
    if provider not in CLI_PROVIDERS:
        supported = ", ".join(CLI_PROVIDERS)
        raise PipelineError(
            f"Provider '{provider}' cannot perform this operation. Use one of: {supported}."
        )
    return make_runner(provider, model, reasoning)


def project_episode(source: ResolvedSource, project: str | None) -> tuple[str, str]:
    project_name = project or source.origin.parent.name or "default"
    return project_name, base_stem(source.origin)


def project_dir(project: str) -> Path:
    """Resolve a flat project name without allowing traversal outside the projects root."""
    name = project.strip()
    if not name or name.startswith(".") or "/" in name or "\\" in name or "\x00" in name:
        raise PipelineError(f"Invalid project name: {project!r}")
    base = config.PROJECTS_DIR.resolve()
    candidate = (base / name).resolve()
    if candidate != base / name or base not in candidate.parents:
        raise PipelineError(f"Invalid project name: {project!r}")
    return base / name


def atomic_save(
    subs,
    out_path: str | Path,
    fmt: str | None = None,
    *,
    validate: Callable[[Path], ValidationResult] | None = None,
) -> ValidationResult | None:
    """Render, validate and atomically replace a subtitle file."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=out_path.parent,
        prefix=f".{out_path.name}.",
        suffix=out_path.suffix,
    )
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        document.save(subs, tmp, fmt=fmt)
        result = validate(tmp) if validate is not None else None
        if result is not None and not result.ok:
            raise PipelineError(
                "Output failed validation, nothing written: " + "; ".join(result.errors)
            )
        os.replace(tmp, out_path)
        return result
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise


def context_path(project: str, episode: str) -> Path:
    return project_dir(project) / episode / "episode.context.json"


def review_path(project: str, episode: str) -> Path:
    return project_dir(project) / episode / "episode.review.md"


def readability_path(project: str, episode: str) -> Path:
    return project_dir(project) / episode / "episode.readability.md"

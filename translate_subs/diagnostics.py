"""Environment diagnostics for the `doctor` command.

Each check returns a `Check` (name, status, detail). Nothing here mutates state or
calls an LLM; it only inspects what the tool needs to run: the external media tools,
the writable data/cache directories, and — when a provider is named — that provider's
backend (a CLI on PATH, a reachable Ollama server, or the optional litellm package).
"""

from __future__ import annotations

import os
import shutil
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from translate_subs import config

Status = Literal["ok", "warn", "fail"]

# Providers whose backend is just a CLI of the same name on PATH.
_CLI_BINARIES = ("claude", "codex", "gemini", "opencode")


@dataclass
class Check:
    name: str
    status: Status
    detail: str


def _media_checks() -> list[Check]:
    checks: list[Check] = []
    for tool in ("ffprobe", "ffmpeg"):
        path = shutil.which(tool)
        if path:
            checks.append(Check(tool, "ok", path))
        else:
            checks.append(
                Check(
                    tool,
                    "warn",
                    "not on PATH — needed only to read subtitles embedded in video "
                    "containers; sidecar .ass/.srt inputs work without it.",
                )
            )
    return checks


def _writable_dir(label: str, path: Path) -> Check:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".doctor-write-test"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return Check(label, "fail", f"{path} is not writable: {exc}")
    return Check(label, "ok", str(path))


def _path_checks() -> list[Check]:
    return [
        _writable_dir("data dir", config.DATA_DIR),
        _writable_dir("projects dir", config.PROJECTS_DIR),
        _writable_dir("cache dir", config.WORK_DIR),
    ]


def _ollama_check() -> Check:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    base = host if host.startswith("http") else f"http://{host}"
    url = f"{base.rstrip('/')}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=5):  # noqa: S310 - local server URL
            return Check("ollama", "ok", f"server reachable at {base}")
    except urllib.error.URLError as exc:
        return Check(
            "ollama",
            "fail",
            f"no server at {base} ({exc}). Start it with `ollama serve` or set $OLLAMA_HOST.",
        )


def _litellm_check() -> Check:
    try:
        import litellm  # noqa: F401
    except ImportError:
        return Check(
            "litellm",
            "fail",
            "package not installed. Run `uv sync --extra litellm`.",
        )
    return Check("litellm", "ok", "package importable")


def _provider_check(provider: str) -> Check:
    if provider in ("identity", "file-handoff"):
        return Check(provider, "ok", "no external backend required")
    if provider in _CLI_BINARIES:
        path = shutil.which(provider)
        if path:
            return Check(provider, "ok", path)
        return Check(provider, "fail", f"`{provider}` CLI not found on PATH.")
    if provider == "ollama":
        return _ollama_check()
    if provider == "litellm":
        return _litellm_check()
    return Check(provider, "fail", f"unknown provider '{provider}'.")


def run_diagnostics(provider: str | None = None) -> list[Check]:
    """Collect all checks; when `provider` is given, also verify its backend."""
    checks: list[Check] = [
        Check("python", "ok", sys.version.split()[0]),
        *_media_checks(),
        *_path_checks(),
    ]
    if provider is not None:
        checks.append(_provider_check(provider))
    return checks

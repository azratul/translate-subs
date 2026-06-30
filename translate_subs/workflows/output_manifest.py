"""Per-output provenance manifest for staleness detection in `batch`.

When `translate` writes an output it records, in the per-episode state directory, the source
fingerprint and the settings that produced it. On a later `batch` run that finds the output already
present, the stored manifest lets it tell an up-to-date output (skip) from one whose source,
provider/model or prompt changed since (report as *stale*, never silently overwritten).

The recorded model is the value the user/settings supplied, so an explicit `--model` change is
detected; relying on a provider's built-in default and that default later changing is not (the
manifest can't see the runner's fallback without building it). Source changes — the common case
after re-ripping or editing a subtitle — are always detected.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from translate_subs.ai.provider import TRANSLATION_PROMPT_VERSION
from translate_subs.fsutil import atomic_write_text
from translate_subs.workflows.support import episode_dir

_MANIFEST_FILE = "output.manifest.json"


class OutputManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    source_hash: str
    target: str
    provider: str
    model: str
    prompt_version: int = TRANSLATION_PROMPT_VERSION


def manifest_path(project: str, target: str, episode: str) -> Path:
    return episode_dir(project, target, episode) / _MANIFEST_FILE


def load_manifest(path: Path) -> OutputManifest | None:
    """The stored manifest, or None when absent or unreadable.

    A missing/legacy/corrupt manifest is treated as absent so an output that predates this feature
    is skipped as before rather than wrongly flagged stale.
    """
    if not path.exists():
        return None
    try:
        return OutputManifest.model_validate_json(path.read_text("utf-8"))
    except Exception:
        return None


def write_manifest(path: Path, manifest: OutputManifest) -> None:
    atomic_write_text(path, manifest.model_dump_json(indent=2), private=True)


def describe_change(stored: OutputManifest, current: OutputManifest) -> str:
    """Human-readable list of what changed between a stored and a current manifest."""
    changed = []
    if stored.source_hash != current.source_hash:
        changed.append("source")
    if stored.provider != current.provider or stored.model != current.model:
        changed.append("provider/model")
    if stored.prompt_version != current.prompt_version:
        changed.append("prompt")
    return ", ".join(changed) or "settings"

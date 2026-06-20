"""Per-episode block translation checkpoint.

Translating a full episode is dozens of slow LLM calls; a crash on the last block must not
throw away the rest. Each block's result is persisted as soon as it returns, keyed by a hash of
the block's own translatable input (target + rules + the id/speaker/text of its lines).
Re-running reuses every block whose input is unchanged — both a resume after a failure and a
cache when only a few lines moved (the rest of the episode is reused verbatim).

The block's surrounding context (the before/after lines sent for reference) is part of the hash:
since context steers the translation (pronouns, register, callbacks), a block must be re-done if
its neighbours changed, even when its own lines did not. The checkpoint is scoped to a
provider/model signature: switching the backend (e.g. ollama -> claude) discards it so the new
model re-translates instead of inheriting the old output. The file is a regenerable cache, so a
corrupt or older-format one is treated as empty, never fatal.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from translate_subs.ai.job_protocol import TranslationJobIn
from translate_subs.ai.provider import TRANSLATION_PROMPT_VERSION, TranslationProvider
from translate_subs.fsutil import atomic_write_text

# Bumped when the persisted schema or hash payload changes. Version 3 validates the complete
# file strictly and includes the translation-prompt version in every block hash.
CHECKPOINT_VERSION = 3
CHECKPOINT_FILE = "translations.checkpoint.json"


def _lines(lines) -> list[dict]:
    return [{"id": line.id, "speaker": line.speaker, "text": line.text} for line in lines]


def block_hash(job: TranslationJobIn) -> str:
    """Stable hash of everything that steers a block's translation, context included."""
    payload = {
        "prompt_version": TRANSLATION_PROMPT_VERSION,
        "target": job.target,
        "rules": list(job.rules),
        "context_before": _lines(job.context_before),
        "translate": _lines(job.translate),
        "context_after": _lines(job.context_after),
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


@dataclass
class _Entry:
    block_id: str
    translations: dict[str, str]
    untranslated: list[str] = field(default_factory=list)


class _CheckpointEntryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    block_id: str
    translations: dict[str, str]
    untranslated: list[str] = Field(default_factory=list)


class _CheckpointFileModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    version: int
    signature: str
    blocks: dict[str, _CheckpointEntryModel] = Field(default_factory=dict)


@dataclass
class BlockProgress:
    done: int
    total: int
    block_id: str
    reused: bool


@dataclass
class BlockCheckpoint:
    path: Path
    signature: str
    entries: dict[str, _Entry] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path, signature: str) -> BlockCheckpoint:
        """Load the checkpoint; an unreadable, stale or wrong-signature file loads as empty."""
        path = Path(path)
        entries: dict[str, _Entry] = {}
        if path.exists():
            try:
                data = _CheckpointFileModel.model_validate_json(path.read_text("utf-8"))
            except (OSError, UnicodeDecodeError, ValidationError):
                data = None
            if (
                data is not None
                and data.version == CHECKPOINT_VERSION
                and data.signature == signature
            ):
                entries = {
                    h: _Entry(e.block_id, dict(e.translations), list(e.untranslated))
                    for h, e in data.blocks.items()
                }
        return cls(path, signature, entries)

    def save(self) -> None:
        data = {
            "version": CHECKPOINT_VERSION,
            "signature": self.signature,
            "blocks": {
                h: {
                    "block_id": e.block_id,
                    "translations": e.translations,
                    "untranslated": e.untranslated,
                }
                for h, e in self.entries.items()
            },
        }
        atomic_write_text(self.path, json.dumps(data, ensure_ascii=False, indent=2))


def translate_with_checkpoint(
    provider: TranslationProvider,
    jobs: list[TranslationJobIn],
    *,
    checkpoint: BlockCheckpoint,
    on_progress: Callable[[BlockProgress], None] | None = None,
) -> tuple[dict[str, str], list[str]]:
    """Translate `jobs` block by block, persisting each result before moving on.

    A block whose hash is already in `checkpoint` is reused without calling the provider. The
    checkpoint is saved after every freshly translated block, so an interruption (or a provider
    error) leaves the completed blocks recoverable on the next run. Pass an empty checkpoint to
    force a full re-translation while still writing fresh progress.
    """
    translations: dict[str, str] = {}
    untranslated: list[str] = []
    total = len(jobs)
    for i, job in enumerate(jobs, start=1):
        h = block_hash(job)
        cached = checkpoint.entries.get(h)
        if cached is not None:
            expected_ids = {line.id for line in job.translate}
            cached_ids = set(cached.translations)
            untranslated_ids = set(cached.untranslated)
            if (
                cached_ids == expected_ids
                and untranslated_ids <= expected_ids
                and all(text.strip() for text in cached.translations.values())
            ):
                translations.update(cached.translations)
                untranslated.extend(cached.untranslated)
                if on_progress:
                    on_progress(BlockProgress(i, total, job.block_id, reused=True))
                continue
            # A structurally valid file can still contain a stale/mismatched entry. Drop only
            # that entry and regenerate the block instead of failing the whole translation.
            checkpoint.entries.pop(h, None)
        block_map = provider.translate([job])
        block_untranslated = list(getattr(provider, "untranslated_ids", []))
        checkpoint.entries[h] = _Entry(job.block_id, dict(block_map), block_untranslated)
        checkpoint.save()
        translations.update(block_map)
        untranslated.extend(block_untranslated)
        if on_progress:
            on_progress(BlockProgress(i, total, job.block_id, reused=False))
    return translations, untranslated

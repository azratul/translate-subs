"""Output naming convention: <base>.<lang>.<format> (format defaults to .ass)."""

from __future__ import annotations

import re
from collections.abc import Collection
from pathlib import Path

# The full ISO 639-1 two-letter set, so a sidecar/output suffix in *any* language (e.g.
# `episode.ru.srt`) is recognized — the tool translates any language to any language.
ISO_639_1 = frozenset(
    "aa ab ae af ak am an ar as av ay az ba be bg bh bi bm bn bo br bs ca ce ch co cr cs cu cv "
    "cy da de dv dz ee el en eo es et eu fa ff fi fj fo fr fy ga gd gl gn gu gv ha he hi ho hr "
    "ht hu hy hz ia id ie ig ii ik io is it iu ja jv ka kg ki kj kk kl km kn ko kr ks ku kv kw "
    "ky la lb lg li ln lo lt lu lv mg mh mi mk ml mn mr ms mt my na nb nd ne ng nl nn no nr nv "
    "ny oc oj om or os pa pi pl ps pt qu rm rn ro ru rw sa sc sd se sg si sk sl sm sn so sq sr "
    "ss st su sv sw ta te tg th ti tk tl tn to tr ts tt tw ty ug uk ur uz ve vi vo wa wo xh yi "
    "yo za zh zu".split()
)

# Recognized as a trailing language suffix in a filename: the ISO codes plus common spellings
# people actually use in subtitle names (full words and 3-letter codes).
_LANG_SUFFIX_SPELLINGS = frozenset(
    {
        "eng",
        "english",
        "spa",
        "esp",
        "lat",
        "latam",
        "spanish",
        "jpn",
        "jp",
        "japanese",
        "fra",
        "fre",
        "french",
        "por",
        "portuguese",
        "ger",
        "deu",
        "german",
        "ita",
        "italian",
        "chi",
        "zho",
        "chinese",
        "kor",
        "korean",
        "rus",
        "russian",
        "ara",
        "arabic",
    }
)
_LANG_TOKENS = ISO_639_1 | _LANG_SUFFIX_SPELLINGS

SUPPORTED_FORMATS = ("ass", "srt")
DEFAULT_FORMAT = "ass"

# A well-formed target is a language tag: one or more alphanumeric subtags joined by single
# hyphens (e.g. `es-latam`, `pt-BR`, `zh-Hans`). Leading/trailing hyphens and consecutive
# hyphens are rejected. Path separators, `..`, and empty values are rejected up front so a
# hostile `--target` can't steer an on-disk path outside its root.
_TARGET_RE = re.compile(r"[A-Za-z0-9]+(-[A-Za-z0-9]+)*")


def validate_target(target: str) -> str:
    """Return the normalised target if it is a valid language tag, else raise ``ValueError``."""
    normalized = target.strip().replace("_", "-")
    if not normalized or not _TARGET_RE.fullmatch(normalized):
        raise ValueError(
            f"Invalid target language {target!r}: use a language tag like 'es-latam' or 'pt-BR'."
        )
    return normalized


def lang_code(target: str) -> str:
    """Filename code for a target: bare language when it has no region/variant, else the full tag.

    'es' -> 'es', but 'es-latam' -> 'es-latam' and 'es-es' -> 'es-es', 'zh-hans' -> 'zh-hans'. Two
    variants of one language therefore produce *different* output filenames (`<base>.es-latam.ass`
    vs `<base>.es-es.ass`) instead of colliding on `<base>.es.ass`. Each subtag is reduced to its
    alphanumerics and rejoined with hyphens, so even a hostile target (path separators, `..`) can
    never inject path components into `<base>.<lang>.<fmt>`.
    """
    subtags = (target.strip().lower().replace("_", "-")).split("-")
    cleaned = ["".join(ch for ch in sub if ch.isalnum()) for sub in subtags]
    cleaned = [sub for sub in cleaned if sub]
    return "-".join(cleaned) or "out"


# Providers whose default model we control here (so a report can name it instead of "(default)").
# The agent CLIs and API routers pick their own default, which we can't read out, so we say so.
_KNOWN_DEFAULT_MODELS = {"claude": "claude-opus-4-8"}


def effective_model(provider: str, model: str | None) -> str:
    """The model string to record in a report: the explicit one, or the resolved default."""
    if model:
        return model
    return _KNOWN_DEFAULT_MODELS.get(provider, f"{provider} default")


def target_dirname(target: str) -> str:
    """Filesystem-safe, case-normalized directory name for a *full* target.

    Like `lang_code`, this keeps the region/script of a variant ('es-latam', 'es-es', 'zh-hans')
    so different variants get separate memory subtrees and can't contaminate each other. It differs
    from `lang_code` only in that it keeps no record of being a *filename* code: it is used solely
    for the on-disk memory layout, while the output *filename* uses `lang_code`.
    """
    name = target.strip().lower().replace("_", "-")
    cleaned = "".join(ch for ch in name if ch.isalnum() or ch == "-").strip("-")
    return cleaned or "out"


def is_lang_suffix(token: str, known: Collection[str]) -> bool:
    """Whether `token` is a filename language suffix given the caller's `known` token set.

    Recognizes both a simple token (`en`, `spa`, `latam`) and a BCP-47-style tag whose **primary**
    subtag is known (`es-latam`, `es-ES`, `zh-Hans`, `pt-BR`). Centralizing this keeps naming,
    sidecar resolution and batch discovery in agreement about what counts as a language suffix —
    otherwise an `es-latam` output is produced but not recognized when read back.
    """
    token = token.lower()
    if token in known:
        return True
    primary, sep, _rest = token.partition("-")
    return bool(sep) and primary in known


def base_stem(origin: Path) -> str:
    """Original name without extension and without a trailing language suffix."""
    stem = origin.stem
    base, _, last = stem.rpartition(".")
    if base and is_lang_suffix(last, _LANG_TOKENS):
        return base
    return stem


def output_path(
    origin: str | Path,
    *,
    fmt: str = DEFAULT_FORMAT,
    out_dir: str | Path | None = None,
    lang: str = "es",
) -> Path:
    """Output path `<base>.<lang>.<fmt>`.

    Defaults next to the original; `out_dir` redirects it (test sandbox). `fmt` is
    the output container ('ass' keeps positioning/styles, 'srt' is flat).
    """
    origin = Path(origin)
    name = f"{base_stem(origin)}.{lang}.{fmt}"
    directory = Path(out_dir) if out_dir is not None else origin.parent
    return directory / name

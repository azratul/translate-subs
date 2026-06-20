"""Inspect embedded subtitle tracks via ffprobe."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class MediaToolError(Exception):
    """ffprobe/ffmpeg is missing, timed out, or failed."""


# Probing metadata is quick; extraction can be a little slower on large containers.
PROBE_TIMEOUT = 60
EXTRACT_TIMEOUT = 300


def ensure_binary(name: str) -> None:
    """Raise a clear error if an external tool (ffprobe/ffmpeg) is not on PATH."""
    if shutil.which(name) is None:
        raise MediaToolError(
            f"`{name}` was not found on PATH. Install ffmpeg (which provides "
            f"ffprobe and ffmpeg) to read embedded subtitle tracks."
        )


# Text-based subtitle codecs we can export to .srt.
TEXT_CODECS = {"ass", "ssa", "subrip", "srt", "webvtt", "mov_text", "text"}

# File extension to use when extracting, per source codec.
_CODEC_EXT = {
    "ass": ".ass",
    "ssa": ".ass",
    "subrip": ".srt",
    "mov_text": ".srt",
    "webvtt": ".vtt",
}


@dataclass
class SubtitleTrack:
    rel_index: int  # index among subtitle streams (for -map 0:s:N)
    stream_index: int  # absolute stream index in the container
    codec: str
    language: str | None
    title: str | None
    default: bool
    forced: bool

    @property
    def is_text(self) -> bool:
        return self.codec in TEXT_CODECS

    @property
    def extract_ext(self) -> str:
        return _CODEC_EXT.get(self.codec, ".srt")


def probe_subtitle_tracks(media_path: str | Path) -> list[SubtitleTrack]:
    """List the container's subtitle tracks. Raises if ffprobe fails."""
    ensure_binary("ffprobe")
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "s",
        "-show_entries",
        "stream=index,codec_name:stream_tags=language,title:stream_disposition=default,forced",
        "-of",
        "json",
        str(media_path),
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=PROBE_TIMEOUT
        )
    except subprocess.TimeoutExpired as exc:
        raise MediaToolError(f"ffprobe timed out after {PROBE_TIMEOUT}s on {media_path}.") from exc
    except subprocess.CalledProcessError as exc:
        raise MediaToolError(f"ffprobe failed on {media_path}: {exc.stderr or exc}") from exc
    data = json.loads(proc.stdout or "{}")

    tracks: list[SubtitleTrack] = []
    for rel, stream in enumerate(data.get("streams", [])):
        disposition = stream.get("disposition", {})
        tags = stream.get("tags", {})
        tracks.append(
            SubtitleTrack(
                rel_index=rel,
                stream_index=stream.get("index", rel),
                codec=stream.get("codec_name", ""),
                language=tags.get("language"),
                title=tags.get("title"),
                default=bool(disposition.get("default", 0)),
                forced=bool(disposition.get("forced", 0)),
            )
        )
    return tracks

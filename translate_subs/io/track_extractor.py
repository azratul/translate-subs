"""Demux a text subtitle track via ffmpeg."""

from __future__ import annotations

import contextlib
import hashlib
import os
import subprocess
import tempfile
from pathlib import Path

from translate_subs.io.media_probe import (
    EXTRACT_TIMEOUT,
    MediaToolError,
    SubtitleTrack,
    ensure_binary,
)


def _cache_key(media_path: Path, track: SubtitleTrack) -> str:
    """Short content-ish key for the extracted file, so two videos with the same name in
    different folders (or an edited file) never share a cache entry."""
    st = media_path.stat()
    raw = f"{media_path.resolve()}|{st.st_size}|{st.st_mtime_ns}|{track.rel_index}|{track.codec}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def extract_track(media_path: str | Path, track: SubtitleTrack, dest_dir: str | Path) -> Path:
    """Extract `track` to a text file in `dest_dir` and return its path.

    The destination name includes a hash of the source (path/size/mtime/track), so distinct
    videos can't collide and an unchanged file is reused. Extraction goes to a unique temp
    file and is swapped into place with os.replace, so a crash never leaves a partial track.
    The output extension is derived from the codec (ass -> .ass, subrip -> .srt).
    """
    ensure_binary("ffmpeg")
    media_path = Path(media_path)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    key = _cache_key(media_path, track)
    dest = dest_dir / f"{media_path.stem}.{key}.track{track.rel_index}{track.extract_ext}"
    if dest.exists():
        return dest  # cache hit: this exact file/track was already extracted

    fd, tmp_name = tempfile.mkstemp(dir=dest_dir, prefix=".extract.", suffix=track.extract_ext)
    os.close(fd)
    tmp = Path(tmp_name)
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-i",
        str(media_path),
        "-map",
        f"0:s:{track.rel_index}",
        str(tmp),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=EXTRACT_TIMEOUT)
        os.replace(tmp, dest)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
        with contextlib.suppress(OSError):
            tmp.unlink()
        if isinstance(exc, subprocess.TimeoutExpired):
            raise MediaToolError(
                f"ffmpeg timed out after {EXTRACT_TIMEOUT}s extracting track "
                f"{track.rel_index} from {media_path}."
            ) from exc
        raise MediaToolError(
            f"ffmpeg failed extracting track {track.rel_index} from {media_path}: "
            f"{exc.stderr or exc}"
        ) from exc
    return dest

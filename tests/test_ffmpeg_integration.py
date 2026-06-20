"""End-to-end probe + extract against a real container, exercised only when ffmpeg is present.

Most tests fake the media layer; this one mux a subtitle track into an actual `.mkv` with
ffmpeg and then runs the real `ffprobe`/`ffmpeg` path to find and pull it back out. It is
skipped where the tools are missing so the rest of the suite stays hermetic.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from translate_subs.io.media_probe import probe_subtitle_tracks
from translate_subs.io.track_extractor import extract_track

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed",
)


def _make_mkv_with_subtitles(tmp_path):
    srt = tmp_path / "src.srt"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHello there.\n\n"
        "2\n00:00:01,000 --> 00:00:02,000\nGeneral Kenobi.\n",
        encoding="utf-8",
    )
    mkv = tmp_path / "ep.mkv"
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=320x240:d=2",
        "-i",
        str(srt),
        "-c:v",
        "mpeg4",
        "-c:s",
        "srt",
        "-metadata:s:s:0",
        "language=eng",
        str(mkv),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:  # build without the needed encoder/muxer
        pytest.skip(f"ffmpeg could not build the fixture: {exc.stderr.strip()[:200]}")
    return mkv


def test_probe_finds_embedded_subtitle_track(tmp_path):
    mkv = _make_mkv_with_subtitles(tmp_path)
    text_tracks = [t for t in probe_subtitle_tracks(mkv) if t.is_text]
    assert text_tracks, "the muxed subtitle track was not detected"
    assert text_tracks[0].language in (None, "eng", "en")


def test_extract_pulls_back_the_subtitle_text(tmp_path):
    mkv = _make_mkv_with_subtitles(tmp_path)
    track = next(t for t in probe_subtitle_tracks(mkv) if t.is_text)
    out = extract_track(mkv, track, tmp_path / "work")
    assert out.exists()
    content = out.read_text("utf-8", errors="ignore")
    assert "General Kenobi." in content

    # A second extract of the same file/track hits the cache and returns the same path.
    assert extract_track(mkv, track, tmp_path / "work") == out

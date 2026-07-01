"""Small filesystem helpers shared across modules."""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path


def default_file_mode() -> int:
    """The mode a normal `open(...,'w')` would produce: 0666 masked by the process umask.

    `tempfile.mkstemp` always creates files as 0600, so files we write atomically would be
    unreadable to other users (e.g. a Jellyfin/Plex process running as a different account).
    Re-deriving the umask restores the user's expected, share-friendly permissions.
    """
    umask = os.umask(0)
    os.umask(umask)
    return 0o666 & ~umask


def ensure_private_dir(path: str | Path) -> Path:
    """Create `path` (and any missing parents) and restrict it to the owner (0700).

    Internal state and the extracted-track cache can carry subtitle text and live under the
    private data root, so the directories holding them must not be traversable by other users.
    The directory and every ancestor *this call creates* are tightened; pre-existing ancestors
    (the user's home, the XDG roots) are left as the user configured them. Tightening the target
    is idempotent, so it also repairs a directory left 0755 by an older release. A chmod failure
    (e.g. a network filesystem that ignores POSIX modes) is swallowed so it never breaks the write.
    """
    path = Path(path)
    # Ancestors that don't exist yet will be created by mkdir(parents=True) with the default umask;
    # collect them first so we can tighten exactly those (never a pre-existing parent).
    created: list[Path] = []
    probe = path
    while not probe.exists():
        created.append(probe)
        if probe.parent == probe:
            break
        probe = probe.parent
    path.mkdir(parents=True, exist_ok=True)
    for directory in {path, *created}:
        with contextlib.suppress(OSError):
            directory.chmod(0o700)
    return path


def atomic_write_text(path: str | Path, text: str, *, private: bool = False) -> None:
    """Write `text` to `path` atomically: a temp file in the same dir, then os.replace.

    An interrupted run can no longer leave a half-written, unparseable file; readers always
    see either the old or the new complete content.

    `private=True` keeps the file owner-only (0600) instead of widening it to the umask, and
    tightens the containing directory to 0700: internal state (series memory, checkpoints, episode
    context, reports) may carry subtitle text and lives in the private data root, so neither it nor
    its directory should be reachable by other users. The share-friendly mode exists for files a
    media server reads — but the final subtitle is written by `atomic_save`, not here.
    """
    path = Path(path)
    if private:
        ensure_private_dir(path.parent)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        # mkstemp already creates the temp file as 0600; only widen it when not private.
        if not private:
            os.chmod(tmp, default_file_mode())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise

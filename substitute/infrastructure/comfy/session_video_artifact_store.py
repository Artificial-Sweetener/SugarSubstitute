#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Own process-lifetime temporary generated video artifacts."""

from __future__ import annotations

import atexit
import shutil
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from threading import Lock
from uuid import uuid4

from substitute.domain.output_media import OutputMediaKind
from substitute.domain.workflow import ImageMeta
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.comfy.session_video_artifact_store")
_OWNERSHIP_MARKER = ".sugarsubstitute-session-video-v1"
_MARKER_CONTENT = "SugarSubstitute session video artifacts v1\n"
_ABANDONED_AFTER_SECONDS = 7 * 24 * 60 * 60


class SessionVideoArtifactStore:
    """Allocate and release video files inside one private session directory."""

    def __init__(
        self,
        root: Path | None = None,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Create a unique owned root without adopting existing content."""

        base = root or Path(tempfile.gettempdir()) / "SugarSubstitute" / "video-output"
        base = base.resolve()
        base.mkdir(parents=True, exist_ok=True)
        _repair_abandoned_roots(base, now=clock())
        self._root = (base / uuid4().hex).resolve()
        self._root.mkdir(parents=True, exist_ok=False)
        (self._root / _OWNERSHIP_MARKER).write_text(
            _MARKER_CONTENT,
            encoding="utf-8",
        )
        self._owned_paths: set[Path] = set()
        self._lock = Lock()
        self._closed = False

    @property
    def root(self) -> Path:
        """Return the private session root."""

        return self._root

    def allocate_partial(self) -> Path:
        """Reserve a unique path for an incomplete transfer."""

        with self._lock:
            self._ensure_open()
            path = self._root / f"{uuid4().hex}.partial"
            self._owned_paths.add(path)
            return path

    def promote(self, partial_path: Path, *, suffix: str) -> Path:
        """Atomically rename one owned partial artifact for session playback."""

        with self._lock:
            self._ensure_owned(partial_path)
            final_path = partial_path.with_suffix(suffix)
            partial_path.replace(final_path)
            self._owned_paths.remove(partial_path)
            self._owned_paths.add(final_path)
            return final_path

    def release(self, path: Path) -> bool:
        """Delete one known owned artifact and reject unrelated paths."""

        resolved = path.resolve()
        with self._lock:
            if resolved not in self._owned_paths:
                return False
            try:
                resolved.unlink(missing_ok=True)
            except OSError as error:
                log_warning(
                    _LOGGER,
                    "Deferred temporary video cleanup until session shutdown",
                    path_suffix=resolved.suffix,
                    error_type=type(error).__name__,
                )
                return False
            self._owned_paths.remove(resolved)
        return True

    def close(self) -> None:
        """Release the complete private store exactly once."""

        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._owned_paths.clear()
        shutil.rmtree(self._root, ignore_errors=True)

    def _ensure_open(self) -> None:
        """Reject allocation after lifecycle shutdown."""

        if self._closed:
            raise RuntimeError("Session video artifact store is closed.")

    def _ensure_owned(self, path: Path) -> None:
        """Reject mutation of paths outside this store's allocation set."""

        if path.resolve() not in self._owned_paths:
            raise ValueError("Video artifact path is not owned by this session.")


_DEFAULT_STORE: SessionVideoArtifactStore | None = None
_DEFAULT_STORE_LOCK = Lock()


def default_session_video_store() -> SessionVideoArtifactStore:
    """Return the process-lifetime generated video store."""

    global _DEFAULT_STORE
    with _DEFAULT_STORE_LOCK:
        if _DEFAULT_STORE is None:
            _DEFAULT_STORE = SessionVideoArtifactStore()
            atexit.register(_DEFAULT_STORE.close)
        return _DEFAULT_STORE


def close_default_session_video_store() -> None:
    """Close and forget the process store without creating it."""

    global _DEFAULT_STORE
    with _DEFAULT_STORE_LOCK:
        store = _DEFAULT_STORE
        _DEFAULT_STORE = None
    if store is not None:
        store.close()


def release_temporary_video_artifact(metadata: ImageMeta) -> None:
    """Release one registry-retired leased video while preserving durable media."""

    if (
        metadata.media_kind is not OutputMediaKind.VIDEO
        or not metadata.temporary
        or not metadata.path
    ):
        return
    default_session_video_store().release(Path(metadata.path))


def _repair_abandoned_roots(base: Path, *, now: float) -> None:
    """Remove only old directories carrying this store's exact ownership marker."""

    try:
        candidates = tuple(base.iterdir())
    except OSError as error:
        log_warning(
            _LOGGER,
            "Skipped temporary video repair scan",
            error_type=type(error).__name__,
        )
        return
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        marker = candidate / _OWNERSHIP_MARKER
        try:
            if marker.read_text(encoding="utf-8") != _MARKER_CONTENT:
                continue
            if now - marker.stat().st_mtime < _ABANDONED_AFTER_SECONDS:
                continue
            resolved = candidate.resolve()
            if resolved.parent != base:
                continue
            shutil.rmtree(resolved)
        except OSError as error:
            log_warning(
                _LOGGER,
                "Skipped abandoned temporary video cleanup",
                error_type=type(error).__name__,
            )


__all__ = [
    "SessionVideoArtifactStore",
    "close_default_session_video_store",
    "default_session_video_store",
    "release_temporary_video_artifact",
]

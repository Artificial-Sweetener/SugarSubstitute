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
from pathlib import Path
from threading import Lock
from uuid import uuid4


class SessionVideoArtifactStore:
    """Allocate and release video files inside one private session directory."""

    def __init__(self, root: Path | None = None) -> None:
        """Create a unique owned root without adopting existing content."""

        base = root or Path(tempfile.gettempdir()) / "SugarSubstitute" / "video-output"
        self._root = (base / uuid4().hex).resolve()
        self._root.mkdir(parents=True, exist_ok=False)
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
            self._owned_paths.remove(resolved)
        resolved.unlink(missing_ok=True)
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


__all__ = ["SessionVideoArtifactStore", "default_session_video_store"]

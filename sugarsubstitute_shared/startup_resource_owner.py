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

"""Retain startup-resource cleanup authority in the creating supervisor."""

from collections.abc import Callable
import logging
from threading import Lock
from uuid import uuid4

_LOGGER = logging.getLogger(__name__)


class StartupResourceOwner:
    """Serialize idempotent cleanup without giving stale clients replacement authority."""

    def __init__(self) -> None:
        """Initialize an empty, process-local resource slot."""
        self._lock = Lock()
        self._closed = False
        self._identity: str | None = None
        self._cleanup: Callable[[], None] | None = None

    def register(self, cleanup: Callable[[], None]) -> str:
        """Bind a fresh identity only after any previous resource has been released."""
        with self._lock:
            if self._closed:
                raise RuntimeError("The startup resource owner is closed.")
            if self._cleanup is not None:
                raise RuntimeError(
                    "The previous startup resource must be released first."
                )
            self._identity = uuid4().hex
            self._cleanup = cleanup
            return self._identity

    def release(self, identity: str) -> bool:
        """Release the matching resource exactly once, retaining failed cleanup for retry."""
        with self._lock:
            if identity != self._identity:
                return False
            return self._release_locked()

    def close(self) -> None:
        """Attempt cleanup on supervisor shutdown without preventing lease release."""
        with self._lock:
            self._closed = True
            self._release_locked()

    def _release_locked(self) -> bool:
        """Run the owner callback under serialization and preserve failure diagnostics."""
        if self._cleanup is None:
            return True
        try:
            self._cleanup()
        except Exception:
            _LOGGER.exception(
                "Startup resource cleanup failed",
                extra={"resource_identity": self._identity},
            )
            return False
        self._cleanup = None
        return True

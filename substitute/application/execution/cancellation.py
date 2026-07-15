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

"""Provide cancellation generations for execution tasks."""

from __future__ import annotations

from threading import Lock
from typing import Protocol


class CancellationToken(Protocol):
    """Describe cancellation state visible to task work."""

    @property
    def generation(self) -> int:
        """Return the cancellation generation for identity matching."""

    @property
    def is_cancelled(self) -> bool:
        """Return whether cancellation has been requested."""

    @property
    def reason(self) -> str | None:
        """Return the cancellation reason when one has been supplied."""


class CancellationSource(CancellationToken):
    """Own cancellation state for one execution request generation."""

    def __init__(self, *, generation: int) -> None:
        """Create an uncancelled source for one request generation."""

        _require_non_negative(generation, field_name="generation")
        self._generation = generation
        self._is_cancelled = False
        self._reason: str | None = None
        self._lock = Lock()

    @property
    def generation(self) -> int:
        """Return the cancellation generation for identity matching."""

        return self._generation

    @property
    def is_cancelled(self) -> bool:
        """Return whether cancellation has been requested."""

        with self._lock:
            return self._is_cancelled

    @property
    def reason(self) -> str | None:
        """Return the cancellation reason when one has been supplied."""

        with self._lock:
            return self._reason

    def cancel(self, *, reason: str) -> None:
        """Request cancellation with a nonblank reason."""

        _require_non_blank(reason, field_name="reason")
        with self._lock:
            if self._is_cancelled:
                return
            self._is_cancelled = True
            self._reason = reason


class CancellationController:
    """Create monotonically increasing execution cancellation sources."""

    def __init__(self, *, initial_generation: int = 0) -> None:
        """Create a controller starting after the supplied generation."""

        _require_non_negative(initial_generation, field_name="initial_generation")
        self._generation = initial_generation
        self._lock = Lock()

    def next_source(self) -> CancellationSource:
        """Return a fresh uncancelled cancellation source."""

        with self._lock:
            self._generation += 1
            generation = self._generation
        return CancellationSource(generation=generation)


class NeverCancelled:
    """Expose a stable uncancelled token for synchronous tests and defaults."""

    @property
    def generation(self) -> int:
        """Return the neutral cancellation generation."""

        return 0

    @property
    def is_cancelled(self) -> bool:
        """Return false because this token never cancels."""

        return False

    @property
    def reason(self) -> str | None:
        """Return no cancellation reason."""

        return None


def _require_non_negative(value: int, *, field_name: str) -> None:
    """Reject negative generation values."""

    if value < 0:
        raise ValueError(f"{field_name} must be non-negative.")


def _require_non_blank(value: str, *, field_name: str) -> None:
    """Reject blank cancellation labels."""

    if not value.strip():
        raise ValueError(f"{field_name} must not be blank.")


__all__ = [
    "CancellationController",
    "CancellationSource",
    "CancellationToken",
    "NeverCancelled",
]

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

"""Provide a deterministic semantic refresh debouncer."""

from __future__ import annotations

from collections.abc import Callable


class FakeSemanticDebouncer:
    """Store the latest semantic debounce callback for deterministic tests."""

    def __init__(self) -> None:
        """Initialize pending callback storage."""

        self.pending_callback: Callable[[], None] | None = None

    @property
    def is_pending(self) -> bool:
        """Return whether a semantic refresh callback is queued."""

        return self.pending_callback is not None

    def request(self, callback: Callable[[], None], *, reason: str) -> None:
        """Store the latest semantic refresh callback."""

        _ = reason
        self.pending_callback = callback

    def flush(self, *, reason: str) -> bool:
        """Run the latest callback immediately."""

        _ = reason
        callback = self.pending_callback
        self.pending_callback = None
        if callback is None:
            return False
        callback()
        return True

    def cancel(self, *, reason: str) -> bool:
        """Drop any queued semantic refresh callback."""

        _ = reason
        had_callback = self.pending_callback is not None
        self.pending_callback = None
        return had_callback

    def fire(self) -> None:
        """Deliver the queued callback when a test advances semantic debounce."""

        assert self.flush(reason="test")

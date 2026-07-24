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

"""Own transient input-method composition state outside persisted source."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromptImePreedit:
    """Describe transient preedit text anchored to source coordinates."""

    source_start: int
    source_end: int
    text: str
    cursor_utf16: int
    cursor_visible: bool

    def __post_init__(self) -> None:
        """Reject invalid source and UTF-16 positions."""

        if self.source_start < 0:
            raise ValueError("IME preedit source start must be non-negative.")
        if self.source_end < self.source_start:
            raise ValueError("IME preedit source end must not precede its start.")
        if self.cursor_utf16 < 0:
            raise ValueError("IME preedit cursor must be non-negative.")
        if not self.text:
            raise ValueError("IME preedit text must not be empty.")


class PromptImeSession:
    """Own preedit lifecycle and unrelated-source-change cancellation."""

    __slots__ = ("_commit_in_progress", "_preedit")

    def __init__(self) -> None:
        """Create an inactive composition session."""

        self._preedit: PromptImePreedit | None = None
        self._commit_in_progress = False

    @property
    def preedit(self) -> PromptImePreedit | None:
        """Return the current immutable preedit state."""

        return self._preedit

    @property
    def is_composing(self) -> bool:
        """Return whether non-empty preedit text is active."""

        return self._preedit is not None

    def set_preedit(self, preedit: PromptImePreedit | None) -> None:
        """Replace transient composition state."""

        self._preedit = preedit

    def begin_commit(self) -> None:
        """Mark the source commit produced by the current IME event."""

        if self._commit_in_progress:
            raise RuntimeError("An IME source commit is already active.")
        self._commit_in_progress = True

    def end_commit(self) -> None:
        """Finish the current IME-produced source commit."""

        if not self._commit_in_progress:
            raise RuntimeError("No IME source commit is active.")
        self._commit_in_progress = False

    def source_changed(self) -> None:
        """Cancel composition after a source change from another owner."""

        if not self._commit_in_progress:
            self._preedit = None

    def cancel(self) -> None:
        """Discard preedit without mutating persisted source."""

        self._preedit = None


__all__ = ["PromptImePreedit", "PromptImeSession"]

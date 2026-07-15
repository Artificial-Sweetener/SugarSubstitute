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

"""Provide a no-op taskbar progress presenter."""

from __future__ import annotations

from typing import Protocol


class TaskbarProgressPresenter(Protocol):
    """Define the shell-facing taskbar progress operations."""

    def set_progress(self, percent: int) -> None:
        """Accept a taskbar progress value."""

    def clear_progress(self) -> None:
        """Accept a taskbar progress clear request."""


class NoOpTaskbarProgressPresenter:
    """Ignore taskbar progress calls while native progress is disabled."""

    def set_progress(self, percent: int) -> None:
        """Ignore progress updates."""

        _ = percent

    def clear_progress(self) -> None:
        """Ignore progress clearing."""


def create_taskbar_progress_presenter(window: object) -> TaskbarProgressPresenter:
    """Return the disabled taskbar progress presenter."""

    _ = window
    return NoOpTaskbarProgressPresenter()


__all__ = [
    "NoOpTaskbarProgressPresenter",
    "TaskbarProgressPresenter",
    "create_taskbar_progress_presenter",
]

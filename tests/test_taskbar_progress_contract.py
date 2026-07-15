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

"""Contract tests for disabled shell taskbar progress presentation."""

from __future__ import annotations

from substitute.presentation.shell.taskbar_progress import (
    NoOpTaskbarProgressPresenter,
    create_taskbar_progress_presenter,
)


def test_taskbar_progress_factory_returns_noop_presenter() -> None:
    """Taskbar progress is currently disabled for every window."""

    presenter = create_taskbar_progress_presenter(object())

    assert isinstance(presenter, NoOpTaskbarProgressPresenter)


def test_noop_taskbar_progress_presenter_accepts_progress_calls() -> None:
    """Disabled taskbar progress should be safe for existing shell callers."""

    presenter = NoOpTaskbarProgressPresenter()

    presenter.set_progress(125)
    presenter.set_progress(-10)
    presenter.clear_progress()

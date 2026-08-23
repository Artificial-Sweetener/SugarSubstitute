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

"""Verify composed signal-binder ownership."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.presentation.shell.main_window_signal_binder import (
    MainWindowSignalBinder,
    main_window_signal_binder_for,
)


def test_signal_binder_for_reuses_composed_shell_instance() -> None:
    """Binder lookup should preserve the shell-composed owner."""

    shell = SimpleNamespace()
    binder = MainWindowSignalBinder(shell)
    shell.main_window_signal_binder = binder

    assert main_window_signal_binder_for(shell) is binder

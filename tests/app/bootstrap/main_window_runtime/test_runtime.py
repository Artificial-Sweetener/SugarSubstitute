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

"""Verify deterministic main-window presentation runtime loading."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.app.bootstrap.main_window_runtime import MainWindowRuntimeLoader


class _MainWindow:
    """Represent the loaded main-window type for the runtime contract."""


def _create_taskbar_progress_presenter(_frame: object) -> object:
    """Return a distinct presenter from the fake presentation module."""

    return object()


def test_main_window_runtime_loader_imports_complete_runtime_once() -> None:
    """Repeated consumers should share one completely loaded runtime."""

    imported_names: list[str] = []
    modules = {
        "substitute.presentation.shell.main_window": SimpleNamespace(
            MainWindow=_MainWindow
        ),
        "substitute.presentation.shell.taskbar_progress": SimpleNamespace(
            create_taskbar_progress_presenter=_create_taskbar_progress_presenter
        ),
    }

    def import_module(name: str) -> object:
        """Record and return one fake presentation module."""

        imported_names.append(name)
        return modules[name]

    loader = MainWindowRuntimeLoader(import_module=import_module)

    first = loader.load()
    second = loader.load()

    assert first is second
    assert first.main_window_class is _MainWindow
    assert first.create_taskbar_progress_presenter is _create_taskbar_progress_presenter
    assert imported_names == [
        "substitute.presentation.shell.main_window",
        "substitute.presentation.shell.taskbar_progress",
    ]

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

"""Load the main-window presentation runtime before external startup begins."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import importlib
from typing import Any, cast


@dataclass(frozen=True, slots=True)
class MainWindowRuntime:
    """Hold the presentation types needed to compose the main shell."""

    main_window_class: type[Any]
    create_taskbar_progress_presenter: Callable[[object], object]


class MainWindowRuntimeLoader:
    """Own idempotent loading of main-window presentation collaborators."""

    def __init__(
        self,
        *,
        import_module: Callable[[str], object] = importlib.import_module,
    ) -> None:
        """Store the import boundary without loading presentation modules."""

        self._import_module = import_module
        self._runtime: MainWindowRuntime | None = None

    def load(self) -> MainWindowRuntime:
        """Import the complete runtime once and return the retained result."""

        if self._runtime is None:
            main_window_module = self._import_module(
                "substitute.presentation.shell.main_window"
            )
            taskbar_module = self._import_module(
                "substitute.presentation.shell.taskbar_progress"
            )
            self._runtime = MainWindowRuntime(
                main_window_class=cast(
                    type[Any],
                    getattr(main_window_module, "MainWindow"),
                ),
                create_taskbar_progress_presenter=cast(
                    Callable[[object], object],
                    getattr(taskbar_module, "create_taskbar_progress_presenter"),
                ),
            )
        return self._runtime


_RUNTIME_LOADER = MainWindowRuntimeLoader()


def load_main_window_runtime() -> MainWindowRuntime:
    """Return the process-owned main-window runtime."""

    return _RUNTIME_LOADER.load()


__all__ = [
    "MainWindowRuntime",
    "MainWindowRuntimeLoader",
    "load_main_window_runtime",
]

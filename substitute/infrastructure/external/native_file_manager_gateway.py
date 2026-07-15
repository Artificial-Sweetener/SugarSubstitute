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

"""Provide native file-manager reveal behavior for local assets."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
import subprocess
import sys

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from substitute.application.ports.file_manager_gateway import (
    FileRevealResult,
    FileRevealStatus,
)
from substitute.infrastructure.process.hidden_process_runner import creation_flags
from substitute.shared.logging.logger import get_logger, log_exception, log_warning

_LOGGER = get_logger("infrastructure.external.native_file_manager_gateway")
ProcessLauncher = Callable[[Sequence[str]], None]
DirectoryOpener = Callable[[Path], bool]


class NativeFileManagerGateway:
    """Reveal local files with native selection and a desktop-folder fallback."""

    def __init__(
        self,
        *,
        platform_name: str | None = None,
        launch_process: ProcessLauncher | None = None,
        open_parent_directory: DirectoryOpener | None = None,
    ) -> None:
        """Configure platform dependencies while keeping native behavior testable."""

        self._platform_name = platform_name or sys.platform
        self._launch_process = launch_process or _launch_process
        self._open_parent_directory = open_parent_directory or _open_parent_directory

    def reveal_file(self, asset_path: Path) -> FileRevealResult:
        """Reveal an existing file or open its parent directory when required."""

        if not asset_path.is_file():
            log_warning(
                _LOGGER,
                "Cannot reveal missing local asset",
                asset_name=asset_path.name,
            )
            return FileRevealResult(FileRevealStatus.MISSING)

        resolved_path = asset_path.resolve()
        try:
            if self._platform_name == "win32":
                self._launch_process(("explorer.exe", "/select,", str(resolved_path)))
                return FileRevealResult(FileRevealStatus.REVEALED)
            if self._platform_name == "darwin":
                self._launch_process(("open", "-R", str(resolved_path)))
                return FileRevealResult(FileRevealStatus.REVEALED)
            if self._open_parent_directory(resolved_path.parent):
                return FileRevealResult(FileRevealStatus.OPENED_PARENT_DIRECTORY)
        except OSError as error:
            log_exception(
                _LOGGER,
                "Failed to launch native file manager",
                asset_name=resolved_path.name,
                platform=self._platform_name,
                error=error,
            )
            return FileRevealResult(FileRevealStatus.FAILED)

        log_warning(
            _LOGGER,
            "Desktop services declined to open asset parent directory",
            asset_name=resolved_path.name,
            platform=self._platform_name,
        )
        return FileRevealResult(FileRevealStatus.FAILED)


def _launch_process(command: Sequence[str]) -> None:
    """Launch one native file-manager command without a shell or console window."""

    subprocess.Popen(list(command), creationflags=creation_flags())


def _open_parent_directory(directory: Path) -> bool:
    """Open a directory through the desktop's registered file manager."""

    return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory))))


__all__ = ["NativeFileManagerGateway"]

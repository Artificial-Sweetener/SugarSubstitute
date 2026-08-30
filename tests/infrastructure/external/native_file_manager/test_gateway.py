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

"""Verify native file-manager reveal behavior without launching desktop processes."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from substitute.application.ports.file_manager_gateway import FileRevealStatus
from substitute.infrastructure.external.native_file_manager_gateway import (
    NativeFileManagerGateway,
)


def test_windows_reveal_selects_existing_file_in_explorer(tmp_path: Path) -> None:
    """Windows reveal should launch Explorer with the resolved file selection."""

    asset = tmp_path / "output.png"
    asset.write_bytes(b"image")
    commands: list[tuple[str, ...]] = []
    gateway = NativeFileManagerGateway(
        platform_name="win32",
        launch_process=lambda command: commands.append(tuple(command)),
    )

    result = gateway.reveal_file(asset)

    assert result.status is FileRevealStatus.REVEALED
    assert commands == [("explorer.exe", "/select,", str(asset.resolve()))]


def test_macos_reveal_selects_existing_file_in_finder(tmp_path: Path) -> None:
    """macOS reveal should ask Finder to reveal the resolved file."""

    asset = tmp_path / "output.png"
    asset.write_bytes(b"image")
    commands: list[tuple[str, ...]] = []
    gateway = NativeFileManagerGateway(
        platform_name="darwin",
        launch_process=lambda command: commands.append(tuple(command)),
    )

    result = gateway.reveal_file(asset)

    assert result.status is FileRevealStatus.REVEALED
    assert commands == [("open", "-R", str(asset.resolve()))]


def test_linux_reveal_opens_parent_directory_when_selection_is_not_portable(
    tmp_path: Path,
) -> None:
    """Linux reveal should open the parent folder through desktop services."""

    asset = tmp_path / "output.png"
    asset.write_bytes(b"image")
    opened_directories: list[Path] = []

    def open_parent_directory(directory: Path) -> bool:
        """Record the desktop-services fallback directory."""

        opened_directories.append(directory)
        return True

    gateway = NativeFileManagerGateway(
        platform_name="linux",
        open_parent_directory=open_parent_directory,
    )

    result = gateway.reveal_file(asset)

    assert result.status is FileRevealStatus.OPENED_PARENT_DIRECTORY
    assert opened_directories == [tmp_path.resolve()]


def test_reveal_rejects_missing_local_asset(tmp_path: Path) -> None:
    """Missing files should not launch a native process or folder fallback."""

    commands: list[Sequence[str]] = []
    gateway = NativeFileManagerGateway(
        platform_name="win32",
        launch_process=commands.append,
    )

    result = gateway.reveal_file(tmp_path / "missing.png")

    assert result.status is FileRevealStatus.MISSING
    assert commands == []

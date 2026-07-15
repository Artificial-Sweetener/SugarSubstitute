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

"""Verify application-level local asset reveal orchestration."""

from __future__ import annotations

from pathlib import Path

from substitute.application.ports.file_manager_gateway import (
    FileRevealResult,
    FileRevealStatus,
)
from substitute.application.workflows.asset_reveal_service import AssetRevealService


class _FileManagerGateway:
    """Record local file-manager reveal calls."""

    def __init__(self, result: FileRevealResult) -> None:
        """Configure the reveal result returned to the service."""

        self._result = result
        self.paths: list[Path] = []

    def reveal_file(self, asset_path: Path) -> FileRevealResult:
        """Record the requested path and return the configured outcome."""

        self.paths.append(asset_path)
        return self._result


def test_reveal_asset_rejects_blank_metadata_path() -> None:
    """Blank metadata should not reach the native file-manager gateway."""

    gateway = _FileManagerGateway(FileRevealResult(FileRevealStatus.REVEALED))
    service = AssetRevealService(gateway)

    result = service.reveal_asset("  ")

    assert result.status is FileRevealStatus.PATH_UNAVAILABLE
    assert gateway.paths == []


def test_reveal_asset_delegates_normalized_metadata_path() -> None:
    """Reveal should forward a non-empty local path through the application port."""

    gateway = _FileManagerGateway(FileRevealResult(FileRevealStatus.REVEALED))
    service = AssetRevealService(gateway)

    result = service.reveal_asset(" C:/outputs/image.png ")

    assert result.succeeded is True
    assert gateway.paths == [Path("C:/outputs/image.png")]

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

"""Coordinate user requests to reveal local canvas assets."""

from __future__ import annotations

from pathlib import Path

from substitute.application.ports.file_manager_gateway import (
    FileManagerGateway,
    FileRevealResult,
    FileRevealStatus,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("application.workflows.asset_reveal_service")


class AssetRevealService:
    """Delegate local asset revelation through the platform file-manager boundary."""

    def __init__(self, file_manager_gateway: FileManagerGateway) -> None:
        """Store the platform adapter responsible for native reveal behavior."""

        self._file_manager_gateway = file_manager_gateway

    def reveal_asset(self, asset_path: str) -> FileRevealResult:
        """Reveal a metadata-backed asset path without exposing platform policy."""

        normalized_path = asset_path.strip()
        if not normalized_path:
            log_warning(
                _LOGGER,
                "Rejected asset reveal request without a local path",
            )
            return FileRevealResult(FileRevealStatus.PATH_UNAVAILABLE)

        result = self._file_manager_gateway.reveal_file(Path(normalized_path))
        if not result.succeeded:
            log_warning(
                _LOGGER,
                "Asset reveal request did not reach a file manager",
                asset_name=Path(normalized_path).name,
                status=result.status.value,
            )
        return result


__all__ = ["AssetRevealService"]

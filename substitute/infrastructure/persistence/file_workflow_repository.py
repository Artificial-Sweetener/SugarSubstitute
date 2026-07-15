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

"""Persist compiled Comfy workflow payloads to JSON files."""

from __future__ import annotations

import json
from pathlib import Path

from substitute.domain.common import JsonObject
from substitute.shared.logging.logger import get_logger, log_error

_LOGGER = get_logger("infrastructure.persistence.file_workflow_repository")


class FileWorkflowRepository:
    """Implement workflow JSON persistence on local filesystem."""

    def save_workflow_json(self, path: Path, workflow_payload: JsonObject) -> None:
        """Write workflow payload to destination path with stable indentation."""

        try:
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w", encoding="utf-8") as handle:
                json.dump(workflow_payload, handle, indent=2)
        except Exception as error:
            log_error(
                _LOGGER,
                "Failed to save workflow JSON",
                path=path,
                error=error,
            )
            raise


__all__ = [
    "FileWorkflowRepository",
]

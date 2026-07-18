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

"""Read direct Comfy workflow documents from local JSON files."""

from __future__ import annotations

import json
from pathlib import Path

from substitute.domain.common import JsonObject

_MAX_WORKFLOW_BYTES = 64 * 1024 * 1024


class JsonComfyWorkflowRepository:
    """Decode bounded UTF-8 Comfy workflow JSON objects."""

    def load(self, path: Path) -> JsonObject:
        """Return a validated top-level JSON object from a local file."""

        source_path = path.resolve()
        if source_path.suffix.casefold() != ".json":
            raise ValueError("Comfy workflow files must use the .json extension.")
        if not source_path.is_file():
            raise FileNotFoundError(
                f"Comfy workflow file does not exist: {source_path}"
            )
        file_size = source_path.stat().st_size
        if file_size > _MAX_WORKFLOW_BYTES:
            raise ValueError("Comfy workflow JSON exceeds the 64 MiB safety limit.")
        try:
            payload = json.loads(source_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Comfy workflow JSON is invalid at line {error.lineno}, "
                f"column {error.colno}."
            ) from error
        if not isinstance(payload, dict):
            raise ValueError("Comfy workflow JSON must contain a top-level object.")
        return payload


__all__ = ["JsonComfyWorkflowRepository"]

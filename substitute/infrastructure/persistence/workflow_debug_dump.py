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

"""Persist workflow debug snapshots for characterization and diagnostics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from substitute.shared.logging.logger import get_logger, log_error

_LOGGER = get_logger("infrastructure.persistence.workflow_debug_dump")


def dump_workflow_raw(workflow: Any, out_path: Path) -> None:
    """Dump full workflow state to JSON for diagnostics and characterization tests."""

    try:

        def default(value: Any) -> Any:
            """Serialize non-JSON-native values for debug dumps."""

            if hasattr(value, "__dataclass_fields__"):
                return {key: getattr(value, key) for key in value.__dataclass_fields__}
            if isinstance(value, set):
                return list(value)
            return str(value)

        full_dump = {
            "cubes": {
                alias: {
                    "cube_id": cube.cube_id,
                    "display_name": cube.display_name,
                    "alias": cube.alias,
                    "original_cube": cube.original_cube,
                    "buffer": cube.buffer,
                    "undo_stack": cube.undo_stack,
                    "redo_stack": cube.redo_stack,
                    "dirty": cube.dirty,
                }
                for alias, cube in workflow.cubes.items()
            },
            "stack_order": list(workflow.stack_order),
            "metadata": dict(workflow.metadata),
        }
        with out_path.open("w", encoding="utf-8") as handle:
            json.dump(full_dump, handle, indent=2, default=default)
    except Exception as error:
        log_error(
            _LOGGER,
            "Failed to dump workflow raw state",
            path=out_path,
            error=error,
        )


__all__ = [
    "dump_workflow_raw",
]

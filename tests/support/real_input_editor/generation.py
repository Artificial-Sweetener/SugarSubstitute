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

"""Expose generation-product assertions for the real Input editor harness."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from substitute.domain.workflow import WorkflowState

from .harness import RealShellInputEditorHarness


def node_image_value(workflow: WorkflowState, node_name: str) -> Path:
    """Return one generation product path from the execution-only graph copy."""
    nodes = cast(
        "dict[str, dict[str, dict[str, object]]]",
        workflow.cubes[RealShellInputEditorHarness.CUBE_ALIAS].buffer["nodes"],
    )
    value = nodes[node_name]["inputs"]["image"]
    if not isinstance(value, str):
        raise AssertionError(f"{node_name} did not receive a generation product")
    return Path(value)

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

"""Apply transient prompt values to detached direct-workflow buffers."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

from substitute.application.workflows import DIRECT_WORKFLOW_SECTION_KEY
from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.common import JsonObject


class DirectWorkflowPromptFieldOverlayService:
    """Own immutable prompt-field overlays for direct Comfy authoring state."""

    def apply(
        self,
        document: DirectWorkflowState,
        *,
        prompt_field_overrides: Mapping[tuple[str, str, str], str],
    ) -> JsonObject:
        """Return a detached editable buffer containing transient prompt values."""

        buffer = document.buffer
        if not isinstance(buffer, Mapping):
            raise ValueError("Direct Comfy workflow has no editable graph buffer.")
        detached_buffer = deepcopy(buffer)
        nodes = detached_buffer.get("nodes")
        if not isinstance(nodes, dict):
            raise ValueError("Direct Comfy workflow buffer has no editable nodes.")
        for locator, value in prompt_field_overrides.items():
            section_key, node_id, field_key = locator
            if section_key != DIRECT_WORKFLOW_SECTION_KEY:
                raise ValueError(f"Unexpected direct prompt section: {section_key}")
            node = nodes.get(node_id)
            if not isinstance(node, dict):
                raise ValueError(f"Direct prompt node is unavailable: {node_id}")
            inputs = node.get("inputs")
            if not isinstance(inputs, dict) or field_key not in inputs:
                raise ValueError(
                    f"Direct prompt input is unavailable: {node_id}.{field_key}"
                )
            inputs[field_key] = value
        return detached_buffer


__all__ = ["DirectWorkflowPromptFieldOverlayService"]

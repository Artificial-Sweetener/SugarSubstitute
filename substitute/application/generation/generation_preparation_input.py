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

"""Capture generation preparation inputs detached from live workflow mutation."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from substitute.application.generation.generation_service import GenerationRequest
from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.domain.recipes.sugar_ast import GlobalOverrideSerializationScope


@dataclass(frozen=True, slots=True)
class CapturedGenerationRequest:
    """Carry workflow generation state detached from live UI/session mutation."""

    workflow_id: str
    workflow_name: str
    workflow: Any
    behavior_snapshot: EditorBehaviorSnapshot | None
    enabled_node_keys_by_alias: Mapping[str, tuple[str, ...]] = field(
        default_factory=dict
    )
    disabled_node_keys_by_alias: Mapping[str, tuple[str, ...]] = field(
        default_factory=dict
    )
    global_override_scopes: Mapping[str, GlobalOverrideSerializationScope] | None = None

    @classmethod
    def capture(
        cls,
        *,
        request: GenerationRequest,
        behavior_snapshot: EditorBehaviorSnapshot | None,
    ) -> "CapturedGenerationRequest":
        """Return a detached preparation request from a live generation request."""

        workflow = deepcopy(request.workflow)
        return cls(
            workflow_id=request.workflow_id,
            workflow_name=request.workflow_name,
            workflow=workflow,
            behavior_snapshot=behavior_snapshot,
            enabled_node_keys_by_alias=dict(request.enabled_node_keys_by_alias),
            disabled_node_keys_by_alias=dict(request.disabled_node_keys_by_alias),
            global_override_scopes=request.global_override_scopes,
        )


__all__ = ["CapturedGenerationRequest"]

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

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, ClassVar

from PySide6.QtWidgets import QWidget

from substitute.application.node_behavior import (
    NodeDisplayDecision,
    ResolvedFieldSpec,
    ResolvedNodeBehavior,
)
from substitute.presentation.editor.panel.service_bundle import EditorPanelServiceBundle

class NodePanelSnapshot:
    cube_id: str | None
    current_alias: str | None
    cube_states: Mapping[str, Any]
    stack_order: Sequence[str]
    def __init__(
        self,
        cube_id: str | None,
        current_alias: str | None,
        cube_states: Mapping[str, Any],
        stack_order: Sequence[str],
    ) -> None: ...
    def first_alias_for_class_type(self, node_type: str) -> str | None: ...

class NodeCardPromptFieldInputs:
    scheduled_lora_resolver: Callable[[str], object] | None
    prompt_field_profile: Any | None
    def __init__(
        self,
        scheduled_lora_resolver: Callable[[str], object] | None = ...,
        prompt_field_profile: Any | None = ...,
    ) -> None: ...

class NodeCardBodyComposer:
    def __init__(self, *, panel: Any, field_rows: Any) -> None: ...
    def add_input_row(
        self,
        *,
        label: str,
        widget: QWidget,
        field_behavior: Any,
        content_layout: Any,
    ) -> None: ...
    def add_n_column_row(
        self,
        *,
        fields: list[tuple[str, QWidget]],
        field_behaviors: Mapping[str, Any],
        content_layout: Any,
        node_name: str = ...,
        field_labels: Mapping[str, str] | None = ...,
    ) -> None: ...

class NodeCardBuilder:
    _ICON_MAP: ClassVar[Mapping[str, Any]]
    def __init__(
        self,
        panel: Any,
        services: EditorPanelServiceBundle,
        model_choice_snapshot_controller: Any | None = ...,
        dimension_preset_source: Any | None = ...,
        node_input_preset_source: Any | None = ...,
        prompt_segment_preset_source: Any | None = ...,
    ) -> None: ...
    def build_node_card(
        self,
        *,
        node_name: str,
        inputs: dict[Any, Any],
        node_type: str,
        field_specs: Mapping[str, ResolvedFieldSpec],
        cube_state: Any,
        resolved_behavior: ResolvedNodeBehavior,
        display_decision: NodeDisplayDecision | None = ...,
        alias: str | None = ...,
        parent: QWidget | None = ...,
        prompt_field_inputs: Mapping[str, NodeCardPromptFieldInputs] | None = ...,
    ) -> Any: ...
    def _create_title_row(self, *args: Any, **kwargs: Any) -> Any: ...

__all__: list[str]

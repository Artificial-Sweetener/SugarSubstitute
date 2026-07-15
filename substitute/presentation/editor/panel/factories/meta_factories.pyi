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

from collections.abc import Callable
from typing import Any, Mapping, MutableMapping, Sequence

from PySide6.QtWidgets import QWidget

from substitute.application.node_behavior import NodeDisplayDecision
from substitute.application.overrides import ChoiceLinkFieldState
from substitute.application.ports import NodeDefinitionGateway
from substitute.application.workflows import (
    NodeLinkEndpoint,
    NodeLinkEndpointIndex,
    NodeLinkIdentity,
)

class NodeLinkComboContext:
    ordered_aliases: Sequence[str]
    apply_manual_node_link_selection: Callable[
        [str, NodeLinkIdentity, str | None, str | None],
        None,
    ]
    notify_node_link_changed: Callable[[], None] | None
    def __init__(
        self,
        ordered_aliases: Sequence[str],
        apply_manual_node_link_selection: Callable[
            [str, NodeLinkIdentity, str | None, str | None],
            None,
        ],
        notify_node_link_changed: Callable[[], None] | None = ...,
    ) -> None: ...

def sanitize_sampler_link_selection(
    all_buffers: Mapping[str, Mapping[str, Any]],
    sampler_option_map: Mapping[tuple[str, str], list[str]],
) -> None: ...
def sanitize_scheduler_link_selection(
    all_buffers: Mapping[str, Mapping[str, Any]],
    scheduler_option_map: Mapping[tuple[str, str], list[str]],
) -> None: ...
def update_prompt_link_references_on_rename(
    all_buffers: Mapping[str, Mapping[str, Any]],
    old_alias: str,
    new_alias: str,
) -> None: ...
def update_sampler_link_references_on_rename(
    all_buffers: Mapping[str, Mapping[str, Any]],
    old_alias: str,
    new_alias: str,
) -> None: ...
def update_scheduler_link_references_on_rename(
    all_buffers: Mapping[str, Mapping[str, Any]],
    old_alias: str,
    new_alias: str,
) -> None: ...
def setup_node_link_combobox(
    parent: Any,
    node_link_widgets: MutableMapping[tuple[str, object], Any],
    endpoint: NodeLinkEndpoint,
    endpoint_index: NodeLinkEndpointIndex,
    all_buffers: Mapping[str, Mapping[str, Any]],
    title_layout: Any,
    beautify_label_func: Any,
    *,
    shared_width_labels: Sequence[str] | None = ...,
    node_definition_gateway: NodeDefinitionGateway | None = ...,
    link_context: NodeLinkComboContext | None = ...,
) -> tuple[Any, str | None]: ...
def setup_sampler_link_combobox(
    parent: Any,
    sampler_link_widgets: Mapping[tuple[str, str], Any],
    cube_alias: str,
    node_name: str,
    all_buffers: Mapping[str, Mapping[str, Any]],
    title_layout: Any | None = ...,
    *,
    node_definition_gateway: NodeDefinitionGateway | None = ...,
    field_state: ChoiceLinkFieldState | None = ...,
) -> None: ...
def setup_scheduler_link_combobox(
    parent: Any,
    scheduler_link_widgets: Mapping[tuple[str, str], Any],
    cube_alias: str,
    node_name: str,
    all_buffers: Mapping[str, Mapping[str, Any]],
    title_layout: Any | None = ...,
    *,
    node_definition_gateway: NodeDefinitionGateway | None = ...,
    field_state: ChoiceLinkFieldState | None = ...,
) -> None: ...
def build_enabled_switch(
    parent: Any,
    cube_alias: str | None,
    node_name: str,
    cube_state: Any,
    display_decision: NodeDisplayDecision,
    *,
    checked_changed_callback: Callable[[bool], None] | None = ...,
) -> QWidget: ...

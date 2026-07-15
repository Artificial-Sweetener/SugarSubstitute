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

"""Adapt saved node input presets to node-card title context menus."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeAlias

from substitute.application.user_presets import (
    NodeInputPresetPayload,
    UserPreset,
    UserPresetAssociation,
    UserPresetService,
)
from substitute.presentation.editor.panel.context.active_model_snapshot import (
    PanelActiveModelSnapshotController,
)
from substitute.presentation.editor.panel.menus.preset_model_scope_policy import (
    node_input_preset_model_scopes,
)
from substitute.presentation.widgets.save_preset_dialog import PresetSaveScope
from substitute.shared.logging.logger import get_logger, log_warning

JsonObject: TypeAlias = dict[str, object]
_LOGGER = get_logger("presentation.editor.panel.menus.node_input_preset_menu_source")


@dataclass(frozen=True, slots=True)
class NodeInputPresetMenuItem:
    """Describe one saved node input preset action."""

    id: str
    label: str
    inputs: JsonObject
    tooltip: str


@dataclass(frozen=True, slots=True)
class NodeInputPresetMenuSection:
    """Group node input presets by matching scope."""

    title: str
    presets: tuple[NodeInputPresetMenuItem, ...]


@dataclass(frozen=True, slots=True)
class NodeInputPresetMenuModel:
    """Return context menu data and save scopes for node input presets."""

    sections: tuple[NodeInputPresetMenuSection, ...] = ()
    save_scopes: tuple[PresetSaveScope, ...] = ()


class NodeInputPresetSource(Protocol):
    """Provide saved node input presets for node-card title menus."""

    def prepare_node_input_preset_menu_model(
        self,
        *,
        node_type: str,
        reason: str,
    ) -> None:
        """Prepare presets and save scopes for one node type outside menu open."""

    def prepare_known_node_input_preset_menu_models(self, *, reason: str) -> None:
        """Refresh already-known node type menu models outside menu open."""

    def current_node_input_preset_menu_model(
        self,
        *,
        node_type: str,
    ) -> NodeInputPresetMenuModel | None:
        """Return the prepared menu model for one node type."""

    def save_node_input_preset(
        self,
        *,
        label: str,
        node_type: str,
        inputs: JsonObject,
        scope: PresetSaveScope,
    ) -> None:
        """Persist current node inputs as a named preset."""


class EditorNodeInputPresetMenuSource(NodeInputPresetSource):
    """Provide saved node input preset menu data for one live editor panel."""

    def __init__(
        self,
        *,
        user_preset_service: UserPresetService,
        active_model_snapshots: PanelActiveModelSnapshotController,
    ) -> None:
        """Store collaborators needed to resolve active node preset scopes."""

        self._user_preset_service = user_preset_service
        self._active_model_snapshots = active_model_snapshots
        self._menu_models: dict[str, NodeInputPresetMenuModel] = {}
        self._known_node_types: set[str] = set()

    def prepare_node_input_preset_menu_model(
        self,
        *,
        node_type: str,
        reason: str,
    ) -> None:
        """Prepare saved node input presets for one node class."""

        self._known_node_types.add(node_type)
        try:
            self._menu_models[node_type] = self._prepared_node_input_preset_model(
                node_type=node_type
            )
        except Exception as error:
            self._menu_models.pop(node_type, None)
            log_warning(
                _LOGGER,
                "Failed to prepare node input presets for context menu",
                node_type=node_type,
                reason=reason,
                error_type=type(error).__name__,
            )

    def prepare_known_node_input_preset_menu_models(self, *, reason: str) -> None:
        """Refresh prepared node input preset menus for known node types."""

        for node_type in tuple(sorted(self._known_node_types)):
            self.prepare_node_input_preset_menu_model(
                node_type=node_type,
                reason=reason,
            )

    def current_node_input_preset_menu_model(
        self,
        *,
        node_type: str,
    ) -> NodeInputPresetMenuModel | None:
        """Return the prepared menu model for one node type."""

        return self._menu_models.get(node_type)

    def _prepared_node_input_preset_model(
        self,
        *,
        node_type: str,
    ) -> NodeInputPresetMenuModel:
        """Build saved node input presets for one node class."""

        scopes = node_input_preset_model_scopes(self._active_model_snapshots.snapshot)
        listing_associations = scopes.listing_associations
        scope_titles = {
            _association_key(scope.association): scope.title
            for scope in scopes.save_scopes
        }
        listing = self._user_preset_service.list_node_input_presets(
            node_type=node_type,
            associations=listing_associations,
        )
        sections = tuple(
            NodeInputPresetMenuSection(
                title=scope_titles.get(
                    _association_key(section.association),
                    section.association.label,
                ),
                presets=_menu_items_for_presets(section.presets),
            )
            for section in listing.sections
        )
        return NodeInputPresetMenuModel(
            sections=sections,
            save_scopes=scopes.save_scopes,
        )

    def save_node_input_preset(
        self,
        *,
        label: str,
        node_type: str,
        inputs: JsonObject,
        scope: PresetSaveScope,
    ) -> None:
        """Persist node inputs through the user preset service."""

        self._user_preset_service.save_node_input_preset(
            label=label,
            node_type=node_type,
            inputs=inputs,
            association=scope.association,
        )
        self.prepare_node_input_preset_menu_model(
            node_type=node_type,
            reason="node_input_preset_saved",
        )


def _menu_items_for_presets(
    presets: tuple[UserPreset, ...],
) -> tuple[NodeInputPresetMenuItem, ...]:
    """Convert application node input presets into presentation menu items."""

    return tuple(
        NodeInputPresetMenuItem(
            id=preset.id,
            label=preset.label,
            inputs=dict(_node_input_payload_for_preset(preset).inputs),
            tooltip=_node_input_tooltip(_node_input_payload_for_preset(preset)),
        )
        for preset in presets
    )


def _node_input_payload_for_preset(preset: UserPreset) -> NodeInputPresetPayload:
    """Return the node input payload for one node input preset."""

    if not isinstance(preset.payload, NodeInputPresetPayload):
        raise TypeError("Node input preset menu item requires a node input payload")
    return preset.payload


def _node_input_tooltip(payload: NodeInputPresetPayload) -> str:
    """Return a compact tooltip describing the saved input count."""

    count = len(payload.inputs)
    noun = "input" if count == 1 else "inputs"
    return f"{payload.node_type} - {count} {noun}"


def _association_key(
    association: UserPresetAssociation,
) -> tuple[object, str | None, str]:
    """Return the matching key used for display-only association labels."""

    return (association.scope, association.provider, association.key)


__all__ = [
    "EditorNodeInputPresetMenuSource",
    "NodeInputPresetMenuItem",
    "NodeInputPresetMenuModel",
    "NodeInputPresetMenuSection",
    "NodeInputPresetSource",
]

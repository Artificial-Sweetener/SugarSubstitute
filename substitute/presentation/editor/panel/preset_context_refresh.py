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

"""Coordinate active-model projection and preset consumer refreshes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from substitute.presentation.editor.panel.context.active_model_context import (
    PanelActiveModelContextController,
)
from substitute.presentation.editor.panel.context.active_model_snapshot import (
    PanelActiveModelSnapshotController,
)
from substitute.presentation.editor.panel.menus.dimension_preset_models import (
    DimensionPresetMenuSource,
)
from substitute.presentation.editor.panel.menus.node_input_preset_menu_source import (
    NodeInputPresetSource,
)
from substitute.presentation.editor.prompt_editor import PromptEditor


class PromptEditorRegistry(Protocol):
    """Expose registered editor field widgets to preset refresh orchestration."""

    input_widgets_by_field_key: Mapping[tuple[str, str, str], object]


class PanelPresetContextRefreshCoordinator:
    """Own ordered active-model and preset snapshot refresh propagation."""

    def __init__(
        self,
        *,
        host: PromptEditorRegistry,
        model_context: PanelActiveModelContextController,
        model_snapshots: PanelActiveModelSnapshotController,
        dimension_presets: DimensionPresetMenuSource | None,
        node_input_presets: NodeInputPresetSource | None,
    ) -> None:
        """Store authoritative model state and downstream preset consumers."""

        self._host = host
        self._model_context = model_context
        self._model_snapshots = model_snapshots
        self._dimension_presets = dimension_presets
        self._node_input_presets = node_input_presets

    def begin_projection(
        self,
        *,
        cube_entries: Sequence[tuple[str, object]],
        cube_states: Mapping[str, object] | None,
        stack_order: Sequence[str] | None,
    ) -> None:
        """Project authoritative model candidates from workflow cube buffers."""

        self._model_context.begin_projection(stack_order)
        for cube_alias, cube_state in _authoritative_cube_entries(
            cube_entries=cube_entries,
            cube_states=cube_states,
            stack_order=stack_order,
        ):
            self._record_cube_state(cube_alias=cube_alias, cube_state=cube_state)

    def begin_cube_projection(
        self,
        *,
        cube_alias: str,
        cube_state: object,
        stack_order: Sequence[str] | None,
    ) -> None:
        """Project one authoritative cube buffer before incremental rendering."""

        self._model_context.begin_cube_projection(
            cube_alias=cube_alias,
            stack_order=stack_order,
        )
        self._record_cube_state(cube_alias=cube_alias, cube_state=cube_state)

    def update_cube_order(self, stack_order: Sequence[str] | None) -> None:
        """Update candidate precedence after cube reordering."""

        self._model_context.update_cube_order(stack_order)

    def remove_cube(self, cube_alias: str) -> None:
        """Remove one cube's model candidates and refresh preset consumers."""

        self._model_context.remove_cube(cube_alias)
        self.refresh(reason="cube_removed")

    def rename_cube(self, old_alias: str, new_alias: str) -> None:
        """Rename one cube's model candidates without changing their values."""

        self._model_context.rename_cube(old_alias, new_alias)

    def _record_cube_state(self, *, cube_alias: str, cube_state: object) -> None:
        """Record generative-model inputs from one authoritative cube buffer."""

        buffer = getattr(cube_state, "buffer", None)
        if not isinstance(buffer, Mapping):
            return
        nodes = buffer.get("nodes")
        if not isinstance(nodes, Mapping):
            return
        for raw_node_name, raw_node in nodes.items():
            if not isinstance(raw_node_name, str) or not isinstance(raw_node, Mapping):
                continue
            node_type = raw_node.get("class_type")
            inputs = raw_node.get("inputs")
            if not isinstance(node_type, str) or not isinstance(inputs, Mapping):
                continue
            self._model_context.record_node_inputs(
                cube_alias=cube_alias,
                node_name=raw_node_name,
                node_type=node_type,
                inputs=inputs,
            )

    def update_field_value(
        self,
        *,
        cube_alias: str | None,
        node_name: str | None,
        node_type: str | None,
        field_key: str,
        value: object,
    ) -> bool:
        """Update active-model state and refresh consumers when relevant."""

        relevant = self._model_context.update_field_value(
            cube_alias=cube_alias,
            node_name=node_name,
            node_type=node_type,
            field_key=field_key,
            value=value,
        )
        if relevant:
            self.refresh(reason="active_model_field_changed")
        return relevant

    def refresh(self, *, reason: str) -> None:
        """Refresh prepared model state before every preset consumer."""

        self._model_snapshots.refresh_from_cache()
        if self._dimension_presets is not None:
            self._dimension_presets.prepare_dimension_preset_menu_model(reason=reason)
        if self._node_input_presets is not None:
            self._node_input_presets.prepare_known_node_input_preset_menu_models(
                reason=reason
            )
        for prompt_editor in self._registered_prompt_editors():
            prompt_editor.refresh_prompt_segment_presets(reason=reason)

    def _registered_prompt_editors(self) -> tuple[PromptEditor, ...]:
        """Return unique registered prompt editors in field-registry order."""

        editors: list[PromptEditor] = []
        seen: set[int] = set()
        for widget in self._host.input_widgets_by_field_key.values():
            if not isinstance(widget, PromptEditor) or id(widget) in seen:
                continue
            seen.add(id(widget))
            editors.append(widget)
        return tuple(editors)


def _authoritative_cube_entries(
    *,
    cube_entries: Sequence[tuple[str, object]],
    cube_states: Mapping[str, object] | None,
    stack_order: Sequence[str] | None,
) -> tuple[tuple[str, object], ...]:
    """Return cube states in workflow order for model-context projection."""

    if cube_states is None:
        return tuple(cube_entries)
    ordered_aliases = tuple(stack_order or ())
    remaining_aliases = tuple(
        alias for alias in cube_states if alias not in ordered_aliases
    )
    return tuple(
        (alias, cube_states[alias])
        for alias in (*ordered_aliases, *remaining_aliases)
        if alias in cube_states
    )


__all__ = [
    "PanelPresetContextRefreshCoordinator",
    "PromptEditorRegistry",
]

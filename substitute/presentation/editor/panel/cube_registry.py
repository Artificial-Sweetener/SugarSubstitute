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

"""Own editor-panel cube alias, widget, and buffer registries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, TypeAlias

from substitute.presentation.editor.panel.cube_section_title import cube_section_title
from substitute.presentation.qt_label_text import literal_label_text

WidgetMapKey: TypeAlias = object
AliasWidgetMap: TypeAlias = Mapping[WidgetMapKey, Any]
CardWrapperMap: TypeAlias = dict[tuple[str, str], object]


@dataclass(frozen=True, slots=True)
class EditorCubeRegistrySnapshot:
    """Capture ordered cube registry state for panel controllers."""

    stack_order: tuple[str, ...]
    cube_states: Mapping[str, object]
    cube_widgets: Mapping[str, object]
    cube_sections: Mapping[str, object]
    card_wrappers: Mapping[tuple[str, str], object]
    buffers: Mapping[str, dict[str, Any]]


class EditorCubeRegistryHost(Protocol):
    """Describe the panel-owned mutable maps controlled by the cube registry."""

    cube_headers: dict[str, object]
    cube_positions: dict[str, object]
    cube_widgets: dict[str, object]
    cube_sections: dict[str, object]
    row_widgets: dict[object, Any]
    col_widgets: dict[object, Any]
    input_widgets_by_field_key: dict[tuple[str, str, str], object]
    card_wrappers: CardWrapperMap
    sampler_link_widgets: dict[tuple[str, str], object]
    scheduler_link_widgets: dict[tuple[str, str], object]
    _cube_visibility_btns: dict[str, object]
    _cube_visibility_menus: dict[str, object]
    _cube_states: dict[str, object] | None
    _stack_order: list[str] | None
    _node_card_mode_controller: object


class EditorCubeRegistry:
    """Coordinate cube alias identity across panel state and widget maps."""

    def __init__(self, host: EditorCubeRegistryHost) -> None:
        """Store the panel host whose registries this controller owns."""

        self._host = host

    def snapshot(self) -> EditorCubeRegistrySnapshot:
        """Return an immutable view of the current ordered cube registry state."""

        cube_states = self._host._cube_states or {}
        stack_order = tuple(self._host._stack_order or ())
        return EditorCubeRegistrySnapshot(
            stack_order=stack_order,
            cube_states=cube_states,
            cube_widgets=self._host.cube_widgets,
            cube_sections=self._host.cube_sections,
            card_wrappers=self._host.card_wrappers,
            buffers=self.ordered_buffers(),
        )

    def ordered_buffers(self) -> dict[str, dict[str, Any]]:
        """Return workflow buffers in the current stack order for link refreshes."""

        if not self._host._cube_states or not self._host._stack_order:
            return {}
        buffers: dict[str, dict[str, Any]] = {}
        for alias in self._host._stack_order:
            cube_state = self._host._cube_states.get(alias)
            buffer = getattr(cube_state, "buffer", None)
            if isinstance(buffer, dict):
                buffers[alias] = buffer
        return buffers

    def ordered_projection_buffers(self) -> dict[str, Mapping[str, object]]:
        """Return active cube buffers in stack order for projection dependency checks."""

        if not self._host._cube_states or not self._host._stack_order:
            return {}
        buffers: dict[str, Mapping[str, object]] = {}
        for alias in self._host._stack_order:
            cube_state = self._host._cube_states.get(alias)
            buffer = getattr(cube_state, "buffer", None)
            if isinstance(buffer, Mapping):
                buffers[alias] = buffer
        return buffers

    def current_cube_entries_for_projection(self) -> list[tuple[str, object]]:
        """Return active cube entries in stack order for projection rebuilds."""

        if not self._host._cube_states or not self._host._stack_order:
            return []
        return [
            (alias, self._host._cube_states[alias])
            for alias in self._host._stack_order
            if alias in self._host._cube_states
        ]

    def register_card_wrapper(
        self,
        cube_alias: str,
        node_name: str,
        wrapper: object,
    ) -> None:
        """Register the current live wrapper for one cube node card."""

        self._host.card_wrappers[(cube_alias, node_name)] = wrapper

    def remove_card_wrapper_if_current(
        self,
        cube_alias: str,
        node_name: str,
        wrapper: object,
    ) -> None:
        """Remove a card wrapper only while it still owns the registry entry."""

        key = (cube_alias, node_name)
        if self._host.card_wrappers.get(key) is wrapper:
            self._host.card_wrappers.pop(key, None)

    def set_stack_order(self, stack_order: list[str]) -> None:
        """Update the canonical cube order used by panel controllers."""

        self._host._stack_order = stack_order

    def rename_cube_alias(self, old_alias: str, new_alias: str) -> None:
        """Migrate registry keys and alias metadata for a renamed cube."""

        self._rename_header(old_alias, new_alias)
        self._rename_dict_entry(self._host.cube_positions, old_alias, new_alias)
        self._rename_dict_entry(self._host.cube_widgets, old_alias, new_alias)
        self._rename_dict_entry(self._host.cube_sections, old_alias, new_alias)
        self._host.row_widgets = _rename_alias_keyed_widget_map(
            getattr(self._host, "row_widgets", {}),
            old_alias,
            new_alias,
        )
        self._host.col_widgets = _rename_alias_keyed_widget_map(
            getattr(self._host, "col_widgets", {}),
            old_alias,
            new_alias,
        )
        self._host.card_wrappers = self._renamed_card_wrappers(old_alias, new_alias)
        self._rename_node_card_mode_alias(old_alias, new_alias)
        self._host.input_widgets_by_field_key = self._renamed_input_widgets(
            old_alias,
            new_alias,
        )
        self._rename_dict_entry(
            self._host._cube_visibility_btns,
            old_alias,
            new_alias,
        )
        self._rename_dict_entry(
            self._host._cube_visibility_menus,
            old_alias,
            new_alias,
        )
        if self._host._cube_states and old_alias in self._host._cube_states:
            self._host._cube_states[new_alias] = self._host._cube_states.pop(old_alias)
        if self._host._stack_order and old_alias in self._host._stack_order:
            self._host._stack_order = [
                new_alias if alias == old_alias else alias
                for alias in self._host._stack_order
            ]
        self._rename_choice_link_widgets(old_alias, new_alias)

    def refresh_cube_header(self, alias: str) -> None:
        """Refresh one cube header title from current cube state."""

        label = self._host.cube_headers.get(alias)
        if label is None:
            return
        self._set_header_text(label, alias, self._cube_state_for_alias(alias))

    def _rename_header(self, old_alias: str, new_alias: str) -> None:
        """Migrate a cube header label and refresh its visible text."""

        label = self._host.cube_headers.pop(old_alias, None)
        if label is None:
            return
        self._set_header_text(label, new_alias, self._cube_state_for_alias(old_alias))
        self._host.cube_headers[new_alias] = label

    def _cube_state_for_alias(self, alias: str) -> object | None:
        """Return the cube state currently registered for an alias."""

        if self._host._cube_states is None:
            return None
        return self._host._cube_states.get(alias)

    @staticmethod
    def _set_header_text(label: object, alias: str, cube_state: object | None) -> None:
        """Apply formatted editor cube-section title to a label-like object."""

        set_text = getattr(label, "setText", None)
        set_title_text = getattr(label, "setTitleText", None)
        title = cube_section_title(alias, cube_state)
        if callable(set_title_text):
            set_title_text(title)
            return
        if callable(set_text):
            set_text(literal_label_text(title))

    def _renamed_card_wrappers(
        self,
        old_alias: str,
        new_alias: str,
    ) -> CardWrapperMap:
        """Return card wrappers keyed by the renamed cube alias."""

        updated_wrappers: CardWrapperMap = {}
        for (cube_alias, node_name), wrapper in self._host.card_wrappers.items():
            next_key = (
                (new_alias, node_name)
                if cube_alias == old_alias
                else (cube_alias, node_name)
            )
            if cube_alias == old_alias:
                set_property = getattr(wrapper, "setProperty", None)
                if callable(set_property):
                    set_property("cube_alias", new_alias)
                if hasattr(wrapper, "_current_cube_alias"):
                    setattr(wrapper, "_current_cube_alias", new_alias)
            updated_wrappers[next_key] = wrapper
        return updated_wrappers

    def _renamed_input_widgets(
        self,
        old_alias: str,
        new_alias: str,
    ) -> dict[tuple[str, str, str], object]:
        """Return input widgets keyed by the renamed cube alias."""

        input_widgets = getattr(self._host, "input_widgets_by_field_key", {})
        updated_widgets: dict[tuple[str, str, str], object] = {}
        for key, widget in input_widgets.items():
            cube_alias, node_name, field_key = key
            next_key = (
                (new_alias, node_name, field_key)
                if cube_alias == old_alias
                else (cube_alias, node_name, field_key)
            )
            if cube_alias == old_alias:
                _rewrite_widget_alias_metadata(widget, old_alias, new_alias)
            updated_widgets[next_key] = widget
        return updated_widgets

    def _rename_choice_link_widgets(self, old_alias: str, new_alias: str) -> None:
        """Migrate sampler and scheduler link widgets owned by the renamed cube."""

        self._rename_tuple_alias_keys(
            self._host.sampler_link_widgets,
            old_alias,
            new_alias,
        )
        self._rename_tuple_alias_keys(
            self._host.scheduler_link_widgets,
            old_alias,
            new_alias,
        )

    def _rename_node_card_mode_alias(self, old_alias: str, new_alias: str) -> None:
        """Notify node-card display mode ownership about an alias rename."""

        node_card_mode_controller = getattr(
            self._host,
            "_node_card_mode_controller",
            None,
        )
        rename_alias = getattr(
            node_card_mode_controller,
            "rename_alias",
            None,
        )
        if callable(rename_alias):
            rename_alias(old_alias, new_alias)

    @staticmethod
    def _rename_dict_entry(
        registry: dict[str, object],
        old_alias: str,
        new_alias: str,
    ) -> None:
        """Move one string-keyed registry entry when the old alias exists."""

        if old_alias in registry:
            registry[new_alias] = registry.pop(old_alias)

    @staticmethod
    def _rename_tuple_alias_keys(
        registry: dict[tuple[str, str], object],
        old_alias: str,
        new_alias: str,
    ) -> None:
        """Move tuple-keyed registry entries owned by the renamed alias."""

        for key in list(registry.keys()):
            alias, node_name = key
            if alias == old_alias:
                registry[(new_alias, node_name)] = registry.pop(key)


def _renamed_alias_key(key: object, old_alias: str, new_alias: str) -> object:
    """Return a copy of an alias-keyed tuple using the new alias."""

    if isinstance(key, tuple) and key and key[0] == old_alias:
        return (new_alias, *key[1:])
    return key


def _rewrite_widget_alias_metadata(
    widget: object,
    old_alias: str,
    new_alias: str,
) -> None:
    """Rewrite Qt dynamic metadata when it stores the renamed cube alias."""

    property_getter = getattr(widget, "property", None)
    set_property = getattr(widget, "setProperty", None)
    if not callable(property_getter) or not callable(set_property):
        return
    metadata = property_getter("input_metadata")
    if isinstance(metadata, dict) and metadata.get("cube_alias") == old_alias:
        updated_metadata = dict(metadata)
        updated_metadata["cube_alias"] = new_alias
        set_property("input_metadata", updated_metadata)


def _rename_alias_keyed_widget_map(
    widget_map: AliasWidgetMap,
    old_alias: str,
    new_alias: str,
) -> dict[object, Any]:
    """Return an alias-keyed widget map with tuple keys and metadata migrated."""

    migrated: dict[object, Any] = {}
    for key, value in widget_map.items():
        next_key = _renamed_alias_key(key, old_alias, new_alias)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for item in value:
                _rewrite_widget_alias_metadata(item, old_alias, new_alias)
        else:
            _rewrite_widget_alias_metadata(value, old_alias, new_alias)
        migrated[next_key] = value
    return migrated


__all__ = [
    "EditorCubeRegistry",
    "EditorCubeRegistryHost",
    "EditorCubeRegistrySnapshot",
]

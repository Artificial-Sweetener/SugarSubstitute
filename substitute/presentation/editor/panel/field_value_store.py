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

"""Own editor field value lookup, mutation, and dirty-state publication."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from substitute.presentation.editor.panel.field_state_binding import (
    DISPLAY_FALLBACK_VALUE_SOURCES,
    EditorFieldBinding,
    NODE_STATE_KEYS,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.editor.panel.field_state_controller")


class EditorFieldValueStore:
    """Read and mutate authoritative cube field values."""

    def __init__(
        self,
        field_value_changed: Callable[[EditorFieldBinding, object], None] | None = None,
    ) -> None:
        """Store the optional observer notified after successful mutations."""

        self._field_value_changed = field_value_changed

    def field_value(self, cube_state: object, binding: EditorFieldBinding) -> object:
        """Return the persisted value for one field binding."""

        node = self.node_payload(cube_state, binding)
        if node is None:
            return None
        if binding.storage_kind == "node":
            return node.get(binding.field_key)
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            return None
        return inputs.get(binding.field_key)

    def display_value(
        self,
        cube_state: object,
        binding: EditorFieldBinding,
    ) -> object:
        """Return the initial widget display value for one field binding."""

        if binding.value_source in DISPLAY_FALLBACK_VALUE_SOURCES:
            return binding.resolved_display_value
        return self.field_value(cube_state, binding)

    def set_field_value(
        self,
        cube_state: object,
        binding: EditorFieldBinding,
        value: object,
    ) -> bool:
        """Persist one field value and mark the cube dirty only on change."""

        canonical_setter = getattr(cube_state, "set_editor_value", None)
        if callable(canonical_setter):
            changed = bool(
                canonical_setter(
                    binding.node_name,
                    field_key=binding.field_key,
                    value=value,
                    storage_kind=binding.storage_kind,
                )
            )
            if changed:
                self.notify_field_value_changed(binding, value)
            return changed
        node = self.mutable_node_payload(cube_state, binding)
        if node is None:
            return False
        if binding.storage_kind == "node":
            previous = node.get(binding.field_key)
            if previous == value:
                return False
            node[binding.field_key] = value
            mark_cube_state_dirty(cube_state)
            self.notify_field_value_changed(binding, value)
            return True

        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            inputs = {}
            node["inputs"] = inputs
        previous = inputs.get(binding.field_key)
        if previous == value:
            return False
        inputs[binding.field_key] = value
        mark_cube_state_dirty(cube_state)
        self.notify_field_value_changed(binding, value)
        return True

    def notify_field_value_changed(
        self,
        binding: EditorFieldBinding,
        value: object,
    ) -> None:
        """Notify the observer about a persisted field mutation."""

        if self._field_value_changed is None:
            return
        try:
            self._field_value_changed(binding, value)
        except Exception as error:
            log_warning(
                _LOGGER,
                "Field value change callback failed",
                node_name=binding.node_name or "",
                field_key=binding.field_key,
                error_type=type(error).__name__,
            )

    @staticmethod
    def node_payload(
        cube_state: object,
        binding: EditorFieldBinding,
    ) -> dict[str, Any] | None:
        """Return one node payload from cube state when present."""

        buffer = getattr(cube_state, "buffer", None)
        if not isinstance(buffer, dict):
            return None
        nodes = buffer.get("nodes")
        if not isinstance(nodes, dict):
            return None
        node = nodes.get(binding.node_name)
        return cast(dict[str, Any], node) if isinstance(node, dict) else None

    @staticmethod
    def mutable_node_payload(
        cube_state: object,
        binding: EditorFieldBinding,
    ) -> dict[str, Any] | None:
        """Return a mutable node payload from cube state when possible."""

        buffer = getattr(cube_state, "buffer", None)
        if not isinstance(buffer, dict):
            return None
        nodes = buffer.get("nodes")
        if not isinstance(nodes, dict):
            nodes = {}
            buffer["nodes"] = nodes
        node = nodes.get(binding.node_name)
        if not isinstance(node, dict):
            node = {}
            nodes[binding.node_name] = node
        return cast(dict[str, Any], node)


def mark_cube_state_dirty(cube_state: object) -> None:
    """Mark cube state dirty when the object supports that attribute."""

    if hasattr(cube_state, "dirty"):
        setattr(cube_state, "dirty", True)


def set_buffer_value_and_dirty(
    cube_state: object,
    node_name: str,
    key: str,
    value: object,
) -> None:
    """Persist one field value through the authoritative value store."""

    binding = EditorFieldBinding(
        cube_alias=None,
        node_name=node_name,
        field_key=key,
        storage_kind="node" if key in NODE_STATE_KEYS else "input",
        value_source=None,
        resolved_display_value=None,
        prompt_field_identity=f"{node_name}.{key}" if node_name else None,
    )
    EditorFieldValueStore().set_field_value(cube_state, binding, value)


__all__ = [
    "EditorFieldValueStore",
    "mark_cube_state_dirty",
    "set_buffer_value_and_dirty",
]

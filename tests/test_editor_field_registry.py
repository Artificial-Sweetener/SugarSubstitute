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

"""Verify authoritative editor field registration and lifecycle behavior."""

from __future__ import annotations

from substitute.presentation.editor.panel.field_registry import EditorFieldRegistry
from substitute.presentation.editor.panel.field_state_controller import (
    EditorFieldBinding,
)


class _Widget:
    """Provide Qt-like dynamic property storage for registry tests."""

    def __init__(self, metadata: dict[str, object]) -> None:
        """Store initial input metadata."""

        self._metadata = metadata

    def property(self, name: str) -> object:
        """Return stored input metadata."""

        return self._metadata if name == "input_metadata" else None

    def setProperty(self, name: str, value: object) -> None:  # noqa: N802
        """Replace stored input metadata."""

        if name == "input_metadata" and isinstance(value, dict):
            self._metadata = value


def _binding(
    alias: str, node_type: str = "CheckpointLoaderSimple"
) -> EditorFieldBinding:
    """Return one model field binding."""

    return EditorFieldBinding(
        cube_alias=alias,
        node_name="loader",
        field_key="ckpt_name",
        storage_kind="input",
        value_source="explicit",
        resolved_display_value="model.safetensors",
        prompt_field_identity="loader.ckpt_name",
        node_type=node_type,
        field_type="COMBO",
    )


def test_registry_indexes_fields_by_identity_and_node_class() -> None:
    """Registered fields should be addressable without Qt tree traversal."""

    registry = EditorFieldRegistry()
    widget = _Widget({"cube_alias": "Cube", "node_name": "loader"})
    binding = _binding("Cube")

    registry.register(binding, widget)

    assert registry.widget_map == {("Cube", "loader", "ckpt_name"): widget}
    assert (
        registry.entries_for_node_classes(("CheckpointLoaderSimple",))[0].binding
        == binding
    )


def test_registry_rename_updates_keys_bindings_and_widget_metadata() -> None:
    """Cube alias migration should remain owned by one registry."""

    registry = EditorFieldRegistry()
    widget = _Widget({"cube_alias": "Old", "node_name": "loader"})
    registry.register(_binding("Old"), widget)

    registry.rename_cube("Old", "New")

    entry = registry.entry(("New", "loader", "ckpt_name"))
    assert entry is not None
    assert entry.binding.cube_alias == "New"
    assert widget.property("input_metadata") == {
        "cube_alias": "New",
        "node_name": "loader",
    }


def test_registry_removes_node_and_cube_entries() -> None:
    """Projection cleanup should remove every authoritative field index."""

    registry = EditorFieldRegistry()
    registry.register(_binding("One"), object())
    registry.register(_binding("Two"), object())

    assert registry.remove_node("One", "loader") == 1
    assert registry.remove_cube("Two") == 1
    assert registry.widget_map == {}

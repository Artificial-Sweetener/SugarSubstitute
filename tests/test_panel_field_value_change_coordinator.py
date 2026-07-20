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

"""Verify schema-changing native fields use targeted production reprojection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from substitute.presentation.editor.panel.field_state_controller import (
    EditorFieldBinding,
)
from substitute.presentation.editor.panel.field_value_change_coordinator import (
    PanelFieldValueChangeCoordinator,
)


@dataclass
class _CubeState:
    """Represent one authoritative cube state for coordinator tests."""

    buffer: dict[str, object]


class _PresetContext:
    """Record preset-context updates without constructing Qt consumers."""

    def __init__(self) -> None:
        """Prepare update observations."""

        self.updates: list[dict[str, object]] = []

    def update_field_value(self, **kwargs: object) -> bool:
        """Record one update and report it as irrelevant to model presets."""

        self.updates.append(kwargs)
        return False


class _Host:
    """Record targeted projection operations requested by the coordinator."""

    def __init__(self) -> None:
        """Provide one cube and projection observations."""

        self.cube = _CubeState(buffer={})
        self._cube_states = {"Workflow": self.cube}
        self._stack_order = ["Workflow"]
        self.stale_calls: list[tuple[tuple[str, ...], str]] = []
        self.insert_calls: list[dict[str, object]] = []

    def mark_cube_sections_stale(
        self,
        cube_aliases: tuple[str, ...],
        *,
        reason: str,
    ) -> bool:
        """Record one stale transition."""

        self.stale_calls.append((cube_aliases, reason))
        return False

    def insert_cube_section(self, *args: object, **kwargs: object) -> None:
        """Record one production incremental projection request."""

        self.insert_calls.append({"args": args, **kwargs})


def _binding(*, native_widget_type: str | None) -> EditorFieldBinding:
    """Return one selector-like field binding."""

    return EditorFieldBinding(
        cube_alias="Workflow",
        node_name="Dynamic Node",
        field_key="model",
        storage_kind="input",
        value_source="explicit",
        resolved_display_value="model-a",
        prompt_field_identity="Dynamic Node.model",
        node_type="DynamicNode",
        field_type="COMBO",
        native_widget_type=native_widget_type,
    )


def test_dynamic_combo_change_defers_one_targeted_cube_reprojection() -> None:
    """Dynamic selectors should replace their cube after the value signal returns."""

    host = _Host()
    presets = _PresetContext()
    scheduled: list[Any] = []
    coordinator = PanelFieldValueChangeCoordinator(
        host=host,  # type: ignore[arg-type]
        preset_context=presets,  # type: ignore[arg-type]
        schedule=scheduled.append,
    )

    coordinator.field_value_changed(
        _binding(native_widget_type="COMFY_DYNAMICCOMBO_V3"),
        "model-b",
    )
    coordinator.field_value_changed(
        _binding(native_widget_type="COMFY_DYNAMICCOMBO_V3"),
        "model-c",
    )

    assert len(presets.updates) == 2
    assert len(scheduled) == 1
    assert host.stale_calls == []

    scheduled[0]()

    assert host.stale_calls == [(("Workflow",), "native_dynamic_field_changed")]
    assert host.insert_calls == [
        {
            "args": ("Workflow", host.cube),
            "cube_states": host._cube_states,
            "stack_order": host._stack_order,
            "completion_phase": "complete",
        }
    ]


def test_ordinary_field_change_updates_context_without_reprojection() -> None:
    """Normal fields should retain the existing preset-only notification path."""

    host = _Host()
    presets = _PresetContext()
    scheduled: list[Any] = []
    coordinator = PanelFieldValueChangeCoordinator(
        host=host,  # type: ignore[arg-type]
        preset_context=presets,  # type: ignore[arg-type]
        schedule=scheduled.append,
    )

    coordinator.field_value_changed(_binding(native_widget_type=None), "model-b")

    assert len(presets.updates) == 1
    assert scheduled == []
    assert host.stale_calls == []
    assert host.insert_calls == []


def test_binding_preserves_native_widget_type_from_metadata() -> None:
    """Sanitized card metadata should retain the dynamic-selector marker."""

    binding = EditorFieldBinding.from_metadata(
        {
            "cube_alias": "Workflow",
            "node_name": "Dynamic Node",
            "key": "model",
            "type": "COMBO",
            "meta_info": {"native_widget_type": "COMFY_DYNAMICCOMBO_V3"},
        }
    )

    assert binding is not None
    assert binding.native_widget_type == "COMFY_DYNAMICCOMBO_V3"

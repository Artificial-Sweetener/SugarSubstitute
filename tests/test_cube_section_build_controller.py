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

"""Verify cube-section build-controller behavior."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from substitute.application.node_behavior import ResolvedFieldSpec
from substitute.presentation.editor.panel.cube_section_build_controller import (
    CubeSectionBuildController,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTROLLER_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "cube_section_build_controller.py"
)
COORDINATOR_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_coordinator.py"
)
COMPOSITION_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_composition.py"
)
FORBIDDEN_CONTROLLER_IMPORT_PREFIXES = (
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.editor.panel.projection_coordinator",
)


def _imported_module_names(source_path: Path) -> set[str]:
    """Return all imported module names from one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


class _Widget:
    """Minimal cube-section widget double for controller-created sessions."""

    def __init__(self) -> None:
        """Initialize refresh counters."""

        self.height_refreshes = 0
        self.width_syncs = 0

    def defer_update_cube_height(self) -> None:
        """Record a height refresh request."""

        self.height_refreshes += 1

    def defer_string_line_edit_width_group_sync(self) -> None:
        """Record a width sync request."""

        self.width_syncs += 1


class _GridLayout:
    """Minimal grid layout double that records added widgets."""

    def __init__(self) -> None:
        """Initialize added widget storage."""

        self.widgets: list[object] = []

    def addWidget(self, widget: object) -> None:
        """Record one added node-card widget."""

        self.widgets.append(widget)


class _Card:
    """Minimal node-card widget double."""

    def __init__(self) -> None:
        """Initialize dynamic property and destroyed-signal fakes."""

        self.destroyed = SimpleNamespace(connect=lambda _slot: None)
        self.properties: dict[str, object] = {}

    def setProperty(self, key: str, value: object) -> None:
        """Record one dynamic Qt property write."""

        self.properties[key] = value


class _Panel:
    """Panel port double used by cube-section build-controller tests."""

    def __init__(self, behavior_snapshot: object | None = None) -> None:
        """Store snapshot and prepared section state."""

        self._last_behavior_snapshot = behavior_snapshot
        self.built_snapshot_count = 0
        self.prepared_aliases: list[str] = []
        self.widget = _Widget()
        self.grid_layout = _GridLayout()
        self.card_wrappers: dict[tuple[str, str], object] = {}

    def _build_behavior_snapshot(self) -> object:
        """Build and return a fallback behavior snapshot."""

        self.built_snapshot_count += 1
        snapshot = _behavior_snapshot(("fallback_prompt",))
        self._last_behavior_snapshot = snapshot
        return snapshot

    def _prepare_cube_section_widget(self, route_key: str) -> object:
        """Return prepared widget and layout parts."""

        self.prepared_aliases.append(route_key)
        return SimpleNamespace(widget=self.widget, grid_layout=self.grid_layout)

    def build_node_card(
        self,
        node_name: str,
        *_args: object,
        **_kwargs: object,
    ) -> object:
        """Build a minimal card for session finish tests."""

        card = _Card()
        setattr(card, "node_name", node_name)
        return card

    def register_card_wrapper(
        self,
        cube_alias: str,
        node_name: str,
        wrapper: object,
    ) -> None:
        """Register a built card wrapper."""

        self.card_wrappers[(cube_alias, node_name)] = wrapper

    def remove_card_wrapper_if_current(
        self,
        cube_alias: str,
        node_name: str,
        wrapper: object,
    ) -> None:
        """Remove the wrapper only while it still owns the registry key."""

        if self.card_wrappers.get((cube_alias, node_name)) is wrapper:
            self.card_wrappers.pop((cube_alias, node_name), None)


def _behavior_snapshot(node_names: tuple[str, ...]) -> object:
    """Return a behavior snapshot with field specs and resolved behaviors."""

    field_spec = cast(ResolvedFieldSpec, SimpleNamespace(meta_info={}))
    resolved_behavior = SimpleNamespace(
        card=SimpleNamespace(card_mode=SimpleNamespace(value="prompt"))
    )
    return SimpleNamespace(
        field_specs_by_alias={
            "Cube": {node_name: {"value": field_spec} for node_name in node_names}
        },
        resolved_nodes_by_alias={
            "Cube": {node_name: resolved_behavior for node_name in node_names}
        },
        card_decisions_by_alias={"Cube": {}},
    )


def test_begin_build_cube_widget_copies_buffer_and_uses_field_spec_order() -> None:
    """Build-session preparation should copy input buffers and trust field specs."""

    panel = _Panel(_behavior_snapshot(("second", "first")))
    cube_state = SimpleNamespace(
        buffer={
            "nodes": {
                "first": {"class_type": "CLIPTextEncode", "inputs": {}},
                "second": {"class_type": "KSampler", "inputs": {}},
            }
        }
    )

    session = CubeSectionBuildController(cast(Any, panel)).begin_build_cube_widget(
        "Cube",
        cube_state,
    )
    cube_state.buffer["nodes"]["second"]["class_type"] = "Mutated"
    copied_nodes = cast(dict[str, dict[str, object]], session._cube["nodes"])

    assert panel.prepared_aliases == ["Cube"]
    assert session._node_order == ["second", "first"]
    assert copied_nodes["second"]["class_type"] == "KSampler"


def test_begin_build_cube_widget_builds_missing_behavior_snapshot() -> None:
    """Controller should create a behavior snapshot when no cached snapshot exists."""

    panel = _Panel()
    cube_state = SimpleNamespace(
        buffer={"nodes": {"fallback_prompt": {"class_type": "CLIPTextEncode"}}}
    )

    session = CubeSectionBuildController(cast(Any, panel)).begin_build_cube_widget(
        "Cube",
        cube_state,
    )

    assert panel.built_snapshot_count == 1
    assert session._node_order == ["fallback_prompt"]


def test_build_cube_widget_finishes_session_and_returns_widget() -> None:
    """Synchronous builds should finish the session and return the section widget."""

    panel = _Panel(_behavior_snapshot(("prompt",)))
    cube_state = SimpleNamespace(
        buffer={"nodes": {"prompt": {"class_type": "CLIPTextEncode", "inputs": {}}}}
    )

    widget = CubeSectionBuildController(cast(Any, panel)).build_cube_widget(
        "Cube",
        cube_state,
    )

    assert widget is panel.widget
    assert panel.widget.height_refreshes >= 1
    assert ("Cube", "prompt") in panel.card_wrappers
    assert len(panel.grid_layout.widgets) == 1


def test_cube_section_build_controller_does_not_import_coordinator_or_fluent() -> None:
    """Build-controller preparation should not depend on the coordinator monolith."""

    forbidden_imports = tuple(
        sorted(
            imported_module
            for imported_module in _imported_module_names(CONTROLLER_SOURCE)
            if imported_module.startswith(FORBIDDEN_CONTROLLER_IMPORT_PREFIXES)
        )
    )

    assert forbidden_imports == ()


def test_projection_coordinator_build_methods_are_controller_adapters() -> None:
    """Projection coordinator should delegate cube-section build preparation."""

    source = COORDINATOR_SOURCE.read_text(encoding="utf-8")
    composition_source = COMPOSITION_SOURCE.read_text(encoding="utf-8")

    assert "raw_buffer = getattr(cube_state" not in source
    assert "node_order_for_cube" not in source
    assert "CubeSectionBuildController(" in composition_source
    assert "self._composition.cube_section_builds.build_cube_widget" in source
    assert "self._composition.cube_section_builds.begin_build_cube_widget" in source

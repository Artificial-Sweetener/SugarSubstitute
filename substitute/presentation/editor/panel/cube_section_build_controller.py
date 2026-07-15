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

"""Prepare and run cube-section build sessions for editor projection."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from time import perf_counter
from typing import cast

from substitute.application.node_behavior import ResolvedFieldSpec
from substitute.shared.logging.logger import get_logger, log_debug, log_timing

from .cube_section_build_plan import node_order_for_cube
from .cube_section_build_session import CubeSectionBuildSession
from .projection_observability import log_panel_projection_event
from .projection_ports import (
    CubeSectionSessionWidgetProtocol,
    EditorRefreshPanelProtocol,
)
from .widgets.masonry_grid_layout import MasonryGridLayout

_LOGGER = get_logger("presentation.editor.panel.cube_section_build_controller")


class CubeSectionBuildController:
    """Own cube-section build-session preparation and synchronous completion."""

    def __init__(self, panel: EditorRefreshPanelProtocol) -> None:
        """Store the editor panel port used to prepare cube-section widgets."""

        self._panel = panel

    def build_cube_widget(self, route_key: str, cube_state: object) -> object:
        """Build one cube section synchronously through projection-owned lifecycle."""

        build_started_at = perf_counter()
        session = self.begin_build_cube_widget(route_key, cube_state)
        session.finish()
        log_timing(
            _LOGGER,
            "Built cube-section widget synchronously",
            started_at=build_started_at,
            cube_alias=route_key,
            level="debug",
        )
        return session.widget

    def begin_build_cube_widget(
        self,
        route_key: str,
        cube_state: object,
    ) -> CubeSectionBuildSession:
        """Prepare one passive cube section and return its incremental build session."""

        panel = self._panel
        build_started_at = perf_counter()
        raw_buffer = getattr(cube_state, "buffer", {})
        cube = copy.deepcopy(raw_buffer if isinstance(raw_buffer, dict) else {})
        log_timing(
            _LOGGER,
            "Copied cube buffer for cube-section build session",
            started_at=build_started_at,
            cube_alias=route_key,
            level="debug",
        )
        current_behavior_snapshot = getattr(panel, "current_behavior_snapshot", None)
        behavior_snapshot = (
            current_behavior_snapshot()
            if callable(current_behavior_snapshot)
            else getattr(panel, "_last_behavior_snapshot", None)
        )
        if behavior_snapshot is None:
            snapshot_started_at = perf_counter()
            behavior_snapshot = panel._build_behavior_snapshot()
            log_timing(
                _LOGGER,
                "Built missing behavior snapshot for cube-section build session",
                started_at=snapshot_started_at,
                cube_alias=route_key,
                level="debug",
            )

        section_parts = panel._prepare_cube_section_widget(route_key)
        widget = cast(
            CubeSectionSessionWidgetProtocol,
            getattr(section_parts, "widget"),
        )
        grid_layout = cast(MasonryGridLayout, getattr(section_parts, "grid_layout"))

        raw_nodes = cube.get("nodes", {})
        nodes = (
            cast(Mapping[str, object], raw_nodes)
            if isinstance(raw_nodes, Mapping)
            else {}
        )
        field_specs_by_alias = getattr(behavior_snapshot, "field_specs_by_alias", {})
        raw_field_specs_by_node = (
            field_specs_by_alias.get(route_key, {})
            if isinstance(field_specs_by_alias, Mapping)
            else {}
        )
        field_specs_by_node = cast(
            Mapping[str, Mapping[str, ResolvedFieldSpec]],
            raw_field_specs_by_node,
        )
        node_order = node_order_for_cube(nodes, field_specs_by_node)
        log_timing(
            _LOGGER,
            "Prepared cube-section build session",
            started_at=build_started_at,
            cube_alias=route_key,
            node_count=len(node_order),
            field_spec_node_count=len(field_specs_by_node),
            level="debug",
        )
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="cube_section_session_prepared",
            cube_alias=route_key,
            node_count=len(node_order),
            field_spec_node_count=len(field_specs_by_node),
            nodes_payload_type=type(nodes).__name__,
            behavior_snapshot_present=behavior_snapshot is not None,
            wrapper_type=type(widget).__name__,
        )
        log_panel_projection_event(
            "hidden_build.section_ready",
            cube_alias=route_key,
            node_count=len(node_order),
            field_spec_node_count=len(field_specs_by_node),
            elapsed_ms=f"{(perf_counter() - build_started_at) * 1000.0:.3f}",
            projection_mode="live",
        )
        return CubeSectionBuildSession(
            panel=panel,
            route_key=route_key,
            cube_state=cube_state,
            cube=cube,
            behavior_snapshot=behavior_snapshot,
            field_specs_by_node=field_specs_by_node,
            node_order=node_order,
            grid_layout=grid_layout,
            widget=widget,
        )

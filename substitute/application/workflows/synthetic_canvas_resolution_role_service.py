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

"""Resolve editor-card roles from authoritative synthetic canvas plans."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from substitute.application.workflows.input_canvas_plan_service import (
    InputCanvasPlanService,
)
from substitute.domain.workflow import CanvasDimensionAuthority, InputCanvasSurfaceKind


@dataclass(frozen=True, slots=True)
class SyntheticCanvasResolutionRole:
    """Identify one graph node that controls a synthetic canvas surface size."""

    section_key: str
    surface_key: str
    authority: CanvasDimensionAuthority

    def field_pair_for_node(self, node_name: str) -> tuple[str, str] | None:
        """Return the authoritative width/height fields owned by one node."""

        for authority_node, field_pair in zip(
            self.authority.node_names,
            self.authority.field_pairs,
            strict=True,
        ):
            if authority_node == node_name:
                return field_pair
        return None


class SyntheticCanvasResolutionRoleService:
    """Map graph nodes to synthetic resolution roles without name heuristics."""

    def __init__(self, plans: InputCanvasPlanService) -> None:
        """Store the shared graph-derived Input canvas planner."""

        self._plans = plans

    def resolve_for_node(
        self,
        *,
        section_key: str,
        graph: Mapping[str, object],
        node_name: str,
        node_definitions: Mapping[str, Mapping[str, object]] | None = None,
    ) -> SyntheticCanvasResolutionRole | None:
        """Return one unambiguous synthetic authority role for a graph node."""

        plan = self._plans.build_plan(
            section_key,
            graph,
            node_definitions=node_definitions,
        )
        matches = tuple(
            surface
            for surface in plan.surfaces
            if surface.kind is InputCanvasSurfaceKind.SYNTHETIC
            and surface.dimension_authority is not None
            and node_name in surface.dimension_authority.node_names
        )
        if len(matches) != 1:
            return None
        surface = matches[0]
        authority = surface.dimension_authority
        if authority is None:
            return None
        role = SyntheticCanvasResolutionRole(
            section_key=section_key,
            surface_key=surface.surface_key,
            authority=authority,
        )
        return role if role.field_pair_for_node(node_name) is not None else None

    def resolve_for_surface(
        self,
        *,
        section_key: str,
        graph: Mapping[str, object],
        surface_key: str,
        node_definitions: Mapping[str, Mapping[str, object]] | None = None,
    ) -> SyntheticCanvasResolutionRole | None:
        """Return one synthetic role by its stable graph-derived surface identity."""

        plan = self._plans.build_plan(
            section_key,
            graph,
            node_definitions=node_definitions,
        )
        matches = tuple(
            surface
            for surface in plan.surfaces
            if surface.kind is InputCanvasSurfaceKind.SYNTHETIC
            and surface.surface_key == surface_key
            and surface.dimension_authority is not None
        )
        if len(matches) != 1 or matches[0].dimension_authority is None:
            return None
        return SyntheticCanvasResolutionRole(
            section_key=section_key,
            surface_key=surface_key,
            authority=matches[0].dimension_authority,
        )


__all__ = ["SyntheticCanvasResolutionRole", "SyntheticCanvasResolutionRoleService"]

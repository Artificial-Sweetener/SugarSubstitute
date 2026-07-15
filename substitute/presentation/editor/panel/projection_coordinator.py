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

"""Coordinate panel projection refreshes for cube load and reorder flows."""

from __future__ import annotations

from collections.abc import Callable, Mapping as MappingABC, Sequence
from time import perf_counter

from .cube_section_build_session import CubeSectionBuildSession
from .projection_composition import (
    EditorProjectionComposition,
    compose_editor_projection,
)
from .projection_models import (
    EditorFullProjectionLoadRequest,
    EditorIncrementalInsertRequest,
)
from .projection_ports import (
    EditorRefreshPanelProtocol,
)
from .projection_session import (
    EditorSurfaceProjectionSignature,
    InsertCompletionPhase,
)


class EditorPanelProjectionCoordinator:
    """Own panel projection sessions, layout commits, and deferred refresh scheduling."""

    def __init__(self, panel: EditorRefreshPanelProtocol) -> None:
        """Store the live editor panel used for widget refresh operations."""

        self._panel = panel
        self._composition: EditorProjectionComposition = compose_editor_projection(
            panel,
            self,
        )

    def build_cube_widget(self, route_key: str, cube_state: object) -> object:
        """Build one cube section synchronously through projection-owned lifecycle."""

        return self._composition.cube_section_builds.build_cube_widget(
            route_key,
            cube_state,
        )

    def begin_build_cube_widget(
        self,
        route_key: str,
        cube_state: object,
    ) -> CubeSectionBuildSession:
        """Prepare one passive cube section and return its incremental build session."""

        return self._composition.cube_section_builds.begin_build_cube_widget(
            route_key,
            cube_state,
        )

    def current_projection_signature(
        self,
        *,
        workflow_id: str,
        cube_entries: Sequence[tuple[str, object]],
        cube_states: MappingABC[str, object] | None,
        stack_order: Sequence[str] | None,
    ) -> EditorSurfaceProjectionSignature:
        """Return the structural signature required by a full editor projection."""

        return self._composition.projection_state.current_projection_signature(
            workflow_id=workflow_id,
            cube_entries=cube_entries,
            cube_states=cube_states,
            stack_order=stack_order,
        )

    def is_projection_clean(
        self,
        signature: EditorSurfaceProjectionSignature,
    ) -> bool:
        """Return whether this editor surface already renders the signature."""

        return self._composition.projection_state.is_projection_clean(signature)

    def mark_projection_clean(
        self,
        signature: EditorSurfaceProjectionSignature,
    ) -> None:
        """Record that the editor surface fully renders the supplied signature."""

        self._composition.projection_state.mark_projection_clean(signature)

    def invalidate_projection(self, *, reason: str) -> None:
        """Mark this editor surface as requiring full projection before reuse."""

        self._composition.projection_state.invalidate_projection(reason=reason)

    def refresh_clean_projection(
        self,
        *,
        cube_states: MappingABC[str, object] | None,
        stack_order: Sequence[str] | None,
    ) -> None:
        """Refresh cheap active-state affordances for an already-clean surface."""

        self._composition.clean_projection_refresh.refresh_clean_projection(
            cube_states=cube_states,
            stack_order=stack_order,
        )

    def has_pending_visible_projection_commit(self) -> bool:
        """Return whether completed staged builds are waiting for visible reveal."""

        return self._composition.visible_commits.has_pending_visible_projection_commit()

    def finalize_pending_visible_projection(self) -> bool:
        """Reveal a completed background projection when the panel is active."""

        return self._composition.visible_commits.finalize_pending_visible_projection()

    def reorder_cube_widgets(self) -> None:
        """Reattach cube widgets in stack order and refresh link widgets once."""

        self._composition.projection_lifecycle.reorder_cube_widgets()

    def remove_cube(self, cube_alias: str) -> None:
        """Immediately discard one cube section from editor-owned projection state."""

        self._composition.projection_lifecycle.remove_cube(cube_alias)

    def rename_cube(self, old_alias: str, new_alias: str) -> None:
        """Rename one cube across projection-owned lifecycle state."""

        self._composition.projection_lifecycle.rename_cube(old_alias, new_alias)

    def clear_layout(self) -> None:
        """Clear rendered projection lifecycle state and layout contents."""

        self._composition.projection_lifecycle.clear_layout()

    def load_all_cubes(
        self,
        cube_entries: Sequence[tuple[str, object]],
        *,
        cube_states: dict[str, object] | None,
        stack_order: Sequence[str] | None,
        projection_signature: object | None = None,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        """Delegate full projection reconciliation to the load pipeline owner."""

        panel = self._panel
        self._composition.full_projection_loads.load_all_cubes(
            EditorFullProjectionLoadRequest(
                cube_entries=tuple(cube_entries),
                cube_states=cube_states,
                stack_order=stack_order,
                projection_signature=projection_signature,
                on_complete=on_complete,
                workflow_id=self._composition.workflow_context.active_workflow_id(),
                previous_cube_states=panel._cube_states,
                previous_stack_order=(
                    list(panel._stack_order) if panel._stack_order else None
                ),
                started_at=perf_counter(),
            )
        )

    def mark_cube_sections_stale(
        self,
        cube_aliases: Sequence[str],
        *,
        reason: str,
    ) -> bool:
        """Mark affected cube sections stale and report active-build impact."""

        return self._composition.cube_section_staleness.mark_cube_sections_stale(
            cube_aliases,
            reason=reason,
        )

    def insert_cube(
        self,
        cube_alias: str,
        cube_state: object,
        *,
        cube_states: dict[str, object] | None,
        stack_order: Sequence[str] | None,
        on_complete: Callable[[], None] | None = None,
        completion_phase: InsertCompletionPhase = "first_usable",
    ) -> None:
        """Insert one cube widget without rebuilding existing cube sections."""

        panel = self._panel
        self._composition.incremental_inserts.insert_cube(
            EditorIncrementalInsertRequest(
                cube_alias=cube_alias,
                cube_state=cube_state,
                cube_states=cube_states,
                stack_order=stack_order,
                on_complete=on_complete,
                completion_phase=completion_phase,
                workflow_id=self._composition.workflow_context.active_workflow_id(),
                previous_cube_states=panel._cube_states,
                previous_stack_order=(
                    list(panel._stack_order) if panel._stack_order else None
                ),
                started_at=perf_counter(),
            )
        )

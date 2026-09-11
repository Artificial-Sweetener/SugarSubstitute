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

"""Define core workflow state models for domain-level orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from substitute.domain.common import (
    GlobalOverrideSelectionMap,
    GlobalOverrideMap,
    JsonObject,
)
from substitute.domain.cube_library import CubeUpdatePolicy
from substitute.domain.generation.seed_control import SeedControlState
from substitute.domain.comfy_workflow.models import DirectWorkflowState
from substitute.domain.workflow.canvas_models import WorkflowCanvasState
from substitute.domain.workflow.document_kind import WorkflowDocumentKind


class OutputFocusMode(StrEnum):
    """Describe whether output focus follows generation or user selection."""

    AUTOMATIC = "automatic"
    MANUAL = "manual"


@dataclass(frozen=True)
class OutputCompareSelection:
    """Identify one output image by output-navigation dimensions."""

    scene_key: str | None
    set_index: int
    source_key: str


@dataclass(frozen=True)
class OutputCompareState:
    """Store workflow-owned output comparison viewing state."""

    enabled: bool = False
    base: OutputCompareSelection | None = None
    comparison: OutputCompareSelection | None = None
    split_position: float = 0.5
    orientation: str = "vertical"


@dataclass
class CubeState:
    """Store mutable state for one cube instance in a workflow stack."""

    cube_id: str
    version: str
    alias: str
    original_cube: JsonObject
    buffer: JsonObject
    display_name: str = ""
    undo_stack: list[JsonObject] = field(default_factory=list)
    redo_stack: list[JsonObject] = field(default_factory=list)
    dirty: bool = False
    ui: dict[str, object] | None = None
    field_control_states: dict[str, dict[str, SeedControlState]] = field(
        default_factory=dict
    )
    update_policy: CubeUpdatePolicy = CubeUpdatePolicy.PINNED
    bypassed: bool = False
    output_persistence_enabled: bool = True

    def __post_init__(self) -> None:
        """Default display name to the canonical cube id when absent."""

        if not self.display_name:
            self.display_name = self.cube_id

    @property
    def activation_storage(self) -> str:
        """Persist cube activation through Sugar's explicit enabled override."""

        return "enabled_override"

    @property
    def shows_cube_section_title(self) -> bool:
        """Render the normal cube section title for cube-stack documents."""

        return True

    @property
    def uses_node_titles_as_card_labels(self) -> bool:
        """Keep cube node keys as the source for normal card label formatting."""

        return False


@dataclass
class WorkflowState:
    """Store workflow-local cube stack, metadata, and per-workflow canvas state."""

    cubes: dict[str, CubeState] = field(default_factory=dict)
    stack_order: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)
    global_overrides: GlobalOverrideMap = field(default_factory=dict)
    global_override_selections: GlobalOverrideSelectionMap = field(default_factory=dict)
    override_control_states: dict[str, SeedControlState] = field(default_factory=dict)
    canvas: WorkflowCanvasState = field(default_factory=WorkflowCanvasState)
    output_image_uuids: list[UUID] = field(default_factory=list)
    output_focus_mode: OutputFocusMode = OutputFocusMode.AUTOMATIC
    active_output_uuid: UUID | None = None
    active_output_set_index: int = 1
    active_output_source_key: str | None = None
    active_output_scene_key: str | None = None
    active_output_scene_overview: bool = False
    output_compare_state: OutputCompareState = field(default_factory=OutputCompareState)
    direct_workflow: DirectWorkflowState | None = None

    def __post_init__(self) -> None:
        """Hydrate graph-backed Cube views or reject conflicting source kinds."""

        if self.direct_workflow is not None and (self.cubes or self.stack_order):
            raise ValueError("Direct Comfy workflows cannot be mixed with cubes.")
        if self.direct_workflow is not None:
            self._refresh_direct_cube_projection()

    @property
    def is_direct_workflow(self) -> bool:
        """Return whether this tab owns one direct Comfy workflow document."""

        return self.document_kind is WorkflowDocumentKind.DIRECT_COMFY

    @property
    def document_kind(self) -> WorkflowDocumentKind:
        """Return the mutually exclusive authoring model owned by this tab."""

        if self.direct_workflow is not None:
            return (
                WorkflowDocumentKind.COMFY_CUBE_GRAPH
                if self.cubes
                else WorkflowDocumentKind.DIRECT_COMFY
            )
        return WorkflowDocumentKind.CUBE_STACK

    @property
    def is_graph_backed_cube_workflow(self) -> bool:
        """Return whether Cube views are derived from an owning Comfy graph."""

        return self.document_kind is WorkflowDocumentKind.COMFY_CUBE_GRAPH

    def load_direct_workflow(self, document: DirectWorkflowState) -> None:
        """Install a direct document only into an empty cube workflow."""

        if self.cubes or self.stack_order:
            raise ValueError("Direct Comfy workflows cannot be mixed with cubes.")
        self.direct_workflow = document
        self._refresh_direct_cube_projection()

    def install_canonical_graph(
        self,
        document: DirectWorkflowState,
        *,
        projection_sources: Mapping[str, CubeState] | None = None,
    ) -> None:
        """Atomically replace workflow authority with one normalized graph."""

        sources = {**self.cubes, **(projection_sources or {})}
        cubes, order = self._project_direct_cube_views(document, sources=sources)
        cubes = self._reuse_projection_objects(cubes, sources=sources)
        self.direct_workflow = document
        self.cubes = cubes
        self.stack_order = order

    def refresh_direct_cube_projection(self) -> None:
        """Rebuild derived Cube views after the owning Comfy graph changes."""

        if self.direct_workflow is None:
            raise ValueError("Workflow does not own a Comfy graph document.")
        self._refresh_direct_cube_projection()

    def _refresh_direct_cube_projection(self) -> None:
        """Replace derived Cube views from canonical embedded graph documents."""

        direct = self.direct_workflow
        if direct is None:
            return
        cubes, order = self._project_direct_cube_views(direct, sources=self.cubes)
        cubes = self._reuse_projection_objects(cubes, sources=self.cubes)
        self.cubes = cubes
        self.stack_order = order

    @staticmethod
    def _project_direct_cube_views(
        direct: DirectWorkflowState,
        *,
        sources: Mapping[str, CubeState],
    ) -> tuple[dict[str, CubeState], list[str]]:
        """Build validated Cube projections without mutating installed state."""

        existing_by_node_id = {
            ui.get("graph_node_id"): cube
            for cube in sources.values()
            if isinstance((ui := cube.ui), dict)
        }
        existing_by_alias = dict(sources)
        cubes: dict[str, CubeState] = {}
        order: list[str] = []
        for projected in direct.projected_cube_documents():
            if projected.alias in cubes:
                raise ValueError(
                    f"Comfy Cube graph contains duplicate alias {projected.alias!r}."
                )
            document = projected.document
            implementation = document.get("implementation")
            if not isinstance(implementation, dict):
                raise ValueError(
                    f"Cube {projected.alias!r} has no embedded implementation."
                )
            cube_id = document.get("cube_id")
            version = document.get("version")
            if not isinstance(cube_id, str) or not isinstance(version, str):
                raise ValueError(
                    f"Cube {projected.alias!r} has invalid embedded identity."
                )
            existing = existing_by_node_id.get(
                projected.node_id
            ) or existing_by_alias.get(projected.alias)
            cube = CubeState(
                cube_id=cube_id,
                version=version,
                alias=projected.alias,
                original_cube=document,
                buffer=implementation,
                display_name=(existing.display_name if existing is not None else ""),
                undo_stack=(existing.undo_stack if existing is not None else []),
                redo_stack=(existing.redo_stack if existing is not None else []),
                dirty=existing.dirty if existing is not None else False,
                ui={
                    **(
                        existing.ui
                        if existing is not None and isinstance(existing.ui, dict)
                        else {}
                    ),
                    "canonical_cube": document,
                    "graph_node_id": projected.node_id,
                },
                field_control_states=(
                    existing.field_control_states if existing is not None else {}
                ),
                update_policy=(
                    existing.update_policy
                    if existing is not None
                    else CubeUpdatePolicy.PINNED
                ),
                bypassed=not projected.active,
                output_persistence_enabled=(
                    existing.output_persistence_enabled
                    if existing is not None
                    else True
                ),
            )
            cubes[projected.alias] = cube
            order.append(projected.alias)
        return cubes, order

    @staticmethod
    def _reuse_projection_objects(
        projected: Mapping[str, CubeState],
        *,
        sources: Mapping[str, CubeState],
    ) -> dict[str, CubeState]:
        """Commit validated projections while preserving mounted Cube identities."""

        sources_by_node_id = {
            str(node_id): cube
            for cube in sources.values()
            if isinstance((ui := cube.ui), Mapping)
            and (node_id := ui.get("graph_node_id")) is not None
        }
        result: dict[str, CubeState] = {}
        for alias, candidate in projected.items():
            candidate_ui = candidate.ui
            node_id = (
                candidate_ui.get("graph_node_id")
                if isinstance(candidate_ui, Mapping)
                else None
            )
            existing = sources_by_node_id.get(str(node_id)) or sources.get(alias)
            if existing is None:
                result[alias] = candidate
                continue
            existing.cube_id = candidate.cube_id
            existing.version = candidate.version
            existing.alias = candidate.alias
            existing.original_cube = candidate.original_cube
            existing.buffer = candidate.buffer
            existing.display_name = candidate.display_name
            existing.undo_stack = candidate.undo_stack
            existing.redo_stack = candidate.redo_stack
            existing.dirty = candidate.dirty
            existing.ui = candidate.ui
            existing.field_control_states = candidate.field_control_states
            existing.update_policy = candidate.update_policy
            existing.bypassed = candidate.bypassed
            existing.output_persistence_enabled = candidate.output_persistence_enabled
            result[alias] = existing
        return result


@dataclass
class ImageMeta:
    """Store origin metadata required to label and route generated images."""

    workflow_name: str
    cube_name: str
    image_number: int
    suffix: str
    path: str
    source_key: str = ""
    source_label: str = ""
    node_id: str = ""
    generation_run_id: str = ""
    output_session_id: str = ""
    prompt_id: str = ""
    client_id: str = ""
    scene_run_id: str = ""
    scene_key: str = ""
    scene_title: str = ""
    scene_order: int | None = None
    scene_count: int | None = None
    width: int | None = None
    height: int | None = None
    list_index: int | None = None
    batch_index: int | None = None
    cube_execution_duration_ms: float | None = None

    def __post_init__(self) -> None:
        """Default source display text to the generated cube label."""

        if not self.source_label:
            self.source_label = self.cube_name


__all__ = [
    "CubeState",
    "ImageMeta",
    "OutputCompareSelection",
    "OutputCompareState",
    "OutputFocusMode",
    "WorkflowState",
]

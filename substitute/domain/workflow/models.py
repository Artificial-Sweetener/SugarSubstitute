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
from substitute.domain.workflow.canvas_models import WorkflowCanvasState
from substitute.domain.workflow.document_kind import WorkflowDocumentKind
from substitute.domain.comfy_workflow.models import DirectWorkflowState


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
        """Reject persisted or constructed documents that mix graph source kinds."""

        if self.direct_workflow is not None and (self.cubes or self.stack_order):
            raise ValueError("Direct Comfy workflows cannot be mixed with cubes.")

    @property
    def is_direct_workflow(self) -> bool:
        """Return whether this tab owns one direct Comfy workflow document."""

        return self.document_kind is WorkflowDocumentKind.DIRECT_COMFY

    @property
    def document_kind(self) -> WorkflowDocumentKind:
        """Return the mutually exclusive authoring model owned by this tab."""

        if self.direct_workflow is not None:
            return WorkflowDocumentKind.DIRECT_COMFY
        return WorkflowDocumentKind.CUBE_STACK

    def load_direct_workflow(self, document: DirectWorkflowState) -> None:
        """Install a direct document only into an empty cube workflow."""

        if self.cubes or self.stack_order:
            raise ValueError("Direct Comfy workflows cannot be mixed with cubes.")
        self.direct_workflow = document


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

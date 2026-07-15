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

"""Define real-shell Output canvas scenario value objects."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from PySide6.QtGui import QColor, QImage


@dataclass(frozen=True, slots=True)
class WorkflowHandle:
    """Identify one workflow in the real shell harness."""

    alias: str
    workflow_id: str


@dataclass(frozen=True, slots=True)
class GenerationRunHandle:
    """Identify one Comfy callback run for a workflow."""

    workflow: WorkflowHandle
    generation_run_id: str
    prompt_id: str
    client_id: str


@dataclass(frozen=True, slots=True)
class SceneSpec:
    """Describe one backend scene identity."""

    run_id: str
    key: str
    title: str
    order: int
    count: int


@dataclass(frozen=True, slots=True)
class OutputSpec:
    """Describe one fake Comfy final output image."""

    source_key: str
    source_label: str
    color: tuple[int, int, int]
    node_id: str = "save-image"
    list_index: int = 0
    width: int = 48
    height: int = 32
    scene: SceneSpec | None = None


@dataclass(frozen=True, slots=True)
class CanvasFingerprint:
    """Capture durable workflow state and the real Output QPane route."""

    active_workflow_id: str
    active_canvas_visible: bool
    output_session_workflow_id: str | None
    workflow_output_image_ids: Mapping[str, tuple[UUID, ...]]
    preview_image_ids: tuple[UUID, ...]
    preview_lane_keys: tuple[str, ...]
    pending_feedback_counts: Mapping[str, int]
    pending_commit_count: int
    pending_projection_workflows: tuple[str, ...]
    pane_image_ids: tuple[UUID, ...]
    pane_current_image_id: UUID | None
    pane_current_composition_id: UUID | None
    composition_image_ids: tuple[UUID, ...]
    scene_bounds: tuple[float, float, float, float] | None
    scene_layer_placements: tuple[tuple[UUID, UUID, float, float, float, float], ...]
    current_image_is_null: bool
    current_image_rgb: tuple[int, int, int] | None


def solid_image(
    rgb: tuple[int, int, int],
    *,
    width: int = 48,
    height: int = 32,
) -> QImage:
    """Return a deterministic solid-color image."""

    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor(rgb[0], rgb[1], rgb[2]))
    return image

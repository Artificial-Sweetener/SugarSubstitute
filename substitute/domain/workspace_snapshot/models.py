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

"""Define Qt-free restorable workspace snapshot value objects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from substitute.domain.workflow import WorkflowState

WORKSPACE_SNAPSHOT_SCHEMA_VERSION = "1"


@dataclass(frozen=True, slots=True)
class ImageMetaSnapshot:
    """Store generated-image origin facts in JSON-friendly form."""

    workflow_name: str
    cube_name: str
    image_number: int
    suffix: str
    path: Path
    source_key: str = ""
    source_label: str = ""
    node_id: str = ""
    generation_run_id: str = ""
    prompt_id: str = ""
    client_id: str = ""
    list_index: int | None = None
    batch_index: int | None = None
    scene_run_id: str | None = None
    scene_key: str | None = None
    scene_title: str | None = None
    scene_order: int | None = None
    scene_count: int | None = None
    width: int | None = None
    height: int | None = None
    cube_execution_duration_ms: float | None = None


@dataclass(frozen=True, slots=True)
class InputImageReference:
    """Describe one input image that can be reloaded into canvas state."""

    image_id: str
    path: Path
    sequence: int


@dataclass(frozen=True, slots=True)
class InputMaskReference:
    """Describe one input mask that can be reloaded into canvas state."""

    mask_id: str
    image_id: str
    path: Path
    association_key: tuple[str, str] | None = None


@dataclass(frozen=True, slots=True)
class OutputImageReference:
    """Describe one output image and the metadata needed to restore it."""

    image_id: str
    path: Path
    metadata: ImageMetaSnapshot
    sequence: int


@dataclass(frozen=True, slots=True)
class WindowGeometrySnapshot:
    """Describe shell geometry without depending on Qt types."""

    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class FloatingCanvasWindowSnapshot:
    """Describe one floating canvas window without Qt dependencies."""

    label: str
    geometry: WindowGeometrySnapshot | None = None
    window_display_state: str = "normal"
    output_generation_controls_revealed: bool = False


@dataclass(frozen=True, slots=True)
class CanvasLayoutSnapshot:
    """Describe restorable canvas docking and floating-window state."""

    floating_windows: tuple[FloatingCanvasWindowSnapshot, ...] = ()


@dataclass(frozen=True, slots=True)
class ShellLayoutSnapshot:
    """Describe restorable shell layout state."""

    layout_schema_version: int = 2
    geometry: WindowGeometrySnapshot | None = None
    window_display_state: str = "normal"
    maximized: bool = False
    main_splitter_sizes: tuple[int, ...] = ()
    editor_output_splitter_sizes: tuple[int, ...] = ()
    cube_stack_width: int | None = None
    editor_panel_width: int | None = None
    canvas_panel_width: int | None = None
    cube_stack_compact: bool = False
    comfy_output_panel_visible: bool = False
    output_panel_height: int | None = None
    side_panel_visible: bool = False
    side_panel_width: int | None = None
    generation_queue_panel_visible: bool = False
    generation_queue_panel_width: int | None = None
    canvas_layout: CanvasLayoutSnapshot | None = None


@dataclass(frozen=True, slots=True)
class EditorViewportSnapshot:
    """Describe restorable editor viewport state without Qt dependencies."""

    scroll_value: int
    scroll_maximum: int
    anchor_cube_alias: str | None = None


@dataclass(frozen=True, slots=True)
class WorkflowSnapshot:
    """Describe one restorable workflow tab."""

    workflow_id: str
    tab_label: str
    workflow: WorkflowState
    active_cube_alias: str | None = None
    input_images: tuple[InputImageReference, ...] = ()
    input_masks: tuple[InputMaskReference, ...] = ()
    output_images: tuple[OutputImageReference, ...] = ()
    editor_viewport: EditorViewportSnapshot | None = None


@dataclass(frozen=True, slots=True)
class WorkspaceSnapshot:
    """Describe restorable workflow workspace state without Qt dependencies."""

    schema_version: str
    workflows: tuple[WorkflowSnapshot, ...]
    tab_order: tuple[str, ...]
    active_route: str
    active_workflow_id: str = ""
    shell_layout: ShellLayoutSnapshot | None = None


__all__ = [
    "WORKSPACE_SNAPSHOT_SCHEMA_VERSION",
    "CanvasLayoutSnapshot",
    "FloatingCanvasWindowSnapshot",
    "ImageMetaSnapshot",
    "InputImageReference",
    "InputMaskReference",
    "OutputImageReference",
    "ShellLayoutSnapshot",
    "EditorViewportSnapshot",
    "WindowGeometrySnapshot",
    "WorkflowSnapshot",
    "WorkspaceSnapshot",
]

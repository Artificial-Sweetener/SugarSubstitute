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

"""Contract tests for shell session snapshot capture adaptation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from substitute.domain.workflow import (
    ImageMeta,
    ProjectAssetRef,
    ProjectMaskAssetRef,
    WorkflowState,
)
from substitute.domain.workspace_snapshot import InputImageReference
from substitute.presentation.shell.session_snapshot_capture_adapter import (
    SessionSnapshotCaptureAdapter,
    snapshot_capture_adapter_for,
)


class _TabItem:
    """Provide the tab label API used by the capture adapter."""

    def __init__(self, label: str) -> None:
        """Store the displayed label."""

        self._label = label

    def text(self) -> str:
        """Return the displayed tab label."""

        return self._label


class _TabBar:
    """Provide workflow tab order and label lookups."""

    def __init__(self) -> None:
        """Initialize one labeled workflow tab."""

        self.itemMap = {"wf-a": _TabItem("Recipe")}

    def workflow_ids_in_order(self) -> list[str]:
        """Return workflow ids in visible order."""

        return ["wf-a"]


class _CubeTab:
    """Provide the cube route key API used by the capture adapter."""

    def routeKey(self) -> str:
        """Return the active cube alias."""

        return "Cube"


class _CubeStack:
    """Provide active cube stack selection APIs."""

    def currentIndex(self) -> int:
        """Return the selected tab index."""

        return 0

    def count(self) -> int:
        """Return the number of cube tabs."""

        return 1

    def tabItem(self, index: int) -> _CubeTab:
        """Return a cube tab item for the selected index."""

        if index != 0:
            raise IndexError(index)
        return _CubeTab()


class _ScrollBar:
    """Provide scroll position APIs used by editor viewport capture."""

    def value(self) -> int:
        """Return the current scroll position."""

        return -10

    def maximum(self) -> int:
        """Return the maximum scroll range."""

        return 320


class _ScrollArea:
    """Provide an editor scroll area API."""

    def verticalScrollBar(self) -> _ScrollBar:
        """Return the vertical scroll bar."""

        return _ScrollBar()


def test_adapter_reads_shell_workflow_identity_and_editor_viewport() -> None:
    """The adapter should expose live shell workflow and viewport state."""

    workflow = WorkflowState()
    shell = SimpleNamespace(
        _active_workspace_route="settings",
        workflow_tabbar=_TabBar(),
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a",
            get_workflow=lambda workflow_id: (
                workflow if workflow_id == "wf-a" else None
            ),
        ),
        cube_stacks={"wf-a": _CubeStack()},
        editor_panels={"wf-a": SimpleNamespace(scroll=_ScrollArea())},
    )
    adapter = SessionSnapshotCaptureAdapter(shell)

    assert adapter.workflow_ids_in_order() == ("wf-a",)
    assert adapter.active_workspace_route() == "settings"
    assert adapter.active_workflow_id() == "wf-a"
    assert adapter.workflow_state("wf-a") is workflow
    assert adapter.workflow_tab_label("wf-a") == "Recipe"
    assert adapter.active_cube_alias("wf-a") == "Cube"

    viewport = adapter.editor_viewport_snapshot("wf-a")

    assert viewport is not None
    assert viewport.scroll_value == 0
    assert viewport.scroll_maximum == 320
    assert viewport.anchor_cube_alias == "Cube"


def test_adapter_resolves_input_image_and_mask_references(tmp_path: Path) -> None:
    """Input asset references should resolve through project-owned paths."""

    image_id = uuid4()
    mask_id = uuid4()
    workflow = WorkflowState()
    canvas = cast(Any, workflow.canvas)
    canvas.input_key_map = {"Cube:Image": image_id, "invalid": uuid4()}
    canvas.mask_associations = {("Cube", "Mask"): mask_id, ("missing", "Mask"): uuid4()}
    canvas.mask_to_image_map = {mask_id: image_id}
    asset_calls: list[tuple[str, str]] = []

    def input_image_asset_ref(
        _workflow: object,
        *,
        section_key: str,
        node_name: str,
    ) -> ProjectAssetRef:
        """Record an input image asset lookup."""

        asset_calls.append((section_key, node_name))
        return ProjectAssetRef(relative_path="inputs/image.png")

    def input_mask_asset_ref(
        _workflow: object,
        *,
        section_key: str,
        node_name: str,
    ) -> ProjectMaskAssetRef:
        """Record an input mask asset lookup."""

        asset_calls.append((section_key, node_name))
        return ProjectMaskAssetRef(relative_path="mask.png")

    shell = SimpleNamespace(
        workflow_tabbar=_TabBar(),
        path_bundle=SimpleNamespace(projects_dir=tmp_path / "projects"),
        input_canvas_state_service=SimpleNamespace(
            input_image_path=lambda candidate_id: (
                tmp_path / "projects" / "Recipe" / "inputs/image.png"
                if candidate_id == image_id
                else None
            )
        ),
        workflow_input_canvas_service=SimpleNamespace(
            input_image_asset_ref=input_image_asset_ref,
            input_mask_asset_ref=input_mask_asset_ref,
        ),
    )
    adapter = SessionSnapshotCaptureAdapter(shell)

    input_images = adapter.input_image_references("wf-a", workflow)
    input_masks = adapter.input_mask_references("wf-a", workflow)

    assert input_images[0].image_id == str(image_id)
    assert input_images[0].path == tmp_path / "projects" / "Recipe" / "inputs/image.png"
    assert input_images[0].sequence == 1
    assert input_masks[0].mask_id == str(mask_id)
    assert input_masks[0].image_id == str(image_id)
    assert (
        input_masks[0].path == tmp_path / "projects" / "Recipe" / "masks" / "mask.png"
    )
    assert input_masks[0].association_key == ("Cube", "Mask")
    assert asset_calls == [("Cube", "Mask")]


def test_adapter_captures_synthetic_input_surface_from_canvas_catalog(
    tmp_path: Path,
) -> None:
    """Synthetic surfaces should persist by their loaded path without a graph node."""

    image_id = uuid4()
    surface_path = (
        tmp_path
        / "projects"
        / "Regional"
        / "input_surfaces"
        / "direct"
        / "mask-authority.png"
    )
    workflow = WorkflowState()
    workflow.canvas.input_key_map = {
        "direct:@synthetic/mask-authority": image_id,
    }
    shell = SimpleNamespace(
        workflow_tabbar=_TabBar(),
        input_canvas_state_service=SimpleNamespace(
            input_image_path=lambda candidate_id: (
                surface_path if candidate_id == image_id else None
            )
        ),
    )

    references = SessionSnapshotCaptureAdapter(shell).input_image_references(
        "wf-a",
        workflow,
    )

    assert references == (
        InputImageReference(
            image_id=str(image_id),
            path=surface_path,
            sequence=1,
        ),
    )


def test_adapter_captures_output_image_metadata_snapshot(tmp_path: Path) -> None:
    """Output image references should include restorable image metadata."""

    image_id = uuid4()
    image_path = tmp_path / "output.png"
    workflow = WorkflowState(output_image_uuids=[image_id])
    shell = SimpleNamespace(
        canvas_image_registry=SimpleNamespace(
            metadata_for=lambda _image_id: ImageMeta(
                workflow_name="Recipe",
                cube_name="Cube",
                image_number=7,
                suffix=".png",
                path=str(image_path),
                source_key="src",
                source_label="Source",
                node_id="node",
                generation_run_id="run",
                prompt_id="prompt",
                client_id="client",
                list_index=3,
                scene_run_id="scene-run",
                scene_key="scene",
                scene_title="Scene",
                scene_order=2,
                scene_count=5,
                width=640,
                height=480,
                cube_execution_duration_ms=12.5,
            )
        )
    )
    adapter = SessionSnapshotCaptureAdapter(shell)

    references = adapter.output_image_references("wf-a", workflow)

    assert len(references) == 1
    assert references[0].image_id == str(image_id)
    assert references[0].path == image_path
    assert references[0].sequence == 1
    assert references[0].metadata.workflow_name == "Recipe"
    assert references[0].metadata.cube_execution_duration_ms == 12.5


def test_adapter_factory_reuses_existing_shell_adapter() -> None:
    """Shell composition should share one adapter instance."""

    shell = SimpleNamespace()

    first = snapshot_capture_adapter_for(shell)
    second = snapshot_capture_adapter_for(shell)

    assert first is second
    assert shell.session_snapshot_capture_adapter is first

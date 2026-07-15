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

"""Cover Phase 16 Input mask tool, presenter, and picker refresh ownership."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

from qpane import QPane

from substitute.presentation.canvas.input import (
    InputCanvasPresenter,
    InputMaskDirtyTracker,
    InputMaskSaveController,
    InputMaskToolController,
    InputMaskToolMenuState,
    InputMaskToolMode,
)
from substitute.presentation.canvas.input.input_mask_save_controller import SignalPort


class _Signal:
    """Provide a minimal Qt-like signal for controller tests."""

    def __init__(self) -> None:
        """Initialize disconnected signal state."""

        self._callbacks: list[Callable[..., object]] = []

    def connect(self, callback: Callable[..., object]) -> object:
        """Connect one callback."""

        self._callbacks.append(callback)
        return None

    def emit(self, *args: object) -> None:
        """Emit the connected callbacks."""

        for callback in self._callbacks:
            callback(*args)


class _Timer:
    """Capture single-shot and debounce scheduling without a Qt event loop."""

    calls: list[int] = []

    def __init__(self, _parent: object | None = None) -> None:
        """Initialize timer state."""

        self._timeout_signal = _Signal()
        self.timeout: SignalPort = self._timeout_signal
        self.started: list[int] = []
        self.single_shot = False

    @staticmethod
    def singleShot(msec: int, callback: Callable[[], None]) -> None:  # noqa: N802
        """Record and immediately run one scheduled callback."""

        _Timer.calls.append(msec)
        callback()

    def setSingleShot(self, value: bool) -> None:  # noqa: N802
        """Store single-shot mode."""

        self.single_shot = value

    def start(self, delay_ms: int) -> None:
        """Record one debounce delay."""

        self.started.append(delay_ms)

    def stop(self) -> None:
        """Accept timer cancellation."""

    def trigger(self) -> None:
        """Fire the timeout signal."""

        self._timeout_signal.emit()


class _MaskImage:
    """Represent a non-null QPane mask image."""

    def isNull(self) -> bool:  # noqa: N802
        """Return whether this fake image is null."""

        return False


class _Panel:
    """Record mask picker refreshes and reject widget-local path reads."""

    def __init__(self) -> None:
        """Initialize empty refresh history."""

        self.refreshes: list[tuple[str, str, str]] = []

    def refresh_mask_picker(
        self, cube_alias: str, node_name: str, new_path: str
    ) -> None:
        """Record one authoritative refresh."""

        self.refreshes.append((cube_alias, node_name, new_path))

    def current_file_path(self) -> str:
        """Fail if presenter code reads widget-local path memory."""

        raise AssertionError("widget-local path memory must not be read")


def test_mask_tool_controller_applies_only_authorized_tool_modes() -> None:
    """Mask tool mode writes should live in the controller and require masks."""

    image_id = uuid4()
    control_modes: list[object] = []
    menu_states: list[InputMaskToolMenuState] = []
    pane = _tool_pane(control_modes=control_modes, masks_by_image={image_id: []})
    controller = InputMaskToolController(
        input_pane=pane,
        current_image_id_provider=lambda: image_id,
        menu_state_sink=menu_states.append,
    )

    assert controller.refresh_tool_menu_state() == InputMaskToolMenuState()
    assert controller.request_tool_mode(InputMaskToolMode.BRUSH) is False
    assert controller.request_tool_mode(InputMaskToolMode.PAN_ZOOM) is True

    pane.masks_by_image[image_id] = [uuid4()]

    assert controller.refresh_tool_menu_state() == InputMaskToolMenuState(
        brush_enabled=True,
        smart_select_enabled=True,
    )
    assert controller.request_tool_mode(InputMaskToolMode.BRUSH) is True
    assert controller.request_tool_mode(InputMaskToolMode.SMART_SELECT) is True
    assert control_modes == [
        QPane.CONTROL_MODE_PANZOOM,
        QPane.CONTROL_MODE_DRAW_BRUSH,
        QPane.CONTROL_MODE_SMART_SELECT,
    ]
    assert menu_states[-1].brush_enabled is True


def test_presenter_mask_click_activates_owner_then_brush_mode() -> None:
    """LoadImageMask click intent should activate image, mask, then brush mode."""

    image_id = uuid4()
    mask_id = uuid4()
    panel = _Panel()
    active_images: list[UUID] = []
    active_masks: list[UUID] = []
    focused: list[str] = []
    control_modes: list[object] = []
    workflow = _workflow(image_id=image_id, mask_id=mask_id)
    pane = _tool_pane(control_modes=control_modes, masks_by_image={image_id: [mask_id]})

    def set_active_input_image(
        _workflow_id: str,
        _workflow: object,
        value: UUID,
    ) -> bool:
        """Record active image activation."""

        active_images.append(value)
        return True

    def set_active_workflow_mask(
        _workflow_id: str,
        _workflow: object,
        value: UUID,
    ) -> bool:
        """Record active mask activation."""

        active_masks.append(value)
        return True

    presenter = _presenter(
        workflow=workflow,
        panel=panel,
        pane=pane,
        current_image_id_provider=lambda: image_id,
        input_canvas_state_service=SimpleNamespace(
            set_active_input_image=set_active_input_image,
            set_active_workflow_mask=set_active_workflow_mask,
        ),
        canvas_tabs=SimpleNamespace(
            canvas_map={"Input": object()},
            focus_attached_canvas=lambda label: focused.append(label),
        ),
    )

    presenter.handle_input_mask_clicked("CubeA", "MaskNode", "")

    assert active_images == [image_id]
    assert active_masks == [mask_id]
    assert focused == ["Input"]
    assert control_modes == [QPane.CONTROL_MODE_DRAW_BRUSH]
    assert workflow.canvas.active_canvas_route == "Input"


def test_presenter_refreshes_materialized_picker_from_asset_state(
    tmp_path: Path,
) -> None:
    """Materialization picker refresh should ignore result-local paths."""

    image_id = uuid4()
    mask_id = uuid4()
    stale_result_path = tmp_path / "stale-widget.png"
    asset_path = tmp_path / "Recipe" / "masks" / "asset.png"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_bytes(b"asset")
    panel = _Panel()
    workflow = _workflow(image_id=image_id, mask_id=mask_id)
    presenter = _presenter(
        workflow=workflow,
        panel=panel,
        asset_path=asset_path,
    )

    presenter.apply_materialization_result(
        SimpleNamespace(
            mask_results=(
                SimpleNamespace(
                    association_key=("CubeA", "MaskNode"),
                    mask_id=mask_id,
                    resolved_path=stale_result_path,
                ),
            ),
            first_mask_id=mask_id,
        )
    )

    assert panel.refreshes == [("CubeA", "MaskNode", str(asset_path))]


def test_presenter_refreshes_user_selected_mask_from_asset_state(
    tmp_path: Path,
) -> None:
    """User-selected mask refresh should use asset state, not selected path."""

    image_id = uuid4()
    mask_id = uuid4()
    selected_path = tmp_path / "selected-but-not-authority.png"
    asset_path = tmp_path / "Recipe" / "masks" / "asset.png"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_bytes(b"asset")
    panel = _Panel()
    workflow = _workflow(image_id=image_id, mask_id=mask_id)
    presenter = _presenter(
        workflow=workflow,
        panel=panel,
        asset_path=asset_path,
        workflow_input_canvas_service=SimpleNamespace(
            apply_user_selected_input_mask=lambda **_kwargs: SimpleNamespace(
                applied=True,
                rejection_reason="",
                selected_dimensions=None,
                required_dimensions=None,
                materialization_result=None,
            )
        ),
    )

    presenter.handle_input_mask_changed("CubeA", "MaskNode", str(selected_path))

    assert panel.refreshes == [("CubeA", "MaskNode", str(asset_path))]


def test_explicit_and_debounced_saves_refresh_from_asset_state(
    tmp_path: Path,
) -> None:
    """Save completion paths should ignore emitted or saved path authority."""

    _Timer.calls = []
    image_id = uuid4()
    mask_id = uuid4()
    old_path = tmp_path / "old-emitted.png"
    asset_path = tmp_path / "Recipe" / "masks" / "asset.png"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_bytes(b"asset")
    panel = _Panel()
    workflow = _workflow(image_id=image_id, mask_id=mask_id)
    pane = _save_pane(mask_id=mask_id)
    presenter = _presenter(
        workflow=workflow,
        panel=panel,
        pane=pane,
        asset_path=asset_path,
        timer=_Timer,
    )

    presenter.handle_mask_save_completed(str(mask_id), str(old_path))
    assert panel.refreshes == [("CubeA", "MaskNode", str(asset_path))]

    def refresh_from_save_controller(
        cube_alias: str,
        node_name: str,
        _path: str,
    ) -> None:
        """Refresh the saved picker through presenter-owned asset-state lookup."""

        presenter.refresh_mask_picker_from_asset_state(
            cube_alias,
            node_name,
        )

    debounce_timer = _Timer()
    tracker = InputMaskDirtyTracker()
    controller = InputMaskSaveController(
        input_pane=pane,
        dirty_tracker=tracker,
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a",
            workflows={"wf-a": workflow},
        ),
        canvas_io_service=SimpleNamespace(
            resolve_mask_save_path=lambda **_kwargs: old_path,
            save_mask_image=lambda **_kwargs: True,
        ),
        workflow_asset_service=SimpleNamespace(
            associate_project_input_mask=lambda *_args, **_kwargs: True
        ),
        workflow_name_provider=lambda _workflow_id: "Recipe",
        projects_dir_provider=lambda: tmp_path,
        refresh_saved_mask=refresh_from_save_controller,
        timer_factory=lambda _parent: debounce_timer,
    )

    pane.mask_controller.mask_updated.emit(mask_id, object())
    debounce_timer.trigger()

    assert controller is not None
    assert panel.refreshes == [
        ("CubeA", "MaskNode", str(asset_path)),
        ("CubeA", "MaskNode", str(asset_path)),
    ]


def test_presenter_rejects_widget_local_path_memory_as_refresh_authority(
    tmp_path: Path,
) -> None:
    """Picker refresh should never consult widget-local current_file_path."""

    image_id = uuid4()
    mask_id = uuid4()
    asset_path = tmp_path / "Recipe" / "masks" / "asset.png"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_bytes(b"asset")
    panel = _Panel()
    workflow = _workflow(image_id=image_id, mask_id=mask_id)
    presenter = _presenter(workflow=workflow, panel=panel, asset_path=asset_path)

    assert presenter.refresh_mask_picker_from_asset_state("CubeA", "MaskNode") is True
    assert panel.refreshes == [("CubeA", "MaskNode", str(asset_path))]


def test_input_canvas_view_does_not_own_phase16_policy() -> None:
    """Static guardrail keeps tool and picker policy out of InputCanvasView."""

    source = Path(
        "substitute/presentation/canvas/input/input_canvas_view.py"
    ).read_text()
    for forbidden in (
        "setControlMode",
        "CONTROL_MODE_DRAW_BRUSH",
        "CONTROL_MODE_SMART_SELECT",
        "CONTROL_MODE_PANZOOM",
        "maskManager",
        "get_masks_for_image",
        "refresh_mask_picker",
        "current_file_path",
        "_current_file_path",
        "request_brush_mode",
    ):
        assert forbidden not in source


def test_phase16_policy_is_not_fallback_routed_through_workspace_actions() -> None:
    """Static guardrail keeps Phase 16 Input policy on presenter/controller paths."""

    controller_source = Path(
        "substitute/presentation/shell/workspace_controller.py"
    ).read_text()
    actions_source = Path(
        "substitute/presentation/shell/workspace_canvas_actions.py"
    ).read_text()
    for forbidden in (
        "_canvas_actions.on_input_image_changed",
        "_canvas_actions.on_input_canvas_image_loaded",
        "_canvas_actions.on_input_image_clicked",
        "_canvas_actions.refresh_active_mask_pickers",
        "_canvas_actions.on_input_mask_changed",
        "_canvas_actions.on_input_mask_clicked",
        "_canvas_actions.on_mask_save_completed",
        "_canvas_actions.materialize_loaded_cube_input_canvas",
        "_canvas_actions.reconcile_active_input_canvas_image",
    ):
        assert forbidden not in controller_source
    for forbidden in (
        "def on_input_image_changed",
        "def on_input_canvas_image_loaded",
        "def reconcile_active_input_canvas_image",
        "def on_input_image_clicked",
        "def refresh_active_mask_pickers",
        "def on_input_mask_changed",
        "def on_input_mask_clicked",
        "def on_mask_save_completed",
        "def materialize_loaded_cube_input_canvas",
        "request_brush_mode",
    ):
        assert forbidden not in actions_source


def _workflow(*, image_id: UUID, mask_id: UUID) -> SimpleNamespace:
    """Return workflow state with one graph-bound image and mask."""

    return SimpleNamespace(
        canvas=SimpleNamespace(
            input_key_map={"CubeA:ImageNode": image_id},
            mask_associations={("CubeA", "MaskNode"): mask_id},
            mask_to_image_map={mask_id: image_id},
            active_canvas_route=None,
        ),
        cubes={
            "CubeA": SimpleNamespace(
                buffer={
                    "nodes": {
                        "MaskNode": {
                            "class_type": "LoadImageMask",
                            "inputs": {"image": "stale-buffer.png"},
                        }
                    }
                }
            )
        },
    )


def _tool_pane(
    *,
    control_modes: list[object],
    masks_by_image: dict[UUID, list[UUID]],
) -> SimpleNamespace:
    """Return a pane fake for mask tool controller tests."""

    mask_manager = SimpleNamespace(
        get_masks_for_image=lambda image_id: masks_by_image.get(image_id, [])
    )
    return SimpleNamespace(
        masks_by_image=masks_by_image,
        setControlMode=lambda mode: control_modes.append(mode),
        catalog=lambda: SimpleNamespace(maskManager=lambda: mask_manager),
    )


def _save_pane(*, mask_id: UUID) -> SimpleNamespace:
    """Return a pane fake with mask update/save signals and current pixels."""

    layer = SimpleNamespace(mask_image=_MaskImage())
    mask_manager = SimpleNamespace(get_layer=lambda _mask_id: layer)
    return SimpleNamespace(
        mask_controller=SimpleNamespace(mask_updated=_Signal()),
        maskSaved=_Signal(),
        settings=SimpleNamespace(mask_autosave_debounce_ms=0),
        catalog=lambda: SimpleNamespace(maskManager=lambda: mask_manager),
        setMaskProperties=lambda *_args, **_kwargs: None,
        loadMaskFromFile=lambda _path: mask_id,
    )


def _presenter(
    *,
    workflow: SimpleNamespace,
    panel: _Panel,
    pane: Any | None = None,
    asset_path: Path | None = None,
    current_image_id_provider: Callable[[], UUID | None] | None = None,
    input_canvas_state_service: Any | None = None,
    workflow_input_canvas_service: Any | None = None,
    canvas_tabs: Any | None = None,
    timer: type[_Timer] = _Timer,
) -> InputCanvasPresenter:
    """Build an InputCanvasPresenter with focused test collaborators."""

    pane = pane or SimpleNamespace(
        setMaskProperties=lambda *_args, **_kwargs: None,
        catalog=lambda: SimpleNamespace(maskManager=lambda: None),
    )
    asset_path = asset_path or Path(__file__).resolve()
    workflow_input_canvas_service = workflow_input_canvas_service or SimpleNamespace(
        binding_for_mask=lambda *_args: SimpleNamespace(
            cube_alias="CubeA",
            image_node_name="ImageNode",
            association_key=("CubeA", "MaskNode"),
        ),
        bindings_for_image=lambda *_args: (
            SimpleNamespace(association_key=("CubeA", "MaskNode")),
        ),
    )
    input_canvas_state_service = input_canvas_state_service or SimpleNamespace(
        set_active_input_image=lambda *_args: True,
        set_active_workflow_mask=lambda *_args: True,
    )
    tool_controller = InputMaskToolController(
        input_pane=pane,
        current_image_id_provider=current_image_id_provider or (lambda: None),
    )
    return InputCanvasPresenter(
        input_pane=pane,
        current_image_id_provider=current_image_id_provider or (lambda: None),
        active_workflow_provider=lambda: cast(Any, workflow),
        active_editor_panel_provider=lambda: panel,
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a",
            workflows={"wf-a": workflow},
        ),
        workflow_input_canvas_service=cast(Any, workflow_input_canvas_service),
        input_canvas_state_service=cast(Any, input_canvas_state_service),
        workflow_asset_service=SimpleNamespace(
            resolve_input_mask_path=lambda *_args, **_kwargs: asset_path
        ),
        canvas_tabs_provider=lambda: cast(Any, canvas_tabs),
        workflow_name_provider=lambda _workflow_id: "Recipe",
        projects_dir_provider=lambda: asset_path.parent,
        mask_color_provider=lambda index, total: f"color-{index}/{total}",
        mask_tool_controller=tool_controller,
        timer=timer,
    )

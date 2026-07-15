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

"""Cover Phase 15 Input mask dirty/save/preflight ownership."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from substitute.presentation.canvas.input import (
    InputMaskDirtyTracker,
    InputMaskSaveController,
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
        """Emit to connected callbacks."""

        for callback in self._callbacks:
            callback(*args)


class _Timer:
    """Capture debounce scheduling without a Qt event loop."""

    def __init__(self, _parent: object | None = None) -> None:
        """Initialize timer state."""

        self._timeout_signal = _Signal()
        self.timeout: SignalPort = self._timeout_signal
        self.started: list[int] = []
        self.stopped = 0
        self.single_shot = False

    def setSingleShot(self, value: bool) -> None:  # noqa: N802
        """Store single-shot mode."""

        self.single_shot = value

    def start(self, delay_ms: int) -> None:
        """Record one scheduled delay."""

        self.started.append(delay_ms)

    def stop(self) -> None:
        """Record timer cancellation."""

        self.stopped += 1

    def trigger(self) -> None:
        """Fire the stored timeout callbacks."""

        self._timeout_signal.emit()


class _MaskImage:
    """Represent a non-null QPane mask image payload."""

    def isNull(self) -> bool:  # noqa: N802
        """Return whether the image is null."""

        return False


def test_dirty_tracker_marks_and_clears_valid_masks() -> None:
    """Dirty tracker should own mask dirty state outside widgets."""

    tracker = InputMaskDirtyTracker()
    mask_id = uuid4()

    assert tracker.mark_dirty(str(mask_id)) == mask_id
    assert tracker.is_dirty(mask_id) is True
    assert tracker.mark_persisted(mask_id, path="mask.png", reason="test") is True
    assert tracker.is_dirty(mask_id) is False
    assert tracker.mark_dirty("not-a-uuid") is None


def test_save_controller_debounces_mask_updates_and_persists_current_pixels(
    tmp_path: Path,
) -> None:
    """Mask updates should schedule controller-owned save debounce."""

    mask_id = uuid4()
    mask_image = _MaskImage()
    timer = _Timer()
    save_calls: list[tuple[Path, object]] = []
    asset_calls: list[tuple[str, str, str]] = []
    refresh_calls: list[tuple[str, str, str]] = []
    workflow = _workflow_with_mask(mask_id, mask_filename="mask.png")
    pane = _pane(mask_id=mask_id, mask_image=mask_image, debounce_ms=123)
    tracker = InputMaskDirtyTracker()

    def save_mask_image(*, destination: Path, image: object) -> bool:
        """Record one saved mask image."""

        save_calls.append((destination, image))
        return True

    def associate_project_input_mask(
        _workflow: object,
        *,
        cube_alias: str,
        node_name: str,
        relative_path: Path | str,
    ) -> bool:
        """Record one project mask association."""

        asset_calls.append((cube_alias, node_name, str(relative_path)))
        return True

    controller = InputMaskSaveController(
        input_pane=pane,
        dirty_tracker=tracker,
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a", workflows={"wf-a": workflow}
        ),
        canvas_io_service=SimpleNamespace(
            resolve_mask_save_path=lambda **_kwargs: tmp_path / "mask.png",
            save_mask_image=save_mask_image,
        ),
        workflow_asset_service=SimpleNamespace(
            associate_project_input_mask=associate_project_input_mask
        ),
        workflow_name_provider=lambda _workflow_id: "Recipe",
        projects_dir_provider=lambda: tmp_path,
        refresh_saved_mask=lambda cube_alias, node_name, path: refresh_calls.append(
            (cube_alias, node_name, path)
        ),
        timer_factory=lambda _parent: timer,
    )

    pane.mask_controller.mask_updated.emit(mask_id, object())
    pane.mask_controller.mask_updated.emit(mask_id, object())
    assert timer.single_shot is True
    assert timer.started == [123, 123]
    assert tracker.is_dirty(mask_id) is True

    timer.trigger()

    assert controller is not None
    assert save_calls == [(tmp_path / "mask.png", mask_image)]
    assert asset_calls == [("CubeA", "MaskNode", "mask.png")]
    assert refresh_calls == [("CubeA", "MaskNode", str(tmp_path / "mask.png"))]
    assert tracker.is_dirty(mask_id) is False
    assert timer.stopped == 1


def test_preflight_persists_dirty_workflow_associated_masks(tmp_path: Path) -> None:
    """Generation preflight should flush dirty associated masks synchronously."""

    mask_id = uuid4()
    mask_image = _MaskImage()
    tracker = InputMaskDirtyTracker()
    tracker.mark_dirty(mask_id)
    workflow = _workflow_with_mask(mask_id, mask_filename="mask.png")
    save_calls: list[tuple[Path, object]] = []
    asset_calls: list[tuple[str, str, str]] = []

    def save_mask_image(*, destination: Path, image: object) -> bool:
        """Record one preflight save call."""

        save_calls.append((destination, image))
        return True

    def associate_project_input_mask(
        _workflow: object,
        *,
        cube_alias: str,
        node_name: str,
        relative_path: Path | str,
    ) -> bool:
        """Record one preflight asset update."""

        asset_calls.append((cube_alias, node_name, str(relative_path)))
        return True

    controller = InputMaskSaveController(
        input_pane=_pane(mask_id=mask_id, mask_image=mask_image),
        dirty_tracker=tracker,
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a", workflows={"wf-a": workflow}
        ),
        canvas_io_service=SimpleNamespace(
            resolve_mask_save_path=lambda **_kwargs: tmp_path / "mask.png",
            save_mask_image=save_mask_image,
        ),
        workflow_asset_service=SimpleNamespace(
            associate_project_input_mask=associate_project_input_mask
        ),
        workflow_name_provider=lambda _workflow_id: "Recipe",
        projects_dir_provider=lambda: tmp_path,
    )

    assert controller.flush_dirty_associated_masks_before_generation() is True
    assert save_calls == [(tmp_path / "mask.png", mask_image)]
    assert asset_calls == [("CubeA", "MaskNode", "mask.png")]
    assert tracker.is_dirty(mask_id) is False


def test_preflight_fails_closed_when_pixels_are_unavailable(tmp_path: Path) -> None:
    """Dirty associated masks without readable QPane pixels should block generation."""

    mask_id = uuid4()
    tracker = InputMaskDirtyTracker()
    tracker.mark_dirty(mask_id)
    workflow = _workflow_with_mask(mask_id, mask_filename="mask.png")
    save_calls: list[object] = []
    controller = InputMaskSaveController(
        input_pane=_pane(mask_id=mask_id, mask_image=None),
        dirty_tracker=tracker,
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a", workflows={"wf-a": workflow}
        ),
        canvas_io_service=SimpleNamespace(
            resolve_mask_save_path=lambda **_kwargs: tmp_path / "mask.png",
            save_mask_image=lambda **kwargs: save_calls.append(kwargs),
        ),
        workflow_asset_service=SimpleNamespace(
            associate_project_input_mask=lambda *_args, **_kwargs: True
        ),
        workflow_name_provider=lambda _workflow_id: "Recipe",
        projects_dir_provider=lambda: tmp_path,
    )

    assert controller.flush_dirty_associated_masks_before_generation() is False
    assert save_calls == []
    assert tracker.is_dirty(mask_id) is True


def test_preflight_fails_closed_when_save_io_fails(tmp_path: Path) -> None:
    """Dirty associated masks should remain dirty when save IO fails."""

    mask_id = uuid4()
    tracker = InputMaskDirtyTracker()
    tracker.mark_dirty(mask_id)
    workflow = _workflow_with_mask(mask_id, mask_filename="mask.png")
    asset_calls: list[object] = []
    controller = InputMaskSaveController(
        input_pane=_pane(mask_id=mask_id, mask_image=_MaskImage()),
        dirty_tracker=tracker,
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a", workflows={"wf-a": workflow}
        ),
        canvas_io_service=SimpleNamespace(
            resolve_mask_save_path=lambda **_kwargs: tmp_path / "mask.png",
            save_mask_image=lambda **_kwargs: False,
        ),
        workflow_asset_service=SimpleNamespace(
            associate_project_input_mask=lambda *args, **kwargs: asset_calls.append(
                (args, kwargs)
            )
        ),
        workflow_name_provider=lambda _workflow_id: "Recipe",
        projects_dir_provider=lambda: tmp_path,
    )

    assert controller.flush_dirty_associated_masks_before_generation() is False
    assert asset_calls == []
    assert tracker.is_dirty(mask_id) is True


def test_preflight_fails_closed_when_dirty_signal_is_unavailable(
    tmp_path: Path,
) -> None:
    """Associated masks should block generation when dirty state cannot be trusted."""

    mask_id = uuid4()
    tracker = InputMaskDirtyTracker()
    tracker.mark_dirty(mask_id)
    workflow = _workflow_with_mask(mask_id, mask_filename="mask.png")
    save_calls: list[object] = []
    controller = InputMaskSaveController(
        input_pane=_pane_without_mask_update_signal(mask_id=mask_id),
        dirty_tracker=tracker,
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a", workflows={"wf-a": workflow}
        ),
        canvas_io_service=SimpleNamespace(
            resolve_mask_save_path=lambda **_kwargs: tmp_path / "mask.png",
            save_mask_image=lambda **kwargs: save_calls.append(kwargs),
        ),
        workflow_asset_service=SimpleNamespace(
            associate_project_input_mask=lambda *_args, **_kwargs: True
        ),
        workflow_name_provider=lambda _workflow_id: "Recipe",
        projects_dir_provider=lambda: tmp_path,
    )

    assert controller.flush_dirty_associated_masks_before_generation() is False
    assert save_calls == []
    assert tracker.is_dirty(mask_id) is True


def test_preflight_fails_closed_when_mask_ownership_is_unproven(
    tmp_path: Path,
) -> None:
    """Dirty masks without mask-to-image ownership proof should not persist."""

    mask_id = uuid4()
    tracker = InputMaskDirtyTracker()
    tracker.mark_dirty(mask_id)
    workflow = _workflow_with_mask(mask_id, mask_filename="mask.png")
    workflow.canvas.mask_to_image_map.clear()
    save_calls: list[object] = []
    controller = InputMaskSaveController(
        input_pane=_pane(mask_id=mask_id, mask_image=_MaskImage()),
        dirty_tracker=tracker,
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a", workflows={"wf-a": workflow}
        ),
        canvas_io_service=SimpleNamespace(
            resolve_mask_save_path=lambda **_kwargs: tmp_path / "mask.png",
            save_mask_image=lambda **kwargs: save_calls.append(kwargs),
        ),
        workflow_asset_service=SimpleNamespace(
            associate_project_input_mask=lambda *_args, **_kwargs: True
        ),
        workflow_name_provider=lambda _workflow_id: "Recipe",
        projects_dir_provider=lambda: tmp_path,
    )

    assert controller.flush_dirty_associated_masks_before_generation() is False
    assert save_calls == []
    assert tracker.is_dirty(mask_id) is True


def test_preflight_fails_closed_when_save_api_is_missing(tmp_path: Path) -> None:
    """Missing CanvasIoService save API should fail without clearing dirty state."""

    mask_id = uuid4()
    tracker = InputMaskDirtyTracker()
    tracker.mark_dirty(mask_id)
    controller = InputMaskSaveController(
        input_pane=_pane(mask_id=mask_id, mask_image=_MaskImage()),
        dirty_tracker=tracker,
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a",
            workflows={"wf-a": _workflow_with_mask(mask_id, mask_filename="mask.png")},
        ),
        canvas_io_service=SimpleNamespace(
            resolve_mask_save_path=lambda **_kwargs: tmp_path / "mask.png",
        ),
        workflow_asset_service=SimpleNamespace(
            associate_project_input_mask=lambda *_args, **_kwargs: True
        ),
        workflow_name_provider=lambda _workflow_id: "Recipe",
        projects_dir_provider=lambda: tmp_path,
    )

    assert controller.flush_dirty_associated_masks_before_generation() is False
    assert tracker.is_dirty(mask_id) is True


def test_preflight_fails_closed_when_path_resolution_api_is_missing(
    tmp_path: Path,
) -> None:
    """Missing mask path resolution API should fail before save IO."""

    mask_id = uuid4()
    tracker = InputMaskDirtyTracker()
    tracker.mark_dirty(mask_id)
    save_calls: list[object] = []
    controller = InputMaskSaveController(
        input_pane=_pane(mask_id=mask_id, mask_image=_MaskImage()),
        dirty_tracker=tracker,
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a",
            workflows={"wf-a": _workflow_with_mask(mask_id, mask_filename="mask.png")},
        ),
        canvas_io_service=SimpleNamespace(
            save_mask_image=lambda **kwargs: save_calls.append(kwargs),
        ),
        workflow_asset_service=SimpleNamespace(
            associate_project_input_mask=lambda *_args, **_kwargs: True
        ),
        workflow_name_provider=lambda _workflow_id: "Recipe",
        projects_dir_provider=lambda: tmp_path,
    )

    assert controller.flush_dirty_associated_masks_before_generation() is False
    assert save_calls == []
    assert tracker.is_dirty(mask_id) is True


def test_preflight_fails_closed_when_asset_api_is_missing(tmp_path: Path) -> None:
    """Missing WorkflowAssetService API should not mark dirty masks persisted."""

    mask_id = uuid4()
    tracker = InputMaskDirtyTracker()
    tracker.mark_dirty(mask_id)
    save_calls: list[Path] = []

    def save_mask_image(*, destination: Path, image: object) -> bool:
        """Record save before asset persistence fails closed."""

        _ = image
        save_calls.append(destination)
        return True

    controller = InputMaskSaveController(
        input_pane=_pane(mask_id=mask_id, mask_image=_MaskImage()),
        dirty_tracker=tracker,
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a",
            workflows={"wf-a": _workflow_with_mask(mask_id, mask_filename="mask.png")},
        ),
        canvas_io_service=SimpleNamespace(
            resolve_mask_save_path=lambda **_kwargs: tmp_path / "mask.png",
            save_mask_image=save_mask_image,
        ),
        workflow_asset_service=SimpleNamespace(),
        workflow_name_provider=lambda _workflow_id: "Recipe",
        projects_dir_provider=lambda: tmp_path,
    )

    assert controller.flush_dirty_associated_masks_before_generation() is False
    assert save_calls == [tmp_path / "mask.png"]
    assert tracker.is_dirty(mask_id) is True


def test_preflight_fails_closed_when_asset_association_fails(
    tmp_path: Path,
) -> None:
    """Asset association failure should keep masks dirty after a disk save."""

    mask_id = uuid4()
    tracker = InputMaskDirtyTracker()
    tracker.mark_dirty(mask_id)
    controller = InputMaskSaveController(
        input_pane=_pane(mask_id=mask_id, mask_image=_MaskImage()),
        dirty_tracker=tracker,
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a",
            workflows={"wf-a": _workflow_with_mask(mask_id, mask_filename="mask.png")},
        ),
        canvas_io_service=SimpleNamespace(
            resolve_mask_save_path=lambda **_kwargs: tmp_path / "mask.png",
            save_mask_image=lambda **_kwargs: True,
        ),
        workflow_asset_service=SimpleNamespace(
            associate_project_input_mask=lambda *_args, **_kwargs: False
        ),
        workflow_name_provider=lambda _workflow_id: "Recipe",
        projects_dir_provider=lambda: tmp_path,
    )

    assert controller.flush_dirty_associated_masks_before_generation() is False
    assert tracker.is_dirty(mask_id) is True


def test_input_canvas_view_and_workspace_actions_do_not_own_persistence_policy() -> (
    None
):
    """Static guardrail prevents dirty/save policy from returning to old owners."""

    input_view = Path(
        "substitute/presentation/canvas/input/input_canvas_view.py"
    ).read_text()
    workspace_actions = Path(
        "substitute/presentation/shell/workspace_canvas_actions.py"
    ).read_text()

    for forbidden in (
        "_mask_save_timers",
        "savePathRequested",
        "save_mask_to_path",
        "is_mask_dirty",
        "mark_mask_persisted",
    ):
        assert forbidden not in input_view
    assert "flush_dirty_input_masks_before_generation" not in workspace_actions
    assert "on_mask_save_path_requested" not in workspace_actions
    assert "save_mask_image" not in workspace_actions


def _workflow_with_mask(mask_id: object, *, mask_filename: str) -> SimpleNamespace:
    """Return workflow state shape with one associated mask."""

    image_id = uuid4()
    return SimpleNamespace(
        canvas=SimpleNamespace(
            input_key_map={"CubeA:ImageNode": image_id},
            mask_associations={("CubeA", "MaskNode"): mask_id},
            mask_to_image_map={mask_id: image_id},
        ),
        cubes={
            "CubeA": SimpleNamespace(
                buffer={"nodes": {"MaskNode": {"inputs": {"image": mask_filename}}}}
            )
        },
    )


def _pane(
    *,
    mask_id: object,
    mask_image: object | None,
    debounce_ms: int = 0,
) -> SimpleNamespace:
    """Return a QPane-like mask surface for save controller tests."""

    layer = SimpleNamespace(mask_image=mask_image) if mask_image is not None else None
    mask_manager = SimpleNamespace(get_layer=lambda _mask_id: layer)
    return SimpleNamespace(
        mask_controller=SimpleNamespace(mask_updated=_Signal()),
        maskSaved=_Signal(),
        settings=SimpleNamespace(mask_autosave_debounce_ms=debounce_ms),
        catalog=lambda: SimpleNamespace(maskManager=lambda: mask_manager),
    )


def _pane_without_mask_update_signal(*, mask_id: object) -> SimpleNamespace:
    """Return a QPane-like mask surface without dirty update signals."""

    mask_manager = SimpleNamespace(get_layer=lambda _mask_id: None)
    return SimpleNamespace(
        mask_controller=SimpleNamespace(),
        maskSaved=_Signal(),
        settings=SimpleNamespace(mask_autosave_debounce_ms=0),
        catalog=lambda: SimpleNamespace(maskManager=lambda: mask_manager),
    )

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

"""Verify node-owned visual opacity for scalar and ordered Input masks."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from PySide6.QtCore import QCoreApplication, QPoint, QSize, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QSpinBox, QWidget
import pytest

from substitute.application.workflows.input_canvas_state_service import (
    InputCanvasStateService,
)
from substitute.application.workflows.input_canvas_document_port import (
    CanvasDocumentMutation,
)
from substitute.domain.workflow import WorkflowState
from substitute.domain.workspace_snapshot.codecs import (
    workflow_state_from_json,
    workflow_state_to_json,
)
from substitute.presentation.canvas.input.input_layer_settings import (
    InputMaskLayerSettings,
)
from substitute.presentation.canvas.input.input_document import InputCanvasDocument
from substitute.presentation.canvas.input.input_mask_visual_opacity_controller import (
    InputMaskVisualOpacityController,
)
from substitute.presentation.editor.panel.mask_visual_opacity_projection import (
    project_mask_visual_opacity,
    project_mask_visual_opacity_value,
)
from substitute.presentation.editor.panel.widgets.fields.load_mask import MaskPicker
from substitute.presentation.editor.panel.widgets.fields.mask_visual_opacity import (
    MaskVisualOpacityControl,
)
from substitute.presentation.editor.panel.widgets.fields.regional_mask_batch import (
    RegionalMaskBatchEditor,
)

_ASSOCIATION_KEY = ("Prompt by Region", "load_mask_batch")


def _app() -> QApplication:
    """Return the shared QApplication for headless widget assertions."""

    instance = QCoreApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


@pytest.mark.parametrize("batch", (False, True))
def test_mask_node_widgets_publish_one_spinner_slider_opacity(batch: bool) -> None:
    """Expose one node-level percentage control for scalar and ordered masks."""

    app = _app()
    widget: QWidget
    if batch:
        widget = RegionalMaskBatchEditor(
            cube_alias="Prompt by Region",
            node_name="load_mask_batch",
            values=["first.png", "second.png"],
        )
    else:
        widget = MaskPicker(
            cube_alias="Inpaint",
            node_name="load_mask",
        )
    changes: list[tuple[str, str, float]] = []
    commits: list[tuple[str, str, float, float]] = []
    cast(Any, widget).visualOpacityChanged.connect(
        lambda alias, node, opacity: changes.append((alias, node, opacity))
    )
    cast(Any, widget).visualOpacityCommitted.connect(
        lambda alias, node, before, after: commits.append((alias, node, before, after))
    )
    control = widget.findChild(QWidget, "MaskVisualOpacityControl")
    spinner = widget.findChild(QSpinBox, "MaskVisualOpacitySpinBox")

    assert control is not None
    assert spinner is not None
    assert spinner.value() == 50

    spinner.setValue(37)
    spinner.editingFinished.emit()

    expected_alias = "Prompt by Region" if batch else "Inpaint"
    expected_node = "load_mask_batch" if batch else "load_mask"
    assert changes == [(expected_alias, expected_node, 0.37)]
    assert commits == [(expected_alias, expected_node, 0.5, 0.37)]
    widget.deleteLater()
    app.processEvents()


def test_input_layer_settings_retains_coverage_edit_without_opacity_controls() -> None:
    """Keep per-layer coverage editing while removing per-layer opacity ownership."""

    app = _app()
    parent = QWidget()
    settings = InputMaskLayerSettings(parent)

    assert settings.findChild(QWidget, "InputLayerVisualOpacity") is None
    assert (
        settings.findChild(
            QPushButton,
            "InputEditLayerCoverageButton",
        )
        is not None
    )
    parent.deleteLater()
    app.processEvents()


def test_mask_opacity_slider_commits_one_edit_after_live_preview() -> None:
    """Coalesce every live slider value into one release-time history intent."""

    app = _app()
    control = MaskVisualOpacityControl()
    previews: list[float] = []
    commits: list[tuple[float, float]] = []
    control.opacityChanged.connect(previews.append)
    control.opacityCommitted.connect(
        lambda before, after: commits.append((before, after))
    )

    control.control.slider.sliderPressed.emit()
    control.control.slider.setValue(42)
    control.control.slider.setValue(37)
    control.control.slider.sliderReleased.emit()

    assert previews == [0.42, 0.37]
    assert commits == [(0.5, 0.37)]
    control.deleteLater()
    app.processEvents()


def test_mask_opacity_groove_drag_commits_only_after_pointer_release() -> None:
    """Treat a Fluent slider groove drag as one continuous history gesture."""

    app = _app()
    control = MaskVisualOpacityControl()
    control.show()
    app.processEvents()
    previews: list[float] = []
    commits: list[tuple[float, float]] = []
    control.opacityChanged.connect(previews.append)
    control.opacityCommitted.connect(
        lambda before, after: commits.append((before, after))
    )
    slider = control.control.slider
    start = QPoint(slider.width() // 4, slider.height() // 2)
    middle = QPoint(slider.width() // 2, slider.height() // 2)
    end = QPoint(slider.width() * 3 // 4, slider.height() // 2)

    QTest.mousePress(slider, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(slider, middle)
    QTest.mouseMove(slider, end)
    app.processEvents()

    assert len(previews) >= 2
    assert commits == []

    QTest.mouseRelease(slider, Qt.MouseButton.LeftButton, pos=end)
    app.processEvents()

    assert commits == [(0.5, control.opacity())]
    control.close()
    control.deleteLater()
    app.processEvents()


def test_workflow_canvas_persists_node_mask_visual_opacity() -> None:
    """Round-trip one authoritative node value independently of mask identities."""

    workflow = WorkflowState()

    assert workflow.canvas.mask_visual_opacity(_ASSOCIATION_KEY) == pytest.approx(0.5)
    workflow.canvas.set_mask_visual_opacity(_ASSOCIATION_KEY, 0.37)

    payload = workflow_state_to_json(workflow)
    restored = workflow_state_from_json(payload)

    assert restored.canvas.mask_visual_opacity(_ASSOCIATION_KEY) == pytest.approx(0.37)


def test_input_canvas_state_applies_node_opacity_to_every_associated_mask() -> None:
    """Project one node value to scalar or ordered layers without affecting coverage."""

    workflow = WorkflowState()
    image_id = uuid4()
    first_mask_id = uuid4()
    second_mask_id = uuid4()
    workflow.canvas.bind_image("Prompt by Region:latent", image_id)
    collection = workflow.canvas.ensure_regional_mask_collection(_ASSOCIATION_KEY)
    collection.add_region(image_id, mask_id=first_mask_id)
    collection.add_region(image_id, mask_id=second_mask_id)
    calls: list[tuple[object, float]] = []

    def apply_opacity(mask_id: object, opacity: float) -> bool:
        """Record one fake document presentation mutation."""

        calls.append((mask_id, opacity))
        return True

    document = SimpleNamespace(
        set_mask_visual_opacity=apply_opacity,
    )
    service = InputCanvasStateService(
        input_document=cast(Any, document),
        input_route_projector=cast(Any, SimpleNamespace()),
    )

    assert service.set_mask_visual_opacity(
        "workflow-a",
        workflow,
        _ASSOCIATION_KEY,
        0.37,
    )

    assert workflow.canvas.mask_visual_opacity(_ASSOCIATION_KEY) == pytest.approx(0.37)
    assert calls == [(first_mask_id, 0.37), (second_mask_id, 0.37)]


def test_node_opacity_updates_real_cutecanvas_layers_without_changing_coverage() -> (
    None
):
    """Update real layer presentation while preserving exported mask pixels."""

    _app()
    document = InputCanvasDocument(features=("mask",))
    workflow = WorkflowState()
    image_id = uuid4()
    image = QImage(24, 16, QImage.Format.Format_ARGB32)
    image.fill(QColor("black"))
    assert (
        document.ensure_image_cached(image_id, image, None)
        is CanvasDocumentMutation.ADDED
    )
    first_mask_id = document.create_blank_mask(image_id, QSize(24, 16))
    second_mask_id = document.create_blank_mask(image_id, QSize(24, 16))
    assert first_mask_id is not None
    assert second_mask_id is not None
    collection = workflow.canvas.ensure_regional_mask_collection(_ASSOCIATION_KEY)
    collection.add_region(image_id, mask_id=first_mask_id)
    collection.add_region(image_id, mask_id=second_mask_id)
    before = {
        mask_id: document.export_mask_image(mask_id)
        for mask_id in (first_mask_id, second_mask_id)
    }
    service = InputCanvasStateService(
        input_document=document,
        input_route_projector=cast(Any, SimpleNamespace()),
    )

    try:
        assert service.set_mask_visual_opacity(
            "workflow-a",
            workflow,
            _ASSOCIATION_KEY,
            0.37,
        )

        masks = document.canvas.listMasksForComposition()
        assert {mask.mask_id: mask.opacity for mask in masks} == {
            first_mask_id: pytest.approx(0.37),
            second_mask_id: pytest.approx(0.37),
        }
        for mask_id, previous in before.items():
            exported = document.export_mask_image(mask_id)
            assert previous is not None
            assert exported is not None
            assert exported == previous
    finally:
        document.close()


def test_real_cutecanvas_history_undoes_one_node_opacity_gesture_atomically() -> None:
    """Record all masks in one node as one chronological CuteCanvas edit."""

    _app()
    document = InputCanvasDocument(features=("mask",))
    image_id = uuid4()
    image = QImage(24, 16, QImage.Format.Format_ARGB32)
    image.fill(QColor("black"))
    assert (
        document.ensure_image_cached(image_id, image, None)
        is CanvasDocumentMutation.ADDED
    )
    first_mask_id = document.create_blank_mask(image_id, QSize(24, 16))
    second_mask_id = document.create_blank_mask(image_id, QSize(24, 16))
    assert first_mask_id is not None
    assert second_mask_id is not None
    mask_ids = (first_mask_id, second_mask_id)

    try:
        assert document.set_mask_visual_opacity(first_mask_id, 0.37)
        assert document.set_mask_visual_opacity(second_mask_id, 0.37)
        assert document.commit_mask_visual_opacity_edit(
            mask_ids,
            before=0.5,
            after=0.37,
        )
        assert document.canvas.sceneEditUndoAvailable()

        assert document.canvas.undoSceneEdit()
        assert not document.canvas.sceneEditUndoAvailable()
        assert document.canvas.sceneEditRedoAvailable()
        masks = document.canvas.listMasksForComposition()
        assert {mask.mask_id: mask.opacity for mask in masks} == {
            first_mask_id: pytest.approx(0.5),
            second_mask_id: pytest.approx(0.5),
        }

        assert document.canvas.redoSceneEdit()
        assert document.canvas.sceneEditUndoAvailable()
        assert not document.canvas.sceneEditRedoAvailable()
        masks = document.canvas.listMasksForComposition()
        assert {mask.mask_id: mask.opacity for mask in masks} == {
            first_mask_id: pytest.approx(0.37),
            second_mask_id: pytest.approx(0.37),
        }
    finally:
        document.close()


def test_new_mask_inherits_its_node_visual_opacity() -> None:
    """Apply the persisted node value when a new mask layer materializes later."""

    workflow = WorkflowState()
    image_id = uuid4()
    mask_id = uuid4()
    workflow.canvas.bind_image("Prompt by Region:latent", image_id)
    workflow.canvas.set_mask_visual_opacity(_ASSOCIATION_KEY, 0.37)
    calls: list[tuple[object, float]] = []

    def apply_opacity(value: object, opacity: float) -> bool:
        """Record inherited presentation on one new fake mask."""

        calls.append((value, opacity))
        return True

    document = SimpleNamespace(
        create_blank_mask=lambda _image_id, _size: mask_id,
        set_mask_visual_opacity=apply_opacity,
    )
    route = SimpleNamespace(
        bind=lambda _scope: None,
        show_image=lambda _image_id: True,
    )
    service = InputCanvasStateService(
        input_document=cast(Any, document),
        input_route_projector=cast(Any, route),
    )

    created = service.create_mask_for_image(
        "workflow-a",
        workflow,
        _ASSOCIATION_KEY,
        image_id,
        object(),
    )

    assert created == mask_id
    assert calls == [(mask_id, 0.37)]


def test_mask_opacity_failure_rolls_back_layers_and_workflow_state() -> None:
    """Avoid partial batch presentation when CuteCanvas rejects one mask."""

    workflow = WorkflowState()
    image_id = uuid4()
    first_mask_id = uuid4()
    second_mask_id = uuid4()
    collection = workflow.canvas.ensure_regional_mask_collection(_ASSOCIATION_KEY)
    collection.add_region(image_id, mask_id=first_mask_id)
    collection.add_region(image_id, mask_id=second_mask_id)
    calls: list[tuple[object, float]] = []

    def apply(mask_id: object, opacity: float) -> bool:
        """Reject the second mask and accept the rollback of the first."""

        calls.append((mask_id, opacity))
        return mask_id != second_mask_id

    service = InputCanvasStateService(
        input_document=cast(
            Any,
            SimpleNamespace(set_mask_visual_opacity=apply),
        ),
        input_route_projector=cast(Any, SimpleNamespace()),
    )

    assert not service.set_mask_visual_opacity(
        "workflow-a",
        workflow,
        _ASSOCIATION_KEY,
        0.37,
    )

    assert workflow.canvas.mask_visual_opacity(_ASSOCIATION_KEY) == pytest.approx(0.5)
    assert calls == [
        (first_mask_id, 0.37),
        (second_mask_id, 0.37),
        (first_mask_id, 0.5),
    ]


def test_node_opacity_controller_routes_binding_and_persistence_once() -> None:
    """Resolve graph identity before applying, invalidating, and autosaving."""

    workflow = WorkflowState()
    calls: list[tuple[str, WorkflowState, tuple[str, str], float]] = []
    invalidations: list[str] = []
    autosaves: list[None] = []

    def apply_opacity(
        workflow_id: str,
        target_workflow: WorkflowState,
        association_key: tuple[str, str],
        opacity: float,
    ) -> bool:
        """Record one controller-to-application mutation."""

        calls.append((workflow_id, target_workflow, association_key, opacity))
        return True

    controller = InputMaskVisualOpacityController(
        active_workflow=lambda: workflow,
        active_workflow_id=lambda: "workflow-a",
        binding_service=cast(
            Any,
            SimpleNamespace(
                binding_for_mask=lambda *_args: SimpleNamespace(
                    association_key=_ASSOCIATION_KEY
                )
            ),
        ),
        state_service=cast(
            Any,
            SimpleNamespace(set_mask_visual_opacity=apply_opacity),
        ),
        document=cast(Any, SimpleNamespace()),
        project_opacity=lambda *_args: None,
        mark_changed=invalidations.append,
        request_autosave=lambda: autosaves.append(None),
    )

    assert controller.handle("Prompt by Region", "load_mask_batch", 0.37)

    assert calls == [("workflow-a", workflow, _ASSOCIATION_KEY, 0.37)]
    assert invalidations == ["workflow-a"]
    assert autosaves == [None]


def test_history_reconciliation_ignores_empty_startup_workflow_route() -> None:
    """Do not query active workflow state before startup establishes its identity."""

    active_workflow_queries: list[None] = []

    def missing_active_workflow() -> WorkflowState:
        """Model the session service's empty-route lookup failure."""

        active_workflow_queries.append(None)
        raise KeyError("")

    controller = InputMaskVisualOpacityController(
        active_workflow=missing_active_workflow,
        active_workflow_id=lambda: "",
        binding_service=cast(Any, SimpleNamespace()),
        state_service=cast(Any, SimpleNamespace()),
        document=cast(Any, SimpleNamespace()),
        project_opacity=lambda *_args: None,
        mark_changed=lambda _workflow_id: None,
        request_autosave=lambda: None,
    )

    assert controller.reconcile_history(False, False) == 0
    assert active_workflow_queries == []


def test_node_opacity_undo_reconciles_document_workflow_and_card_state() -> None:
    """Undo and redo one gesture across CuteCanvas, persistence, and node UI."""

    _app()
    document = InputCanvasDocument(features=("mask",))
    workflow = WorkflowState()
    image_id = uuid4()
    image = QImage(24, 16, QImage.Format.Format_ARGB32)
    image.fill(QColor("black"))
    assert (
        document.ensure_image_cached(image_id, image, None)
        is CanvasDocumentMutation.ADDED
    )
    first_mask_id = document.create_blank_mask(image_id, QSize(24, 16))
    second_mask_id = document.create_blank_mask(image_id, QSize(24, 16))
    assert first_mask_id is not None
    assert second_mask_id is not None
    collection = workflow.canvas.ensure_regional_mask_collection(_ASSOCIATION_KEY)
    collection.add_region(image_id, mask_id=first_mask_id)
    collection.add_region(image_id, mask_id=second_mask_id)
    state_service = InputCanvasStateService(
        input_document=document,
        input_route_projector=cast(Any, SimpleNamespace()),
    )
    projected: list[float] = []
    invalidations: list[str] = []
    autosaves: list[None] = []
    controller = InputMaskVisualOpacityController(
        active_workflow=lambda: workflow,
        active_workflow_id=lambda: "workflow-a",
        binding_service=cast(
            Any,
            SimpleNamespace(
                binding_for_mask=lambda *_args: SimpleNamespace(
                    association_key=_ASSOCIATION_KEY
                )
            ),
        ),
        state_service=state_service,
        document=document,
        project_opacity=lambda _workflow_id, _key, opacity: projected.append(opacity),
        mark_changed=invalidations.append,
        request_autosave=lambda: autosaves.append(None),
    )
    document.canvas.sceneEditHistoryChanged.connect(controller.reconcile_history)

    try:
        assert controller.handle(*_ASSOCIATION_KEY, 0.37)
        assert controller.handle_commit(*_ASSOCIATION_KEY, 0.5, 0.37)

        assert document.canvas.undoSceneEdit()
        assert workflow.canvas.mask_visual_opacity(_ASSOCIATION_KEY) == pytest.approx(
            0.5
        )
        assert projected == [0.5]

        assert document.canvas.redoSceneEdit()
        assert workflow.canvas.mask_visual_opacity(_ASSOCIATION_KEY) == pytest.approx(
            0.37
        )
        assert projected == [0.5, 0.37]
        assert invalidations == ["workflow-a", "workflow-a", "workflow-a"]
        assert autosaves == [None, None, None]
    finally:
        document.close()


def test_real_groove_drag_undoes_once_and_resynchronizes_complete_control() -> None:
    """Undo one real drag and restore spinner, slider fill, and Fluent handle."""

    app = _app()
    document = InputCanvasDocument(features=("mask",))
    workflow = WorkflowState()
    image_id = uuid4()
    image = QImage(24, 16, QImage.Format.Format_ARGB32)
    image.fill(QColor("black"))
    assert (
        document.ensure_image_cached(image_id, image, None)
        is CanvasDocumentMutation.ADDED
    )
    mask_id = document.create_blank_mask(image_id, QSize(24, 16))
    assert mask_id is not None
    workflow.canvas.ensure_regional_mask_collection(_ASSOCIATION_KEY).add_region(
        image_id,
        mask_id=mask_id,
    )
    state_service = InputCanvasStateService(
        input_document=document,
        input_route_projector=cast(Any, SimpleNamespace()),
    )
    control = MaskVisualOpacityControl()
    control.show()
    app.processEvents()
    controller = InputMaskVisualOpacityController(
        active_workflow=lambda: workflow,
        active_workflow_id=lambda: "workflow-a",
        binding_service=cast(
            Any,
            SimpleNamespace(
                binding_for_mask=lambda *_args: SimpleNamespace(
                    association_key=_ASSOCIATION_KEY
                )
            ),
        ),
        state_service=state_service,
        document=document,
        project_opacity=lambda _workflow_id, _key, opacity: control.set_opacity(
            opacity
        ),
        mark_changed=lambda _workflow_id: None,
        request_autosave=lambda: None,
    )
    control.opacityChanged.connect(
        lambda opacity: controller.handle(*_ASSOCIATION_KEY, opacity)
    )
    control.opacityCommitted.connect(
        lambda before, after: controller.handle_commit(
            *_ASSOCIATION_KEY,
            before,
            after,
        )
    )
    document.canvas.sceneEditHistoryChanged.connect(controller.reconcile_history)
    slider = control.control.slider
    start = QPoint(slider.width() // 4, slider.height() // 2)
    middle = QPoint(slider.width() // 2, slider.height() // 2)
    end = QPoint(slider.width() * 3 // 4, slider.height() // 2)

    try:
        QTest.mousePress(slider, Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(slider, middle)
        QTest.mouseMove(slider, end)
        QTest.mouseRelease(slider, Qt.MouseButton.LeftButton, pos=end)
        app.processEvents()

        assert document.canvas.sceneEditUndoAvailable()
        assert document.canvas.undoSceneEdit()
        app.processEvents()

        assert not document.canvas.sceneEditUndoAvailable()
        assert workflow.canvas.mask_visual_opacity(_ASSOCIATION_KEY) == pytest.approx(
            0.5
        )
        assert control.control.spinbox.value() == 50
        assert slider.value() == 50
        fluent_slider = cast(Any, slider)
        assert fluent_slider.handle.x() == int(0.5 * fluent_slider.grooveLength)
    finally:
        control.close()
        control.deleteLater()
        document.close()
        app.processEvents()


def test_restored_node_opacity_projects_without_republishing_intent() -> None:
    """Initialize a rebuilt node card from workflow state without a write loop."""

    app = _app()
    workflow = WorkflowState()
    workflow.canvas.set_mask_visual_opacity(_ASSOCIATION_KEY, 0.37)
    panel = QWidget()
    mainwindow = SimpleNamespace(
        editor_panels={"workflow-a": panel},
        workflow_session_service=SimpleNamespace(workflows={"workflow-a": workflow}),
    )
    cast(Any, panel).mainwindow = mainwindow
    widget = RegionalMaskBatchEditor(
        cube_alias=_ASSOCIATION_KEY[0],
        node_name=_ASSOCIATION_KEY[1],
        values=[],
        parent=panel,
    )
    changes: list[float] = []
    widget.visualOpacityChanged.connect(
        lambda _alias, _node, opacity: changes.append(opacity)
    )

    assert project_mask_visual_opacity(
        widget,
        panel,
        cube_alias=_ASSOCIATION_KEY[0],
        node_name=_ASSOCIATION_KEY[1],
    )

    spinner = widget.findChild(QSpinBox, "MaskVisualOpacitySpinBox")
    assert spinner is not None
    assert spinner.value() == 37
    assert changes == []
    panel.deleteLater()
    app.processEvents()


def test_history_opacity_projects_into_mounted_node_without_new_intent() -> None:
    """Reflect undo and redo values in a live node control without a write loop."""

    app = _app()
    panel = QWidget()
    widget = RegionalMaskBatchEditor(
        cube_alias=_ASSOCIATION_KEY[0],
        node_name=_ASSOCIATION_KEY[1],
        values=[],
        parent=panel,
    )
    widget.setProperty(
        "input_metadata",
        {
            "cube_alias": _ASSOCIATION_KEY[0],
            "node_name": _ASSOCIATION_KEY[1],
        },
    )
    changes: list[float] = []
    widget.visualOpacityChanged.connect(
        lambda _alias, _node, opacity: changes.append(opacity)
    )

    assert project_mask_visual_opacity_value(
        panel,
        cube_alias=_ASSOCIATION_KEY[0],
        node_name=_ASSOCIATION_KEY[1],
        opacity=0.37,
    )

    spinner = widget.findChild(QSpinBox, "MaskVisualOpacitySpinBox")
    assert spinner is not None
    assert spinner.value() == 37
    assert changes == []
    panel.deleteLater()
    app.processEvents()

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

"""Verify native ordered regional-mask editor interaction behavior."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import json
from pathlib import Path

import pytest

from PySide6.QtCore import QEvent, QPointF, Signal
from PySide6.QtGui import QColor, QEnterEvent
from PySide6.QtWidgets import QFileDialog, QLabel, QPushButton, QWidget

from substitute.domain.workflow import ProjectMaskAssetRef, WorkflowState
from substitute.application.workflows.input_canvas_state_service import (
    InputCanvasStateService,
)
from substitute.application.workflows.workflow_input_canvas_service import (
    WorkflowInputCanvasService,
)
from substitute.presentation.canvas.input.input_materialization_presenter import (
    InputMaterializationPresenter,
)
from substitute.presentation.editor.panel.widgets.fields.regional_mask_batch import (
    RegionalMaskBatchEditor,
)
from substitute.presentation.regional.mask_collection_presenter import (
    RegionalMaskCollectionPresenter,
)
from substitute.presentation.regional.panel_initial_projection import (
    project_regional_panel_widget,
)
from substitute.presentation.regional.panel_signal_binding import (
    bind_regional_panel_signals,
)
from substitute.presentation.shell.regional_mask_action_controller import (
    RegionalMaskActionController,
)
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application


class _RegionalPromptSignalWidget(QWidget):
    """Expose the prompt signals consumed by regional panel binding."""

    regionHovered = Signal(object)
    textChanged = Signal()

    def __init__(self, text: str, parent: QWidget) -> None:
        """Store one current prompt source snapshot."""

        super().__init__(parent)
        self.text = text

    def toPlainText(self) -> str:  # noqa: N802
        """Return the current prompt source snapshot."""

        return self.text


def test_mask_batch_editor_expands_selection_and_publishes_add_intent() -> None:
    """Rows should select locally while Add awaits authoritative collection state."""

    ensure_qt_application()
    editor = RegionalMaskBatchEditor(
        cube_alias="Prompt by Region",
        node_name="load_mask_batch",
        values=["foreground.png", "background.png"],
    )
    actions: list[tuple[str, str, str]] = []
    editor.regionActionRequested.connect(
        lambda alias, node, action: actions.append((alias, node, action))
    )

    rows = {
        button.property("region_index"): button
        for button in editor.findChildren(QPushButton)
        if button.property("region_index") is not None
    }
    add_button = next(
        button
        for button in editor.findChildren(QPushButton)
        if button.property("region_add_button") is True
    )
    rows[1].click()
    add_button.click()

    assert actions == [
        ("Prompt by Region", "load_mask_batch", "@region:select:1"),
        ("Prompt by Region", "load_mask_batch", "@region:add"),
    ]
    assert editor.region_count == 2
    assert editor.selected_index == 0
    updated_rows = {
        button.property("region_index"): button
        for button in editor.findChildren(QPushButton)
        if button.property("region_index") is not None
    }
    assert updated_rows[0].property("region_selected") is True
    assert updated_rows[1].property("region_selected") is False
    assert updated_rows[0].minimumHeight() == 48
    assert updated_rows[1].minimumHeight() == 44
    destroy_qt_object(editor)


def test_mask_batch_editor_publishes_hover_without_changing_selection() -> None:
    """Row hover should link views transiently without selecting another mask."""

    application = ensure_qt_application()
    editor = RegionalMaskBatchEditor(
        cube_alias="Prompt by Region",
        node_name="load_mask_batch",
        values=["first.png", "second.png"],
    )
    editor.resize(320, 160)
    editor.show()
    application.processEvents()
    try:
        hovered: list[int | None] = []
        rows = {
            button.property("region_index"): button
            for button in editor.findChildren(QPushButton)
            if button.property("region_index") is not None
        }
        row = rows[1]
        application.sendEvent(row, QEvent(QEvent.Type.Leave))
        editor.regionHoverChanged.connect(hovered.append)
        local_position = QPointF(row.rect().center())

        application.sendEvent(
            row,
            QEnterEvent(
                local_position,
                local_position,
                QPointF(row.mapToGlobal(row.rect().center())),
            ),
        )

        assert hovered == [1]
        assert editor.selected_index == 0
        assert row.property("region_linked_hovered") is True
    finally:
        destroy_qt_object(editor)


def test_mask_batch_editor_prefers_sep_names_without_large_button_titles() -> None:
    """Rows should show normal-sized authored names without internal button text."""

    ensure_qt_application()
    editor = RegionalMaskBatchEditor(
        cube_alias="Prompt by Region",
        node_name="load_mask_batch",
        values=["foreground.png", "background.png"],
        labels=["Character", None],
    )
    rows = sorted(
        (
            button
            for button in editor.findChildren(QPushButton)
            if button.property("region_index") is not None
        ),
        key=lambda button: int(button.property("region_index")),
    )
    labels = [row.findChild(QLabel, "regionalMaskLabel") for row in rows]

    assert [label.text() for label in labels if label is not None] == [
        "Character",
        "background",
    ]
    assert all(row.text() == "" for row in rows)
    assert all(
        label is not None and label.font().pointSizeF() == editor.font().pointSizeF()
        for label in labels
    )

    editor.set_region_names(["Subject", "Setting"])

    assert [label.text() for label in labels if label is not None] == [
        "Subject",
        "Setting",
    ]
    destroy_qt_object(editor)


def test_regional_prompt_text_change_routes_current_sep_names_to_coordinator() -> None:
    """Prompt commits should publish current source for immediate mask relabeling."""

    ensure_qt_application()
    panel = QWidget()
    widget = _RegionalPromptSignalWidget(
        "global\n[SEP|Subject]\nregion",
        panel,
    )
    calls: list[tuple[QWidget, str, str, str]] = []
    cast(Any, panel).mainwindow = SimpleNamespace(
        regional_interaction_coordinator=SimpleNamespace(
            handle_prompt_text_changed=lambda *args: calls.append(args)
        )
    )
    bind_regional_panel_signals(
        widget,
        panel,
        cube_alias="Region",
        node_name="positive",
    )

    widget.textChanged.emit()

    assert calls == [(panel, "Region", "positive", "global\n[SEP|Subject]\nregion")]
    destroy_qt_object(panel)


def test_mask_batch_editor_imports_multiple_paths_and_removes_selection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Import and remove controls should publish unambiguous ordered actions."""

    ensure_qt_application()
    paths = [str(tmp_path / "a.png"), str(tmp_path / "b.png")]
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileNames",
        lambda *_args, **_kwargs: (paths, ""),
    )
    editor = RegionalMaskBatchEditor(
        cube_alias="Prompt by Region",
        node_name="load_mask_batch",
        values=["first.png"],
    )
    actions: list[str] = []
    editor.regionActionRequested.connect(
        lambda _alias, _node, action: actions.append(action)
    )
    import_button = next(
        button
        for button in editor.findChildren(QPushButton)
        if button.property("region_import_button") is True
    )
    remove_button = next(
        button
        for button in editor.findChildren(QPushButton)
        if button.property("region_remove_button") is True
    )

    import_button.click()
    editor.set_regions(
        ["first.png", paths[0], paths[1]],
        selected_index=2,
    )
    remove_button.click()

    imported_actions = [
        action.removeprefix("@region:import:") for action in actions[:2]
    ]
    assert [json.loads(payload) for payload in imported_actions] == [
        [1, paths[0]],
        [2, paths[1]],
    ]
    assert actions[2] == "@region:remove:2"
    assert editor.region_count == 3
    assert editor.selected_index == 2
    destroy_qt_object(editor)


def test_materialization_publishes_authoritative_initial_regions_to_editor() -> None:
    """Initial blank materialization should replace an editor's empty graph value."""

    ensure_qt_application()
    panel = QWidget()
    editor = RegionalMaskBatchEditor(
        cube_alias="Prompt by Region",
        node_name="load_mask_batch",
        values=[],
        parent=panel,
    )
    workflow = WorkflowState()
    image_id = uuid4()
    first_mask_id = uuid4()
    second_mask_id = uuid4()
    collection = workflow.canvas.ensure_regional_mask_collection(
        ("Prompt by Region", "load_mask_batch")
    )
    collection.add_region(
        image_id,
        mask_id=first_mask_id,
        asset_ref=ProjectMaskAssetRef("first.png"),
    )
    second = collection.add_region(
        image_id,
        mask_id=second_mask_id,
        asset_ref=ProjectMaskAssetRef("second.png"),
    )
    collection.select(second.region_id)
    activated: list[object] = []

    def activate_mask(_workflow: WorkflowState, mask_id: UUID) -> bool:
        """Record the materialization-selected mask layer."""

        activated.append(mask_id)
        return True

    collection_presenter = RegionalMaskCollectionPresenter(
        input_document=SimpleNamespace(
            set_mask_properties=lambda *_args, **_kwargs: None
        ),
        active_workflow=lambda: workflow,
        active_panel=lambda: panel,
        mask_color=lambda index, total: QColor(index, total, 0),
    )
    presenter = InputMaterializationPresenter(
        input_document=SimpleNamespace(
            set_mask_properties=lambda *_args, **_kwargs: None
        ),
        active_workflow=lambda: workflow,
        mask_color=lambda index, total: QColor(index, total, 0),
        refresh_scalar_mask=lambda *_args: None,
        refresh_ordered_mask=collection_presenter.refresh,
        activate_mask=activate_mask,
    )

    presenter.apply(
        SimpleNamespace(
            mask_results=(
                SimpleNamespace(
                    association_key=("Prompt by Region", "load_mask_batch"),
                    mask_id=first_mask_id,
                ),
                SimpleNamespace(
                    association_key=("Prompt by Region", "load_mask_batch"),
                    mask_id=second_mask_id,
                ),
            ),
            first_mask_id=first_mask_id,
        )
    )

    assert editor.region_count == 2
    assert editor.selected_index == 1
    assert activated == [first_mask_id]
    destroy_qt_object(panel)


def test_restored_panel_mount_projects_existing_collection_before_interaction() -> None:
    """A restored editor must render durable masks without an Add-button refresh."""

    ensure_qt_application()
    workflow = WorkflowState()
    image_id = uuid4()
    collection = workflow.canvas.ensure_regional_mask_collection(
        ("Region", "load_mask_batch")
    )
    collection.add_region(image_id, asset_ref=ProjectMaskAssetRef("first.png"))
    selected = collection.add_region(
        image_id,
        asset_ref=ProjectMaskAssetRef("second.png"),
    )
    collection.select(selected.region_id)
    panel = QWidget()
    editor = RegionalMaskBatchEditor(
        cube_alias="Region",
        node_name="load_mask_batch",
        values=[],
        parent=panel,
    )
    cast(Any, panel).mainwindow = SimpleNamespace(
        editor_panels={"workflow": panel},
        workflow_session_service=SimpleNamespace(workflows={"workflow": workflow}),
    )

    projected = project_regional_panel_widget(
        editor,
        panel,
        cube_alias="Region",
        node_name="load_mask_batch",
    )

    remove_button = next(
        button
        for button in editor.findChildren(QPushButton)
        if button.property("region_remove_button") is True
    )
    assert projected is True
    assert editor.region_count == 2
    assert editor.selected_index == 1
    assert remove_button.isEnabled()
    destroy_qt_object(panel)


def test_node_and_canvas_selection_share_authoritative_region_state(
    tmp_path: Path,
) -> None:
    """Either linked surface should update durable region and expanded node row."""

    ensure_qt_application()
    workflow = WorkflowState()
    image_id = uuid4()
    first_mask_id = uuid4()
    second_mask_id = uuid4()
    workflow.canvas.bind_image("Region:@synthetic/surface", image_id)
    workflow.canvas.input_image_uuid = image_id
    collection = workflow.canvas.ensure_regional_mask_collection(
        ("Region", "load_mask_batch")
    )
    first = collection.add_region(image_id, mask_id=first_mask_id)
    second = collection.add_region(image_id, mask_id=second_mask_id)
    collection.select(first.region_id)
    panel = QWidget()
    editor = RegionalMaskBatchEditor(
        cube_alias="Region",
        node_name="load_mask_batch",
        values=["first.png", "second.png"],
        parent=panel,
    )
    presenter = RegionalMaskCollectionPresenter(
        input_document=SimpleNamespace(
            set_mask_properties=lambda *_args, **_kwargs: None
        ),
        active_workflow=lambda: workflow,
        active_panel=lambda: panel,
        mask_color=lambda index, total: QColor(index, total, 0),
    )

    def activate_mask(
        _workflow_id: str,
        active_workflow: WorkflowState,
        mask_id: UUID,
    ) -> bool:
        """Record the durable active-mask selection."""

        active_workflow.canvas.active_input_mask_uuid = mask_id
        return True

    controller = RegionalMaskActionController(
        active_workflow=lambda: workflow,
        active_workflow_id=lambda: "workflow",
        workflow_name=lambda _workflow_id: "Recipe",
        projects_dir=lambda: tmp_path,
        workflow_service=cast(WorkflowInputCanvasService, SimpleNamespace()),
        state_service=cast(
            InputCanvasStateService,
            SimpleNamespace(set_active_workflow_mask=activate_mask),
        ),
        presenter=presenter,
        accept_canvas_selection=lambda: True,
    )

    outcome = controller.handle("Region", "load_mask_batch", "@region:select:1")
    assert outcome.handled is True
    assert outcome.activate_canvas is True
    assert collection.selected_region_id == second.region_id
    assert workflow.canvas.active_input_mask_uuid == second_mask_id
    assert editor.selected_index == 1

    collection.select(first.region_id)
    workflow.canvas.active_input_mask_uuid = first_mask_id
    presenter.refresh(("Region", "load_mask_batch"))
    assert controller.select_canvas_mask(second_mask_id) is True
    assert collection.selected_region_id == second.region_id
    assert editor.selected_index == 1
    destroy_qt_object(panel)


def test_canvas_mask_selection_is_ignored_during_restore(tmp_path: Path) -> None:
    """Programmatic document restoration must not become user navigation intent."""

    workflow = WorkflowState()
    image_id = uuid4()
    mask_id = uuid4()
    workflow.canvas.bind_image("Region:image", image_id)
    workflow.canvas.bind_mask(("Region", "mask"), mask_id, image_id)
    activation_calls: list[UUID] = []

    def activate_mask(_workflow_id: str, _workflow: WorkflowState, value: UUID) -> bool:
        """Record an unexpected mask activation during restore."""

        activation_calls.append(value)
        return True

    controller = RegionalMaskActionController(
        active_workflow=lambda: workflow,
        active_workflow_id=lambda: "workflow",
        workflow_name=lambda _workflow_id: "Recipe",
        projects_dir=lambda: tmp_path,
        workflow_service=cast(WorkflowInputCanvasService, SimpleNamespace()),
        state_service=cast(
            InputCanvasStateService,
            SimpleNamespace(set_active_workflow_mask=activate_mask),
        ),
        presenter=cast(RegionalMaskCollectionPresenter, SimpleNamespace()),
        accept_canvas_selection=lambda: False,
    )

    assert controller.select_canvas_mask(mask_id) is False
    assert activation_calls == []

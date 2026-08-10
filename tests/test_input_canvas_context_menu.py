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

"""Verify the Input canvas context menu owns canvas commands only."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QWidget
from cutecanvas import MaskInfo
from sugarsubstitute_shared.localization import ApplicationMessage, ApplicationText

from substitute.presentation.canvas.input.input_canvas_context_menu import (
    InputCanvasContextMenuController,
)
from substitute.presentation.widgets.menu_model import MenuItem, MenuSeparator


def _app() -> QApplication:
    """Return the shared Qt application for context-menu owner tests."""

    instance = QCoreApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


def _source_text(value: ApplicationText) -> str:
    """Return canonical source copy from one localized menu label."""

    return value.source_text if isinstance(value, ApplicationMessage) else value


def _mask(mask_id: UUID) -> MaskInfo:
    """Return the minimum typed mask projection needed by menu policy."""

    return cast(MaskInfo, SimpleNamespace(mask_id=mask_id))


def test_context_menu_contains_coverage_and_docking_commands_without_tools() -> None:
    """Keep tool selection in the toolbar and canvas commands in this menu."""

    _app()
    parent = QWidget()
    mask_id = uuid4()
    coverage_requests: list[UUID] = []
    dock_requests: list[bool] = []
    controller = InputCanvasContextMenuController(
        canvas=parent,
        active_mask_id_provider=lambda: mask_id,
        mask_layers_provider=lambda: (_mask(mask_id),),
        coverage_edit_requested=coverage_requests.append,
        detached_provider=lambda: False,
        dock_requested=lambda: dock_requests.append(True),
    )

    model = controller.create_model()
    items = [entry for entry in model.entries if isinstance(entry, MenuItem)]

    assert [item.action_id for item in items] == [
        "input_canvas.edit_layer_coverage",
        "input_canvas.dock_action",
    ]
    assert [_source_text(item.label) for item in items] == [
        "Edit layer coverage",
        "Undock canvas",
    ]
    assert all(not item.action_id.startswith("canvas.tool.") for item in items)
    assert sum(isinstance(entry, MenuSeparator) for entry in model.entries) == 1
    assert items[0].enabled
    assert items[0].callback is not None
    assert items[1].callback is not None

    items[0].callback()
    items[1].callback()

    assert coverage_requests == [mask_id]
    assert dock_requests == [True]
    parent.deleteLater()


def test_context_menu_resolves_the_latest_active_mask_for_every_opening() -> None:
    """Never retain a mask identity captured by an earlier menu opening."""

    _app()
    parent = QWidget()
    first_mask_id = uuid4()
    second_mask_id = uuid4()
    active_mask_id = first_mask_id
    layers = (_mask(first_mask_id), _mask(second_mask_id))
    coverage_requests: list[UUID] = []
    controller = InputCanvasContextMenuController(
        canvas=parent,
        active_mask_id_provider=lambda: active_mask_id,
        mask_layers_provider=lambda: layers,
        coverage_edit_requested=coverage_requests.append,
        detached_provider=lambda: False,
        dock_requested=lambda: None,
    )

    first_item = cast(MenuItem, controller.create_model().entries[0])
    assert first_item.callback is not None
    first_item.callback()

    active_mask_id = second_mask_id
    second_item = cast(MenuItem, controller.create_model().entries[0])
    assert second_item.callback is not None
    second_item.callback()

    assert coverage_requests == [first_mask_id, second_mask_id]
    parent.deleteLater()


def test_context_menu_disables_coverage_without_an_editable_active_mask() -> None:
    """Keep coverage discoverable without dispatching absent or stale targets."""

    _app()
    parent = QWidget()
    current_mask_id: UUID | None = None
    existing_mask_id = uuid4()
    controller = InputCanvasContextMenuController(
        canvas=parent,
        active_mask_id_provider=lambda: current_mask_id,
        mask_layers_provider=lambda: (_mask(existing_mask_id),),
        coverage_edit_requested=lambda _mask_id: None,
        detached_provider=lambda: False,
        dock_requested=lambda: None,
    )

    missing_item = cast(MenuItem, controller.create_model().entries[0])
    assert not missing_item.enabled
    assert missing_item.callback is None

    current_mask_id = uuid4()
    stale_item = cast(MenuItem, controller.create_model().entries[0])
    assert not stale_item.enabled
    assert stale_item.callback is None
    parent.deleteLater()


def test_context_menu_exposes_coverage_for_a_synthetic_canvas_mask() -> None:
    """Base coverage availability on mask ownership, not raster provenance."""

    _app()
    parent = QWidget()
    synthetic_mask_id = uuid4()
    controller = InputCanvasContextMenuController(
        canvas=parent,
        active_mask_id_provider=lambda: synthetic_mask_id,
        mask_layers_provider=lambda: (_mask(synthetic_mask_id),),
        coverage_edit_requested=lambda _mask_id: None,
        detached_provider=lambda: True,
        dock_requested=lambda: None,
    )

    items = [
        entry
        for entry in controller.create_model().entries
        if isinstance(entry, MenuItem)
    ]

    assert items[0].enabled
    assert _source_text(items[1].label) == "Redock canvas"
    parent.deleteLater()

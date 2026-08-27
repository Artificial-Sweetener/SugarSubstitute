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

"""Verify model picker metadata actions contracts."""

from __future__ import annotations


import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget

from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextMenuTarget,
    ModelMetadataMenuAction,
)
from substitute.presentation.widgets.model_picker import (
    ModelPickerField,
)
from substitute.presentation.widgets.model_picker.model_picker_field import (
    _ModelPickerComboSurface,
)
from tests.support.qt.lifecycle import destroy_qt_object


from tests.presentation.widgets.model_picker.catalog_fixtures import (
    _FakeModelCatalog,
    _MetadataActionHandler,
    _item,
)
from tests.presentation.widgets.model_picker.support import (
    _right_click_closed_picker_surface,
    ensure_qapp,
)


def test_model_picker_field_right_click_menu_opens_selected_civitai_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Right-clicking a closed picker field should expose selected model CivitAI URL."""

    app = ensure_qapp()
    opened_urls: list[str] = []

    def open_url(url: str) -> bool:
        """Record URL opens without launching a browser."""

        opened_urls.append(url)
        return True

    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (
                _item(
                    "models/alpha.safetensors",
                    "Alpha Model",
                    "v1",
                    model_page_url="https://civitai.com/models/1?modelVersionId=2",
                ),
            )
        ),
        current_value="models/alpha.safetensors",
        open_url=open_url,
    )
    field.resize(260, 34)
    field.show()
    app.processEvents()
    surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
    assert surface is not None
    shown_targets: list[ModelMetadataContextMenuTarget] = []

    def show_menu(target: ModelMetadataContextMenuTarget, _pos: QPoint) -> bool:
        """Record and invoke the selected model's page action."""

        shown_targets.append(target)
        actions = tuple(
            item
            for item in field._metadata_context_menu.menu_items_for_target(target)
            if isinstance(item, ModelMetadataMenuAction)
        )
        actions[0].callback()
        return True

    monkeypatch.setattr(field._metadata_context_menu, "show_menu", show_menu)

    _right_click_closed_picker_surface(surface)
    app.processEvents()

    assert len(shown_targets) == 1
    assert shown_targets[0].backend_value == "models/alpha.safetensors"
    assert opened_urls == ["https://civitai.com/models/1?modelVersionId=2"]
    destroy_qt_object(host)


def test_model_picker_field_right_click_menu_omits_missing_civitai_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Right-clicking a local-only selection should not show an empty context menu."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (_item("models/alpha.safetensors", "Alpha Model", "v1"),)
        ),
        current_value="models/alpha.safetensors",
    )
    field.resize(260, 34)
    field.show()
    app.processEvents()
    surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
    assert surface is not None
    shown_targets: list[ModelMetadataContextMenuTarget] = []

    def show_menu(target: ModelMetadataContextMenuTarget, _pos: QPoint) -> bool:
        """Record the request while preserving empty-menu suppression."""

        shown_targets.append(target)
        return bool(field._metadata_context_menu.menu_items_for_target(target))

    monkeypatch.setattr(
        field._metadata_context_menu,
        "show_menu",
        show_menu,
    )

    _right_click_closed_picker_surface(surface)
    app.processEvents()

    assert len(shown_targets) == 1
    assert field._metadata_context_menu.menu_items_for_target(shown_targets[0]) == ()
    destroy_qt_object(host)


def test_model_picker_field_right_click_refresh_targets_selected_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Right-clicking a selected model should expose manual metadata refresh."""

    app = ensure_qapp()
    handler = _MetadataActionHandler()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (_item("models/alpha.safetensors", "Alpha Model", "v1"),)
        ),
        current_value="models/alpha.safetensors",
        metadata_action_handler=handler,
    )
    field.resize(260, 34)
    field.show()
    app.processEvents()
    surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
    assert surface is not None
    shown_targets: list[ModelMetadataContextMenuTarget] = []

    def show_menu(target: ModelMetadataContextMenuTarget, _pos: QPoint) -> bool:
        """Record and invoke the selected model's refresh action."""

        shown_targets.append(target)
        actions = tuple(
            item
            for item in field._metadata_context_menu.menu_items_for_target(target)
            if isinstance(item, ModelMetadataMenuAction)
        )
        refresh_action = next(
            action for action in actions if action.label == "Refresh CivitAI metadata"
        )
        refresh_action.callback()
        return True

    monkeypatch.setattr(field._metadata_context_menu, "show_menu", show_menu)

    _right_click_closed_picker_surface(surface)
    app.processEvents()

    assert len(shown_targets) == 1
    assert len(handler.refresh_targets) == 1
    refresh_target = handler.refresh_targets[0]
    assert getattr(refresh_target, "model_kind") == "checkpoints"
    assert getattr(refresh_target, "backend_value") == "models/alpha.safetensors"
    destroy_qt_object(host)

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

"""Verify one installed-model update appears on both picker surfaces."""

from __future__ import annotations

from dataclasses import replace

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.presentation.model_updates.picker_bridge import ModelUpdatePickerBridge
from substitute.presentation.widgets.media_wall.media_wall_badge import (
    media_wall_badge_rect,
)
from substitute.presentation.widgets.model_picker import ModelPickerField
from substitute.presentation.widgets.model_picker.model_picker_update_button import (
    ModelPickerUpdateButton,
)
from tests.presentation.model_updates.support import update_proposal
from tests.presentation.widgets.model_picker.catalog_fixtures import (
    _FakeModelCatalog,
    _item,
)
from tests.presentation.widgets.model_picker.support import ensure_qapp
from tests.presentation.widgets.media_wall.support import mouse_press_event
from tests.support.qt.lifecycle import destroy_qt_object


def test_selected_banner_and_matching_tile_share_update_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the matching file gets an icon, and clicking it keeps selection."""

    application = ensure_qapp()
    proposal = update_proposal("a" * 64)
    updates = ModelUpdatePickerBridge()
    host = QWidget()
    host.resize(650, 500)
    host.show()
    current = replace(
        _item("artist/current.safetensors", "Artist", "v1"),
        sha256=proposal.current.sha256,
    )
    other = replace(
        _item("artist/other.safetensors", "Other", "v1"),
        sha256="c" * 64,
    )
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog((current, other)),
        current_value=current.backend_value,
        model_updates=updates,
    )
    field.resize(420, 34)
    field.show()
    application.processEvents()
    button = field.findChild(ModelPickerUpdateButton)
    assert button is not None
    assert button.isHidden()
    requested: list[str] = []
    updates.familyRequested.connect(requested.append)

    updates.replace((proposal,))
    application.processEvents()
    assert button.isVisible()
    assert button.geometry().right() < field._surface.dropButton.geometry().left()
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    assert requested == [proposal.current.sha256]
    assert field.currentText() == current.backend_value
    banner_menu_requests: list[str] = []

    def capture_banner_menu(
        *,
        parent: QWidget,
        updates: ModelUpdatePickerBridge,
        sha256: str | None,
        global_pos: QPoint,
    ) -> bool:
        """Observe the banner icon's exact menu target."""

        assert parent is button
        assert updates is not None
        assert global_pos is not None
        if sha256 is not None:
            banner_menu_requests.append(sha256)
        return True

    monkeypatch.setattr(
        "substitute.presentation.widgets.model_picker.model_picker_update_button.show_update_icon_menu",
        capture_banner_menu,
    )
    button.contextMenuEvent(
        QContextMenuEvent(
            QContextMenuEvent.Reason.Mouse,
            button.rect().center(),
            button.mapToGlobal(button.rect().center()),
        )
    )
    assert banner_menu_requests == [proposal.current.sha256]

    field.open_picker()
    application.processEvents()
    assert field._popup is not None
    tiles = field._popup._view.items()
    assert tiles[0].corner_badge_icon is not None
    assert tiles[1].corner_badge_icon is None
    view = field._popup._view
    point = media_wall_badge_rect(view._placed_items[0].rect).center()
    view.mousePressEvent(
        mouse_press_event(view, point, button=Qt.MouseButton.LeftButton)
    )
    assert requested == [proposal.current.sha256, proposal.current.sha256]
    icon_menu_requests: list[str] = []

    def capture_icon_menu(
        *,
        parent: QWidget,
        updates: ModelUpdatePickerBridge,
        sha256: str | None,
        global_pos: QPoint,
    ) -> bool:
        """Observe the icon-only menu route without opening a blocking popup."""

        assert parent is view
        assert updates is not None
        assert global_pos is not None
        if sha256 is not None:
            icon_menu_requests.append(sha256)
        return True

    monkeypatch.setattr(
        "substitute.presentation.widgets.model_picker.model_picker_wall.show_update_icon_menu",
        capture_icon_menu,
    )
    view.mousePressEvent(
        mouse_press_event(view, point, button=Qt.MouseButton.RightButton)
    )
    assert icon_menu_requests == [proposal.current.sha256]
    field._popup.hide()
    updates.replace(())
    application.processEvents()
    assert button.isHidden()
    destroy_qt_object(host)

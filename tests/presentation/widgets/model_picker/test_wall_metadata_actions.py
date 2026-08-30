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

"""Verify model picker wall metadata actions contracts."""

from __future__ import annotations


from substitute.presentation.widgets.model_picker import (
    ModelPickerPopup,
    ModelPickerWallView,
)
from tests.support.qt.lifecycle import destroy_qt_object


from tests.presentation.widgets.model_picker.popup_fixtures import (
    _MetadataActionHandler,
    ensure_qapp,
    _actions,
    _item,
)


def test_model_picker_wall_civitai_action_opens_item_url() -> None:
    """The shared metadata menu action should open model CivitAI URLs."""

    ensure_qapp()
    opened_urls: list[str] = []

    def open_url(url: str) -> bool:
        """Record opened URLs without launching a browser."""

        opened_urls.append(url)
        return True

    wall = ModelPickerWallView(open_url=open_url)
    target = wall._metadata_context_menu_target(
        _item(
            "Model",
            "model",
            model_page_url="https://civitai.com/models/1?modelVersionId=2",
        )
    )

    assert target is not None
    actions = _actions(wall._metadata_context_menu.menu_items_for_target(target))
    assert len(actions) == 1
    action = actions[0]
    assert action is not None
    action.callback()
    assert opened_urls == ["https://civitai.com/models/1?modelVersionId=2"]
    local_target = wall._metadata_context_menu_target(_item("Local", "local"))
    assert local_target is not None
    assert wall._metadata_context_menu.menu_items_for_target(local_target) == ()
    destroy_qt_object(wall)


def test_model_picker_wall_refresh_action_targets_item_metadata() -> None:
    """Picker grid refresh actions should target the item's model kind and value."""

    ensure_qapp()
    handler = _MetadataActionHandler()
    wall = ModelPickerWallView(metadata_action_handler=handler)
    target = wall._metadata_context_menu_target(
        _item("Model", "model", model_kind="checkpoints")
    )

    assert target is not None
    actions = _actions(wall._metadata_context_menu.menu_items_for_target(target))

    assert [action.label for action in actions] == [
        "Refresh CivitAI metadata",
        "Set thumbnail from canvas",
    ]
    actions[0].callback()
    assert len(handler.refresh_targets) == 1
    refresh_target = handler.refresh_targets[0]
    assert getattr(refresh_target, "model_kind") == "checkpoints"
    assert getattr(refresh_target, "backend_value") == "Folder/Model.safetensors"
    destroy_qt_object(wall)


def test_model_picker_wall_items_carry_relative_path_tooltips() -> None:
    """Picker wall items should expose model relative paths as tile tooltips."""

    ensure_qapp()
    popup = ModelPickerPopup(
        (
            _item(
                "Model",
                "model",
            ),
        )
    )

    assert popup._view.items()[0].tooltip == "Folder/Model.safetensors"
    destroy_qt_object(popup)

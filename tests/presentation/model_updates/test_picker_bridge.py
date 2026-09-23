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

"""Verify one exact update state feeds every picker entry point."""

from __future__ import annotations

from substitute.presentation.model_updates.picker_bridge import ModelUpdatePickerBridge
from substitute.presentation.model_updates.icon_menu import update_icon_menu
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextMenuActionBuilder,
    ModelMetadataContextMenuTarget,
    ModelMetadataMenuAction,
)
from sugarsubstitute_shared.localization import render_source_application_text
from tests.presentation.model_updates.support import update_proposal
from tests.presentation.widgets.model_picker.support import ensure_qapp
from PySide6.QtWidgets import QWidget


def test_bridge_exposes_only_checked_installed_identity() -> None:
    """Unrelated tiles cannot inherit a nearby model's update badge."""

    bridge = ModelUpdatePickerBridge()
    requested: list[str] = []
    bridge.familyRequested.connect(requested.append)
    proposal = update_proposal("a" * 64)

    assert not bridge.request_family("a" * 64)
    bridge.replace((proposal,))
    assert bridge.proposal_for_sha("A" * 64) == proposal
    assert bridge.proposal_for_sha("c" * 64) is None
    assert not bridge.request_family("c" * 64)
    assert bridge.request_family("a" * 64)
    assert requested == ["a" * 64]
    bridge.replace(())
    assert bridge.proposal_for_sha("a" * 64) is None


def test_context_menu_opens_only_the_target_models_family() -> None:
    """Banner and tile menus open or dismiss only the exact checked update."""

    bridge = ModelUpdatePickerBridge()
    bridge.replace((update_proposal("a" * 64),))
    requested: list[str] = []
    bridge.familyRequested.connect(requested.append)
    builder = ModelMetadataContextMenuActionBuilder(model_updates=bridge)
    target = ModelMetadataContextMenuTarget(title="Installed", sha256="a" * 64)
    unrelated = ModelMetadataContextMenuTarget(title="Other", sha256="b" * 64)

    actions = builder.menu_items_for_target(target)
    assert len(actions) == 1
    action = actions[0]
    assert isinstance(action, ModelMetadataMenuAction)
    assert render_source_application_text(action.label) == "View model updates"
    action.callback()
    assert requested == ["a" * 64]
    assert builder.menu_items_for_target(unrelated) == ()


def test_update_icon_menu_has_only_dismiss_and_page_opt_out() -> None:
    """Right-clicking the update icon must not show general model actions."""

    ensure_qapp()
    parent = QWidget()
    bridge = ModelUpdatePickerBridge()
    bridge.replace((update_proposal("a" * 64),))
    dismissed: list[str] = []
    disabled: list[str] = []
    bridge.dismissRequested.connect(dismissed.append)
    bridge.pageOptOutRequested.connect(disabled.append)

    menu = update_icon_menu(parent=parent, updates=bridge, sha256="a" * 64)
    assert menu is not None
    actions = menu.actions()
    assert [action.text() for action in actions] == [
        "Dismiss",
        "Don't check for updates for Model",
    ]
    actions[0].trigger()
    actions[1].trigger()
    assert dismissed == ["a" * 64]
    assert disabled == ["a" * 64]
    assert update_icon_menu(parent=parent, updates=bridge, sha256="b" * 64) is None
    parent.deleteLater()

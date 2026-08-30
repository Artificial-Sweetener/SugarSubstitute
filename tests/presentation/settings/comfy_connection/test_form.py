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

"""Test Comfy connection form layout and editable draft state."""

from __future__ import annotations

from pathlib import Path


from substitute.domain.onboarding import ComfyTargetMode
from substitute.presentation.settings.settings_card import (
    InteractiveSettingsCard,
    SettingsCard,
)
from substitute.presentation.settings.settings_card_group import SettingsCardGroup
from tests.presentation.settings.comfy_connection.support import (
    application,
    build_page,
)


def test_comfy_connection_page_builds_expected_form_cards(tmp_path: Path) -> None:
    """The page should expose grouped form cards without interactive row behavior."""

    application()
    page = build_page(tmp_path)

    assert page.mode_options() == ("Managed local", "Existing local", "Remote")
    row_titles = tuple(
        row.title_label.text()
        for row in page.findChildren(SettingsCard)
        if not row.isHidden()
    )
    group_titles = tuple(
        group.title_label.text() for group in page.findChildren(SettingsCardGroup)
    )
    assert row_titles == (
        "ComfyUI source",
        "ComfyUI folder",
        "Model folder",
        "Local endpoint",
        "Setup wizard",
        "Connection check",
    )
    assert group_titles == (
        "ComfyUI source",
        "Managed local setup",
        "Connection check",
    )
    assert page.findChildren(InteractiveSettingsCard) == []
    assert page.discard_button.isEnabled() is False
    assert page.save_button.isEnabled() is False
    assert page.setup_action_row.isHidden() is False
    assert page.port_spinbox.property("symbolVisible") is False
    assert page.port_spinbox.minimumWidth() >= page.port_spinbox.sizeHint().width()
    assert page.port_spinbox.minimumWidth() < page.host_edit.minimumWidth()
    assert page.port_spinbox.minimumHeight() == page.host_edit.minimumHeight()
    assert page.port_spinbox.maximumHeight() == page.host_edit.maximumHeight()
    page.close()


def test_comfy_connection_page_does_not_clip_grouped_inputs(tmp_path: Path) -> None:
    """Grouped connection inputs should keep their full Fluent control height."""

    app = application()
    page = build_page(tmp_path)
    page.resize(914, 720)
    page.show()
    app.processEvents()

    for control in (
        page.host_edit,
        page.port_spinbox,
        page.managed_folder_edit,
        page.model_folder_edit,
    ):
        group = control.parentWidget()
        assert group is not None
        assert group.height() >= control.minimumHeight()
        assert control.geometry().bottom() <= group.contentsRect().bottom()

    page.set_selected_mode(ComfyTargetMode.ATTACHED_LOCAL)
    app.processEvents()
    group = page.existing_folder_edit.parentWidget()
    assert group is not None
    assert group.height() >= page.existing_folder_edit.minimumHeight()
    assert (
        page.existing_folder_edit.geometry().bottom() <= group.contentsRect().bottom()
    )

    page.close()


def test_comfy_connection_page_switches_mode_specific_folder_rows(
    tmp_path: Path,
) -> None:
    """Target mode changes should expose only the relevant folder row."""

    application()
    page = build_page(tmp_path)

    assert page.is_managed_folder_row_visible() is True
    assert page.is_model_folder_row_visible() is True
    assert page.is_existing_folder_row_visible() is False

    page.set_selected_mode(ComfyTargetMode.ATTACHED_LOCAL)
    assert page.is_managed_folder_row_visible() is False
    assert page.is_model_folder_row_visible() is True
    assert page.is_existing_folder_row_visible() is True
    assert page.setup_action_row.isHidden() is False
    assert page.configuration_group.title_label.text() == "Existing local setup"
    assert page.endpoint_row.title_label.text() == "Local endpoint"

    page.set_selected_mode(ComfyTargetMode.REMOTE)
    assert page.is_managed_folder_row_visible() is False
    assert page.is_model_folder_row_visible() is True
    assert page.model_folder_browse_button.isHidden() is True
    assert page.is_existing_folder_row_visible() is False
    assert page.setup_action_row.isHidden() is True
    assert page.configuration_group.title_label.text() == "Remote server"
    assert page.endpoint_row.title_label.text() == "Server endpoint"
    page.close()


def test_comfy_connection_page_marks_dirty_after_edit(tmp_path: Path) -> None:
    """Editing form values should enable save without adding row details."""

    application()
    page = build_page(tmp_path)

    assert page.save_button.isEnabled() is False
    page.host_edit.setText("127.0.0.2")

    assert page.save_button.isEnabled() is True
    assert page.discard_button.isEnabled() is True
    page.close()


def test_comfy_connection_page_discard_restores_loaded_draft(
    tmp_path: Path,
) -> None:
    """Discarding changes should restore loaded values and clean action state."""

    application()
    page = build_page(tmp_path)
    page.set_selected_mode(ComfyTargetMode.REMOTE)
    page.host_edit.setText("remote-box")
    page.port_spinbox.setValue(8190)

    assert page.save_button.isEnabled() is True
    assert page.discard_button.isEnabled() is True

    page.discard_changes()

    assert page.selected_mode() is ComfyTargetMode.MANAGED_LOCAL
    assert page.host_edit.text() == "127.0.0.1"
    assert page.port_spinbox.value() == 8188
    assert page.save_button.isEnabled() is False
    assert page.discard_button.isEnabled() is False
    page.close()

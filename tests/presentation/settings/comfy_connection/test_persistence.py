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

"""Test Comfy connection draft persistence and restart behavior."""

from __future__ import annotations

from pathlib import Path


from substitute.domain.onboarding import ComfyTargetMode
from tests.presentation.settings.comfy_connection.support import (
    FakeComfyConnectionService,
    build_page,
    managed_target,
)


def test_comfy_connection_page_save_submits_current_draft(tmp_path: Path) -> None:
    """Saving should pass the edited draft to the service and reload clean state."""

    service = FakeComfyConnectionService(managed_target(tmp_path))
    page = build_page(tmp_path, service=service)
    page.set_selected_mode(ComfyTargetMode.REMOTE)
    page.host_edit.setText("remote-box")
    page.port_spinbox.setValue(8190)

    page.save_changes()

    assert len(service.saved_drafts) == 1
    saved = service.saved_drafts[0]
    assert saved.mode is ComfyTargetMode.REMOTE
    assert saved.host == "remote-box"
    assert saved.port == 8190
    assert page.save_button.isEnabled() is False
    page.close()


def test_comfy_connection_page_save_submits_explicit_model_root(
    tmp_path: Path,
) -> None:
    """Saving should include explicit managed model root edits in the draft."""

    service = FakeComfyConnectionService(managed_target(tmp_path))
    page = build_page(tmp_path, service=service)
    model_root = tmp_path / "Models"

    page.model_folder_edit.setText(str(model_root))
    page.save_changes()

    assert len(service.saved_drafts) == 1
    saved = service.saved_drafts[0]
    assert saved.managed_model_root == str(model_root)
    assert saved.managed_model_root_uses_default is False
    page.close()


def test_comfy_connection_page_default_model_root_follows_managed_folder(
    tmp_path: Path,
) -> None:
    """Default model root should track managed workspace folder edits."""

    service = FakeComfyConnectionService(managed_target(tmp_path))
    page = build_page(tmp_path, service=service)
    new_workspace = tmp_path / "OtherComfy"

    page.managed_folder_edit.setText(str(new_workspace))
    page.save_changes()

    assert len(service.saved_drafts) == 1
    saved = service.saved_drafts[0]
    assert saved.managed_model_root == str(new_workspace / "models")
    assert saved.managed_model_root_uses_default is True
    page.close()


def test_comfy_connection_page_restart_prompt_uses_shared_callback(
    tmp_path: Path,
) -> None:
    """A restart-producing save should open the shared restart requirements UI."""

    service = FakeComfyConnectionService(managed_target(tmp_path))
    calls: list[str] = []
    page = build_page(
        tmp_path,
        service=service,
        show_restart_requirements=lambda: calls.append("show"),
    )

    page.host_edit.setText("127.0.0.2")
    page.save_changes()

    assert len(service.saved_drafts) == 1
    assert calls == ["show"]
    page.close()


def test_comfy_connection_page_failed_save_keeps_draft_editable(
    tmp_path: Path,
) -> None:
    """A failed save should leave the draft editable without row detail text."""

    service = FakeComfyConnectionService(managed_target(tmp_path))
    service.save_succeeds = False
    page = build_page(tmp_path, service=service)
    page.host_edit.setText("127.0.0.2")

    page.save_changes()

    assert len(service.saved_drafts) == 1
    assert page.save_button.isEnabled() is True
    page.close()

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

"""Test Comfy connection endpoint checks and feedback."""

from __future__ import annotations

from pathlib import Path


from tests.presentation.settings.comfy_connection.support import (
    FakeComfyConnectionService,
    build_page,
    managed_target,
)


def test_comfy_connection_page_tests_endpoint_without_saving(tmp_path: Path) -> None:
    """Test connection should call the service test path only."""

    service = FakeComfyConnectionService(managed_target(tmp_path))
    page = build_page(tmp_path, service=service)
    page.host_edit.setText("127.0.0.9")
    page.port_spinbox.setValue(8199)

    page.test_connection()

    assert service.test_calls == [("127.0.0.9", 8199)]
    assert service.saved_drafts == []
    page.close()


def test_comfy_connection_page_renders_successful_connection_test(
    tmp_path: Path,
) -> None:
    """A successful connection test should render visible success feedback."""

    service = FakeComfyConnectionService(managed_target(tmp_path))
    page = build_page(tmp_path, service=service)

    page.test_connection()

    assert service.test_calls == [("127.0.0.1", 8188)]
    assert page.connection_feedback_bar.isHidden() is False
    assert page.connection_feedback_bar.severity() == "success"
    assert page.connection_feedback_bar.title_label.text() == (
        "Connection check succeeded"
    )
    assert "ComfyUI responded" in page.connection_check_row.description_label.text()
    page.close()


def test_comfy_connection_page_renders_failed_connection_test(
    tmp_path: Path,
) -> None:
    """A failed connection test should render visible error feedback."""

    service = FakeComfyConnectionService(managed_target(tmp_path))
    service.test_succeeds = False
    page = build_page(tmp_path, service=service)

    page.test_connection()

    assert service.test_calls == [("127.0.0.1", 8188)]
    assert page.connection_feedback_bar.isHidden() is False
    assert page.connection_feedback_bar.severity() == "error"
    assert page.connection_feedback_bar.title_label.text() == "Connection check failed"
    assert "did not respond" in page.connection_check_row.description_label.text()
    page.close()

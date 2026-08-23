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

"""Verify endpoint validation, reachability, and non-persistent probes."""

from __future__ import annotations

from pathlib import Path

from substitute.application.onboarding import ComfyConnectionSettingsDraft
from substitute.domain.onboarding import ComfyTargetMode
from tests.application.onboarding.environment.connection_settings.support import (
    build_service,
)


def test_connection_settings_rejects_invalid_endpoint(tmp_path: Path) -> None:
    """Saving should reject blank hosts and invalid ports before persistence."""

    service, repository, _checks = build_service(tmp_path)

    blank_host = service.save_draft(
        ComfyConnectionSettingsDraft(
            mode=ComfyTargetMode.REMOTE,
            host=" ",
            port=8188,
            managed_workspace_path=None,
            attached_workspace_path=None,
        )
    )
    invalid_port = service.save_draft(
        ComfyConnectionSettingsDraft(
            mode=ComfyTargetMode.REMOTE,
            host="127.0.0.1",
            port=70000,
            managed_workspace_path=None,
            attached_workspace_path=None,
        )
    )

    assert blank_host.succeeded is False
    assert blank_host.message == "Host cannot be blank."
    assert invalid_port.succeeded is False
    assert invalid_port.message == "Port must be between 1 and 65535."
    assert repository.saved is None


def test_connection_settings_blocks_unreachable_remote_save(tmp_path: Path) -> None:
    """Remote saves should reject unreachable endpoints."""

    service, repository, checks = build_service(tmp_path)
    checks.endpoint_reachable = False

    result = service.save_draft(
        ComfyConnectionSettingsDraft(
            mode=ComfyTargetMode.REMOTE,
            host="remote-box",
            port=8188,
            managed_workspace_path=None,
            attached_workspace_path=None,
        )
    )

    assert result.succeeded is False
    assert "did not respond" in result.message
    assert repository.saved is None


def test_connection_settings_tests_endpoint_without_saving(tmp_path: Path) -> None:
    """Endpoint testing should report reachability without persisting."""

    service, repository, checks = build_service(tmp_path)

    success = service.test_endpoint("127.0.0.1", 8188)
    checks.endpoint_reachable = False
    failure = service.test_endpoint("127.0.0.1", 8188)

    assert success.succeeded is True
    assert "responded" in success.message
    assert failure.succeeded is False
    assert "did not respond" in failure.message
    assert repository.saved is None

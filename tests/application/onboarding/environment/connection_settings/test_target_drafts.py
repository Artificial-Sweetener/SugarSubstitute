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

"""Verify persisted and default connection target drafts."""

from __future__ import annotations

from pathlib import Path

from sugarsubstitute_shared.localization import render_source_application_text

from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
)
from tests.application.onboarding.environment.connection_settings.support import (
    build_service,
)


def test_connection_settings_loads_persisted_target(tmp_path: Path) -> None:
    """Loading should prefer the persisted target over the default."""

    service, repository, _checks = build_service(tmp_path)
    repository.saved = ComfyTargetConfiguration(
        mode=ComfyTargetMode.REMOTE,
        endpoint=ComfyEndpoint(host="remote-box", port=8190),
        workspace_path=None,
        install_owned=False,
        launch_owned=False,
    )

    snapshot = service.load_snapshot()

    assert snapshot.persisted_exists is True
    assert snapshot.target == repository.saved
    assert "remote-box:8190" in render_source_application_text(snapshot.status_message)


def test_connection_settings_uses_default_when_target_is_missing(
    tmp_path: Path,
) -> None:
    """Loading should show default managed-local settings without saving them."""

    service, repository, _checks = build_service(tmp_path)

    snapshot = service.load_snapshot()

    assert snapshot.persisted_exists is False
    assert snapshot.target == repository.build_default()
    assert repository.saved is None

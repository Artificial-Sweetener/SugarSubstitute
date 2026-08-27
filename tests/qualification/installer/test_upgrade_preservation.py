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

"""Qualify historical upgrade preservation markers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.ci.historical_install_qualification import (
    assert_historical_user_configuration_preserved,
    seed_historical_user_configuration,
)
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError


def test_upgrade_preservation_marker_requires_exact_authoritative_state(
    tmp_path: Path,
) -> None:
    """Candidate activation must preserve user configuration from history."""

    install_root = tmp_path / "SugarSubstitute"
    workspace = install_root / "comfyui"
    model_root = install_root / "models"
    marker = seed_historical_user_configuration(
        install_root=install_root,
        historical_version="0.19.0",
        managed_workspace=workspace,
        managed_model_root=model_root,
    )
    target_path = install_root / "user" / "settings" / "comfy_target.json"
    target_path.write_text(
        json.dumps(
            {
                "mode": "managed_local",
                "workspace_path": str(workspace.resolve()),
            }
        ),
        encoding="utf-8",
    )

    assert_historical_user_configuration_preserved(
        preservation_marker=marker,
        historical_version="0.19.0",
        managed_workspace=workspace,
        managed_model_root=model_root,
    )

    marker.write_text("{}", encoding="utf-8")
    with pytest.raises(InstallerLifecycleError, match="authoritative"):
        assert_historical_user_configuration_preserved(
            preservation_marker=marker,
            historical_version="0.19.0",
            managed_workspace=workspace,
            managed_model_root=model_root,
        )

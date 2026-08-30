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

"""Verify candidate-update manifest compatibility."""

from __future__ import annotations

from pathlib import Path

from launcher.sugarsubstitute_launcher.config import (
    RELEASE_SOURCE_KIND_GITHUB,
    LauncherConfig,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from tools.ci.historical_update_qualification import set_update_manifest


def test_lifecycle_candidate_manifest_preserves_release_source_contract(
    tmp_path: Path,
) -> None:
    """The upgrade verifier should write config loadable by historical launchers."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    LauncherConfig.from_layout(layout=layout).save(layout.config_path)
    candidate_manifest_url = "https://localhost:44443/manifest.json"

    set_update_manifest(layout.root, candidate_manifest_url, channel="canary")

    updated_config = LauncherConfig.load(layout.config_path)
    assert updated_config.release_source is not None
    assert updated_config.release_source.kind == RELEASE_SOURCE_KIND_GITHUB
    assert updated_config.release_source.manifest_url == candidate_manifest_url
    assert updated_config.channel == "canary"

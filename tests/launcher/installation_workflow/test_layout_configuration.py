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

"""Verify launcher-owned installation layout and configuration contracts."""

from __future__ import annotations

import json
from pathlib import Path

from launcher.sugarsubstitute_launcher.config import (
    DEFAULT_RELEASE_MANIFEST_URL,
    LauncherConfig,
    UpdateCheckConfig,
)
from launcher.sugarsubstitute_launcher.install_layout import (
    InstallLayout,
    default_install_root,
)
from launcher.sugarsubstitute_launcher.installer import LayoutInstaller
from launcher.sugarsubstitute_launcher.platforms import (
    LauncherOperatingSystem,
    detect_launcher_target,
)


def test_install_layout_resolves_target_paths(tmp_path: Path) -> None:
    """Resolve the planned launcher-owned directory shape."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")

    assert (
        layout.executable_path == layout.root / layout.target.executable_relative_path
    )
    assert layout.config_path == layout.root / "launcher" / "config.json"
    assert layout.state_path == layout.root / "launcher" / "state.json"
    assert layout.logs_dir == layout.root / "launcher" / "logs"
    assert layout.cache_dir == layout.root / "launcher" / "cache"
    assert layout.downloads_dir == layout.root / "launcher" / "downloads"
    assert (
        layout.runtime_python
        == layout.root / "runtime" / layout.target.runtime_python_relative_path
    )
    assert (
        layout.runtime_gui_python
        == layout.root / "runtime" / layout.target.runtime_gui_python_relative_path
    )
    assert layout.app_entrypoint == layout.root / "app" / "main.py"
    assert layout.user_dir == layout.root / "user"
    assert layout.appdata_dir == layout.root / "appdata"


def test_default_install_root_uses_setup_executable_drive(tmp_path: Path) -> None:
    """Place setup-mode installations on the setup executable's drive."""

    executable_path = (
        tmp_path / "Downloads" / "SugarSubstitute-Installer-Windows-x64.exe"
    )
    target = detect_launcher_target()
    expected_root = (
        Path(f"{executable_path.drive}\\") / "SugarSubstitute"
        if target.operating_system is LauncherOperatingSystem.WINDOWS
        else default_install_root(target=target)
    )

    assert default_install_root(executable_path) == expected_root


def test_layout_installer_creates_base_directories_and_config(tmp_path: Path) -> None:
    """Prepare launcher state without creating application payload data."""

    result = LayoutInstaller().prepare(tmp_path / "SugarSubstitute")

    assert result.layout.root.is_dir()
    assert result.layout.launcher_dir.is_dir()
    assert result.layout.logs_dir.is_dir()
    assert result.layout.cache_dir.is_dir()
    assert result.layout.downloads_dir.is_dir()
    assert not (result.layout.launcher_dir / "locks").exists()
    assert result.layout.runtime_dir.is_dir()
    assert result.layout.user_dir.is_dir()
    assert result.layout.appdata_dir.is_dir()
    assert not result.layout.app_dir.exists()
    assert result.layout.config_path.is_file()
    assert LauncherConfig.load(result.layout.config_path) == result.config


def test_launcher_config_round_trips_schema_json(tmp_path: Path) -> None:
    """Persist and reload the planned configuration schema."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    config = LauncherConfig.from_layout(
        layout=layout,
        channel="stable",
        update_check=UpdateCheckConfig(enabled=False, frequency="manual"),
    )

    config.save(layout.config_path)
    loaded = LauncherConfig.load(layout.config_path)

    assert loaded == config
    raw_payload = json.loads(layout.config_path.read_text(encoding="utf-8"))
    assert raw_payload["schema_version"] == 1
    assert raw_payload["install_root"] == str(layout.root)
    assert raw_payload["app_dir"] == str(layout.app_dir)
    assert raw_payload["runtime_python"] == str(layout.runtime_python)
    assert raw_payload["update_check"] == {"enabled": False, "frequency": "manual"}
    assert raw_payload["release_source"] == {
        "kind": "github_release_manifest",
        "manifest_url": DEFAULT_RELEASE_MANIFEST_URL,
    }


def test_launcher_config_can_disable_persisted_release_source(tmp_path: Path) -> None:
    """Permit dev-only local installs to avoid a persisted production source."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    config = LauncherConfig.from_layout(layout=layout, release_source=None)

    config.save(layout.config_path)
    loaded = LauncherConfig.load(layout.config_path)

    assert loaded.release_source is None
    raw_payload = json.loads(layout.config_path.read_text(encoding="utf-8"))
    assert raw_payload["release_source"] is None

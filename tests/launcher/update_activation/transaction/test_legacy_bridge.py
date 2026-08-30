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

"""Verify migration from legacy launcher update scheduling."""

from __future__ import annotations

from pathlib import Path

from substitute.infrastructure.launcher_update.legacy_bridge import (
    LegacyLauncherUpdateBridge,
)
from sugarsubstitute_shared.launcher_update.models import LauncherInstallationRecord
from sugarsubstitute_shared.launcher_update.targets import WINDOWS_X64_BUNDLE

from .support import (
    _manifest_payload,
    _write_bundle,
    _write_installed_layout,
    _write_launcher_config,
)


def test_legacy_bridge_schedules_missing_installation_record(tmp_path: Path) -> None:
    """An updated app should automatically migrate an old installed launcher."""

    install_root = _write_installed_layout(tmp_path / "SugarSubstitute")
    runtime_python = install_root / "runtime" / ".venv" / "Scripts" / "python.exe"
    runtime_python.parent.mkdir(parents=True, exist_ok=True)
    runtime_python.write_text("python", encoding="utf-8")
    (install_root / "app" / "main.py").write_text("", encoding="utf-8")
    _write_launcher_config(install_root, runtime_python=runtime_python)
    archive = _write_bundle(tmp_path / "launcher.zip", marker="new")
    scheduled: list[dict[str, object]] = []

    def schedule(**kwargs: object) -> int:
        """Record one helper scheduling request."""

        scheduled.append(kwargs)
        return 1234

    bridge = LegacyLauncherUpdateBridge(
        target_detector=lambda: WINDOWS_X64_BUNDLE,
        manifest_loader=lambda _url: _manifest_payload(archive),
        scheduler=schedule,
    )

    assert bridge.run(install_root=install_root) is True

    assert len(scheduled) == 1
    assert scheduled[0]["runtime_python"] == runtime_python.resolve()
    assert scheduled[0]["relaunch"] is False
    assert scheduled[0]["wait_pid"] is None


def test_legacy_bridge_does_not_reschedule_current_launcher(tmp_path: Path) -> None:
    """A current installation record should end legacy bridge ownership."""

    install_root = _write_installed_layout(tmp_path / "SugarSubstitute")
    runtime_python = install_root / "runtime" / ".venv" / "Scripts" / "python.exe"
    runtime_python.parent.mkdir(parents=True, exist_ok=True)
    runtime_python.write_text("python", encoding="utf-8")
    (install_root / "app" / "main.py").write_text("", encoding="utf-8")
    _write_launcher_config(install_root, runtime_python=runtime_python)
    LauncherInstallationRecord(
        version="0.11.0",
        target_key="windows_x64",
    ).save(install_root / "launcher" / "installation.json")
    archive = _write_bundle(tmp_path / "launcher.zip", marker="new")
    scheduled: list[object] = []

    def schedule(**kwargs: object) -> int:
        """Record any unexpected helper scheduling request."""

        scheduled.append(kwargs)
        return 1234

    bridge = LegacyLauncherUpdateBridge(
        target_detector=lambda: WINDOWS_X64_BUNDLE,
        manifest_loader=lambda _url: _manifest_payload(archive),
        scheduler=schedule,
    )

    assert bridge.run(install_root=install_root) is False
    assert scheduled == []

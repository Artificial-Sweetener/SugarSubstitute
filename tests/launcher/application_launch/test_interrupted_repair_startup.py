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

"""Reach interrupted repair recovery through ordinary launcher startup."""

from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys
import pytest
from launcher.sugarsubstitute_launcher import (
    app,
    application_launch,
    splash_session,
    installed_app_handoff,
    launcher_ui_supervision,
    logging_setup,
    crash_routing,
    startup_plan,
    generation_dispatch,
)
from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64
from tests.launcher.application_launch.instance_routing_support import BrokerDouble
from tests.launcher.repair.execution_support import (
    _write_old_install,
    _prepared_request,
)


@pytest.mark.parametrize("boundary", ["config", "app"])
def test_ordinary_startup_recovers_before_assessing_installation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    """Restore quarantined startup dependencies without asking the user to initiate repair."""
    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    _write_old_install(layout)
    LauncherConfig.from_layout(layout=layout).save(layout.config_path)
    request = _prepared_request(layout)
    request.save(request.request_path)
    child = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.launcher.repair.startup_crash_process",
            str(request.request_path),
            boundary,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        check=False,
    )
    assert child.returncode == 73, child.stderr
    assert (layout.root / ".repair" / "pending.json").exists()
    broker = BrokerDouble()
    observed: list[str] = []

    def elect(candidate: InstallLayout, _arguments: object) -> BrokerDouble:
        """Reject discovery outside the exact fixture before any real election."""
        assert candidate.root == layout.root
        return broker

    def start_splash(**_kwargs: object) -> None:
        """Record the optional presentation boundary without starting any UI."""
        observed.append("splash")

    def handoff(**_kwargs: object) -> None:
        """Verify recovered production state at the process-launch boundary."""
        assert observed == ["splash", "dispatch"]
        assert layout.runtime_python.read_bytes() == b"old-python"
        assert "0.9.0" in (layout.app_dir / "substitute" / "_version.py").read_text()
        assert LauncherConfig.load(layout.config_path).install_root == layout.root
        assert not (layout.root / ".repair" / "pending.json").exists()
        observed.append("handoff")

    def dispatch(**_kwargs: object) -> None:
        """Observe completed recovery before any generation selection can run."""
        assert observed == ["splash"]
        assert not (layout.root / ".repair" / "pending.json").exists()
        assert layout.config_path.is_file()
        assert layout.app_entrypoint.is_file()
        observed.append("dispatch")

    monkeypatch.setattr(generation_dispatch, "dispatch_selected_launcher", dispatch)
    monkeypatch.setattr(sys, "executable", str(layout.executable_path))
    monkeypatch.setattr(startup_plan, "detect_launcher_target", lambda: WINDOWS_X64)
    monkeypatch.setattr(
        logging_setup, "configure_launcher_logging", lambda **_kwargs: None
    )
    monkeypatch.setattr(app, "_configure_normal_logging", lambda _plan: None)
    monkeypatch.setattr(application_launch, "elect_application", elect)
    monkeypatch.setattr(splash_session, "start_launcher_splash_session", start_splash)
    monkeypatch.setattr(
        crash_routing, "recover_pending_crash_reports", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        installed_app_handoff, "complete_installed_app_handoff", handoff
    )
    monkeypatch.setattr(
        launcher_ui_supervision,
        "supervise_launcher_window",
        lambda **_kwargs: pytest.fail(
            "Recoverable install must reach the application automatically"
        ),
    )
    assert app.main(["--locale=en", "--no-update-check"]) == 0
    assert observed == ["splash", "dispatch", "handoff"]
    assert broker.closed

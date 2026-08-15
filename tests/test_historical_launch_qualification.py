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

"""Verify process-bound splash-to-shell evidence for installed history."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from typing import cast

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from tools.ci.historical_launch_qualification import (
    assert_historical_installed_launch_contract,
    wait_for_historical_main_shell,
)
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError
from tools.ci.installer_ui_qualification import InstalledCandidateLaunch


def test_historical_installed_contract_requires_self_consistent_launch_paths(
    tmp_path: Path,
) -> None:
    """Portable history must identify the exact root its executable will resolve."""

    layout = InstallLayout.from_root(tmp_path / "installed")
    for path in (
        layout.executable_path,
        layout.app_entrypoint,
        layout.runtime_python,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("qualification", encoding="utf-8")
    layout.config_path.parent.mkdir(parents=True, exist_ok=True)
    layout.config_path.write_text(
        json.dumps(
            {
                "install_root": str(layout.root),
                "app_dir": str(layout.app_dir),
                "runtime_python": str(layout.runtime_python),
            }
        ),
        encoding="utf-8",
    )

    assert_historical_installed_launch_contract(layout.root)

    layout.config_path.write_text(
        json.dumps(
            {
                "install_root": str(tmp_path / "wrong-root"),
                "app_dir": str(layout.app_dir),
                "runtime_python": str(layout.runtime_python),
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(InstallerLifecycleError, match="does not identify"):
        assert_historical_installed_launch_contract(layout.root)


def test_historical_shell_requires_ordered_trace_and_live_handoff_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A historical install is complete only after its real app owns the shell."""

    layout = InstallLayout.from_root(tmp_path / "installed")
    trace_path = layout.appdata_dir / "diagnostics" / "logs" / "startup-trace.jsonl"
    trace_path.parent.mkdir(parents=True)
    trace_path.write_text(
        "".join(
            json.dumps({"event": event}) + "\n"
            for event in (
                "launch_splash.started",
                "launch_splash.closed",
                "main_shell.shown",
            )
        ),
        encoding="utf-8",
    )
    lock_path = layout.locks_dir / "application-launch.lock"
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text(
        json.dumps(
            {
                "handoff_consumed": True,
                "pid": 456,
                "restart_token_digest": None,
                "token_digest": "historical-app",
            }
        ),
        encoding="utf-8",
    )
    launch = _launch(pid=123, returncode=0, output_path=layout.logs_dir / "launch.log")
    monkeypatch.setattr(
        "tools.ci.historical_launch_qualification.process_is_alive",
        lambda pid: pid == 456,
    )

    main_pid = wait_for_historical_main_shell(
        install_root=layout.root,
        launch=launch,
        timeout_seconds=30.0,
    )

    assert main_pid == 456


def test_historical_shell_rejects_trace_without_live_app_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A synthetic trace cannot substitute for a live historical app process."""

    layout = InstallLayout.from_root(tmp_path / "installed")
    trace_path = layout.appdata_dir / "diagnostics" / "logs" / "startup-trace.jsonl"
    trace_path.parent.mkdir(parents=True)
    trace_path.write_text(
        "".join(
            json.dumps({"event": event}) + "\n"
            for event in (
                "launch_splash.started",
                "launch_splash.closed",
                "main_shell.shown",
            )
        ),
        encoding="utf-8",
    )
    lock_path = layout.locks_dir / "application-launch.lock"
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text(json.dumps({"pid": 456}), encoding="utf-8")
    monkeypatch.setattr(
        "tools.ci.historical_launch_qualification.process_is_alive",
        lambda _pid: False,
    )
    clock = iter((0.0, 31.0))
    monkeypatch.setattr(
        "tools.ci.historical_launch_qualification.time.monotonic",
        lambda: next(clock),
    )

    with pytest.raises(InstallerLifecycleError, match="live main-shell process"):
        wait_for_historical_main_shell(
            install_root=layout.root,
            launch=_launch(
                pid=123,
                returncode=0,
                output_path=layout.logs_dir / "launch.log",
            ),
            timeout_seconds=30.0,
        )


def test_historical_shell_surfaces_terminal_startup_failure(
    tmp_path: Path,
) -> None:
    """Historical startup failures should stop qualification without a long wait."""

    layout = InstallLayout.from_root(tmp_path / "installed")
    trace_path = layout.appdata_dir / "diagnostics" / "logs" / "startup-trace.jsonl"
    trace_path.parent.mkdir(parents=True)
    trace_path.write_text(
        json.dumps({"event": "startup.gui_task.failure"}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        InstallerLifecycleError,
        match="startup.gui_task.failure",
    ):
        wait_for_historical_main_shell(
            install_root=layout.root,
            launch=_launch(
                pid=123,
                returncode=None,
                output_path=layout.logs_dir / "launch.log",
            ),
            timeout_seconds=30.0,
        )


def test_historical_shell_fails_fast_without_owned_launch_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A silent historical launcher must yield process evidence after 120 seconds."""

    layout = InstallLayout.from_root(tmp_path / "installed")
    progress_path = layout.logs_dir / "launcher.log"
    clock = iter((0.0, 121.0))
    monkeypatch.setattr(
        "tools.ci.historical_launch_qualification.time.monotonic",
        lambda: next(clock),
    )
    monkeypatch.setattr(
        "tools.ci.historical_launch_qualification.process_tree_diagnostics",
        lambda pid: f"process-tree-for-{pid}",
        raising=False,
    )

    with pytest.raises(
        InstallerLifecycleError,
        match="did not begin.*120 seconds",
    ) as error:
        wait_for_historical_main_shell(
            install_root=layout.root,
            launch=_launch(
                pid=123,
                returncode=0,
                output_path=layout.logs_dir / "launch.log",
                progress_baselines=((progress_path, (False, 0)),),
            ),
            timeout_seconds=600.0,
        )

    assert "process-tree-for-123" in str(error.value)
    assert "return code: 0" in str(error.value)


def _launch(
    *,
    pid: int,
    returncode: int | None,
    output_path: Path,
    progress_baselines: tuple[tuple[Path, tuple[bool, int]], ...] = (),
) -> InstalledCandidateLaunch:
    """Build one deterministic installed-launch process fixture."""

    process = cast(
        subprocess.Popen[bytes],
        SimpleNamespace(pid=pid, poll=lambda: returncode),
    )
    return InstalledCandidateLaunch(
        process=process,
        output_path=output_path,
        progress_baselines=progress_baselines,
    )

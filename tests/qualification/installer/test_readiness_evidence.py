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

"""Qualify readiness evidence and process-bound terminal failure reporting."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
from typing import cast

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError
from tools.ci import installer_ui_qualification
from tools.ci.installer_ui_qualification import (
    InstalledCandidateLaunch,
    launch_installed_candidate,
    process_tree_diagnostics,
)


@pytest.mark.parametrize(
    "terminal_event",
    ["startup.gui_task.failure", "startup.managed.failure"],
)
def test_readiness_wait_fails_immediately_on_terminal_startup_trace(
    tmp_path: Path,
    terminal_event: str,
) -> None:
    """Qualification should stop once the app records terminal startup failure."""

    trace_path = tmp_path / "startup-trace.jsonl"
    trace_path.write_text(
        json.dumps(
            {
                "event": terminal_event,
                "fields": {},
                "kind": "mark",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    managed_output_path = tmp_path / "managed-comfy-startup.log"
    managed_output_path.write_text("fatal comfy traceback", encoding="utf-8")

    with pytest.raises(
        InstallerLifecycleError,
        match=f"terminal startup failure.*{terminal_event}",
    ) as captured:
        installer_ui_qualification._wait_for_readiness_receipt(
            readiness_path=tmp_path / "missing-readiness.json",
            token="qualification-token",
            timeout_seconds=30.0,
            trace_path=trace_path,
            diagnostic_paths=(managed_output_path,),
        )

    assert "fatal comfy traceback" in str(captured.value)


def test_installed_candidate_launch_is_observed_without_capture_bound_wait(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Updater qualification should observe a process while evidence arrives."""

    install_root = tmp_path / "installed"
    layout = InstallLayout.from_root(install_root)
    layout.root.mkdir(parents=True)
    observed: dict[str, object] = {}
    fake_process = cast(
        subprocess.Popen[bytes],
        SimpleNamespace(pid=123, poll=lambda: None),
    )

    def _popen(command: list[str], **kwargs: object) -> object:
        """Capture the process contract without starting an executable."""

        observed["command"] = command
        observed.update(kwargs)
        return fake_process

    monkeypatch.setattr(
        "tools.ci.installer_ui_qualification.subprocess.Popen",
        _popen,
    )

    launch = launch_installed_candidate(
        install_root=install_root,
        environment={
            "QUALIFICATION": "1",
            "SSL_CERT_FILE": "candidate-ca.pem",
            "PYTHONHOME": "hosted-python",
            "PYTHONPATH": "hosted-packages",
            "LD_LIBRARY_PATH": "hosted-python/lib",
            "LD_LIBRARY_PATH_ORIG": "system/lib",
            "DYLD_LIBRARY_PATH": "hosted-python/lib",
            "DYLD_FRAMEWORK_PATH": "hosted-python/frameworks",
            "QT_PLUGIN_PATH": "hosted-qt/plugins",
            "QML2_IMPORT_PATH": "hosted-qt/qml",
            "_PYI_ARCHIVE_FILE": "unrelated-frozen-parent",
        },
    )

    assert isinstance(launch, InstalledCandidateLaunch)
    assert launch.process is fake_process
    assert observed["command"] == [str(layout.executable_path)]
    assert observed["stdout"] is observed["stderr"]
    assert observed["stdin"] is subprocess.DEVNULL
    assert observed["close_fds"] is True
    assert observed["start_new_session"] is (os.name != "nt")
    assert observed["env"] == {
        "QUALIFICATION": "1",
        "SSL_CERT_FILE": "candidate-ca.pem",
    }


def test_stalled_process_diagnostics_expose_runtime_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A frozen launcher stall should reveal its cwd and opened state owner."""

    class _Process:
        """Expose deterministic psutil identity for one stalled launcher."""

        pid = 123

        def children(self, *, recursive: bool) -> list[_Process]:
            """Return no child because the launcher never handed off."""

            assert recursive is True
            return []

        def cmdline(self) -> list[str]:
            """Return the installed executable invocation."""

            return ["/installed/SugarSubstitute"]

        def cpu_times(self) -> tuple[float, float, float, float]:
            """Return bounded CPU counters for the stalled process."""

            return (1.0, 2.0, 0.0, 0.0)

        def cwd(self) -> str:
            """Return the intended installation root."""

            return "/installed"

        def exe(self) -> str:
            """Return the frozen executable path."""

            return "/installed/SugarSubstitute"

        def name(self) -> str:
            """Return the frozen process name."""

            return "SugarSubstitute"

        def memory_maps(self, *, grouped: bool) -> list[SimpleNamespace]:
            """Return mappings that reveal whether Qt startup was reached."""

            assert grouped is True
            return [
                SimpleNamespace(path="/installed/launcher-bin/libpython3.12.so"),
                SimpleNamespace(path="/installed/launcher-bin/libQt6Core.so.6"),
                SimpleNamespace(path="/usr/lib/libunrelated.so"),
            ]

        def num_threads(self) -> int:
            """Return the frozen process thread count."""

            return 2

        def open_files(self) -> list[SimpleNamespace]:
            """Return the launcher state file that identifies its chosen root."""

            return [SimpleNamespace(path="/wrong-root/launcher/logs/launcher.log")]

        def ppid(self) -> int:
            """Return one deterministic parent PID."""

            return 45

        def status(self) -> str:
            """Return the observed sleeping status."""

            return "sleeping"

    monkeypatch.setattr(
        "tools.ci.installer_ui_qualification.psutil.Process",
        lambda _pid: _Process(),
    )

    payload = json.loads(process_tree_diagnostics(123))

    assert payload[0]["cwd"] == "/installed"
    assert payload[0]["open_files"] == ["/wrong-root/launcher/logs/launcher.log"]
    assert payload[0]["mapped_runtime_paths"] == [
        "/installed/launcher-bin/libQt6Core.so.6",
        "/installed/launcher-bin/libpython3.12.so",
    ]
    assert payload[0]["num_threads"] == 2

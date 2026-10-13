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

"""Preserve actual helper-process diagnostics before failed setup cleanup."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import ExitStack, contextmanager
import json
from pathlib import Path
import subprocess
import sys

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from tools import single_instance_launcher_surface_qualification as qualification
from tools.single_instance_packaged_launcher import PackagedLauncherProcess

pytestmark = pytest.mark.platforms("windows")


@contextmanager
def _diagnostic_child(output_path: Path) -> Iterator[subprocess.Popen[bytes]]:
    """Own a real child with bounded termination even when evidence assertions fail."""
    with (
        output_path.open("wb") as output,
        subprocess.Popen(
            [sys.executable, "-c", "import sys;sys.stdin.buffer.read(1)"],
            stdin=subprocess.PIPE,
            stdout=output,
            stderr=subprocess.STDOUT,
        ) as process,
    ):
        try:
            yield process
        finally:
            if process.poll() is None:
                try:
                    process.communicate(input=b"x", timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate(timeout=10)
                    raise


@pytest.mark.parametrize("spawn_failure", [False, True])
def test_setup_failure_retains_its_own_logs_and_live_bootstrap_observations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spawn_failure: bool
) -> None:
    """Keep nested setup evidence even when burst creation stops partway through."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "SugarSubstitute.exe").write_bytes(b"external executable boundary")
    artifacts = tmp_path / "evidence"
    artifacts.mkdir()
    processes: list[subprocess.Popen[bytes]] = []
    children = ExitStack()
    layout_seen: list[InstallLayout] = []
    expected_error = (
        OSError("controlled spawn failure")
        if spawn_failure
        else RuntimeError("controlled setup failure")
    )

    def launch(layout: InstallLayout, *, repair: bool) -> PackagedLauncherProcess:
        """Observe a physical child while replacing only the packaged executable."""
        del repair
        layout_seen.append(layout)
        if spawn_failure and len(processes) == 2:
            raise expected_error
        layout.logs_dir.mkdir(parents=True, exist_ok=True)
        (layout.logs_dir / "launcher.log").write_text("setup-specific evidence\n")
        output_path = layout.logs_dir / f"bootstrap-{len(processes)}.log"
        process = children.enter_context(_diagnostic_child(output_path))
        processes.append(process)
        return PackagedLauncherProcess(process, layout, output_path=output_path)

    def fail_owner(
        launchers: Sequence[PackagedLauncherProcess],
    ) -> PackagedLauncherProcess:
        """Terminate the scenario at the real qualification failure boundary."""
        del launchers
        raise expected_error

    def cleanup(launchers: Sequence[PackagedLauncherProcess]) -> None:
        """Require saved evidence while the owned native children still exist."""
        diagnostics = artifacts / "launcher-surfaces" / "failure-diagnostics"
        assert (diagnostics / "launcher.log").read_text() == "setup-specific evidence\n"
        records = json.loads((diagnostics / "launcher-processes.json").read_text())
        assert len(records) == len(processes) == len(launchers)
        assert all(record["returncode"] is None for record in records)
        assert all((diagnostics / record["output_file"]).exists() for record in records)
        for process in processes:
            process.communicate(input=b"x", timeout=10)

    monkeypatch.setattr(qualification, "_launch_launcher", launch)
    monkeypatch.setattr(qualification, "_wait_for_single_owner", fail_owner)
    monkeypatch.setattr(qualification, "_terminate_launchers", cleanup)
    monkeypatch.setattr(
        qualification, "_terminate_installation_processes", lambda layout: None
    )
    with children:
        with pytest.raises(type(expected_error), match=str(expected_error)) as raised:
            qualification.qualify_launcher_surfaces(
                launcher_bundle=bundle,
                temporary_root=tmp_path / "temporary",
                artifact_dir=artifacts,
            )
        assert raised.value is expected_error
        assert layout_seen

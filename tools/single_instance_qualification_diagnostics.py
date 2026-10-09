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

"""Preserve packaged process and output evidence before qualification cleanup."""

from __future__ import annotations

from collections.abc import Sequence
import json
import logging
from pathlib import Path
import shutil

import psutil  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.process_identity import ProcessIdentity
from tools.single_instance_packaged_launcher import PackagedLauncherProcess

_LOGGER = logging.getLogger(__name__)


def capture_failure_diagnostics(
    layout: InstallLayout,
    artifact_dir: Path,
    launchers: Sequence[PackagedLauncherProcess],
) -> None:
    """Retain pre-cleanup incarnations and logs without hiding the original failure."""
    diagnostics_dir = artifact_dir / "failure-diagnostics"
    try:
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
        records = [capture_launcher_snapshot(launcher) for launcher in launchers]
        (diagnostics_dir / "launcher-processes.json").write_text(
            json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except OSError:
        _LOGGER.exception("Could not preserve failed launcher process snapshots")
    for source in (
        layout.logs_dir / "launcher.log",
        layout.logs_dir / "launcher-bootstrap.log",
        layout.logs_dir / "app-startup.log",
        *(launcher.output_path for launcher in launchers if launcher.output_path),
    ):
        try:
            if source.is_file():
                shutil.copy2(source, diagnostics_dir / source.name)
        except OSError:
            _LOGGER.exception(
                "Could not preserve launcher diagnostic | path=%s", source
            )
    crash_diagnostics = layout.appdata_dir / "diagnostics"
    try:
        if crash_diagnostics.is_dir():
            shutil.copytree(
                crash_diagnostics,
                diagnostics_dir / "app-diagnostics",
                dirs_exist_ok=True,
            )
    except OSError:
        _LOGGER.exception("Could not preserve application crash diagnostics")


def capture_launcher_snapshot(launcher: PackagedLauncherProcess) -> dict[str, object]:
    """Observe a tracked bootstrap and descendants without waiting for runtime logs."""
    identity = launcher.bootstrap_identity
    record: dict[str, object] = {
        "bootstrap_identity": {"pid": identity.pid, "created_at": identity.created_at},
        "returncode": launcher.poll(),
        "output_file": launcher.output_path.name if launcher.output_path else None,
    }
    record["process_tree"] = _capture_process(identity)
    return record


def _capture_process(identity: ProcessIdentity) -> dict[str, object]:
    """Inspect only the captured incarnation and recursively retain its live children."""
    record: dict[str, object] = {"pid": identity.pid, "created_at": identity.created_at}
    try:
        process = psutil.Process(identity.pid)
        if (
            float(process.create_time()) != identity.created_at
            or not process.is_running()
        ):
            record["observation"] = "incarnation_exited"
            return record
        cpu = process.cpu_times()
        memory = process.memory_info()
        record.update(
            image=process.exe(),
            parent_pid=process.ppid(),
            status=process.status(),
            cpu_user_seconds=cpu.user,
            cpu_system_seconds=cpu.system,
            rss_bytes=memory.rss,
            thread_count=process.num_threads(),
        )
        children = []
        for child in process.children():
            try:
                child_identity = ProcessIdentity(child.pid, float(child.create_time()))
                if (
                    child_identity.created_at >= identity.created_at
                    and child.ppid() == identity.pid
                    and process.is_running()
                ):
                    children.append(_capture_process(child_identity))
            except (OSError, psutil.Error) as error:
                children.append({"pid": child.pid, "observation": type(error).__name__})
        if not process.is_running():
            return {**record, "observation": "exited_during_snapshot"}
        record["children"] = children
    except (OSError, psutil.Error) as error:
        record["observation"] = type(error).__name__
    return record


def capture_success_diagnostics(layout: InstallLayout, artifact_dir: Path) -> None:
    """Preserve the qualified launcher log beside the structured report."""
    source = layout.logs_dir / "launcher.log"
    if source.is_file():
        shutil.copy2(source, artifact_dir / "launcher.log")

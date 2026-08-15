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

"""Prove an installed historical app completes its splash-to-shell handoff."""

from __future__ import annotations

import json
from pathlib import Path
from time import monotonic, sleep

import psutil  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher.install_layout import (
    InstallLayout,
    default_install_root,
)
from sugarsubstitute_shared.application_launch_guard import (
    application_launch_lock_path,
)
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError
from tools.ci.installer_ui_qualification import (
    InstalledCandidateLaunch,
    assert_startup_trace_sequence,
    diagnostic_tail,
    installed_launch_has_progress,
    process_tree_diagnostics,
)
from tools.ci.historical_release_contract import (
    HISTORICAL_MANAGED_COMFY_OUTPUT_LOG_NAME,
)


_MAIN_SHELL_EVENT = "main_shell.shown"
_LAUNCH_PROGRESS_TIMEOUT_SECONDS = 120.0
_TERMINAL_EVENTS = frozenset(
    {
        "startup.gui_task.failure",
        "startup.managed.failure",
    }
)


def wait_for_historical_main_shell(
    *,
    install_root: Path,
    launch: InstalledCandidateLaunch,
    timeout_seconds: float,
) -> int:
    """Return the live historical app PID after its real main shell is shown."""

    layout = InstallLayout.from_root(install_root)
    trace_path = layout.appdata_dir / "diagnostics" / "logs" / "startup-trace.jsonl"
    started_at = monotonic()
    deadline = started_at + timeout_seconds
    launch_progress_deadline = min(
        deadline,
        started_at + _LAUNCH_PROGRESS_TIMEOUT_SECONDS,
    )
    while (now := monotonic()) < deadline:
        events = _read_trace_events(trace_path)
        terminal_event = next(
            (event for event in events if event in _TERMINAL_EVENTS),
            None,
        )
        if terminal_event is not None:
            raise InstallerLifecycleError(
                "Historical application reported terminal startup failure: "
                f"{terminal_event}.\n{_historical_diagnostics(layout, launch)}"
            )
        if _MAIN_SHELL_EVENT in events:
            assert_startup_trace_sequence(trace_path)
            main_pid = _live_launch_owner_pid(layout)
            if main_pid is not None:
                return main_pid
        return_code = launch.process.poll()
        if return_code not in {None, 0}:
            raise InstallerLifecycleError(
                "Historical installed launcher exited before the main shell with "
                f"code {return_code}.\n{_historical_diagnostics(layout, launch)}"
            )
        if now >= launch_progress_deadline and not installed_launch_has_progress(
            launch
        ):
            raise InstallerLifecycleError(
                "Historical installed launcher did not begin its application "
                "handoff within 120 seconds. "
                f"Launcher PID: {launch.process.pid}; return code: {return_code}.\n"
                "process tree:\n"
                f"{process_tree_diagnostics(launch.process.pid)}\n\n"
                f"{_historical_diagnostics(layout, launch)}"
            )
        sleep(0.1)
    raise InstallerLifecycleError(
        "Historical installation did not produce a live main-shell process before "
        f"timeout.\n{_historical_diagnostics(layout, launch)}"
    )


def process_is_alive(pid: int) -> bool:
    """Return whether one non-zombie process remains alive."""

    try:
        process = psutil.Process(pid)
        return bool(process.is_running() and process.status() != psutil.STATUS_ZOMBIE)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def _live_launch_owner_pid(layout: InstallLayout) -> int | None:
    """Read the app PID claimed through the production launch-guard handoff."""

    lock_path = application_launch_lock_path(layout.root)
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    pid = payload.get("pid")
    token_digest = payload.get("token_digest")
    handoff_consumed = payload.get("handoff_consumed")
    if (
        not isinstance(pid, int)
        or pid <= 0
        or not isinstance(token_digest, str)
        or not token_digest
        or handoff_consumed is not True
    ):
        return None
    return pid if process_is_alive(pid) else None


def assert_historical_installed_launch_contract(install_root: Path) -> None:
    """Require historical launcher state to resolve to one installed app root."""

    layout = InstallLayout.from_root(install_root)
    required_files = {
        "launcher executable": layout.executable_path,
        "launcher config": layout.config_path,
        "application entrypoint": layout.app_entrypoint,
        "runtime Python": layout.runtime_python,
    }
    missing = [name for name, path in required_files.items() if not path.is_file()]
    if missing:
        raise InstallerLifecycleError(
            "Historical installation is not launchable; missing " + ", ".join(missing)
        )
    try:
        payload = json.loads(layout.config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InstallerLifecycleError(
            f"Historical launcher config is unreadable: {layout.config_path}."
        ) from error
    if not isinstance(payload, dict):
        raise InstallerLifecycleError("Historical launcher config is not an object.")
    expected_paths = {
        "install_root": layout.root,
        "app_dir": layout.app_dir,
        "runtime_python": layout.runtime_python,
    }
    mismatches: list[str] = []
    for field, expected_path in expected_paths.items():
        value = payload.get(field)
        if not isinstance(value, str) or not value:
            mismatches.append(f"{field}=<missing>")
            continue
        if Path(value).expanduser().resolve() != expected_path.resolve():
            mismatches.append(f"{field}={value!r} expected={str(expected_path)!r}")
    if mismatches:
        raise InstallerLifecycleError(
            "Historical launcher config does not identify its installed root: "
            + "; ".join(mismatches)
        )


def _read_trace_events(trace_path: Path) -> tuple[str, ...]:
    """Return complete event names while tolerating an in-flight final record."""

    try:
        lines = trace_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ()
    events: list[str] = []
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        event = payload.get("event") if isinstance(payload, dict) else None
        if isinstance(event, str):
            events.append(event)
    return tuple(events)


def _historical_diagnostics(
    layout: InstallLayout,
    launch: InstalledCandidateLaunch,
) -> str:
    """Render bounded logs for one failed historical app handoff."""

    paths = (
        launch.output_path,
        *(path for path, _baseline in launch.progress_baselines),
        layout.config_path,
        layout.state_path,
        layout.logs_dir / "launcher.log",
        layout.logs_dir / "app-startup.log",
        layout.appdata_dir / "diagnostics" / "logs" / "startup-trace.jsonl",
        layout.appdata_dir / "diagnostics" / "logs" / "sugarsubstitute.log",
        layout.root / HISTORICAL_MANAGED_COMFY_OUTPUT_LOG_NAME,
        application_launch_lock_path(layout.root),
    )
    default_log = (
        default_install_root(layout.executable_path)
        / "launcher"
        / "logs"
        / "launcher.log"
    )
    complete_paths = (*paths, *((default_log,) if default_log not in paths else ()))
    return "\n\n".join(f"{path}:\n{diagnostic_tail(path)}" for path in complete_paths)


__all__ = [
    "assert_historical_installed_launch_contract",
    "process_is_alive",
    "wait_for_historical_main_shell",
]

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

"""Capture exact process and splash evidence for packaged cold starts."""

from __future__ import annotations

from collections.abc import Sequence
import json
import os
from pathlib import Path
import time

import psutil  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout


SPLASH_SURFACE_EVIDENCE_ENV = "SUGAR_SUBSTITUTE_SPLASH_SURFACE_EVIDENCE"
_TIMEOUT_SECONDS = 30.0


def capture_cold_start_snapshot(layout: InstallLayout) -> dict[str, object]:
    """Return synchronized process, ownership, adoption, and surface evidence."""

    surface_records = _wait_for_json_records(
        layout.user_dir / "qualification-splash-surfaces",
        expected_count=1,
        description="one splash surface record",
    )
    adoption_records = _wait_for_json_records(
        layout.user_dir / "qualification-splash-adoptions",
        expected_count=1,
        description="one splash adoption record",
    )
    application_runtime_pids = tuple(sorted(_application_runtime_pids(layout)))
    launcher_pids = tuple(sorted(packaged_launcher_pids(layout)))
    host_pids = tuple(sorted(splash_host_pids(layout)))
    return {
        "application_owner_pids": list(sorted(qualification_app_pids(layout))),
        "application_runtime_process_pids": list(application_runtime_pids),
        "application_runtime_processes": list(_process_facts(application_runtime_pids)),
        "packaged_launcher_pids": list(launcher_pids),
        "packaged_launcher_processes": list(_process_facts(launcher_pids)),
        "splash_adoptions": list(adoption_records),
        "splash_host_process_pids": list(host_pids),
        "splash_host_processes": list(_process_facts(host_pids)),
        "splash_surfaces": list(surface_records),
    }


def assert_cold_start_snapshot(
    snapshot: dict[str, object],
    *,
    expected_launcher_pids: tuple[int, ...],
    expected_app_pid: int,
) -> None:
    """Require exactly one app owner, splash adoption, and visible surface."""

    if snapshot["application_owner_pids"] != [expected_app_pid]:
        raise AssertionError(f"Unexpected application owners: {snapshot}")
    if snapshot["packaged_launcher_pids"] != list(sorted(expected_launcher_pids)):
        raise AssertionError(f"Unexpected packaged launcher processes: {snapshot}")
    surfaces = snapshot["splash_surfaces"]
    adoptions = snapshot["splash_adoptions"]
    if not isinstance(surfaces, list) or len(surfaces) != 1:
        raise AssertionError(f"Expected one splash surface: {snapshot}")
    if not isinstance(adoptions, list) or len(adoptions) != 1:
        raise AssertionError(f"Expected one splash adoption: {snapshot}")
    surface = surfaces[0]
    adoption = adoptions[0]
    if not isinstance(surface, dict) or not isinstance(adoption, dict):
        raise AssertionError(f"Malformed splash evidence: {snapshot}")
    if (
        surface.get("splash_is_visible") is not True
        or surface.get("first_paint_confirmed") is not True
        or not isinstance(surface.get("launch_to_first_paint_ms"), (int, float))
        or surface.get("top_level_surface_count") != 1
        or surface.get("visible_top_level_surface_count") != 1
        or surface.get("platform_name") != "offscreen"
        or adoption.get("app_pid") != expected_app_pid
        or adoption.get("splash_host_pid") != surface.get("host_pid")
        or adoption.get("close_acknowledged") is not True
    ):
        raise AssertionError(f"Splash surface evidence was not singular: {snapshot}")
    _assert_startup_phase_order(surface, snapshot=snapshot)


def _assert_startup_phase_order(
    surface: dict[str, object],
    *,
    snapshot: dict[str, object],
) -> None:
    """Require each observed splash phase to follow its causal predecessor."""

    raw_phases = surface.get("startup_phase_ms")
    if not isinstance(raw_phases, dict):
        raise AssertionError(f"Splash startup phases were missing: {snapshot}")
    ordered_names = (
        "host_process_requested",
        "host_module_started",
        "host_main_entered",
        "arguments_parsed",
        "application_ready",
        "icon_ready",
        "splash_module_ready",
        "splash_constructed",
        "first_paint",
    )
    try:
        phases = [float(raw_phases[name]) for name in ordered_names]
    except (KeyError, TypeError, ValueError) as error:
        raise AssertionError(
            f"Splash startup phases were malformed: {snapshot}"
        ) from error
    if phases != sorted(phases):
        raise AssertionError(f"Splash startup phases were out of order: {snapshot}")


def splash_host_pids(layout: InstallLayout) -> tuple[int, ...]:
    """Return physical processes in splash-host chains for one installation."""

    root_key = os.path.normcase(str(layout.root))
    matches: list[int] = []
    for process in psutil.process_iter(["pid", "cmdline", "cwd"]):
        try:
            command = process.info.get("cmdline") or []
            working_directory = process.info.get("cwd") or ""
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
        command_text = " ".join(str(part) for part in command)
        if (
            command
            and os.path.normcase(str(working_directory)) == root_key
            and "substitute.app.bootstrap.shared_splash_host" in command_text
        ):
            matches.append(int(process.info["pid"]))
    return tuple(matches)


def packaged_launcher_pids(layout: InstallLayout) -> tuple[int, ...]:
    """Return live packaged launcher processes for the disposable installation."""

    expected_executable = layout.executable_path.resolve()
    matches: list[int] = []
    for process in psutil.process_iter(["pid", "exe"]):
        try:
            executable = Path(process.info.get("exe") or "").resolve()
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
        if executable == expected_executable:
            matches.append(int(process.info["pid"]))
    return tuple(matches)


def clear_splash_qualification_records(layout: InstallLayout) -> None:
    """Remove only known JSON evidence records before the next cold launch."""

    for directory_name in (
        "qualification-splash-adoptions",
        "qualification-splash-surfaces",
    ):
        directory = (layout.user_dir / directory_name).resolve()
        if layout.user_dir.resolve() not in directory.parents:
            raise AssertionError(
                f"Qualification evidence escaped user data: {directory}"
            )
        for record_path in directory.glob("*.json"):
            record_path.unlink()


def _wait_for_json_records(
    directory: Path,
    *,
    expected_count: int,
    description: str,
) -> tuple[dict[str, object], ...]:
    """Wait for an exact number of complete JSON qualification records."""

    deadline = time.monotonic() + _TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        records = _read_json_records(directory)
        if len(records) == expected_count:
            return records
        time.sleep(0.05)
    raise TimeoutError(f"Timed out waiting for {description}.")


def _read_json_records(directory: Path) -> tuple[dict[str, object], ...]:
    """Read complete mapping records from one qualification directory."""

    records: list[dict[str, object]] = []
    for record_path in directory.glob("*.json"):
        try:
            payload = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and all(isinstance(key, str) for key in payload):
            records.append(payload)
    return tuple(records)


def _application_runtime_pids(layout: InstallLayout) -> tuple[int, ...]:
    """Return every physical runtime process executing the qualification app."""

    entrypoint_key = os.path.normcase(str(layout.app_entrypoint.resolve()))
    matches: list[int] = []
    for process in psutil.process_iter(["pid", "cmdline"]):
        try:
            command = process.info.get("cmdline") or []
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
        if any(
            os.path.normcase(str(argument)) == entrypoint_key for argument in command
        ):
            matches.append(int(process.info["pid"]))
    return tuple(matches)


def qualification_app_pids(layout: InstallLayout) -> tuple[int, ...]:
    """Return live marker owners whose process identity still matches the app."""

    marker_dir = layout.user_dir / "qualification-owners"
    entrypoint_key = os.path.normcase(str(layout.app_entrypoint.resolve()))
    matches: list[int] = []
    for marker_path in marker_dir.glob("*.json"):
        try:
            payload = json.loads(marker_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        pid = payload.get("pid") if isinstance(payload, dict) else None
        parent_pid = payload.get("parent_pid") if isinstance(payload, dict) else None
        if not isinstance(pid, int) or not isinstance(parent_pid, int):
            continue
        try:
            process = psutil.Process(pid)
            command = process.cmdline()
            if process.ppid() != parent_pid:
                continue
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
        if any(
            os.path.normcase(str(argument)) == entrypoint_key for argument in command
        ):
            matches.append(pid)
    return tuple(matches)


def _process_facts(pids: Sequence[int]) -> tuple[dict[str, object], ...]:
    """Return stable process-tree facts for exact qualification PIDs."""

    facts: list[dict[str, object]] = []
    for pid in pids:
        try:
            process = psutil.Process(pid)
            facts.append(
                {
                    "executable": process.exe(),
                    "name": process.name(),
                    "parent_pid": process.ppid(),
                    "pid": pid,
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
    return tuple(facts)


__all__ = [
    "SPLASH_SURFACE_EVIDENCE_ENV",
    "assert_cold_start_snapshot",
    "capture_cold_start_snapshot",
    "clear_splash_qualification_records",
    "packaged_launcher_pids",
    "qualification_app_pids",
    "splash_host_pids",
]

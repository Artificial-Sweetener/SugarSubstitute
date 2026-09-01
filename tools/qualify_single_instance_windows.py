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

"""Qualify packaged Windows single-instance behavior against real processes."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from typing import TypeVar

import psutil  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_instance_control import (
    ApplicationShutdownRequestResult,
    request_active_application_shutdown,
)
from sugarsubstitute_shared.application_instance_lease import ApplicationInstanceLease
from sugarsubstitute_shared.application_launch_guard import application_launch_lock_path
from tools.single_instance_cold_start_evidence import (
    SPLASH_SURFACE_EVIDENCE_ENV,
    assert_cold_start_snapshot,
    capture_cold_start_snapshot,
    clear_splash_qualification_records,
    splash_host_pids,
)
from tools.single_instance_qualification_installation import (
    prepare_qualification_installation,
)
from tools.single_instance_qualification_app import APPLICATION_CLAIM_DELAY_ENV


_TIMEOUT_SECONDS = 30.0
_RACE_APPLICATION_CLAIM_DELAY_SECONDS = 5.0
_T = TypeVar("_T")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the packaged-launcher qualification and persist its evidence."""

    if os.name != "nt":
        raise RuntimeError("Packaged single-instance qualification requires Windows.")
    arguments = _parse_arguments(argv)
    repository_root = Path(__file__).resolve().parents[1]
    artifact_dir = arguments.artifact_dir.resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    evidence: dict[str, object] = {}

    with tempfile.TemporaryDirectory(prefix="SugarSubstitute-instance-") as temporary:
        install_root = Path(temporary) / "SugarSubstitute"
        layout = prepare_qualification_installation(
            repository_root=repository_root,
            launcher_bundle=arguments.launcher_bundle.resolve(),
            install_root=install_root,
        )
        active_launchers: list[subprocess.Popen[bytes]] = []
        try:
            first_launcher = _launch(layout)
            active_launchers.append(first_launcher)
            first_pid = _wait_for_new_app_pid(layout)
            single_snapshot = capture_cold_start_snapshot(layout)
            assert_cold_start_snapshot(
                single_snapshot,
                expected_launcher_pids=(first_launcher.pid,),
                expected_app_pid=first_pid,
            )
            evidence["single_cold_start"] = single_snapshot
            _wait_for_splash_hosts_exit(layout)
            _assert_app_owners(layout, expected=(first_pid,))

            _request_shutdown_and_wait(layout)
            _wait_for_process_exit(first_pid)
            _wait_for_exit(first_launcher)
            clear_splash_qualification_records(layout)

            race_started_at = time.perf_counter_ns()
            race_winner = _launch(
                layout,
                application_claim_delay_seconds=(_RACE_APPLICATION_CLAIM_DELAY_SECONDS),
            )
            _wait_for_launcher_before_application(layout)
            race_duplicate = _launch(layout)
            race_launchers = [race_winner, race_duplicate]
            active_launchers.extend(race_launchers)
            _wait_for_exit(race_duplicate)
            race_pid = _wait_for_new_app_pid(layout, previous_pid=first_pid)
            race_snapshot = capture_cold_start_snapshot(layout)
            assert_cold_start_snapshot(
                race_snapshot,
                expected_launcher_pids=(race_winner.pid,),
                expected_app_pid=race_pid,
            )
            race_snapshot["invocation_start_elapsed_ms"] = (
                time.perf_counter_ns() - race_started_at
            ) / 1_000_000
            race_snapshot["rejected_duplicate_launcher_pid"] = race_duplicate.pid
            evidence["rapid_double_invocation"] = race_snapshot
            _wait_for_splash_hosts_exit(layout)
            _assert_app_owners(layout, expected=(race_pid,))

            duplicate_launchers = [_launch(layout) for _index in range(5)]
            active_launchers.extend(duplicate_launchers)
            _wait_for_value(
                lambda: (
                    True
                    if sum(process.poll() is None for process in duplicate_launchers)
                    == 1
                    and all(
                        process.poll() in (None, 0) for process in duplicate_launchers
                    )
                    else None
                ),
                description="one serialized headless duplicate negotiation",
            )
            negotiation_launcher = next(
                process for process in duplicate_launchers if process.poll() is None
            )
            _assert_app_owners(layout, expected=(race_pid,))
            evidence["duplicate_launch_preserved_pid"] = race_pid
            evidence["negotiation_launcher_pid"] = negotiation_launcher.pid
            evidence["suppressed_duplicate_count"] = len(duplicate_launchers) - 1
            _terminate_launchers(duplicate_launchers)

            _request_shutdown_and_wait(layout)
            _wait_for_process_exit(race_pid)
            _wait_for_exit(race_winner)
            replacement_launcher = _launch(layout)
            active_launchers.append(replacement_launcher)
            replacement_pid = _wait_for_new_app_pid(layout, previous_pid=race_pid)
            _wait_for_splash_hosts_exit(layout)
            _assert_app_owners(layout, expected=(replacement_pid,))
            evidence["graceful_replacement_pid"] = replacement_pid

            _request_shutdown_and_wait(layout)
            _wait_for_process_exit(replacement_pid)
            _wait_for_exit(replacement_launcher)
            lock_path = application_launch_lock_path(layout.root)
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_path.write_text("truncated-not-json", encoding="utf-8")
            malformed_recovery_launcher = _launch(layout)
            active_launchers.append(malformed_recovery_launcher)
            malformed_recovery_pid = _wait_for_new_app_pid(layout)
            _wait_for_splash_hosts_exit(layout)
            evidence["malformed_record_recovery_pid"] = malformed_recovery_pid

            psutil.Process(malformed_recovery_pid).kill()
            _wait_for_process_exit(malformed_recovery_pid)
            _wait_for_exit(malformed_recovery_launcher)
            crash_recovery_launcher = _launch(layout)
            active_launchers.append(crash_recovery_launcher)
            crash_recovery_pid = _wait_for_new_app_pid(
                layout,
                previous_pid=malformed_recovery_pid,
            )
            _wait_for_splash_hosts_exit(layout)
            _assert_app_owners(layout, expected=(crash_recovery_pid,))
            evidence["crash_recovery_pid"] = crash_recovery_pid
            _request_shutdown_and_wait(layout)
            _wait_for_process_exit(crash_recovery_pid)
            _wait_for_exit(crash_recovery_launcher)
        finally:
            _terminate_launchers(active_launchers)
            _terminate_qualification_apps(layout)
            _terminate_installation_processes(layout)

    evidence["result"] = "passed"
    report_path = artifact_dir / "single-instance-qualification.json"
    report_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(report_path)
    return 0


def _parse_arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse explicit launcher bundle and evidence paths."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--launcher-bundle",
        type=Path,
        default=Path("dist") / "SugarSubstitute",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("build") / "qualification" / "single-instance",
    )
    return parser.parse_args(argv)


def _launch(
    layout: InstallLayout,
    *,
    application_claim_delay_seconds: float | None = None,
) -> subprocess.Popen[bytes]:
    """Start one real packaged launcher invocation without desktop surfaces."""

    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment[SPLASH_SURFACE_EVIDENCE_ENV] = "1"
    if application_claim_delay_seconds is not None:
        environment[APPLICATION_CLAIM_DELAY_ENV] = str(application_claim_delay_seconds)

    return subprocess.Popen(  # noqa: S603
        [str(layout.executable_path), "--no-update-check", "--locale=en"],
        cwd=layout.root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=environment,
        shell=False,
    )


def _wait_for_new_app_pid(
    layout: InstallLayout,
    *,
    previous_pid: int | None = None,
) -> int:
    """Wait for a live qualification app marker with a new process identity."""

    marker_path = layout.user_dir / "qualification-app.json"

    def current_pid() -> int | None:
        try:
            payload = json.loads(marker_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None
        pid = payload.get("pid") if isinstance(payload, dict) else None
        if (
            not isinstance(pid, int)
            or pid == previous_pid
            or not psutil.pid_exists(pid)
        ):
            return None
        return pid

    return _wait_for_value(current_pid, description="qualification application start")


def _wait_for_launcher_before_application(layout: InstallLayout) -> None:
    """Stop in the exact launch phase that previously produced the false dialog."""

    lock_path = application_launch_lock_path(layout.root)
    _wait_for_value(
        lambda: (
            True
            if lock_path.is_file()
            and not ApplicationInstanceLease.owner_exists(layout.root)
            else None
        ),
        description="launcher ownership before application handoff",
    )


def _assert_app_owners(layout: InstallLayout, *, expected: tuple[int, ...]) -> None:
    """Assert exactly the expected interpreters successfully claimed app ownership."""

    observed = tuple(sorted(_qualification_app_pids(layout, live_only=True)))
    if observed != tuple(sorted(expected)):
        raise AssertionError(
            f"Expected qualification app owners {expected}, observed {observed}."
        )
    if not ApplicationInstanceLease.owner_exists(layout.root):
        raise AssertionError(
            "The expected application owner does not hold its OS lease."
        )


def _qualification_app_pids(
    layout: InstallLayout,
    *,
    live_only: bool,
) -> tuple[int, ...]:
    """Return interpreters that wrote an accepted-owner qualification marker."""

    marker_dir = layout.user_dir / "qualification-owners"
    matches: list[int] = []
    for marker_path in marker_dir.glob("*.json"):
        try:
            payload = json.loads(marker_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        pid = payload.get("pid") if isinstance(payload, dict) else None
        if not isinstance(pid, int):
            continue
        if not live_only or psutil.pid_exists(pid):
            matches.append(pid)
    return tuple(matches)


def _wait_for_splash_hosts_exit(layout: InstallLayout) -> None:
    """Prove every launcher splash host exits after the app adopts its session."""

    _wait_for_value(
        lambda: True if not splash_host_pids(layout) else None,
        description="launcher splash host exit",
    )


def _request_shutdown_and_wait(layout: InstallLayout) -> None:
    """Request graceful shutdown and prove both IPC and lease release."""

    result = request_active_application_shutdown(layout.root)
    if result is not ApplicationShutdownRequestResult.ACCEPTED:
        raise AssertionError(f"Graceful shutdown request was not accepted: {result}")
    _wait_for_value(
        lambda: (
            True if not ApplicationInstanceLease.owner_exists(layout.root) else None
        ),
        description="application lease release",
    )


def _wait_for_exit(process: subprocess.Popen[bytes]) -> None:
    """Wait for one packaged supervisor after its application reaches terminal state."""

    process.wait(timeout=_TIMEOUT_SECONDS)
    if process.returncode != 0:
        raise AssertionError(f"Packaged launcher exited with {process.returncode}.")


def _wait_for_process_exit(pid: int) -> None:
    """Wait until a force-terminated qualification process is gone."""

    _wait_for_value(
        lambda: True if not psutil.pid_exists(pid) else None,
        description=f"process {pid} exit",
    )


def _wait_for_value(
    value_factory: Callable[[], _T | None],
    *,
    description: str,
) -> _T:
    """Return the first non-None value produced within the global timeout."""

    deadline = time.monotonic() + _TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        value = value_factory()
        if value is not None:
            return value
        time.sleep(0.05)
    raise TimeoutError(f"Timed out waiting for {description}.")


def _terminate_launchers(processes: Sequence[subprocess.Popen[bytes]]) -> None:
    """Stop only still-running launcher processes created by this qualification."""

    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        if process.poll() is None:
            try:
                process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5.0)


def _terminate_qualification_apps(layout: InstallLayout) -> None:
    """Stop only app processes belonging to the disposable qualification layout."""

    for pid in _qualification_app_pids(layout, live_only=True):
        try:
            process = psutil.Process(pid)
            process.kill()
            process.wait(timeout=5.0)
        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
            continue


def _terminate_installation_processes(layout: InstallLayout) -> None:
    """Stop remaining launcher or runtime helpers rooted in the disposable install."""

    root_key = os.path.normcase(str(layout.root))
    owned: list[psutil.Process] = []
    for process in psutil.process_iter(["exe", "cmdline"]):
        try:
            executable = os.path.normcase(str(process.info.get("exe") or ""))
            command = process.info.get("cmdline") or []
            invoked = os.path.normcase(str(command[0])) if command else ""
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
        if executable.startswith(root_key) or invoked.startswith(root_key):
            owned.append(process)
    for process in owned:
        try:
            process.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    _, alive = psutil.wait_procs(owned, timeout=3.0)
    for process in alive:
        try:
            process.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    psutil.wait_procs(alive, timeout=3.0)


if __name__ == "__main__":
    raise SystemExit(main())

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

"""Qualify packaged Windows instance-broker behavior against real processes."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import TypeVar

import psutil  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from tools.single_instance_cold_start_evidence import (
    SPLASH_SURFACE_EVIDENCE_ENV,
    assert_cold_start_snapshot,
    capture_cold_start_snapshot,
    splash_host_pids,
)
from tools.single_instance_qualification_app import (
    APPLICATION_REGISTRATION_DELAY_ENV,
    APPLICATION_RESTART_AFTER_INVOCATIONS_ENV,
    application_preregistration_marker_path,
    invocation_evidence_path,
    restart_evidence_path,
)
from tools.single_instance_qualification_installation import (
    prepare_qualification_installation,
)


_TIMEOUT_SECONDS = 30.0
_REGISTRATION_DELAY_SECONDS = 5.0
_BURST_SIZE = 16
_T = TypeVar("_T")


def main(argv: Sequence[str] | None = None) -> int:
    """Run native election, burst, and crash-recovery qualification."""

    if os.name != "nt":
        raise RuntimeError("Packaged instance qualification requires Windows.")
    arguments = _parse_arguments(argv)
    repository_root = Path(__file__).resolve().parents[1]
    artifact_dir = arguments.artifact_dir.resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    evidence: dict[str, object] = {}

    with tempfile.TemporaryDirectory(prefix="SugarSubstitute-instance-") as temporary:
        layout = prepare_qualification_installation(
            repository_root=repository_root,
            launcher_bundle=arguments.launcher_bundle.resolve(),
            install_root=Path(temporary) / "SugarSubstitute",
        )
        launchers: list[subprocess.Popen[bytes]] = []
        try:
            primary = _launch(
                layout,
                registration_delay_seconds=_REGISTRATION_DELAY_SECONDS,
                restart_after_invocations=_BURST_SIZE * 2,
            )
            launchers.append(primary)
            _wait_for_preregistration(layout)
            burst = [_launch(layout) for _index in range(_BURST_SIZE)]
            launchers.extend(burst)
            _wait_for_clean_exits(burst)
            app_pid = _wait_for_new_app_pid(layout, supervisor=primary)
            _wait_for_invocation_count(layout, _BURST_SIZE)
            _wait_for_splash_hosts_exit(layout)
            _assert_single_child(layout, app_pid)
            snapshot = capture_cold_start_snapshot(layout)
            assert_cold_start_snapshot(
                snapshot,
                expected_launcher_pids=(primary.pid,),
                expected_app_pid=app_pid,
            )
            evidence["startup_burst"] = {
                **snapshot,
                "forwarded_invocation_count": len(burst),
                "forwarder_exit_codes": [process.returncode for process in burst],
            }

            steady_burst = [_launch(layout) for _index in range(_BURST_SIZE)]
            launchers.extend(steady_burst)
            _wait_for_clean_exits(steady_burst)
            restart_evidence = _wait_for_restart_evidence(
                layout,
                expected_pid=app_pid,
                expected_invocation_count=_BURST_SIZE * 2,
            )
            restarted_pid = _wait_for_new_app_pid(
                layout,
                previous_pid=app_pid,
                supervisor=primary,
            )
            _assert_single_child(layout, restarted_pid)
            evidence["steady_state_burst"] = {
                "application_pid": app_pid,
                "forwarded_invocation_count": len(steady_burst),
            }
            evidence["supervised_restart"] = {
                **restart_evidence,
                "restarted_application_pid": restarted_pid,
                "supervisor_pid": primary.pid,
            }

            psutil.Process(primary.pid).kill()
            _wait_for_process_exit(primary.pid)
            _wait_for_process_exit(restarted_pid)
            replacement = _launch(layout)
            launchers.append(replacement)
            replacement_pid = _wait_for_new_app_pid(
                layout,
                previous_pid=restarted_pid,
                supervisor=replacement,
            )
            _wait_for_splash_hosts_exit(layout)
            _assert_single_child(layout, replacement_pid)
            evidence["supervisor_crash_recovery"] = {
                "terminated_supervisor_pid": primary.pid,
                "terminated_child_pid": restarted_pid,
                "replacement_supervisor_pid": replacement.pid,
                "replacement_child_pid": replacement_pid,
            }
            _assert_no_live_ownership_files(layout)
            evidence["native_ownership"] = {
                "created_live_ownership_files": [],
                "election": "first-local-named-pipe-instance",
                "peer_scope": "same-user-session",
                "remote_clients": "rejected",
            }
        except BaseException:
            _capture_failure_diagnostics(layout, artifact_dir)
            raise
        finally:
            _terminate_launchers(launchers)
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
    registration_delay_seconds: float | None = None,
    restart_after_invocations: int | None = None,
) -> subprocess.Popen[bytes]:
    """Start one packaged launcher invocation without desktop surfaces."""

    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment[SPLASH_SURFACE_EVIDENCE_ENV] = "1"
    if registration_delay_seconds is not None:
        environment[APPLICATION_REGISTRATION_DELAY_ENV] = str(
            registration_delay_seconds
        )
    if restart_after_invocations is not None:
        environment[APPLICATION_RESTART_AFTER_INVOCATIONS_ENV] = str(
            restart_after_invocations
        )
    return subprocess.Popen(  # noqa: S603
        [str(layout.executable_path), "--no-update-check", "--locale=en"],
        cwd=layout.root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=environment,
        shell=False,
    )


def _wait_for_preregistration(layout: InstallLayout) -> None:
    """Wait until the elected supervisor has started its delayed child."""

    marker_path = application_preregistration_marker_path(layout.root)
    _wait_for_value(
        lambda: True if marker_path.is_file() else None,
        description="application preregistration phase",
    )


def _wait_for_new_app_pid(
    layout: InstallLayout,
    *,
    previous_pid: int | None = None,
    supervisor: subprocess.Popen[bytes] | None = None,
) -> int:
    """Wait for a live registered child with a new process identity."""

    marker_path = layout.user_dir / "qualification-app.json"

    def current_pid() -> int | None:
        if supervisor is not None and supervisor.poll() is not None:
            raise RuntimeError(
                f"Application supervisor {supervisor.pid} exited with "
                f"{supervisor.returncode} before its child registered."
            )
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

    return _wait_for_value(current_pid, description="registered application child")


def _qualification_app_pids(layout: InstallLayout) -> tuple[int, ...]:
    """Return live registered children in the disposable installation."""

    matches: list[int] = []
    for marker_path in (layout.user_dir / "qualification-owners").glob("*.json"):
        try:
            payload = json.loads(marker_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        pid = payload.get("pid") if isinstance(payload, dict) else None
        if isinstance(pid, int) and psutil.pid_exists(pid):
            matches.append(pid)
    return tuple(matches)


def _wait_for_invocation_count(layout: InstallLayout, expected_count: int) -> None:
    """Require every acknowledged secondary launch to be handled exactly once."""

    evidence_path = invocation_evidence_path(layout.root)

    def observed_count() -> int | None:
        try:
            payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None
        count = payload.get("count") if isinstance(payload, dict) else None
        return count if count == expected_count else None

    _wait_for_value(
        observed_count,
        description=f"{expected_count} exactly-once forwarded invocations",
    )


def _wait_for_restart_evidence(
    layout: InstallLayout,
    *,
    expected_pid: int,
    expected_invocation_count: int,
) -> dict[str, object]:
    """Require a real child-to-supervisor restart request at the exact count."""

    evidence_path = restart_evidence_path(layout.root)

    def accepted_evidence() -> dict[str, object] | None:
        try:
            payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        if payload != {
            "accepted": True,
            "invocation_count": expected_invocation_count,
            "pid": expected_pid,
        }:
            return None
        return payload

    return _wait_for_value(
        accepted_evidence,
        description="authenticated supervised application restart",
    )


def _assert_single_child(layout: InstallLayout, expected_pid: int) -> None:
    """Prove exactly one registered application child remains live."""

    observed = tuple(sorted(_qualification_app_pids(layout)))
    if observed != (expected_pid,):
        raise AssertionError(f"Expected one child {expected_pid}, observed {observed}.")


def _assert_no_live_ownership_files(layout: InstallLayout) -> None:
    """Prove the packaged run created none of the removed ownership artifacts."""

    forbidden = (
        "application-instance.lease",
        "launcher-invocation.lease",
        "application-launch.mutex",
        "application-launch.lock",
        "app-update.lock",
    )
    historical_lock_directory = layout.launcher_dir / "locks"
    created = [
        name for name in forbidden if (historical_lock_directory / name).exists()
    ]
    if created:
        raise AssertionError(f"Removed ownership files were recreated: {created}")


def _wait_for_clean_exits(processes: Sequence[subprocess.Popen[bytes]]) -> None:
    """Require every forwarded launcher invocation to acknowledge and exit cleanly."""

    for process in processes:
        process.wait(timeout=_TIMEOUT_SECONDS)
        if process.returncode != 0:
            raise AssertionError(
                f"Forwarding launcher {process.pid} exited with {process.returncode}."
            )


def _wait_for_splash_hosts_exit(layout: InstallLayout) -> None:
    """Prove every launcher splash host exits after child adoption."""

    _wait_for_value(
        lambda: True if not splash_host_pids(layout) else None,
        description="launcher splash host exit",
    )


def _wait_for_process_exit(pid: int) -> None:
    """Wait until one supervisor or child process is gone."""

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
    """Stop only still-running launchers created by this qualification."""

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
    """Stop remaining children belonging to the disposable installation."""

    for pid in _qualification_app_pids(layout):
        try:
            process = psutil.Process(pid)
            process.kill()
            process.wait(timeout=5.0)
        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
            continue


def _terminate_installation_processes(layout: InstallLayout) -> None:
    """Stop remaining helpers rooted in the disposable installation."""

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


def _capture_failure_diagnostics(
    layout: InstallLayout,
    artifact_dir: Path,
) -> None:
    """Retain bounded launcher and crash evidence before disposal."""

    diagnostics_dir = artifact_dir / "failure-diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    for source in (
        layout.logs_dir / "launcher.log",
        layout.logs_dir / "app-startup.log",
    ):
        if source.is_file():
            shutil.copy2(source, diagnostics_dir / source.name)
    crash_diagnostics = layout.appdata_dir / "diagnostics"
    if crash_diagnostics.is_dir():
        shutil.copytree(
            crash_diagnostics,
            diagnostics_dir / "app-diagnostics",
            dirs_exist_ok=True,
        )


if __name__ == "__main__":
    raise SystemExit(main())

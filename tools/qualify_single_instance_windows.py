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
from collections.abc import Sequence
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

import psutil  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from tools.single_instance_cold_start_evidence import (
    SPLASH_SURFACE_EVIDENCE_ENV,
    assert_cold_start_snapshot,
    capture_cold_start_snapshot,
    clear_splash_qualification_records,
)
from tools.single_instance_qualification_app import (
    APPLICATION_EXIT_AFTER_INVOCATIONS_ENV,
    APPLICATION_INITIAL_WINDOW_STATE_ENV,
    APPLICATION_REGISTRATION_GATE_ENV,
    APPLICATION_RESTART_AFTER_INVOCATIONS_ENV,
    APPLICATION_WINDOW_CONSTRUCTION_GATE_ENV,
    application_prewindow_marker_path,
    application_prewindow_release_path,
    application_preregistration_claim_path,
    application_preregistration_marker_path,
    application_preregistration_release_path,
)
from tools.single_instance_qualification_installation import (
    prepare_qualification_installation,
)
from tools.single_instance_log_evidence import audit_launcher_log
from tools.single_instance_windows_process_support import (
    _assert_no_live_ownership_files,
    _assert_single_child,
    _capture_failure_diagnostics,
    _capture_success_diagnostics,
    _terminate_installation_processes,
    _terminate_launchers,
    _terminate_qualification_apps,
    _terminate_supervisor_and_child,
    _wait_for_clean_exits,
    _wait_for_forwarder_acceptance,
    _wait_for_forwarder_surface,
    _wait_for_invocation_count,
    _wait_for_presented_surface,
    _wait_for_process_exit,
    _wait_for_replacement_broker_child,
    _wait_for_restart_evidence,
    _wait_for_splash_host_pid,
    _wait_for_splash_hosts_exit,
    _wait_for_value,
)
from tools.single_instance_launcher_surface_qualification import (
    qualify_launcher_surfaces,
)


_TIMEOUT_SECONDS = 30.0
_BURST_SIZE = 16


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
                gate_application_registration=True,
                restart_after_invocations=_BURST_SIZE * 2,
            )
            launchers.append(primary)
            _wait_for_preregistration(layout)
            burst = [_launch(layout) for _index in range(_BURST_SIZE)]
            launchers.extend(burst)
            _release_application_registration(layout)
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

            _terminate_supervisor_and_child(replacement, replacement_pid)
            previous_state_pid = replacement_pid
            prewindow_supervisor = _launch(
                layout,
                gate_window_construction=True,
            )
            launchers.append(prewindow_supervisor)
            prewindow_child_pid = _wait_for_prewindow_phase(layout)
            prewindow_forwarder = _launch(layout)
            launchers.append(prewindow_forwarder)
            _wait_for_clean_exits((prewindow_forwarder,))
            _release_window_construction(layout)
            registered_prewindow_pid = _wait_for_new_app_pid(
                layout,
                previous_pid=previous_state_pid,
                supervisor=prewindow_supervisor,
            )
            if registered_prewindow_pid != prewindow_child_pid:
                raise AssertionError(
                    "Window-construction gate changed child identity before paint."
                )
            _wait_for_invocation_count(layout, 1)
            prewindow_surface = _wait_for_presented_surface(layout)
            _wait_for_splash_hosts_exit(layout)
            _assert_single_child(layout, registered_prewindow_pid)
            evidence["registered_before_window"] = {
                "child_pid": registered_prewindow_pid,
                "forwarder_exit_code": prewindow_forwarder.returncode,
                "presented_surface": prewindow_surface,
                "supervisor_pid": prewindow_supervisor.pid,
            }
            _terminate_supervisor_and_child(
                prewindow_supervisor,
                registered_prewindow_pid,
            )
            previous_state_pid = registered_prewindow_pid
            state_results: dict[str, object] = {}
            for initial_state in ("hidden", "minimized", "offscreen"):
                state_supervisor = _launch(
                    layout,
                    initial_window_state=initial_state,
                )
                launchers.append(state_supervisor)
                state_child_pid = _wait_for_new_app_pid(
                    layout,
                    previous_pid=previous_state_pid,
                    supervisor=state_supervisor,
                )
                forwarder = _launch(layout)
                launchers.append(forwarder)
                _wait_for_clean_exits((forwarder,))
                state_surface = _wait_for_presented_surface(layout)
                _wait_for_splash_hosts_exit(layout)
                _assert_single_child(layout, state_child_pid)
                state_results[initial_state] = {
                    "child_pid": state_child_pid,
                    "forwarder_exit_code": forwarder.returncode,
                    "presented_surface": state_surface,
                    "supervisor_pid": state_supervisor.pid,
                }
                _terminate_supervisor_and_child(
                    state_supervisor,
                    state_child_pid,
                )
                previous_state_pid = state_child_pid
            evidence["window_state_recovery"] = state_results

            clear_splash_qualification_records(layout)
            application_preregistration_claim_path(layout.root).unlink(missing_ok=True)
            splash_crash_supervisor = _launch(
                layout,
                gate_application_registration=True,
            )
            launchers.append(splash_crash_supervisor)
            _wait_for_preregistration(layout)
            crashed_splash_pid = _wait_for_splash_host_pid(layout)
            psutil.Process(crashed_splash_pid).kill()
            _wait_for_process_exit(crashed_splash_pid)
            abandoned_forwarder = _launch(layout)
            launchers.append(abandoned_forwarder)
            _wait_for_forwarder_acceptance(layout, abandoned_forwarder.pid)
            psutil.Process(abandoned_forwarder.pid).kill()
            _wait_for_process_exit(abandoned_forwarder.pid)
            surviving_forwarder = _launch(layout)
            launchers.append(surviving_forwarder)
            _release_application_registration(layout)
            splash_crash_child_pid = _wait_for_new_app_pid(
                layout,
                previous_pid=previous_state_pid,
                supervisor=splash_crash_supervisor,
            )
            _wait_for_clean_exits((surviving_forwarder,))
            _wait_for_invocation_count(layout, 2)
            splash_crash_surface = _wait_for_presented_surface(
                layout,
                expected_invocation_count=2,
            )
            _assert_single_child(layout, splash_crash_child_pid)
            evidence["splash_crash_and_dropped_acknowledgement"] = {
                "abandoned_forwarder_pid": abandoned_forwarder.pid,
                "application_pid": splash_crash_child_pid,
                "crashed_splash_pid": crashed_splash_pid,
                "forwarded_invocation_count": 2,
                "presented_surface": splash_crash_surface,
                "surviving_forwarder_exit_code": surviving_forwarder.returncode,
                "supervisor_pid": splash_crash_supervisor.pid,
            }
            _terminate_supervisor_and_child(
                splash_crash_supervisor,
                splash_crash_child_pid,
            )
            application_prewindow_marker_path(layout.root).unlink(missing_ok=True)
            application_prewindow_release_path(layout.root).unlink(missing_ok=True)
            child_crash_supervisor = _launch(
                layout,
                gate_window_construction=True,
            )
            launchers.append(child_crash_supervisor)
            crashed_child_pid = _wait_for_prewindow_phase(layout)
            psutil.Process(crashed_child_pid).kill()
            _wait_for_process_exit(crashed_child_pid)
            repair_child_pid = _wait_for_replacement_broker_child(
                layout,
                owner_pid=child_crash_supervisor.pid,
                previous_child_pid=crashed_child_pid,
            )
            _wait_for_splash_hosts_exit(layout)
            repair_forwarder = _launch(layout)
            launchers.append(repair_forwarder)
            _wait_for_clean_exits((repair_forwarder,))
            repair_surface = _wait_for_forwarder_surface(
                layout,
                requester_pid=repair_forwarder.pid,
                expected_surface="LauncherMainWindow",
            )
            _terminate_supervisor_and_child(
                child_crash_supervisor,
                repair_child_pid,
            )
            child_crash_replacement = _launch(layout)
            launchers.append(child_crash_replacement)
            replacement_child_pid = _wait_for_new_app_pid(
                layout,
                previous_pid=crashed_child_pid,
                supervisor=child_crash_replacement,
            )
            child_crash_forwarder = _launch(layout)
            launchers.append(child_crash_forwarder)
            _wait_for_clean_exits((child_crash_forwarder,))
            _wait_for_invocation_count(layout, 1)
            child_crash_surface = _wait_for_presented_surface(layout)
            _assert_single_child(layout, replacement_child_pid)
            evidence["child_crash_recovery"] = {
                "crashed_child_pid": crashed_child_pid,
                "departed_supervisor_pid": child_crash_supervisor.pid,
                "repair_forwarder_exit_code": repair_forwarder.returncode,
                "repair_surface": repair_surface,
                "repair_ui_pid": repair_child_pid,
                "replacement_forwarder_exit_code": child_crash_forwarder.returncode,
                "presented_surface": child_crash_surface,
                "replacement_child_pid": replacement_child_pid,
                "replacement_supervisor_pid": child_crash_replacement.pid,
            }
            _terminate_supervisor_and_child(
                child_crash_replacement,
                replacement_child_pid,
            )
            graceful_supervisor = _launch(layout, exit_after_invocations=1)
            launchers.append(graceful_supervisor)
            graceful_child_pid = _wait_for_new_app_pid(
                layout,
                previous_pid=replacement_child_pid,
                supervisor=graceful_supervisor,
            )
            graceful_forwarder = _launch(layout)
            launchers.append(graceful_forwarder)
            _wait_for_clean_exits((graceful_forwarder, graceful_supervisor))
            _wait_for_process_exit(graceful_child_pid)
            evidence["graceful_shutdown"] = {
                "application_pid": graceful_child_pid,
                "forwarder_exit_code": graceful_forwarder.returncode,
                "supervisor_exit_code": graceful_supervisor.returncode,
                "supervisor_pid": graceful_supervisor.pid,
            }
            _assert_no_live_ownership_files(layout)
            evidence["native_ownership"] = {
                "created_live_ownership_files": [],
                "election": "first-local-named-pipe-instance",
                "peer_scope": "same-user-session",
                "remote_clients": "rejected",
            }
            evidence["launcher_log"] = audit_launcher_log(layout)
            _capture_success_diagnostics(layout, artifact_dir)
            evidence["launcher_surfaces"] = qualify_launcher_surfaces(
                launcher_bundle=arguments.launcher_bundle.resolve(),
                temporary_root=Path(temporary),
                artifact_dir=artifact_dir,
            )
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
    gate_application_registration: bool = False,
    restart_after_invocations: int | None = None,
    exit_after_invocations: int | None = None,
    initial_window_state: str | None = None,
    gate_window_construction: bool = False,
) -> subprocess.Popen[bytes]:
    """Start one packaged launcher invocation without desktop surfaces."""

    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment[SPLASH_SURFACE_EVIDENCE_ENV] = "1"
    environment["SUGAR_SUBSTITUTE_SPLASH_REQUESTED_MONOTONIC_NS"] = str(
        time.monotonic_ns()
    )
    if gate_application_registration:
        environment[APPLICATION_REGISTRATION_GATE_ENV] = "1"
    if restart_after_invocations is not None:
        environment[APPLICATION_RESTART_AFTER_INVOCATIONS_ENV] = str(
            restart_after_invocations
        )
    if exit_after_invocations is not None:
        environment[APPLICATION_EXIT_AFTER_INVOCATIONS_ENV] = str(
            exit_after_invocations
        )
    if initial_window_state is not None:
        environment[APPLICATION_INITIAL_WINDOW_STATE_ENV] = initial_window_state
    if gate_window_construction:
        environment[APPLICATION_WINDOW_CONSTRUCTION_GATE_ENV] = "1"
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


def _release_application_registration(layout: InstallLayout) -> None:
    """Release one child waiting before supervisor registration."""

    application_preregistration_release_path(layout.root).write_text(
        "release",
        encoding="utf-8",
    )


def _wait_for_prewindow_phase(layout: InstallLayout) -> int:
    """Require a registered child that has not constructed its first window."""

    marker_path = application_prewindow_marker_path(layout.root)

    def child_pid() -> int | None:
        try:
            payload = json.loads(marker_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None
        pid = payload.get("pid") if isinstance(payload, dict) else None
        return pid if isinstance(pid, int) and psutil.pid_exists(pid) else None

    return _wait_for_value(
        child_pid,
        description="registered pre-window application phase",
    )


def _release_window_construction(layout: InstallLayout) -> None:
    """Release one child waiting at the explicit pre-window phase gate."""

    application_prewindow_release_path(layout.root).write_text(
        "release",
        encoding="utf-8",
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


if __name__ == "__main__":
    raise SystemExit(main())

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

"""Drive packaged setup UI and require process-bound splash-to-shell evidence."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState
from sugarsubstitute_shared.application_readiness import (
    READINESS_PATH_ENV,
    READINESS_TOKEN_ENV,
    ApplicationReadinessReceipt,
    ApplicationReadinessSurface,
)
from sugarsubstitute_shared.installer_qualification import (
    INSTALLER_QUALIFICATION_PLAN_ENV,
    InstallerQualificationPlan,
)
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError
from tools.ci.managed_comfy_qualification import assert_real_managed_comfy

_INSTALL_TIMEOUT_SECONDS = 3_600.0
_LAUNCH_TIMEOUT_SECONDS = 600.0
_REQUIRED_STARTUP_EVENTS = (
    "launch_splash.started",
    "launch_splash.closed",
    "main_shell.shown",
)


@dataclass(frozen=True, slots=True)
class InstallerQualificationEvidence:
    """Own paths and identity for one installer-to-main-shell proof."""

    environment: dict[str, str]
    readiness_path: Path
    trace_path: Path
    event_log_path: Path
    token: str
    plan: InstallerQualificationPlan


def prepare_qualification_evidence(
    *,
    install_root: Path,
    expected_version: str,
    endpoint_port: int,
    phase: str,
) -> InstallerQualificationEvidence:
    """Build inherited automation and readiness state for one continuous chain."""

    resolved_root = install_root.resolve()
    layout = InstallLayout.from_root(resolved_root)
    readiness_path = layout.launcher_dir / "readiness" / "ci-installer-chain.json"
    trace_path = (
        layout.root / "appdata" / "diagnostics" / "logs" / "startup-trace.jsonl"
    )
    event_log_path = resolved_root.parent / (
        f".{resolved_root.name}-{phase}-installer-qualification.jsonl"
    )
    readiness_path.unlink(missing_ok=True)
    trace_path.unlink(missing_ok=True)
    event_log_path.unlink(missing_ok=True)
    token = f"ci-installer-{phase}-{expected_version}-{os.getpid()}"
    plan = InstallerQualificationPlan(
        token=token,
        install_root=resolved_root,
        endpoint_host="127.0.0.1",
        endpoint_port=endpoint_port,
        event_log_path=event_log_path,
        timeout_seconds=_INSTALL_TIMEOUT_SECONDS,
        target_mode="managed_local",
        managed_workspace_path=resolved_root / "comfyui",
        managed_model_root=resolved_root / "qualified-models",
    )
    environment = dict(os.environ)
    environment[READINESS_PATH_ENV] = str(readiness_path)
    environment[READINESS_TOKEN_ENV] = token
    environment[INSTALLER_QUALIFICATION_PLAN_ENV] = plan.to_json()
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")
    return InstallerQualificationEvidence(
        environment=environment,
        readiness_path=readiness_path,
        trace_path=trace_path,
        event_log_path=event_log_path,
        token=token,
        plan=plan,
    )


def run_current_installer_ui(
    *,
    installer_path: Path,
    install_root: Path,
    manifest_url: str | None,
    environment: dict[str, str],
) -> None:
    """Launch packaged setup normally and let its real Install action run."""

    command = [
        str(installer_path.resolve()),
        f"--install-root={install_root.resolve()}",
    ]
    if manifest_url is not None:
        command.append(f"--manifest-url={manifest_url}")
    result = subprocess.run(
        command,
        cwd=installer_path.resolve().parent,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_INSTALL_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0:
        raise InstallerLifecycleError(
            f"Installer UI exited with {result.returncode}.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def launch_installed_candidate(
    *,
    install_root: Path,
    environment: dict[str, str],
) -> None:
    """Launch a historical install so it updates and continues onboarding."""

    layout = InstallLayout.from_root(install_root)
    result = subprocess.run(
        [str(layout.executable_path)],
        cwd=layout.root,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_LAUNCH_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0:
        raise InstallerLifecycleError(
            f"Installed launcher exited with {result.returncode}.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def verify_main_shell_evidence(
    *,
    install_root: Path,
    expected_version: str,
    evidence: InstallerQualificationEvidence,
    required_qualification_events: tuple[str, ...],
    require_governed_setup_record: bool = True,
) -> None:
    """Require UI events, installed version, splash sequence, and main shell."""

    receipt = _wait_for_readiness_receipt(
        readiness_path=evidence.readiness_path,
        token=evidence.token,
        timeout_seconds=_LAUNCH_TIMEOUT_SECONDS,
    )
    try:
        assert_installed_version(install_root, expected_version)
        if required_qualification_events:
            assert_qualification_event_sequence(
                evidence.event_log_path,
                token=evidence.token,
                required_events=required_qualification_events,
            )
        assert_startup_trace_sequence(evidence.trace_path)
        assert_real_managed_comfy(
            install_root=install_root,
            plan=evidence.plan,
            require_governed_setup_record=require_governed_setup_record,
        )
    finally:
        terminate_verified_process(receipt.pid)


def available_loopback_port() -> int:
    """Reserve and release one loopback port for the managed Comfy launch."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def assert_installed_version(install_root: Path, expected_version: str) -> None:
    """Require both launcher state and app source to identify the expected release."""

    layout = InstallLayout.from_root(install_root)
    state = LauncherUpdateState.load(layout.state_path)
    if state.installed_app_version != expected_version:
        raise InstallerLifecycleError(
            "Launcher state version mismatch: "
            f"{state.installed_app_version} != {expected_version}."
        )
    expected_line = f'__version__ = "{expected_version}"'
    version_path = layout.app_dir / "substitute" / "_version.py"
    if expected_line not in version_path.read_text(encoding="utf-8"):
        raise InstallerLifecycleError(
            f"Installed app source does not identify version {expected_version}."
        )


def assert_qualification_event_sequence(
    event_log_path: Path,
    *,
    token: str,
    required_events: tuple[str, ...],
) -> None:
    """Require token-bound production UI interactions in their expected order."""

    try:
        lines = event_log_path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()
    except OSError as error:
        raise InstallerLifecycleError(
            f"Installer did not write its UI qualification log: {event_log_path}."
        ) from error
    events: list[str] = []
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as error:
            raise InstallerLifecycleError(
                f"Installer wrote malformed UI qualification JSON: {event_log_path}."
            ) from error
        if not isinstance(payload, dict) or payload.get("token") != token:
            raise InstallerLifecycleError(
                "Installer UI qualification evidence did not match this CI run."
            )
        event = payload.get("event")
        if isinstance(event, str):
            events.append(event)
    if not _contains_ordered_events(events, required_events):
        raise InstallerLifecycleError(
            "Installer UI did not complete the required interaction sequence: "
            + " -> ".join(required_events)
            + ".\n"
            + diagnostic_tail(event_log_path)
        )


def terminate_verified_process(pid: int) -> None:
    """Terminate only the token-verified app process and its child processes."""

    if os.name == "nt":
        result = subprocess.run(
            ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
        if result.returncode not in {0, 128} and _windows_process_exists(pid):
            raise InstallerLifecycleError(
                f"Could not terminate verified app process {pid}: "
                + result.stderr.decode("utf-8", errors="replace")
            )
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return


def diagnostic_tail(path: Path, *, maximum_lines: int = 80) -> str:
    """Return a bounded diagnostic suffix when a qualification step fails."""

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return f"<missing diagnostics: {path}>"
    return "\n".join(lines[-maximum_lines:])


def _wait_for_readiness_receipt(
    *,
    readiness_path: Path,
    token: str,
    timeout_seconds: float,
) -> ApplicationReadinessReceipt:
    """Wait for a token-bound main-shell receipt or surface diagnostics."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if readiness_path.is_file():
            try:
                payload = json.loads(readiness_path.read_text(encoding="utf-8"))
                receipt = ApplicationReadinessReceipt.from_json(payload)
            except (OSError, json.JSONDecodeError, ValueError) as error:
                raise InstallerLifecycleError(
                    f"Application wrote an invalid readiness receipt: {readiness_path}."
                ) from error
            if receipt.token != token:
                raise InstallerLifecycleError(
                    "Application readiness receipt did not match this CI launch."
                )
            if receipt.surface is ApplicationReadinessSurface.ONBOARDING:
                time.sleep(0.1)
                continue
            if receipt.surface is not ApplicationReadinessSurface.MAIN_SHELL:
                raise InstallerLifecycleError(
                    "Application revealed the wrong surface: "
                    f"{receipt.surface.value} != main_shell."
                )
            return receipt
        time.sleep(0.1)
    layout_root = readiness_path.parents[2]
    raise InstallerLifecycleError(
        "Application did not reveal a post-splash window before timeout.\n"
        + diagnostic_tail(layout_root / "launcher" / "logs" / "app-startup.log")
        + "\n"
        + diagnostic_tail(
            layout_root.parent
            / "appdata"
            / "diagnostics"
            / "logs"
            / "startup-trace.jsonl"
        )
    )


def assert_startup_trace_sequence(trace_path: Path) -> None:
    """Require splash start, splash close, then main-shell reveal in that order."""

    try:
        lines = trace_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as error:
        raise InstallerLifecycleError(
            f"Button-launched child did not write its startup trace: {trace_path}."
        ) from error
    events: list[str] = []
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as error:
            raise InstallerLifecycleError(
                f"Button-launched child wrote malformed startup trace JSON: {trace_path}."
            ) from error
        if isinstance(payload, dict) and isinstance(payload.get("event"), str):
            events.append(payload["event"])
    if not _contains_ordered_events(events, _REQUIRED_STARTUP_EVENTS):
        raise InstallerLifecycleError(
            "Open Substitute did not complete the required splash-to-shell sequence: "
            + " -> ".join(_REQUIRED_STARTUP_EVENTS)
            + ".\n"
            + diagnostic_tail(trace_path)
        )


def _contains_ordered_events(
    events: list[str],
    required_events: tuple[str, ...],
) -> bool:
    """Return whether every required event appears in order."""

    if not required_events:
        return True
    next_index = 0
    for event in events:
        if event == required_events[next_index]:
            next_index += 1
            if next_index == len(required_events):
                return True
    return False


def _windows_process_exists(pid: int) -> bool:
    """Return whether a Windows process still owns the supplied identifier."""

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    handle = kernel32.OpenProcess(0x1000, 0, pid)
    if handle:
        kernel32.CloseHandle(handle)
        return True
    return ctypes.get_last_error() == 5


__all__ = [
    "InstallerQualificationEvidence",
    "assert_installed_version",
    "assert_qualification_event_sequence",
    "assert_startup_trace_sequence",
    "available_loopback_port",
    "diagnostic_tail",
    "launch_installed_candidate",
    "prepare_qualification_evidence",
    "run_current_installer_ui",
    "terminate_verified_process",
    "verify_main_shell_evidence",
]

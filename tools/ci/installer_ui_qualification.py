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
import socket
import subprocess
import sys
import time

import psutil  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher.install_layout import (
    InstallLayout,
    default_install_root,
)
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
_LAUNCH_PROGRESS_TIMEOUT_SECONDS = 120.0
_MANAGED_COMFY_OUTPUT_LOG_ENV = "SUGAR_SUBSTITUTE_STARTUP_HARNESS_COMFY_OUTPUT_LOG"
_TERMINAL_STARTUP_FAILURE_EVENTS = frozenset(
    {
        "startup.gui_task.failure",
        "startup.managed.failure",
    }
)
_PROCESS_TERMINATION_TIMEOUT_SECONDS = 10.0
_REQUIRED_STARTUP_EVENTS = (
    "launch_splash.started",
    "launch_splash.closed",
    "main_shell.shown",
)
_FROZEN_LAUNCH_OVERRIDE_VARIABLES = (
    "PYTHONHOME",
    "PYTHONPATH",
    "LD_LIBRARY_PATH",
    "LD_LIBRARY_PATH_ORIG",
    "DYLD_LIBRARY_PATH",
    "DYLD_LIBRARY_PATH_ORIG",
    "DYLD_FALLBACK_LIBRARY_PATH",
    "DYLD_FRAMEWORK_PATH",
    "QT_PLUGIN_PATH",
    "QML2_IMPORT_PATH",
    "QML_IMPORT_PATH",
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


@dataclass(frozen=True, slots=True)
class InstalledCandidateLaunch:
    """Bind an installed-launcher process to its durable diagnostic output."""

    process: subprocess.Popen[bytes]
    output_path: Path
    progress_baselines: tuple[tuple[Path, tuple[bool, int]], ...] = ()


def prepare_qualification_evidence(
    *,
    install_root: Path,
    expected_version: str,
    endpoint_port: int,
    phase: str,
    timeout_seconds: float = _INSTALL_TIMEOUT_SECONDS,
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
        timeout_seconds=timeout_seconds,
        target_mode="managed_local",
        managed_workspace_path=resolved_root / "comfyui",
        managed_model_root=resolved_root / "qualified-models",
        force_cpu_mode=sys.platform != "darwin",
    )
    environment = dict(os.environ)
    environment[READINESS_PATH_ENV] = str(readiness_path)
    environment[READINESS_TOKEN_ENV] = token
    environment[INSTALLER_QUALIFICATION_PLAN_ENV] = plan.to_json()
    environment[_MANAGED_COMFY_OUTPUT_LOG_ENV] = str(
        layout.root / "managed-comfy-startup.log"
    )
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
    timeout_seconds: float = _INSTALL_TIMEOUT_SECONDS,
) -> None:
    """Launch packaged setup normally and let its real Install action run."""

    command = [
        str(installer_path.resolve()),
        f"--install-root={install_root.resolve()}",
    ]
    if manifest_url is not None:
        command.append(f"--manifest-url={manifest_url}")
    try:
        result = subprocess.run(
            command,
            cwd=installer_path.resolve().parent,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        diagnostics = _installer_failure_diagnostics(
            install_root=install_root,
            environment=environment,
        )
        raise InstallerLifecycleError(
            f"Installer UI did not complete within {timeout_seconds:g} seconds.\n"
            f"stdout:\n{_timeout_output(error.stdout)}\n"
            f"stderr:\n{_timeout_output(error.stderr)}\n"
            f"{diagnostics}"
        ) from error
    if result.returncode != 0:
        diagnostics = _installer_failure_diagnostics(
            install_root=install_root,
            environment=environment,
        )
        raise InstallerLifecycleError(
            f"Installer UI exited with {result.returncode}.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}\n"
            f"{diagnostics}"
        )


def _installer_failure_diagnostics(
    *,
    install_root: Path,
    environment: dict[str, str],
) -> str:
    """Expose token-bound UI events and launcher logs after a failed install."""

    plan = InstallerQualificationPlan.from_environment(environment)
    event_log = (
        diagnostic_tail(plan.event_log_path)
        if plan is not None
        else "Qualification plan was not inherited."
    )
    launcher_log = diagnostic_tail(
        InstallLayout.from_root(install_root).logs_dir / "launcher.log"
    )
    return f"qualification events:\n{event_log}\nlauncher log:\n{launcher_log}"


def launch_installed_candidate(
    *,
    install_root: Path,
    environment: dict[str, str],
    progress_paths: tuple[Path | None, ...] = (),
) -> InstalledCandidateLaunch:
    """Launch a historical install and return immediately for evidence polling."""

    layout = InstallLayout.from_root(install_root)
    output_path = layout.logs_dir / "candidate-update-launch.log"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    launch_environment = _external_frozen_launch_environment(environment)
    observed_progress_paths = (
        layout.logs_dir / "launcher.log",
        layout.logs_dir / "launcher-update.log",
        layout.logs_dir / "app-startup.log",
        *(path for path in progress_paths if path is not None),
    )
    progress_baselines = tuple(
        (path, _path_signature(path)) for path in observed_progress_paths
    )
    with output_path.open("wb") as output:
        process = subprocess.Popen(
            [str(layout.executable_path)],
            cwd=layout.root,
            env=launch_environment,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=output,
            close_fds=True,
            start_new_session=os.name != "nt",
        )
    return InstalledCandidateLaunch(
        process=process,
        output_path=output_path,
        progress_baselines=progress_baselines,
    )


def _external_frozen_launch_environment(
    environment: dict[str, str],
) -> dict[str, str]:
    """Remove host Python and frozen-runtime overrides from a packaged launch."""

    launch_environment = dict(environment)
    for variable_name in _FROZEN_LAUNCH_OVERRIDE_VARIABLES:
        launch_environment.pop(variable_name, None)
    for variable_name in tuple(launch_environment):
        if variable_name.startswith("_PYI_"):
            launch_environment.pop(variable_name, None)
    return launch_environment


def verify_main_shell_evidence(
    *,
    install_root: Path,
    expected_version: str,
    evidence: InstallerQualificationEvidence,
    required_qualification_events: tuple[str, ...],
    require_governed_setup_record: bool = True,
    candidate_launch: InstalledCandidateLaunch | None = None,
    expected_main_pid: int | None = None,
    additional_diagnostic_paths: tuple[Path | None, ...] = (),
    timeout_seconds: float | None = None,
) -> None:
    """Require UI events, installed version, splash sequence, and main shell."""

    receipt: ApplicationReadinessReceipt | None = None
    try:
        receipt = _wait_for_readiness_receipt(
            readiness_path=evidence.readiness_path,
            token=evidence.token,
            timeout_seconds=(
                evidence.plan.timeout_seconds
                if timeout_seconds is None
                else timeout_seconds
            ),
            candidate_launch=candidate_launch,
            trace_path=evidence.trace_path,
            diagnostic_paths=_evidence_diagnostic_paths(
                install_root=install_root,
                evidence=evidence,
                candidate_launch=candidate_launch,
                additional_paths=additional_diagnostic_paths,
            ),
        )
        if expected_main_pid is not None and receipt.pid != expected_main_pid:
            raise InstallerLifecycleError(
                "The completion action and readiness receipt identified different "
                f"main-shell processes: {expected_main_pid} != {receipt.pid}."
            )
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
        if receipt is not None:
            terminate_verified_process(receipt.pid)
        if candidate_launch is not None and candidate_launch.process.poll() is None:
            terminate_verified_process(candidate_launch.process.pid)


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
    _terminate_posix_process_tree(pid)


def _terminate_posix_process_tree(pid: int) -> None:
    """Stop and reap one verified POSIX process tree before the next launch."""

    try:
        root = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    except psutil.AccessDenied as error:
        raise InstallerLifecycleError(
            f"Could not inspect verified app process {pid} for cleanup."
        ) from error

    try:
        processes = tuple(root.children(recursive=True)) + (root,)
    except psutil.NoSuchProcess:
        return
    except psutil.AccessDenied as error:
        raise InstallerLifecycleError(
            f"Could not inspect children of verified app process {pid}."
        ) from error

    inaccessible: list[int] = []
    for process in processes:
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            inaccessible.append(process.pid)
    _, alive = psutil.wait_procs(
        processes,
        timeout=_PROCESS_TERMINATION_TIMEOUT_SECONDS / 2,
    )
    for process in alive:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            inaccessible.append(process.pid)
    _, remaining = psutil.wait_procs(
        alive,
        timeout=_PROCESS_TERMINATION_TIMEOUT_SECONDS / 2,
    )
    if inaccessible or remaining:
        unresolved = sorted(
            set(inaccessible).union(process.pid for process in remaining)
        )
        raise InstallerLifecycleError(
            "Could not terminate verified app process tree: "
            + ", ".join(str(process_id) for process_id in unresolved)
            + "."
        )


def diagnostic_tail(path: Path, *, maximum_lines: int = 80) -> str:
    """Return a bounded diagnostic suffix when a qualification step fails."""

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return f"<missing diagnostics: {path}>"
    return "\n".join(lines[-maximum_lines:])


def _timeout_output(output: bytes | str | None) -> str:
    """Render bounded subprocess timeout output without losing byte diagnostics."""

    if output is None:
        return "<no output>"
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output


def _wait_for_readiness_receipt(
    *,
    readiness_path: Path,
    token: str,
    timeout_seconds: float,
    candidate_launch: InstalledCandidateLaunch | None = None,
    trace_path: Path | None = None,
    diagnostic_paths: tuple[Path, ...] = (),
) -> ApplicationReadinessReceipt:
    """Wait for a token-bound main-shell receipt or surface diagnostics."""

    started_at = time.monotonic()
    deadline = started_at + timeout_seconds
    launch_progress_deadline = min(
        deadline,
        started_at + _LAUNCH_PROGRESS_TIMEOUT_SECONDS,
    )
    trace_offset = 0
    while (now := time.monotonic()) < deadline:
        if candidate_launch is not None:
            return_code = candidate_launch.process.poll()
            if return_code not in {None, 0}:
                raise InstallerLifecycleError(
                    f"Installed launcher exited with {return_code} before the "
                    "main-shell receipt.\n"
                    + diagnostic_tail(candidate_launch.output_path)
                )
            if now >= launch_progress_deadline and not installed_launch_has_progress(
                candidate_launch
            ):
                diagnostics = "\n\n".join(
                    f"{path}:\n{diagnostic_tail(path)}" for path in diagnostic_paths
                )
                process_diagnostics = process_tree_diagnostics(
                    candidate_launch.process.pid
                )
                raise InstallerLifecycleError(
                    "Installed launcher did not begin its configured update or "
                    "application handoff within 120 seconds. "
                    f"Launcher PID: {candidate_launch.process.pid}; "
                    f"return code: {return_code}.\n"
                    f"process tree:\n{process_diagnostics}\n\n{diagnostics}"
                )
        if trace_path is not None:
            trace_offset, terminal_event = _read_terminal_startup_failure(
                trace_path,
                offset=trace_offset,
            )
            if terminal_event is not None:
                diagnostics = "\n\n".join(
                    f"{path}:\n{diagnostic_tail(path)}" for path in diagnostic_paths
                )
                raise InstallerLifecycleError(
                    "Application reported a terminal startup failure before the "
                    f"main-shell receipt: {terminal_event}.\n{diagnostics}"
                )
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
    diagnostics = "\n\n".join(
        f"{path}:\n{diagnostic_tail(path)}" for path in diagnostic_paths
    )
    raise InstallerLifecycleError(
        "Application did not reveal a post-splash window before timeout.\n"
        + diagnostics
    )


def _read_terminal_startup_failure(
    trace_path: Path,
    *,
    offset: int,
) -> tuple[int, str | None]:
    """Read new trace records and return the first terminal failure event."""

    try:
        with trace_path.open(encoding="utf-8", errors="replace") as trace:
            trace.seek(offset)
            while True:
                line = trace.readline()
                if not line:
                    return trace.tell(), None
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event = payload.get("event") if isinstance(payload, dict) else None
                if event in _TERMINAL_STARTUP_FAILURE_EVENTS:
                    return trace.tell(), str(event)
    except OSError:
        return offset, None


def _evidence_diagnostic_paths(
    *,
    install_root: Path,
    evidence: InstallerQualificationEvidence,
    candidate_launch: InstalledCandidateLaunch | None,
    additional_paths: tuple[Path | None, ...] = (),
) -> tuple[Path, ...]:
    """Return authoritative logs for one installed splash-to-shell chain."""

    layout = InstallLayout.from_root(install_root)
    paths = [
        evidence.event_log_path,
        layout.logs_dir / "launcher.log",
        layout.logs_dir / "launcher-update.log",
        layout.logs_dir / "app-startup.log",
        evidence.trace_path,
        layout.appdata_dir / "diagnostics" / "logs" / "sugarsubstitute.log",
        layout.appdata_dir / "runtime_state" / "setup_transaction.json",
        layout.root / "managed-comfy-startup.log",
    ]
    inferred_default_log = (
        default_install_root(layout.executable_path)
        / "launcher"
        / "logs"
        / "launcher.log"
    )
    if inferred_default_log != layout.logs_dir / "launcher.log":
        paths.append(inferred_default_log)
    paths.extend(path for path in additional_paths if path is not None)
    if candidate_launch is not None:
        paths.insert(0, candidate_launch.output_path)
    return tuple(paths)


def installed_launch_has_progress(launch: InstalledCandidateLaunch) -> bool:
    """Return whether the installed launcher touched any owned handoff evidence."""

    return any(
        _path_signature(path) != baseline
        for path, baseline in launch.progress_baselines
    )


def process_tree_diagnostics(pid: int) -> str:
    """Render bounded non-secret identity for one qualification process tree."""

    try:
        root = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return f"<launcher process {pid} already exited>"
    except psutil.AccessDenied:
        return f"<launcher process {pid} could not be inspected>"
    try:
        processes = (root, *root.children(recursive=True))
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        processes = (root,)
    records: list[dict[str, object]] = []
    for process in processes:
        try:
            opened_files = [
                str(open_file.path) for open_file in process.open_files()[:20]
            ]
            mapped_runtime_paths = sorted(
                {
                    str(memory_map.path)
                    for memory_map in process.memory_maps(grouped=True)
                    if _is_relevant_runtime_mapping(str(memory_map.path))
                }
            )[:60]
            records.append(
                {
                    "cmdline": [str(argument) for argument in process.cmdline()],
                    "cpu_times": [float(value) for value in process.cpu_times()[:4]],
                    "cwd": str(process.cwd()),
                    "exe": str(process.exe()),
                    "mapped_runtime_paths": mapped_runtime_paths,
                    "name": str(process.name()),
                    "num_threads": int(process.num_threads()),
                    "open_files": opened_files,
                    "pid": int(process.pid),
                    "ppid": int(process.ppid()),
                    "status": str(process.status()),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            records.append({"pid": int(process.pid), "status": "unavailable"})
    return json.dumps(records, indent=2, sort_keys=True)


def _is_relevant_runtime_mapping(path: str) -> bool:
    """Return whether one mapped file identifies the frozen startup subsystem."""

    normalized = path.casefold()
    return any(
        marker in normalized
        for marker in (
            "python",
            "pyside",
            "qt6",
            "libqt",
            "ssl",
            "truststore",
        )
    )


def _path_signature(path: Path) -> tuple[bool, int]:
    """Return a race-tolerant existence and size signature for one evidence file."""

    try:
        return True, path.stat().st_size
    except OSError:
        return False, 0


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
    "InstalledCandidateLaunch",
    "InstallerQualificationEvidence",
    "assert_installed_version",
    "assert_qualification_event_sequence",
    "assert_startup_trace_sequence",
    "available_loopback_port",
    "diagnostic_tail",
    "installed_launch_has_progress",
    "launch_installed_candidate",
    "prepare_qualification_evidence",
    "process_tree_diagnostics",
    "run_current_installer_ui",
    "terminate_verified_process",
    "verify_main_shell_evidence",
]

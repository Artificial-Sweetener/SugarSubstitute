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

"""Terminate managed-local Comfy subprocesses and normalize shutdown facts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from time import monotonic, sleep
import subprocess

from sugarsubstitute_shared.localization import ApplicationText, app_text

from substitute.infrastructure.comfy.managed_process_containment import (
    ManagedProcessHandle,
)
from substitute.infrastructure.comfy.managed_process_metadata import (
    ManagedProcessMetadata,
)
from substitute.infrastructure.comfy.managed_process_probe import is_process_running
from substitute.shared.logging.logger import (
    get_logger,
    log_exception,
    log_info,
    log_warning,
)

_LOGGER = get_logger("infrastructure.comfy.managed_shutdown")
_PROCESS_EXIT_TIMEOUT_SECONDS = 5.0
_WINDOWS_TASKKILL_TIMEOUT_SECONDS = 5.0


class ManagedProcessTerminationStatus(Enum):
    """Describe the normalized result of one managed-process termination attempt."""

    NO_ACTION_REQUIRED = "no_action_required"
    TERMINATED_CONFIRMED = "terminated_confirmed"
    TERMINATION_UNCONFIRMED = "termination_unconfirmed"
    TERMINATION_COMMAND_FAILED = "termination_command_failed"


@dataclass(frozen=True)
class ManagedProcessTerminationResult:
    """Describe normalized termination facts for one managed process."""

    status: ManagedProcessTerminationStatus
    pid: int | None
    attempted: bool
    verification_timed_out: bool = False
    termination_command_timed_out: bool = False
    elapsed_ms: int = 0
    user_safe_detail: ApplicationText = ""
    diagnostic_detail: str = ""


def kill_managed_comfy(
    proc: ManagedProcessHandle | None,
) -> ManagedProcessTerminationResult:
    """Terminate a running managed ComfyUI subprocess and verify it is gone."""

    if proc is None:
        return ManagedProcessTerminationResult(
            status=ManagedProcessTerminationStatus.NO_ACTION_REQUIRED,
            pid=None,
            attempted=False,
            user_safe_detail=app_text("No managed process shutdown was required."),
            diagnostic_detail="No managed process handle was available.",
        )
    if proc.poll() is not None:
        return ManagedProcessTerminationResult(
            status=ManagedProcessTerminationStatus.TERMINATED_CONFIRMED,
            pid=proc.pid,
            attempted=False,
            user_safe_detail=app_text("Shutdown finished cleanly."),
            diagnostic_detail="Managed process had already exited.",
        )
    return kill_managed_comfy_pid(proc.pid)


def kill_managed_comfy_metadata(
    metadata: ManagedProcessMetadata | None,
    *,
    containment_handle: object | None = None,
) -> ManagedProcessTerminationResult:
    """Terminate one managed ComfyUI resource using containment-aware metadata."""

    if metadata is None:
        return ManagedProcessTerminationResult(
            status=ManagedProcessTerminationStatus.NO_ACTION_REQUIRED,
            pid=None,
            attempted=False,
            user_safe_detail=app_text("No managed process shutdown was required."),
            diagnostic_detail="Managed process metadata was unavailable.",
        )
    if metadata.containment_mode == "windows_job_object":
        return _kill_windows_job_owned_process(
            metadata=metadata,
            containment_handle=containment_handle,
        )
    if metadata.containment_mode == "posix_guardian":
        return _kill_posix_guardian_owned_process(
            metadata=metadata,
            containment_handle=containment_handle,
        )
    return kill_managed_comfy_pid(metadata.pid)


def kill_managed_comfy_pid(pid: int | None) -> ManagedProcessTerminationResult:
    """Terminate a managed ComfyUI process tree by pid and verify it is gone."""

    if pid is None or pid <= 0:
        return ManagedProcessTerminationResult(
            status=ManagedProcessTerminationStatus.NO_ACTION_REQUIRED,
            pid=pid,
            attempted=False,
            user_safe_detail=app_text("No managed process shutdown was required."),
            diagnostic_detail="Managed process pid was unavailable.",
        )
    started_at = monotonic()
    log_info(_LOGGER, "Terminating ComfyUI subprocess", pid=pid, platform=os.name)
    if os.name == "nt":
        result = _kill_windows_process(pid=pid, started_at=started_at)
    else:
        result = _kill_posix_process(pid=pid, started_at=started_at)
    _log_termination_result(result)
    return result


def _kill_windows_process(
    *,
    pid: int,
    started_at: float,
) -> ManagedProcessTerminationResult:
    """Terminate one Windows process tree and normalize the result."""

    log_info(
        _LOGGER,
        "Windows taskkill invoked",
        pid=pid,
        timeout_seconds=_WINDOWS_TASKKILL_TIMEOUT_SECONDS,
    )
    try:
        command_result = subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_WINDOWS_TASKKILL_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        elapsed_ms = _elapsed_ms_since(started_at)
        log_exception(
            _LOGGER,
            "Windows taskkill timed out",
            pid=pid,
            elapsed_ms=elapsed_ms,
            taskkill_timeout=True,
        )
        return ManagedProcessTerminationResult(
            status=ManagedProcessTerminationStatus.TERMINATION_COMMAND_FAILED,
            pid=pid,
            attempted=True,
            termination_command_timed_out=True,
            elapsed_ms=elapsed_ms,
            user_safe_detail=app_text(
                "The termination command timed out before completion."
            ),
            diagnostic_detail=_format_timeout_diagnostic(error),
        )
    except OSError as error:
        elapsed_ms = _elapsed_ms_since(started_at)
        log_exception(
            _LOGGER,
            "Windows taskkill invocation failed",
            pid=pid,
            elapsed_ms=elapsed_ms,
        )
        return ManagedProcessTerminationResult(
            status=ManagedProcessTerminationStatus.TERMINATION_COMMAND_FAILED,
            pid=pid,
            attempted=True,
            elapsed_ms=elapsed_ms,
            user_safe_detail=app_text("The termination command could not be started."),
            diagnostic_detail=_format_os_error_diagnostic(error),
        )
    elapsed_ms = _elapsed_ms_since(started_at)
    terminated, verification_timed_out = _verify_process_exit(pid)
    diagnostic_detail = _format_completed_process_diagnostic(command_result)
    if command_result.returncode == 0:
        if not terminated and verification_timed_out:
            log_warning(
                _LOGGER,
                "Windows taskkill succeeded but exit verification timed out",
                pid=pid,
                verification_timeout=True,
                diagnostic_detail=diagnostic_detail,
            )
        return ManagedProcessTerminationResult(
            status=ManagedProcessTerminationStatus.TERMINATED_CONFIRMED,
            pid=pid,
            attempted=True,
            verification_timed_out=verification_timed_out,
            elapsed_ms=elapsed_ms,
            user_safe_detail=app_text("Shutdown finished cleanly."),
            diagnostic_detail=diagnostic_detail,
        )
    if terminated:
        return ManagedProcessTerminationResult(
            status=ManagedProcessTerminationStatus.TERMINATED_CONFIRMED,
            pid=pid,
            attempted=True,
            elapsed_ms=elapsed_ms,
            user_safe_detail=app_text("Shutdown finished cleanly."),
            diagnostic_detail=diagnostic_detail,
        )
    return ManagedProcessTerminationResult(
        status=ManagedProcessTerminationStatus.TERMINATION_COMMAND_FAILED,
        pid=pid,
        attempted=True,
        verification_timed_out=verification_timed_out,
        elapsed_ms=elapsed_ms,
        user_safe_detail=app_text(
            "The termination command did not complete successfully."
        ),
        diagnostic_detail=diagnostic_detail,
    )


def _kill_windows_job_owned_process(
    *,
    metadata: ManagedProcessMetadata,
    containment_handle: object | None,
) -> ManagedProcessTerminationResult:
    """Terminate one live Windows job-owned child through its owning job handle."""

    from substitute.infrastructure.comfy.windows_job_containment import (
        WindowsJobContainmentHandle,
        close_job_containment_handle,
    )

    if not isinstance(containment_handle, WindowsJobContainmentHandle):
        return kill_managed_comfy_pid(metadata.pid)
    started_at = monotonic()
    log_info(
        _LOGGER,
        "Explicit contained shutdown requested",
        containment_mode=metadata.containment_mode,
        termination_phase="job_close_requested",
        owner_pid=metadata.owner_pid,
        managed_pid=metadata.pid,
        job_name=metadata.job_name,
    )
    close_job_containment_handle(containment_handle)
    terminated, verification_timed_out = _verify_process_exit(metadata.pid)
    result = ManagedProcessTerminationResult(
        status=(
            ManagedProcessTerminationStatus.TERMINATED_CONFIRMED
            if terminated
            else ManagedProcessTerminationStatus.TERMINATION_UNCONFIRMED
        ),
        pid=metadata.pid,
        attempted=True,
        verification_timed_out=verification_timed_out,
        elapsed_ms=_elapsed_ms_since(started_at),
        user_safe_detail=(
            app_text("Shutdown finished cleanly.")
            if terminated
            else app_text(
                "Shutdown could not be confirmed before the verification timeout."
            )
        ),
        diagnostic_detail=(
            "Closed Windows Job Object handle and verified managed process exit."
            if terminated
            else "Closed Windows Job Object handle but managed process exit could not be verified."
        ),
    )
    _log_termination_result(result)
    return result


def _kill_posix_process(
    *,
    pid: int,
    started_at: float,
) -> ManagedProcessTerminationResult:
    """Terminate one POSIX process tree and normalize the result."""

    _terminate_posix_process_tree(pid)
    elapsed_ms = _elapsed_ms_since(started_at)
    terminated, verification_timed_out = _verify_process_exit(pid)
    if terminated:
        return ManagedProcessTerminationResult(
            status=ManagedProcessTerminationStatus.TERMINATED_CONFIRMED,
            pid=pid,
            attempted=True,
            elapsed_ms=elapsed_ms,
            user_safe_detail=app_text("Shutdown finished cleanly."),
            diagnostic_detail="POSIX managed process tree terminated.",
        )
    return ManagedProcessTerminationResult(
        status=ManagedProcessTerminationStatus.TERMINATION_UNCONFIRMED,
        pid=pid,
        attempted=True,
        verification_timed_out=verification_timed_out,
        elapsed_ms=elapsed_ms,
        user_safe_detail=app_text(
            "Shutdown could not be confirmed before the verification timeout."
        ),
        diagnostic_detail="Managed process tree remained alive after POSIX termination.",
    )


def _kill_posix_guardian_owned_process(
    *,
    metadata: ManagedProcessMetadata,
    containment_handle: object | None,
) -> ManagedProcessTerminationResult:
    """Terminate one guardian-owned POSIX process using persisted metadata."""

    from substitute.infrastructure.comfy.posix_guardian_containment import (
        PosixGuardianContainmentHandle,
        request_guardian_stop,
        request_guardian_stop_by_pid,
        terminate_process_group,
    )

    started_at = monotonic()
    handle = (
        containment_handle
        if isinstance(containment_handle, PosixGuardianContainmentHandle)
        else None
    )
    log_info(
        _LOGGER,
        "Explicit contained shutdown requested",
        containment_mode=metadata.containment_mode,
        termination_phase="guardian_stop_requested",
        owner_pid=metadata.owner_pid,
        managed_pid=metadata.pid,
        process_group_id=metadata.process_group_id,
    )
    if handle is not None:
        request_guardian_stop(handle)
    else:
        request_guardian_stop_by_pid(metadata.owner_pid)
    terminated, verification_timed_out = _verify_posix_guardian_exit(metadata)
    if not terminated and metadata.process_group_id is not None:
        terminate_process_group(
            metadata.process_group_id,
            timeout_seconds=_PROCESS_EXIT_TIMEOUT_SECONDS,
        )
        terminated, verification_timed_out = _verify_posix_guardian_exit(metadata)
    if handle is not None:
        handle.close()
    result = ManagedProcessTerminationResult(
        status=(
            ManagedProcessTerminationStatus.TERMINATED_CONFIRMED
            if terminated
            else ManagedProcessTerminationStatus.TERMINATION_UNCONFIRMED
        ),
        pid=metadata.pid,
        attempted=True,
        verification_timed_out=verification_timed_out,
        elapsed_ms=_elapsed_ms_since(started_at),
        user_safe_detail=(
            app_text("Shutdown finished cleanly.")
            if terminated
            else app_text(
                "Shutdown could not be confirmed before the verification timeout."
            )
        ),
        diagnostic_detail=(
            "Guardian-owned managed process group terminated."
            if terminated
            else "Guardian-owned managed process group remained alive after shutdown requests."
        ),
    )
    _log_termination_result(result)
    return result


def _verify_process_exit(
    pid: int,
    *,
    timeout_seconds: float = _PROCESS_EXIT_TIMEOUT_SECONDS,
) -> tuple[bool, bool]:
    """Wait for one process to exit and log whether verification succeeded."""

    log_info(
        _LOGGER,
        "Process exit verification started",
        pid=pid,
        timeout_seconds=timeout_seconds,
    )
    terminated, timed_out = _wait_for_process_exit(
        pid,
        timeout_seconds=timeout_seconds,
    )
    if terminated:
        log_info(_LOGGER, "Process exit verification succeeded", pid=pid)
    elif timed_out:
        log_warning(
            _LOGGER,
            "Process exit verification timed out",
            pid=pid,
            verification_timeout=True,
        )
    return terminated, timed_out


def _verify_posix_guardian_exit(
    metadata: ManagedProcessMetadata,
    *,
    timeout_seconds: float = _PROCESS_EXIT_TIMEOUT_SECONDS,
) -> tuple[bool, bool]:
    """Wait for one guardian-owned managed pid and process group to exit."""

    from substitute.infrastructure.comfy.posix_guardian_containment import (
        is_process_group_running,
    )

    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        managed_running = is_process_running(metadata.pid)
        group_running = is_process_group_running(metadata.process_group_id)
        if not managed_running and not group_running:
            return True, False
        sleep(0.1)
    final_managed_running = is_process_running(metadata.pid)
    final_group_running = is_process_group_running(metadata.process_group_id)
    terminated = not final_managed_running and not final_group_running
    return terminated, not terminated


def _wait_for_process_exit(
    pid: int,
    *,
    timeout_seconds: float = _PROCESS_EXIT_TIMEOUT_SECONDS,
) -> tuple[bool, bool]:
    """Poll the supplied pid until it exits or the timeout elapses."""

    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        if not is_process_running(pid):
            return True, False
        sleep(0.1)
    final_state = not is_process_running(pid)
    return final_state, not final_state


def _terminate_posix_process_tree(pid: int) -> None:
    """Terminate one POSIX process tree rooted at the supplied pid."""

    descendants = _posix_descendants(pid)
    for descendant in reversed(descendants):
        _signal_posix(descendant, force=False)
    _signal_posix(pid, force=False)
    sleep(0.5)
    if is_process_running(pid):
        for descendant in reversed(descendants):
            _signal_posix(descendant, force=True)
        _signal_posix(pid, force=True)


def _posix_descendants(pid: int) -> list[int]:
    """Return the recursively discovered child pids for one POSIX process."""

    try:
        result = subprocess.run(
            ["ps", "-o", "pid=", "--ppid", str(pid)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
    except OSError:
        return []
    descendants: list[int] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped.isdigit():
            continue
        child_pid = int(stripped)
        descendants.extend(_posix_descendants(child_pid))
        descendants.append(child_pid)
    return descendants


def _signal_posix(pid: int, *, force: bool) -> None:
    """Send SIGTERM or SIGKILL to one POSIX process when it is still alive."""

    if not is_process_running(pid):
        return
    signal_name = "-KILL" if force else "-TERM"
    subprocess.run(
        ["kill", signal_name, str(pid)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=5,
        check=False,
    )


def _format_timeout_diagnostic(error: subprocess.TimeoutExpired) -> str:
    """Render one sanitized timeout diagnostic string for logs."""

    return (
        f"TimeoutExpired(cmd={error.cmd!r}, timeout={error.timeout}, "
        f"stdout={error.output!r}, stderr={error.stderr!r})"
    )


def _format_os_error_diagnostic(error: OSError) -> str:
    """Render one concise process-launch diagnostic string for logs."""

    return f"{type(error).__name__}: {error}"


def _format_completed_process_diagnostic(
    result: subprocess.CompletedProcess[str],
) -> str:
    """Render one subprocess completion summary including raw command output."""

    return (
        f"returncode={result.returncode} "
        f"stdout={result.stdout.strip()!r} "
        f"stderr={result.stderr.strip()!r}"
    )


def _log_termination_result(result: ManagedProcessTerminationResult) -> None:
    """Log the normalized termination result with structured diagnostics."""

    log_method = (
        log_info
        if result.status
        in {
            ManagedProcessTerminationStatus.NO_ACTION_REQUIRED,
            ManagedProcessTerminationStatus.TERMINATED_CONFIRMED,
            ManagedProcessTerminationStatus.TERMINATION_UNCONFIRMED,
        }
        else log_warning
    )
    log_method(
        _LOGGER,
        "Managed process termination finished",
        pid=result.pid,
        elapsed_ms=result.elapsed_ms,
        termination_status=result.status.value,
        attempted=result.attempted,
        verification_timed_out=result.verification_timed_out,
        taskkill_timeout=result.termination_command_timed_out,
        diagnostic_detail=result.diagnostic_detail,
    )


def _elapsed_ms_since(started_at: float) -> int:
    """Return elapsed whole milliseconds since one monotonic start timestamp."""

    return int((monotonic() - started_at) * 1000)


__all__ = [
    "ManagedProcessTerminationResult",
    "ManagedProcessTerminationStatus",
    "kill_managed_comfy",
    "kill_managed_comfy_metadata",
    "kill_managed_comfy_pid",
]

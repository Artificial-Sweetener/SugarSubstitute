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

"""Supervise a candidate application until its visible shell proves readiness."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import json
from pathlib import Path
import secrets
import subprocess
import threading
import time
from typing import Protocol

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process import spawn_detached_process
from sugarsubstitute_shared.application_readiness import (
    ApplicationReadinessReceipt,
    ApplicationReadinessSurface,
    READINESS_PATH_ENV,
    READINESS_TOKEN_ENV,
)


DEFAULT_READINESS_TIMEOUT_SECONDS = 300.0
_POLL_INTERVAL_SECONDS = 0.05
_TERMINATION_TIMEOUT_SECONDS = 5.0


class ApplicationReadinessError(RuntimeError):
    """Report a candidate that exits or stalls before its shell is ready."""


class CandidateProcess(Protocol):
    """Expose process lifecycle operations used by readiness supervision."""

    @property
    def pid(self) -> int:
        """Return the operating-system process identifier."""

    def poll(self) -> int | None:
        """Return the exit status when the process has ended."""

    def terminate(self) -> None:
        """Request graceful process termination."""

    def kill(self) -> None:
        """Force process termination."""

    def wait(self, timeout: float | None = None) -> int:
        """Wait for process termination and return its exit status."""


class ApplicationReadinessSupervisor:
    """Start a candidate and wait for its token-bound visible-shell receipt."""

    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_READINESS_TIMEOUT_SECONDS,
        process_starter: Callable[
            [Sequence[str], Mapping[str, str]], tuple[CandidateProcess, Path]
        ]
        | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        wait: Callable[[float], object] | None = None,
        token_factory: Callable[[], str] | None = None,
    ) -> None:
        """Store bounded process and clock collaborators."""

        if timeout_seconds <= 0:
            raise ValueError("Application readiness timeout must be positive.")
        self._timeout_seconds = timeout_seconds
        self._process_starter = process_starter or _start_candidate_process
        self._monotonic = monotonic
        self._wait = wait or threading.Event().wait
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(32))

    def launch_until_ready(
        self,
        *,
        layout: InstallLayout,
        command: Sequence[str],
        environment: Mapping[str, str],
    ) -> CandidateProcess:
        """Return the running candidate only after its main shell is responsive."""

        token = self._token_factory()
        receipt_path = layout.launcher_dir / "readiness" / "candidate.json"
        try:
            receipt_path.unlink()
        except FileNotFoundError:
            pass
        child_environment = dict(environment)
        child_environment[READINESS_PATH_ENV] = str(receipt_path)
        child_environment[READINESS_TOKEN_ENV] = token
        process, startup_log_path = self._process_starter(
            command,
            child_environment,
        )
        try:
            deadline = self._monotonic() + self._timeout_seconds
            while self._monotonic() < deadline:
                return_code = process.poll()
                if return_code is not None:
                    raise ApplicationReadinessError(
                        "SugarSubstitute exited before its main window became ready. "
                        f"Exit code: {return_code}. Startup log: {startup_log_path}."
                    )
                if receipt_path.exists():
                    self._validate_receipt(
                        receipt_path=receipt_path,
                        expected_token=token,
                        expected_pid=process.pid,
                    )
                    receipt_path.unlink()
                    return process
                self._wait(_POLL_INTERVAL_SECONDS)
            raise ApplicationReadinessError(
                "SugarSubstitute did not reveal its main window before the startup "
                f"timeout. Startup log: {startup_log_path}."
            )
        except BaseException:
            stop_candidate_process(process)
            raise

    @staticmethod
    def _validate_receipt(
        *,
        receipt_path: Path,
        expected_token: str,
        expected_pid: int,
    ) -> None:
        """Fail closed unless a receipt belongs to the supervised process."""

        try:
            payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ApplicationReadinessError(
                f"SugarSubstitute wrote an invalid readiness receipt: {receipt_path}."
            ) from error
        try:
            receipt = ApplicationReadinessReceipt.from_json(payload)
        except ValueError as error:
            raise ApplicationReadinessError(
                "Application readiness receipt is invalid."
            ) from error
        if receipt.token != expected_token or receipt.pid != expected_pid:
            raise ApplicationReadinessError(
                "Application readiness receipt did not match the launched process."
            )
        if receipt.surface is not ApplicationReadinessSurface.MAIN_SHELL:
            raise ApplicationReadinessError(
                "SugarSubstitute did not reveal its main shell. "
                f"Reported surface: {receipt.surface.value}."
            )


def _start_candidate_process(
    command: Sequence[str],
    environment: Mapping[str, str],
) -> tuple[CandidateProcess, Path]:
    """Adapt the launcher process owner to the supervision port."""

    process, log_path = spawn_detached_process(command, environment=environment)
    return process, log_path


def stop_candidate_process(process: CandidateProcess) -> None:
    """Ensure a timed-out candidate no longer holds app or runtime files."""

    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=_TERMINATION_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=_TERMINATION_TIMEOUT_SECONDS)


__all__ = [
    "ApplicationReadinessError",
    "ApplicationReadinessSupervisor",
    "CandidateProcess",
    "DEFAULT_READINESS_TIMEOUT_SECONDS",
    "stop_candidate_process",
]

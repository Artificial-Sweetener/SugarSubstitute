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

"""Qualify readiness receipt access while atomic publication settles."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
import subprocess

import pytest

from launcher.sugarsubstitute_launcher.application_readiness_supervisor import (
    ApplicationReadinessError,
    ApplicationReadinessSupervisor,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_readiness import (
    ApplicationReadinessReceipt,
    ApplicationReadinessSurface,
    READINESS_PATH_ENV,
    READINESS_TOKEN_ENV,
    publish_application_readiness_receipt,
)


class _CandidateProcess:
    """Represent a live supervised child without launching an application."""

    pid = 321

    def __init__(self) -> None:
        """Start with a running process state."""

        self.terminated = False

    def poll(self) -> int | None:
        """Return a completed code only after termination."""

        return 0 if self.terminated else None

    def terminate(self) -> None:
        """Record graceful candidate termination."""

        self.terminated = True

    def kill(self) -> None:
        """Record forced candidate termination."""

        self.terminated = True

    def wait(self, timeout: float | None = None) -> int:
        """Return completion or expose an unresponsive live process."""

        if not self.terminated:
            raise subprocess.TimeoutExpired("candidate", timeout or 0)
        return 0


class _Clock:
    """Advance supervision deterministically through requested poll waits."""

    def __init__(self) -> None:
        """Start the synthetic startup clock at zero."""

        self.elapsed = 0.0
        self.polls = 0

    def monotonic(self) -> float:
        """Return elapsed synthetic time."""

        return self.elapsed

    def wait(self, seconds: float) -> None:
        """Advance time by the requested poll interval."""

        self.elapsed += seconds
        self.polls += 1


def _starter(
    process: _CandidateProcess, startup_log: Path
) -> Callable[[Sequence[str], Mapping[str, str]], tuple[_CandidateProcess, Path]]:
    """Return a launcher that publishes one complete authenticated receipt."""

    def start(
        _command: Sequence[str], environment: Mapping[str, str]
    ) -> tuple[_CandidateProcess, Path]:
        """Publish the simulated child's receipt before observation."""

        publish_application_readiness_receipt(
            receipt_path=Path(environment[READINESS_PATH_ENV]),
            receipt=ApplicationReadinessReceipt(
                pid=process.pid,
                parent_pid=999,
                token=environment[READINESS_TOKEN_ENV],
                surface=ApplicationReadinessSurface.MAIN_SHELL,
            ),
        )
        return process, startup_log

    return start


def _block_receipt_reads(
    monkeypatch: pytest.MonkeyPatch,
    receipt_path: Path,
    *,
    error_type: type[OSError],
    blocked_attempts: int | None,
) -> list[int]:
    """Block selected receipt opens without changing the published file."""

    original_read_text = Path.read_text
    attempts = [0]

    def read_text(
        path: Path,
        encoding: str | None = None,
        errors: str | None = None,
    ) -> str:
        """Raise the configured filesystem error at the receipt boundary."""

        if path == receipt_path:
            attempts[0] += 1
            if blocked_attempts is None or attempts[0] <= blocked_attempts:
                raise error_type("receipt publication is still settling")
        return original_read_text(path, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", read_text)
    return attempts


@pytest.mark.parametrize("access_error", (PermissionError, FileNotFoundError))
def test_supervisor_accepts_receipt_after_transient_publication_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    access_error: type[OSError],
) -> None:
    """Keep the live child while an atomic receipt briefly cannot be opened."""

    layout = InstallLayout.from_root(tmp_path / "install")
    receipt_path = layout.launcher_dir / "readiness" / "candidate.json"
    process = _CandidateProcess()
    clock = _Clock()
    attempts = _block_receipt_reads(
        monkeypatch,
        receipt_path,
        error_type=access_error,
        blocked_attempts=2,
    )

    result = ApplicationReadinessSupervisor(
        timeout_seconds=10,
        process_starter=_starter(process, tmp_path / "startup.log"),
        monotonic=clock.monotonic,
        wait=clock.wait,
        token_factory=lambda: "candidate-token",
    ).launch_until_ready(
        layout=layout,
        command=["python", "main.py"],
        environment={},
    )

    assert result is process
    assert not process.terminated
    assert attempts == [3]
    assert clock.polls == 2


def test_supervisor_rejects_persistently_inaccessible_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail a blocked receipt promptly instead of consuming startup timeout."""

    layout = InstallLayout.from_root(tmp_path / "install")
    receipt_path = layout.launcher_dir / "readiness" / "candidate.json"
    process = _CandidateProcess()
    clock = _Clock()
    _block_receipt_reads(
        monkeypatch,
        receipt_path,
        error_type=PermissionError,
        blocked_attempts=None,
    )

    with pytest.raises(ApplicationReadinessError) as failure:
        ApplicationReadinessSupervisor(
            timeout_seconds=10,
            process_starter=_starter(process, tmp_path / "startup.log"),
            monotonic=clock.monotonic,
            wait=clock.wait,
            token_factory=lambda: "candidate-token",
        ).launch_until_ready(
            layout=layout,
            command=["python", "main.py"],
            environment={},
        )

    assert failure.value.diagnostics["readiness_failure_kind"] == "unreadable_receipt"
    assert 2 <= clock.elapsed < 3
    assert process.terminated

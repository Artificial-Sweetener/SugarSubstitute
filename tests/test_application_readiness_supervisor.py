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

"""Tests for launcher supervision of visible application readiness."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import json
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
)


class _CandidateProcess:
    """Expose deterministic candidate process state for supervision tests."""

    def __init__(self, *, return_code: int | None = None) -> None:
        """Store the initial process state."""

        self.pid = 321
        self.return_code = return_code
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        """Return the configured process state."""

        return self.return_code

    def terminate(self) -> None:
        """Record graceful termination and complete the process."""

        self.terminated = True
        self.return_code = 0

    def kill(self) -> None:
        """Record forced termination and complete the process."""

        self.killed = True
        self.return_code = -9

    def wait(self, timeout: float | None = None) -> int:
        """Return the completed process result."""

        _ = timeout
        if self.return_code is None:
            raise subprocess.TimeoutExpired("candidate", timeout or 0.0)
        return self.return_code


def test_supervisor_returns_only_after_matching_receipt(tmp_path: Path) -> None:
    """A running process is accepted only after its token and PID match."""

    layout = InstallLayout.from_root(tmp_path / "install")
    process = _CandidateProcess()
    child_environments: list[dict[str, str]] = []

    def start(
        _command: Sequence[str],
        environment: Mapping[str, str],
    ) -> tuple[_CandidateProcess, Path]:
        """Capture the launch environment and return the candidate."""

        child_environments.append(dict(environment))
        return process, tmp_path / "startup.log"

    def publish_receipt(_seconds: float) -> None:
        """Publish the receipt during the first bounded wait."""

        environment = child_environments[0]
        receipt_path = Path(environment[READINESS_PATH_ENV])
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(
                ApplicationReadinessReceipt(
                    pid=process.pid,
                    token=environment[READINESS_TOKEN_ENV],
                    surface=ApplicationReadinessSurface.MAIN_SHELL,
                ).to_json()
            ),
            encoding="utf-8",
        )

    result = ApplicationReadinessSupervisor(
        timeout_seconds=5,
        process_starter=start,
        monotonic=_increasing_clock(),
        wait=publish_receipt,
        token_factory=lambda: "candidate-token",
    ).launch_until_ready(
        layout=layout,
        command=["python", "main.py"],
        environment={"BASE": "preserved"},
    )

    assert result is process
    assert child_environments[0]["BASE"] == "preserved"
    assert not (layout.launcher_dir / "readiness" / "candidate.json").exists()


def test_supervisor_preserves_outer_readiness_receipt(tmp_path: Path) -> None:
    """An outer installer proof must retain the receipt it owns for validation."""

    layout = InstallLayout.from_root(tmp_path / "install")
    process = _CandidateProcess()
    receipt_path = tmp_path / "qualification" / "candidate.json"

    def start(
        _command: Sequence[str],
        environment: Mapping[str, str],
    ) -> tuple[_CandidateProcess, Path]:
        """Write the outer token to its caller-owned receipt path."""

        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(
                ApplicationReadinessReceipt(
                    pid=process.pid,
                    token=environment[READINESS_TOKEN_ENV],
                    surface=ApplicationReadinessSurface.MAIN_SHELL,
                ).to_json()
            ),
            encoding="utf-8",
        )
        return process, tmp_path / "startup.log"

    result = ApplicationReadinessSupervisor(
        timeout_seconds=5,
        process_starter=start,
        monotonic=_increasing_clock(),
        wait=lambda _seconds: None,
    ).launch_until_ready(
        layout=layout,
        command=["python", "main.py"],
        environment={
            READINESS_PATH_ENV: str(receipt_path),
            READINESS_TOKEN_ENV: "outer-token",
        },
    )

    assert result is process
    assert receipt_path.is_file()


def test_supervisor_rejects_partial_outer_readiness_contract(tmp_path: Path) -> None:
    """A partial outer contract must fail before launching an unverifiable app."""

    started = False

    def start(
        _command: Sequence[str],
        _environment: Mapping[str, str],
    ) -> tuple[_CandidateProcess, Path]:
        """Record any forbidden process start."""

        nonlocal started
        started = True
        return _CandidateProcess(), tmp_path / "startup.log"

    with pytest.raises(ApplicationReadinessError, match="supplied together"):
        ApplicationReadinessSupervisor(process_starter=start).launch_until_ready(
            layout=InstallLayout.from_root(tmp_path / "install"),
            command=["python", "main.py"],
            environment={READINESS_PATH_ENV: str(tmp_path / "receipt.json")},
        )

    assert started is False


def test_supervisor_rejects_onboarding_as_candidate_readiness(tmp_path: Path) -> None:
    """Candidate activation must require the real main shell."""

    receipt_path = tmp_path / "onboarding.json"
    receipt_path.write_text(
        json.dumps(
            ApplicationReadinessReceipt(
                pid=123,
                token="candidate-token",
                surface=ApplicationReadinessSurface.ONBOARDING,
            ).to_json()
        ),
        encoding="utf-8",
    )

    with pytest.raises(ApplicationReadinessError, match="main shell"):
        ApplicationReadinessSupervisor._validate_receipt(
            receipt_path=receipt_path,
            expected_token="candidate-token",
            expected_pid=123,
        )


def test_supervisor_rejects_early_process_exit(tmp_path: Path) -> None:
    """An app crash before shell reveal should fail the candidate launch."""

    layout = InstallLayout.from_root(tmp_path / "install")
    process = _CandidateProcess(return_code=7)
    supervisor = ApplicationReadinessSupervisor(
        timeout_seconds=5,
        process_starter=lambda _command, _environment: (
            process,
            tmp_path / "startup.log",
        ),
        monotonic=_increasing_clock(),
        wait=lambda _seconds: None,
    )

    with pytest.raises(ApplicationReadinessError, match="Exit code: 7"):
        supervisor.launch_until_ready(
            layout=layout,
            command=["python", "main.py"],
            environment={},
        )


def test_supervisor_terminates_candidate_on_readiness_timeout(tmp_path: Path) -> None:
    """A splash hang should end the candidate before rollback touches its files."""

    layout = InstallLayout.from_root(tmp_path / "install")
    process = _CandidateProcess()
    supervisor = ApplicationReadinessSupervisor(
        timeout_seconds=0.5,
        process_starter=lambda _command, _environment: (
            process,
            tmp_path / "startup.log",
        ),
        monotonic=_increasing_clock(step=0.3),
        wait=lambda _seconds: None,
    )

    with pytest.raises(ApplicationReadinessError, match="did not reveal"):
        supervisor.launch_until_ready(
            layout=layout,
            command=["python", "main.py"],
            environment={},
        )

    assert process.terminated is True
    assert process.killed is False


def _increasing_clock(*, step: float = 0.1) -> Callable[[], float]:
    """Return a callable deterministic monotonic clock."""

    current = 0.0

    def clock() -> float:
        """Advance and return deterministic monotonic time."""

        nonlocal current
        current += step
        return current

    return clock

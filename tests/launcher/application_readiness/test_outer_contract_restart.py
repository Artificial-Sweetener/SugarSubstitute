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

"""Test nested readiness proofs across authorized application restarts."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from launcher.sugarsubstitute_launcher.application_readiness_supervisor import (
    ApplicationReadinessError,
    ApplicationReadinessSupervisor,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_readiness import (
    ApplicationReadinessReceipt,
    ApplicationReadinessSurface,
    READINESS_ACCEPTED_SCHEMA_VERSIONS_ENV,
    READINESS_DELEGATION_PATH_ENV,
    READINESS_DELEGATION_TOKEN_ENV,
    READINESS_PATH_ENV,
    READINESS_TOKEN_ENV,
)


class _CandidateProcess:
    """Expose deterministic candidate process state for restart tests."""

    def __init__(self, *, pid: int) -> None:
        """Store one running process identity."""

        self.pid = pid
        self.return_code: int | None = None
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

        if self.return_code is None:
            raise subprocess.TimeoutExpired("candidate", timeout or 0.0)
        return self.return_code


def _publish_test_receipt(
    *,
    receipt_path: Path,
    pid: int,
    token: str,
    surface: ApplicationReadinessSurface,
    parent_pid: int = 999,
) -> None:
    """Write one deterministic readiness receipt for a supervised child."""

    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(
            ApplicationReadinessReceipt(
                pid=pid,
                token=token,
                surface=surface,
                parent_pid=parent_pid,
            ).to_json()
        ),
        encoding="utf-8",
    )


def test_supervisor_replaces_outer_receipt_across_authorized_restart(
    tmp_path: Path,
) -> None:
    """An onboarding receipt must not poison the authorized main-shell restart."""

    layout = InstallLayout.from_root(tmp_path / "install")
    receipt_path = tmp_path / "qualification" / "candidate.json"
    processes = (
        _CandidateProcess(pid=321),
        _CandidateProcess(pid=654),
    )
    child_environments: list[dict[str, str]] = []

    def start(
        _command: Sequence[str],
        environment: Mapping[str, str],
    ) -> tuple[_CandidateProcess, Path]:
        """Return each authorized application process in launch order."""

        child_environments.append(dict(environment))
        return processes[len(child_environments) - 1], tmp_path / "startup.log"

    surfaces = (
        ApplicationReadinessSurface.ONBOARDING,
        ApplicationReadinessSurface.MAIN_SHELL,
    )

    def publish_receipt(_seconds: float) -> None:
        """Publish readiness for the application process currently starting."""

        launch_index = len(child_environments) - 1
        environment = child_environments[launch_index]
        _publish_test_receipt(
            receipt_path=Path(environment[READINESS_PATH_ENV]),
            pid=processes[launch_index].pid,
            token=environment[READINESS_TOKEN_ENV],
            surface=surfaces[launch_index],
        )

    supervisor = ApplicationReadinessSupervisor(
        accepted_surfaces=surfaces,
        timeout_seconds=5,
        process_starter=start,
        monotonic=_increasing_clock(),
        wait=publish_receipt,
        token_factory=iter(("onboarding-token", "main-shell-token")).__next__,
    )
    outer_environment = {
        READINESS_ACCEPTED_SCHEMA_VERSIONS_ENV: "5",
        READINESS_PATH_ENV: str(receipt_path),
        READINESS_TOKEN_ENV: "outer-token",
    }

    supervisor.launch_until_ready(
        layout=layout,
        command=["python", "main.py"],
        environment=outer_environment,
    )
    onboarding_receipt = ApplicationReadinessReceipt.from_json(
        json.loads(receipt_path.read_text(encoding="utf-8"))
    )
    assert onboarding_receipt.pid == processes[0].pid
    assert onboarding_receipt.parent_pid == 999
    assert os.getpid() in onboarding_receipt.attester_pids
    assert onboarding_receipt.token == "outer-token"
    assert onboarding_receipt.surface is ApplicationReadinessSurface.ONBOARDING
    assert child_environments[0][READINESS_PATH_ENV] != str(receipt_path)
    assert child_environments[0][READINESS_TOKEN_ENV] == "onboarding-token"
    processes[0].return_code = 0
    second_result = supervisor.launch_until_ready(
        layout=layout,
        command=["python", "main.py"],
        environment=outer_environment,
    )

    final_receipt = ApplicationReadinessReceipt.from_json(
        json.loads(receipt_path.read_text(encoding="utf-8"))
    )
    assert second_result is processes[1]
    assert final_receipt.pid == processes[1].pid
    assert final_receipt.parent_pid == 999
    assert os.getpid() in final_receipt.attester_pids
    assert final_receipt.token == "outer-token"
    assert final_receipt.surface is ApplicationReadinessSurface.MAIN_SHELL
    assert child_environments[1][READINESS_PATH_ENV] != str(receipt_path)
    assert child_environments[1][READINESS_TOKEN_ENV] == "main-shell-token"


def test_nested_supervisor_projects_final_surface_to_original_outer_contract(
    tmp_path: Path,
) -> None:
    """A setup child must not strand final readiness inside its private proof."""

    layout = InstallLayout.from_root(tmp_path / "install")
    outer_receipt_path = tmp_path / "qualification" / "candidate.json"
    setup_process = _CandidateProcess(pid=321)
    app_process = _CandidateProcess(pid=654)
    setup_child_environment: dict[str, str] = {}

    def start_setup(
        _command: Sequence[str],
        environment: Mapping[str, str],
    ) -> tuple[_CandidateProcess, Path]:
        """Publish the setup launcher's painted surface and retain its environment."""

        setup_child_environment.update(environment)
        _publish_test_receipt(
            receipt_path=Path(environment[READINESS_PATH_ENV]),
            pid=setup_process.pid,
            token=environment[READINESS_TOKEN_ENV],
            surface=ApplicationReadinessSurface.LAUNCHER_WINDOW,
        )
        return setup_process, tmp_path / "setup-startup.log"

    ApplicationReadinessSupervisor(
        accepted_surfaces=(ApplicationReadinessSurface.LAUNCHER_WINDOW,),
        timeout_seconds=5,
        process_starter=start_setup,
        monotonic=_increasing_clock(),
        wait=lambda _seconds: None,
        token_factory=lambda: "setup-private-token",
    ).launch_until_ready(
        layout=layout,
        command=["setup.exe", "--launcher-ui-child"],
        environment={
            READINESS_ACCEPTED_SCHEMA_VERSIONS_ENV: "5",
            READINESS_PATH_ENV: str(outer_receipt_path),
            READINESS_TOKEN_ENV: "outer-token",
        },
    )
    assert setup_child_environment[READINESS_DELEGATION_PATH_ENV] == str(
        outer_receipt_path.resolve()
    )
    assert setup_child_environment[READINESS_DELEGATION_TOKEN_ENV] == "outer-token"

    def start_app(
        _command: Sequence[str],
        environment: Mapping[str, str],
    ) -> tuple[_CandidateProcess, Path]:
        """Publish the final shell through the nested launcher's private proof."""

        _publish_test_receipt(
            receipt_path=Path(environment[READINESS_PATH_ENV]),
            pid=app_process.pid,
            token=environment[READINESS_TOKEN_ENV],
            surface=ApplicationReadinessSurface.MAIN_SHELL,
        )
        return app_process, tmp_path / "app-startup.log"

    ApplicationReadinessSupervisor(
        accepted_surfaces=(ApplicationReadinessSurface.MAIN_SHELL,),
        timeout_seconds=5,
        process_starter=start_app,
        monotonic=_increasing_clock(),
        wait=lambda _seconds: None,
        token_factory=lambda: "app-private-token",
    ).launch_until_ready(
        layout=layout,
        command=["python", "main.py"],
        environment=setup_child_environment,
    )

    final_receipt = ApplicationReadinessReceipt.from_json(
        json.loads(outer_receipt_path.read_text(encoding="utf-8"))
    )
    assert final_receipt.pid == app_process.pid
    assert final_receipt.parent_pid == 999
    assert os.getpid() in final_receipt.attester_pids
    assert final_receipt.token == "outer-token"
    assert final_receipt.surface is ApplicationReadinessSurface.MAIN_SHELL


def test_invalid_restarted_child_cannot_replace_outer_receipt(tmp_path: Path) -> None:
    """A failed restart proof must preserve the last truthful outer receipt."""

    layout = InstallLayout.from_root(tmp_path / "install")
    process = _CandidateProcess(pid=654)
    receipt_path = tmp_path / "qualification" / "candidate.json"
    original_receipt = ApplicationReadinessReceipt(
        pid=321,
        token="outer-token",
        surface=ApplicationReadinessSurface.ONBOARDING,
        parent_pid=999,
    )
    _publish_test_receipt(
        receipt_path=receipt_path,
        pid=original_receipt.pid,
        token=original_receipt.token,
        surface=original_receipt.surface,
        parent_pid=original_receipt.parent_pid or 999,
    )

    def start(
        _command: Sequence[str],
        environment: Mapping[str, str],
    ) -> tuple[_CandidateProcess, Path]:
        """Publish a forged child receipt with the wrong process identity."""

        _publish_test_receipt(
            receipt_path=Path(environment[READINESS_PATH_ENV]),
            pid=777,
            token=environment[READINESS_TOKEN_ENV],
            surface=ApplicationReadinessSurface.MAIN_SHELL,
            parent_pid=778,
        )
        return process, tmp_path / "startup.log"

    with pytest.raises(ApplicationReadinessError, match="launched process"):
        ApplicationReadinessSupervisor(
            accepted_surfaces=(
                ApplicationReadinessSurface.MAIN_SHELL,
                ApplicationReadinessSurface.ONBOARDING,
            ),
            timeout_seconds=5,
            process_starter=start,
            monotonic=_increasing_clock(),
            wait=lambda _seconds: None,
            token_factory=lambda: "private-restart-token",
        ).launch_until_ready(
            layout=layout,
            command=["python", "main.py"],
            environment={
                READINESS_PATH_ENV: str(receipt_path),
                READINESS_TOKEN_ENV: "outer-token",
            },
        )

    preserved_receipt = ApplicationReadinessReceipt.from_json(
        json.loads(receipt_path.read_text(encoding="utf-8"))
    )
    assert preserved_receipt == original_receipt
    assert process.terminated is True


def test_supervisor_replaces_outer_receipt_across_real_processes(
    tmp_path: Path,
) -> None:
    """Exercise the onboarding-to-main-shell proof chain with real process IDs."""

    layout = InstallLayout.from_root(tmp_path / "install")
    receipt_path = tmp_path / "qualification" / "candidate.json"
    supervisor = ApplicationReadinessSupervisor(
        accepted_surfaces=(
            ApplicationReadinessSurface.MAIN_SHELL,
            ApplicationReadinessSurface.ONBOARDING,
        ),
        timeout_seconds=10,
    )
    script = (
        "import os, time; "
        "from pathlib import Path; "
        "from sugarsubstitute_shared.application_readiness import "
        "ApplicationReadinessReceipt, ApplicationReadinessSurface, "
        "READINESS_PATH_ENV, READINESS_TOKEN_ENV, "
        "publish_application_readiness_receipt; "
        "Path(os.environ['TEST_PID_PATH']).write_text("
        "str(os.getpid()), encoding='utf-8'); "
        "publish_application_readiness_receipt("
        "receipt_path=Path(os.environ[READINESS_PATH_ENV]), "
        "receipt=ApplicationReadinessReceipt("
        "pid=os.getpid(), parent_pid=os.getppid(), "
        "token=os.environ[READINESS_TOKEN_ENV], "
        "surface=ApplicationReadinessSurface(os.environ['TEST_SURFACE']))); "
        "time.sleep(1)"
    )
    outer_environment = {
        READINESS_ACCEPTED_SCHEMA_VERSIONS_ENV: "5",
        READINESS_PATH_ENV: str(receipt_path),
        READINESS_TOKEN_ENV: "outer-token",
    }
    onboarding_pid_path = tmp_path / "onboarding.pid"
    main_shell_pid_path = tmp_path / "main-shell.pid"

    onboarding_process = supervisor.launch_until_ready(
        layout=layout,
        command=[sys.executable, "-c", script],
        environment={
            **outer_environment,
            "TEST_SURFACE": ApplicationReadinessSurface.ONBOARDING.value,
            "TEST_PID_PATH": str(onboarding_pid_path),
        },
    )
    onboarding_receipt = ApplicationReadinessReceipt.from_json(
        json.loads(receipt_path.read_text(encoding="utf-8"))
    )
    assert onboarding_receipt.pid == int(
        onboarding_pid_path.read_text(encoding="utf-8")
    )
    assert onboarding_process.pid in {
        onboarding_receipt.parent_pid,
        *onboarding_receipt.attester_pids,
    }
    assert os.getpid() in onboarding_receipt.attester_pids
    assert onboarding_process.wait(timeout=5) == 0
    main_shell_process = supervisor.launch_until_ready(
        layout=layout,
        command=[sys.executable, "-c", script],
        environment={
            **outer_environment,
            "TEST_SURFACE": ApplicationReadinessSurface.MAIN_SHELL.value,
            "TEST_PID_PATH": str(main_shell_pid_path),
        },
    )
    try:
        final_receipt = ApplicationReadinessReceipt.from_json(
            json.loads(receipt_path.read_text(encoding="utf-8"))
        )
        assert final_receipt.pid == int(main_shell_pid_path.read_text(encoding="utf-8"))
        assert main_shell_process.pid in {
            final_receipt.parent_pid,
            *final_receipt.attester_pids,
        }
        assert os.getpid() in final_receipt.attester_pids
        assert main_shell_process.pid != onboarding_process.pid
        assert final_receipt.token == "outer-token"
        assert final_receipt.surface is ApplicationReadinessSurface.MAIN_SHELL
    finally:
        assert main_shell_process.wait(timeout=5) == 0


def _increasing_clock(*, step: float = 0.1) -> Callable[[], float]:
    """Return a callable deterministic monotonic clock."""

    current = 0.0

    def clock() -> float:
        """Advance and return deterministic monotonic time."""

        nonlocal current
        current += step
        return current

    return clock

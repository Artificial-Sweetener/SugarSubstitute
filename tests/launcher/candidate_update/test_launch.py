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

"""Verify candidate update launch, commit, rollback, and fallback."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
import pytest

from launcher.sugarsubstitute_launcher.application_readiness_supervisor import (
    ApplicationReadinessError,
    CandidateProcess,
)
from launcher.sugarsubstitute_launcher.candidate_update_launch import (
    launch_prepared_update,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_runtime_mode import (
    APPLICATION_RUNTIME_MODE_ENV,
    PACKAGED_APPLICATION_RUNTIME_MODE,
)


class _Guard:
    """Expose the launch-guard behavior used by candidate orchestration."""

    def __init__(self, name: str) -> None:
        """Store the environment marker and release state."""

        self.name = name
        self.released = False

    def initial_handoff_environment(
        self,
        environment: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Return a recognizable child environment."""

        child_environment = dict(environment or {})
        child_environment["GUARD"] = self.name
        return child_environment

    def release(self) -> None:
        """Record guard release."""

        self.released = True


class _Activation:
    """Record candidate update terminal transitions."""

    def __init__(self) -> None:
        """Create an empty transition log."""

        self.transitions: list[str] = []

    def commit(self) -> None:
        """Record commit."""

        self.transitions.append("commit")

    def rollback(self) -> None:
        """Record rollback."""

        self.transitions.append("rollback")


class _Supervisor:
    """Return or reject one candidate launch."""

    def __init__(self, *, fail: bool) -> None:
        """Store whether launch should fail."""

        self._fail = fail
        self.environments: list[dict[str, str]] = []

    def launch_until_ready(
        self,
        *,
        layout: InstallLayout,
        command: Sequence[str],
        environment: Mapping[str, str],
    ) -> CandidateProcess:
        """Record candidate inputs and return a ready process or fail."""

        _ = layout
        _ = command
        self.environments.append(dict(environment))
        if self._fail:
            raise ApplicationReadinessError("candidate failed")
        return _ReadyProcess()


class _ReadyProcess:
    """Represent a process that remains alive after readiness."""

    pid = 123

    def poll(self) -> int | None:
        """Report a running process."""

        return None

    def terminate(self) -> None:
        """Satisfy the candidate process lifecycle port."""

    def kill(self) -> None:
        """Satisfy the candidate process lifecycle port."""

    def wait(self, timeout: float | None = None) -> int:
        """Satisfy the candidate process lifecycle port."""

        _ = timeout
        return 0


def test_ready_candidate_commits_without_fallback(tmp_path: Path) -> None:
    """A visible candidate should become the installed update."""

    layout = InstallLayout.from_root(tmp_path / "install")
    guard = _Guard("candidate")
    activation = _Activation()
    supervisor = _Supervisor(fail=False)

    launch_prepared_update(
        layout=layout,
        command=["python", "main.py"],
        initial_guard=guard,
        activation=activation,
        supervisor=supervisor,
        fallback_guard_factory=lambda _layout: pytest.fail("unexpected fallback"),
    )

    assert activation.transitions == ["commit"]
    assert supervisor.environments == [
        {
            "GUARD": "candidate",
            APPLICATION_RUNTIME_MODE_ENV: PACKAGED_APPLICATION_RUNTIME_MODE,
        }
    ]
    assert guard.released is False


def test_failed_candidate_rolls_back_and_launches_previous_app(
    tmp_path: Path,
) -> None:
    """A failed candidate should restore and start the prior known-good app."""

    layout = InstallLayout.from_root(tmp_path / "install")
    candidate_guard = _Guard("candidate")
    fallback_guard = _Guard("fallback")
    activation = _Activation()
    started: list[tuple[list[str], dict[str, str]]] = []

    launch_prepared_update(
        layout=layout,
        command=["python", "main.py"],
        initial_guard=candidate_guard,
        activation=activation,
        supervisor=_Supervisor(fail=True),
        fallback_guard_factory=lambda _layout: fallback_guard,
        fallback_process_starter=lambda command, *, environment: started.append(
            (list(command), dict(environment))
        ),
    )

    assert activation.transitions == ["rollback"]
    assert candidate_guard.released is True
    assert fallback_guard.released is False
    assert started == [
        (
            ["python", "main.py"],
            {
                "GUARD": "fallback",
                APPLICATION_RUNTIME_MODE_ENV: PACKAGED_APPLICATION_RUNTIME_MODE,
            },
        ),
    ]

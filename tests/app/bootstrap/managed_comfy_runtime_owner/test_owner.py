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

"""Cover safe in-place managed Comfy process replacement."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from substitute.app.bootstrap.managed_comfy_runtime_owner import (
    ManagedComfyRuntimeOwner,
)
from substitute.application.execution import TaskOutcome
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
)


class _Handle:
    """Execute captured restart work and publish its outcome deterministically."""

    def __init__(self, request: Any) -> None:
        """Store one task request."""

        self.identity = request.identity
        self._request = request
        self.is_finished = False
        self.outcome: TaskOutcome[Any] | None = None
        self._callbacks: list[Any] = []

    @property
    def state(self) -> str:
        """Return the fake task lifecycle state."""

        return "finished" if self.is_finished else "pending"

    def add_done_callback(self, callback: Any, *, reason: str) -> None:
        """Capture one completion callback."""

        del reason
        self._callbacks.append(callback)

    def cancel(self, *, reason: str) -> None:
        """Accept task-scope cancellation for teardown."""

        del reason

    def run(self) -> None:
        """Run work and publish a protocol-shaped task outcome."""

        outcome: TaskOutcome[Any]
        try:
            result = self._request.work(object())
        except Exception as error:
            outcome = TaskOutcome(
                identity=self.identity,
                context=self._request.context,
                status="failed",
                error=error,
            )
        else:
            outcome = TaskOutcome(
                identity=self.identity,
                context=self._request.context,
                status="succeeded",
                result=result,
            )
        self.outcome = outcome
        self.is_finished = True
        for callback in self._callbacks:
            callback(outcome)


class _Submitter:
    """Capture submitted restart work for explicit test execution."""

    def __init__(self) -> None:
        """Initialize an empty handle collection."""

        self.handles: list[_Handle] = []

    def submit(self, request: Any, *, cancellation: object) -> _Handle:
        """Capture one request and ignore the fake cancellation token."""

        del cancellation
        handle = _Handle(request)
        self.handles.append(handle)
        return handle


@dataclass(frozen=True)
class _CleanupResult:
    """Expose one managed termination status."""

    status: object


def _managed_target() -> ComfyTargetConfiguration:
    """Build one owned managed-local target."""

    return ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL,
        endpoint=ComfyEndpoint("127.0.0.1", 8188),
        workspace_path=Path("ComfyUI"),
        install_owned=True,
        launch_owned=True,
    )


def test_owner_replaces_state_only_after_confirmed_termination() -> None:
    """A restart should stop, confirm cleanup, and then publish replacement state."""

    confirmed = object()
    submitter = _Submitter()
    calls: list[tuple[str, object | None]] = []
    replacement = object()

    def cleanup_state(state: object | None) -> _CleanupResult:
        """Record cleanup and return confirmed termination."""

        calls.append(("cleanup", state))
        return _CleanupResult(confirmed)

    def launch_state() -> object:
        """Record launch and return replacement process state."""

        calls.append(("launch", None))
        return replacement

    owner = ManagedComfyRuntimeOwner(
        target=_managed_target(),
        submitter=submitter,
        request_stop=lambda state: calls.append(("stop", state)),
        cleanup_state=cleanup_state,
        confirmed_termination_status=confirmed,
        launch_state=launch_state,
    )
    original = object()
    owner.set_state(original)

    owner.request_restart(on_failure=lambda: calls.append(("failure", None)))
    submitter.handles[0].run()

    assert calls == [
        ("stop", original),
        ("cleanup", original),
        ("launch", None),
    ]
    assert owner.state is replacement


def test_owner_reports_failure_and_does_not_launch_after_unconfirmed_cleanup() -> None:
    """Unconfirmed process cleanup should fail closed before a replacement launch."""

    submitter = _Submitter()
    failures: list[str] = []
    launches: list[str] = []
    owner = ManagedComfyRuntimeOwner(
        target=_managed_target(),
        submitter=submitter,
        request_stop=lambda _state: None,
        cleanup_state=lambda _state: _CleanupResult(object()),
        confirmed_termination_status=object(),
        launch_state=lambda: launches.append("launch"),
    )

    owner.request_restart(on_failure=lambda: failures.append("failed"))
    submitter.handles[0].run()

    assert failures == ["failed"]
    assert launches == []


def test_owner_close_cancels_pending_restart_before_process_mutation() -> None:
    """Runtime shutdown should make delayed restart work a harmless no-op."""

    confirmed = object()
    submitter = _Submitter()
    calls: list[str] = []
    owner = ManagedComfyRuntimeOwner(
        target=_managed_target(),
        submitter=submitter,
        request_stop=lambda _state: calls.append("stop"),
        cleanup_state=lambda _state: _CleanupResult(confirmed),
        confirmed_termination_status=confirmed,
        launch_state=lambda: calls.append("launch"),
    )
    owner.request_restart(on_failure=lambda: calls.append("failure"))

    owner.close()
    submitter.handles[0].run()

    assert calls == []

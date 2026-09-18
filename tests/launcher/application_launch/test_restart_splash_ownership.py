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

"""Regress presentation ownership across complete installed application restarts."""

from __future__ import annotations
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast
import pytest
from launcher.sugarsubstitute_launcher import (
    installed_application_supervisor,
    installed_app_handoff,
)
from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.startup_splash_session import (
    StartupSplashSession,
)
from launcher.sugarsubstitute_launcher.update_orchestrator import PreLaunchUpdateResult
from launcher.sugarsubstitute_launcher.update_activation import PendingUpdateActivation
from launcher.sugarsubstitute_launcher.application_startup_contract import (
    ApplicationStartupCancelled,
)
from sugarsubstitute_shared.launch_splash.session import SplashSessionSpec
from sugarsubstitute_shared.application_broker_session import ApplicationBrokerSession
from sugarsubstitute_shared.application_instance_protocol import ApplicationInvocation
from sugarsubstitute_shared.launch_splash.client import SocketSplashSessionClient


class Splash:
    """Represent an independently owned presentation process at its IPC boundary."""

    def __init__(self, name: str) -> None:
        """Store distinct session identity and process lifetime."""
        self.name = name
        self.closed = False
        self.client = SocketSplashSessionClient(
            SplashSessionSpec("127.0.0.1", 1, name * 24, 1)
        )
        self.app_arguments = (f"--splash-session-token={name}",)

    def present(self) -> str | None:
        """A closed process cannot acknowledge a secondary launch."""
        return None if self.closed else self.name

    def cancellation_requested(self) -> bool:
        """Expose whether a caller is incorrectly observing the old session."""
        return self.closed

    def ensure_closed(self) -> None:
        """Retire the process after the replacement surface is ready."""
        self.closed = True

    def close(self) -> None:
        """Close the process at the end of its own generation."""
        self.closed = True


class Broker:
    """Retain one installation owner while its presentation process changes."""

    def __init__(self, initial: Splash) -> None:
        """Begin with the initial launch's registered presentation surface."""
        self.presenter: Callable[[ApplicationInvocation], str | None] | None = (
            lambda _: initial.present()
        )
        self.restarts = iter((True, False))

    def bind_startup_presenter(
        self, presenter: Callable[[ApplicationInvocation], str | None] | None
    ) -> None:
        """Expose the currently supervised startup surface."""
        self.presenter = presenter

    def child_environment(self, environment: Mapping[str, str]) -> dict[str, str]:
        """Preserve the normal child environment at the broker boundary."""
        return dict(environment)

    def consume_restart_request(self) -> bool:
        """Authorize exactly one replacement application run."""
        return next(self.restarts, False)

    def close(self) -> None:
        """Leave broker lifetime with the outer launcher owner."""


@dataclass(frozen=True)
class RunObservation:
    """Record the contracts handed to the external application process."""

    command: tuple[str, ...]
    presentation: str | None
    cancellation: bool | None


@pytest.mark.parametrize("prepared_update", [False, True])
@pytest.mark.parametrize("contract", ["command", "presentation", "cancellation"])
def test_restart_uses_current_splash_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    contract: str,
    prepared_update: bool,
) -> None:
    """A legitimate restart must not retain a retired startup session anywhere."""
    layout = InstallLayout.from_root(tmp_path / "install")
    LauncherConfig.from_layout(layout=layout, release_source=None).save(
        layout.config_path
    )
    first = Splash("first")
    replacement = Splash("replacement")
    broker = Broker(first)
    observations: list[RunObservation] = []

    class Activation:
        """Represent the independent update transaction at its cleanup boundary."""

        def rollback(self) -> None:
            """No files were promoted by this external update fixture."""

    activation = cast(PendingUpdateActivation, Activation())

    class Updates:
        """Keep network/update work outside this lifetime regression."""

        def run(self, **kwargs: object) -> PreLaunchUpdateResult:
            """Select the ordinary installed path."""
            return PreLaunchUpdateResult(
                False,
                False,
                skipped_reason="disabled",
                pending_activation=activation if prepared_update else None,
                attempted_version="1.0.0" if prepared_update else None,
            )

    class Supervisor:
        """Observe startup contracts at the application-process boundary."""

        def __init__(
            self, *, cancellation_requested: Callable[[], bool] | None = None
        ) -> None:
            """Capture the generation's cancellation authority."""
            self.cancel = cancellation_requested

        def supervise(self, **kwargs: object) -> int:
            """Present before readiness, then retire the first process normally."""
            command = cast(Sequence[str], kwargs["command"])
            observations.append(
                RunObservation(
                    command=tuple(command),
                    presentation=broker.presenter(ApplicationInvocation.capture(()))
                    if broker.presenter
                    else None,
                    cancellation=self.cancel() if self.cancel else None,
                )
            )
            on_ready = kwargs["on_ready"]
            if callable(on_ready):
                on_ready()
            return 0

    def launch_update(**kwargs: object) -> None:
        """Run the same external process boundary after update preparation."""
        Supervisor(
            cancellation_requested=cast(
                Callable[[], bool] | None, kwargs["cancellation_requested"]
            )
        ).supervise(**kwargs)

    monkeypatch.setattr(installed_app_handoff, "launch_prepared_update", launch_update)
    monkeypatch.setattr(installed_app_handoff, "LauncherUpdateOrchestrator", Updates)
    monkeypatch.setattr(
        installed_application_supervisor, "ApplicationLifecycleSupervisor", Supervisor
    )
    monkeypatch.setattr(
        installed_application_supervisor,
        "start_launcher_splash_session",
        lambda **_: replacement,
    )
    installed_app_handoff.complete_installed_app_handoff(
        layout=layout,
        broker=cast(ApplicationBrokerSession, broker),
        locale_argument="--locale=en",
        no_update_check=True,
        splash_session=cast(StartupSplashSession, first),
        handoff_geometry=None,
    )
    assert len(observations) == 2
    if contract == "command":
        assert "--splash-session-token=replacement" in observations[1].command
        assert "--splash-session-token=first" not in observations[1].command
    elif contract == "presentation":
        assert observations[1].presentation == "replacement"
    else:
        assert observations[1].cancellation is False


@pytest.mark.parametrize("outcome", ["ready", "cancelled", "failed"])
def test_startup_session_is_released_on_every_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, outcome: str
) -> None:
    """Readiness, cancellation and failure all retire the run's presentation owner."""
    splash = Splash("only")
    broker = Broker(splash)
    broker.restarts = iter((False,))

    class Supervisor:
        """Finish or interrupt the external child startup at a controlled boundary."""

        def __init__(self, **kwargs: object) -> None:
            """Accept the run's cancellation contract."""

        def supervise(self, **kwargs: object) -> int:
            """Expose startup interruption independently from broker ownership."""
            if outcome == "cancelled":
                raise ApplicationStartupCancelled()
            if outcome == "failed":
                raise RuntimeError("fixture startup failure")
            on_ready = kwargs["on_ready"]
            assert callable(on_ready)
            on_ready()
            assert broker.presenter is None
            assert splash.closed
            return 0

    monkeypatch.setattr(
        installed_application_supervisor, "ApplicationLifecycleSupervisor", Supervisor
    )
    owner = installed_application_supervisor.InstalledApplicationSupervisor(
        broker=broker,
        layout=InstallLayout.from_root(tmp_path / "install"),
        command=("python", "main.py"),
        locale_override="en",
        remote_failure_reason=None,
    )
    if outcome == "ready":
        owner.supervise(splash_session=splash)
    else:
        with pytest.raises(
            ApplicationStartupCancelled if outcome == "cancelled" else RuntimeError
        ):
            owner.supervise(splash_session=splash)
    assert broker.presenter is None
    assert splash.closed

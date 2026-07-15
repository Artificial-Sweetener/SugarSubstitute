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

"""Tests for sanctioned full GUI reload coordination."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from substitute.app.bootstrap.gui_reload_coordinator import (
    GuiReloadCoordinator,
    ShellFrameProtocol,
)
from substitute.app.bootstrap.lifecycle import (
    ManagedComfyCleanupOutcome,
    ManagedComfyCleanupResult,
)
from substitute.app.bootstrap.startup_shutdown import ManagedComfyLease


def test_gui_reload_rebuilds_shell_without_managed_comfy_cleanup() -> None:
    """Successful reload should dispose only the GUI shell and keep Comfy alive."""

    state = _CoordinatorState()
    old_shell = _FakeShell("old", state.events)
    new_shell = _FakeShell("new", state.events)
    old_main_window = _FakeMainWindow(save_result=True)
    state.current_shell = old_shell

    def build_shell() -> _FakeShell:
        """Record new shell construction."""

        state.record("build")
        return new_shell

    def show_shell(shell: _FakeShell) -> _FakeShell:
        """Record new shell show."""

        state.record("show")
        return shell

    coordinator = state.build_coordinator(
        main_window_for_shell=lambda shell: (
            old_main_window if shell is old_shell else _FakeMainWindow()
        ),
        build_shell=build_shell,
        show_shell=show_shell,
        hydrate_shell=lambda shell: state.record(
            f"hydrate:{cast(_FakeShell, shell).name}"
        ),
    )

    assert coordinator.reload_shell() is True

    assert state.current_shell is new_shell
    assert state.cleanup_calls == []
    assert old_main_window.save_calls == 1
    assert old_main_window.detach_calls == 1
    assert state.events == [
        "old:suppress",
        "old:allow_direct_close",
        "set:None",
        "old:hide",
        "old:close",
        "old:delete",
        "build",
        "set:new",
        "hydrate:new",
        "show",
        "set:new",
    ]


def test_gui_reload_rejects_active_cancellable_jobs() -> None:
    """Reload should not dispose the shell while active queue callbacks are unsafe."""

    state = _CoordinatorState(has_cancellable_jobs=True)
    shell = _FakeShell("old", state.events)
    main_window = _FakeMainWindow(save_result=True)
    state.current_shell = shell
    coordinator = state.build_coordinator(
        main_window_for_shell=lambda _shell: main_window,
    )

    assert coordinator.reload_shell() is False

    assert state.current_shell is shell
    assert main_window.save_calls == 0
    assert state.events == []
    assert state.messages == [
        "Wait for the generation queue to finish before reloading the GUI."
    ]


def test_gui_reload_rejects_after_managed_comfy_cleanup_finished() -> None:
    """Reload should not autosave or dispose the shell once shutdown cleanup finished."""

    state = _CoordinatorState()
    shell = _FakeShell("old", state.events)
    main_window = _FakeMainWindow(save_result=True)
    state.current_shell = shell
    lease = ManagedComfyLease(state.cleanup)
    lease.cleanup()
    coordinator = state.build_coordinator(
        main_window_for_shell=lambda _shell: main_window,
        managed_comfy_lease=lease,
    )

    assert coordinator.reload_shell() is False

    assert state.current_shell is shell
    assert main_window.save_calls == 0
    assert state.events == []
    assert state.messages == ["Substitute cannot reload the GUI while closing."]


def test_gui_reload_keeps_old_shell_when_session_save_fails() -> None:
    """Capture failure should stop the transaction before shell disposal."""

    state = _CoordinatorState()
    shell = _FakeShell("old", state.events)
    main_window = _FakeMainWindow(save_result=False)
    state.current_shell = shell
    coordinator = state.build_coordinator(
        main_window_for_shell=lambda _shell: main_window,
    )

    assert coordinator.reload_shell() is False

    assert state.current_shell is shell
    assert main_window.save_calls == 1
    assert state.events == []
    assert state.messages == ["Substitute could not save the current session."]


def test_gui_reload_fails_closed_when_rebuild_fails_after_disposal() -> None:
    """A rebuild failure after disposal must route through normal shutdown."""

    state = _CoordinatorState()
    shell = _FakeShell("old", state.events)
    state.current_shell = shell
    coordinator = state.build_coordinator(
        main_window_for_shell=lambda _shell: _FakeMainWindow(save_result=True),
        build_shell=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert coordinator.reload_shell() is False

    assert state.current_shell is None
    assert state.shutdown_requests == [None]
    assert state.messages == [
        "Substitute could not reload the GUI and will close safely."
    ]


def test_gui_reload_fails_closed_when_old_resources_cannot_be_released() -> None:
    """A cleanup failure should stop replacement before old shell disposal."""

    state = _CoordinatorState()
    shell = _FakeShell("old", state.events)
    main_window = _FakeMainWindow(
        save_result=True,
        detach_error=RuntimeError("resource busy"),
    )
    state.current_shell = shell
    coordinator = state.build_coordinator(
        main_window_for_shell=lambda _shell: main_window,
    )

    assert coordinator.reload_shell() is False

    assert state.current_shell is shell
    assert state.shutdown_requests == [shell]
    assert state.events == []
    assert state.messages == [
        "Substitute could not release the current GUI and will close safely."
    ]


def test_gui_reload_fails_closed_when_hydration_fails() -> None:
    """A materialization failure after new shell creation must close safely."""

    state = _CoordinatorState()
    old_shell = _FakeShell("old", state.events)
    new_shell = _FakeShell("new", state.events)
    state.current_shell = old_shell
    coordinator = state.build_coordinator(
        main_window_for_shell=lambda _shell: _FakeMainWindow(save_result=True),
        build_shell=lambda: new_shell,
        show_shell=lambda shell: shell,
        hydrate_shell=lambda _shell: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert coordinator.reload_shell() is False

    assert state.current_shell is new_shell
    assert state.shutdown_requests == [new_shell]


class _CoordinatorState:
    """Hold mutable collaborator state for coordinator tests."""

    def __init__(self, *, has_cancellable_jobs: bool = False) -> None:
        """Initialize fake reload collaborators."""

        self.events: list[str] = []
        self.messages: list[str] = []
        self.cleanup_calls: list[str] = []
        self.shutdown_requests: list[ShellFrameProtocol | None] = []
        self.current_shell: ShellFrameProtocol | None = None
        self._has_cancellable_jobs = has_cancellable_jobs

    def build_coordinator(
        self,
        *,
        main_window_for_shell: Callable[[ShellFrameProtocol], object | None],
        build_shell: Callable[[], _FakeShell] | None = None,
        show_shell: Callable[[_FakeShell], _FakeShell] | None = None,
        hydrate_shell: Callable[[ShellFrameProtocol], None] | None = None,
        managed_comfy_lease: ManagedComfyLease | None = None,
    ) -> GuiReloadCoordinator:
        """Build one coordinator from fake collaborators."""

        resolved_show_shell = show_shell or (lambda shell: shell)
        return GuiReloadCoordinator(
            current_shell=lambda: self.current_shell,
            set_current_shell=self.set_current_shell,
            main_window_for_shell=main_window_for_shell,
            build_shell=build_shell or (lambda: _FakeShell("new", self.events)),
            show_shell=cast(
                Callable[[ShellFrameProtocol], ShellFrameProtocol],
                resolved_show_shell,
            ),
            hydrate_shell=hydrate_shell or (lambda _shell: None),
            managed_comfy_lease=managed_comfy_lease or ManagedComfyLease(self.cleanup),
            request_shutdown=lambda shell: self.shutdown_requests.append(shell),
            has_cancellable_jobs=lambda: self._has_cancellable_jobs,
            message_sink=self.messages.append,
        )

    def cleanup(self) -> ManagedComfyCleanupResult:
        """Record unexpected managed cleanup invocations."""

        self.cleanup_calls.append("cleanup")
        return _cleanup_result()

    def set_current_shell(self, shell: ShellFrameProtocol | None) -> None:
        """Record current-shell replacement."""

        self.current_shell = shell
        shell_name = getattr(shell, "name", "None") if shell is not None else "None"
        self.events.append(f"set:{shell_name}")

    def record(self, event: str) -> None:
        """Record one arbitrary event."""

        self.events.append(event)


class _FakeShell:
    """Mimic the shell-frame lifecycle surface used by reload."""

    def __init__(self, name: str, events: list[str]) -> None:
        """Store shell identity and shared event log."""

        self.name = name
        self._events = events

    def suppress_app_quit_on_close(self) -> None:
        """Record close suppression."""

        self._events.append(f"{self.name}:suppress")

    def allow_direct_close(self) -> None:
        """Record sanctioned direct close allowance."""

        self._events.append(f"{self.name}:allow_direct_close")

    def hide(self) -> None:
        """Record shell hide."""

        self._events.append(f"{self.name}:hide")

    def close(self) -> object:
        """Record shell close."""

        self._events.append(f"{self.name}:close")
        return True

    def deleteLater(self) -> None:
        """Record deferred deletion."""

        self._events.append(f"{self.name}:delete")


class _FakeMainWindow:
    """Record session-save attempts for reload tests."""

    def __init__(
        self,
        *,
        save_result: bool = True,
        detach_error: Exception | None = None,
    ) -> None:
        """Initialize the fake save result."""

        self._save_result = save_result
        self._detach_error = detach_error
        self.save_calls = 0
        self.detach_calls = 0
        self.session_autosave_controller = SimpleNamespace(
            force_save_session_snapshot=self._force_save_session_snapshot,
        )
        self.shell_reload_lifecycle_controller = SimpleNamespace(
            detach_for_gui_reload=self._detach_for_gui_reload,
        )

    def _force_save_session_snapshot(self) -> bool:
        """Record one forced session save."""

        self.save_calls += 1
        return self._save_result

    def _detach_for_gui_reload(self) -> None:
        """Record one shell detach request."""

        self.detach_calls += 1
        if self._detach_error is not None:
            raise self._detach_error


def _cleanup_result() -> ManagedComfyCleanupResult:
    """Build one deterministic cleanup result."""

    return ManagedComfyCleanupResult(
        cleanup_ran=True,
        outcome=ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS,
        managed_resource_present=True,
        live_process_present=False,
        metadata_present=True,
        used_persisted_metadata=False,
        termination_attempted=True,
        registry_cleared=True,
        pid=1234,
        host="127.0.0.1",
        port=8188,
        workspace=Path("E:/ComfyUI"),
        elapsed_ms=10,
        taskkill_timeout=False,
        verification_timeout=False,
        user_detail="done",
        technical_detail="done",
        diagnostic_detail="done",
    )

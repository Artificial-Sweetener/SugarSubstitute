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

"""Tests for startup shell reload adapter wiring."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

from substitute.app.bootstrap.shell_reload_adapter import (
    ComfyRuntimeRestartActions,
    ShellReloadAdapter,
    StartupShellReloadState,
    create_bound_shell_reload_adapter,
    create_shell_reload_adapter,
    create_startup_shell_reload_state,
)
from substitute.app.bootstrap.lifecycle import (
    ManagedComfyCleanupOutcome,
    ManagedComfyCleanupResult,
)
from substitute.app.bootstrap.startup_shutdown import ManagedComfyLease

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
SUPPORT_GRAPH_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_support_graph.py"
)


def test_shell_reload_adapter_attaches_reload_and_restart_commands() -> None:
    """Adapter should attach GUI reload and Comfy restart commands to main window."""

    state = _AdapterState()
    shell = object()
    main_window = SimpleNamespace()
    state.main_windows[shell] = main_window

    adapter = state.build_adapter()
    adapter.attach_gui_reload_command(shell)

    assert callable(main_window.request_full_gui_reload)
    assert (
        state.restart_handler_for(main_window)
        == adapter.request_comfy_restart_from_shell
    )


def test_shell_reload_adapter_requests_comfy_restart_once() -> None:
    """Duplicate Comfy restart requests should not request shutdown twice."""

    state = _AdapterState(restart_launch_command=("python", "main.py"))
    shell = object()
    adapter = state.build_adapter()
    adapter.set_current_shell(shell)

    adapter.request_comfy_restart_from_shell()
    adapter.request_comfy_restart_from_shell()

    assert adapter.restart_after_cleanup_requested is True
    assert adapter.restart_launch_command == ("python", "main.py")
    assert state.shutdown_requests == [shell]


def test_shell_reload_adapter_builds_hydrates_and_shows_reloaded_shell() -> None:
    """Reload shell ports should build, attach, hydrate, and show with preserved geometry."""

    state = _AdapterState()
    new_shell = object()
    main_window = SimpleNamespace(
        workspace_restore_controller=SimpleNamespace(
            hydrate_initial_workspace=lambda: state.events.append("hydrate")
        )
    )
    state.built_shell = new_shell
    state.main_windows[new_shell] = main_window
    adapter = state.build_adapter()

    built_shell = adapter.build_reloaded_shell()
    adapter.hydrate_shell(built_shell)
    shown_shell = adapter.show_reloaded_shell(built_shell)

    assert built_shell is new_shell
    assert shown_shell is state.shown_shell
    assert state.events == [
        "apply_appearance",
        "record_appearance",
        "build_main_window",
        "runtime_restart_handler",
        "hydrate",
        "show_built_main_window",
    ]
    assert state.show_kwargs == {"apply_default_geometry": False}


def test_shell_reload_adapter_reads_current_shell_state() -> None:
    """Adapter should expose current shell, session-save, and cancellable-job ports."""

    state = _AdapterState()
    shell = object()
    save_calls: list[str] = []
    main_window = SimpleNamespace(
        session_autosave_controller=SimpleNamespace(
            force_save_session_snapshot=lambda: save_calls.append("save")
        ),
        generation_job_queue_service=SimpleNamespace(has_cancellable_jobs=lambda: True),
    )
    state.main_windows[shell] = main_window
    adapter = state.build_adapter()

    assert adapter.current_shell() is None
    adapter.set_current_shell(shell)

    adapter.save_session_before_cleanup()

    assert adapter.current_shell() is shell
    assert state.current_shell_changes == [shell]
    assert save_calls == ["save"]
    assert adapter.has_cancellable_generation_jobs() is True


def test_shell_reload_adapter_restores_generation_actions_on_replacement() -> None:
    """Reload should carry ready backend and selected mode into the new shell."""

    state = _AdapterState()
    old_shell = object()
    new_shell = object()
    restored_backend_states: list[str] = []
    restored_modes: list[str] = []
    state.main_windows[old_shell] = SimpleNamespace(
        _backend_state="ready",
        _current_generate_mode="continuous",
    )
    state.main_windows[new_shell] = SimpleNamespace(
        generation_action_controller=SimpleNamespace(
            set_backend_state=restored_backend_states.append,
            set_generation_selected_mode=restored_modes.append,
        )
    )
    adapter = state.build_adapter()

    adapter.set_current_shell(old_shell)
    adapter.set_current_shell(None)
    adapter.set_current_shell(new_shell)

    assert restored_backend_states == ["ready"]
    assert restored_modes == ["continuous"]


def test_shell_reload_adapter_does_not_project_state_on_initial_shell() -> None:
    """Initial shell registration should not overwrite startup readiness projection."""

    state = _AdapterState()
    shell = object()
    backend_states: list[str] = []
    state.main_windows[shell] = SimpleNamespace(
        generation_action_controller=SimpleNamespace(
            set_backend_state=backend_states.append,
            set_generation_selected_mode=lambda _mode: None,
        )
    )
    adapter = state.build_adapter()

    adapter.set_current_shell(shell)

    assert backend_states == []


def test_startup_shell_reload_state_tracks_shell_and_delegates_session_save() -> None:
    """Startup shell reload state should own shell reference and cleanup save handoff."""

    save_calls: list[str] = []
    state = StartupShellReloadState()
    adapter = SimpleNamespace(
        save_session_before_cleanup=lambda: save_calls.append("save")
    )
    shell = object()

    state.save_session_before_cleanup()
    state.set_shell_frame(shell)
    state.bind_adapter(adapter)  # type: ignore[arg-type]
    state.save_session_before_cleanup()

    assert state.shell_frame is shell
    assert save_calls == ["save"]


def test_create_startup_shell_reload_state_returns_empty_state() -> None:
    """Shell reload state factory should own startup state construction."""

    state = create_startup_shell_reload_state()

    assert isinstance(state, StartupShellReloadState)
    assert state.shell_frame is None


def test_create_shell_reload_adapter_returns_adapter() -> None:
    """Shell reload adapter factory should construct the concrete adapter."""

    state = _AdapterState()
    adapter = create_shell_reload_adapter(
        main_window_for_shell=lambda shell: state.main_windows.get(shell),
        build_main_window=state.build_main_window,
        show_built_main_window=state.show_built_main_window,
        comfy_runtime_actions_for=state.comfy_runtime_actions_for,
        installation_context=object(),
        comfy_output_stream=object(),
        shutdown_request=state.shutdown_requests.append,
        startup_timer=object(),
        runtime_services=object(),
        managed_comfy_lease=ManagedComfyLease(_cleanup_result),
        restart_launch_command=state.restart_launch_command,
        current_shell_changed=state.current_shell_changes.append,
    )

    assert isinstance(adapter, ShellReloadAdapter)
    assert adapter.restart_launch_command == state.restart_launch_command


def test_create_bound_shell_reload_adapter_binds_state() -> None:
    """Bound shell reload factory should pair adapter and startup shell state."""

    state = _AdapterState()
    reload_state = create_startup_shell_reload_state()
    shell = object()

    adapter = create_bound_shell_reload_adapter(
        state=reload_state,
        main_window_for_shell=lambda frame: state.main_windows.get(frame),
        build_main_window=state.build_main_window,
        show_built_main_window=state.show_built_main_window,
        comfy_runtime_actions_for=state.comfy_runtime_actions_for,
        installation_context=object(),
        comfy_output_stream=object(),
        shutdown_request=state.shutdown_requests.append,
        startup_timer=object(),
        runtime_services=object(),
        managed_comfy_lease=ManagedComfyLease(_cleanup_result),
        restart_launch_command=state.restart_launch_command,
    )

    adapter.set_current_shell(shell)
    reload_state.save_session_before_cleanup()

    assert reload_state.shell_frame is shell
    assert isinstance(adapter, ShellReloadAdapter)


def test_startup_facade_delegates_shell_reload_adapter() -> None:
    """Startup should no longer own private shell reload adapter functions."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    support_graph_source = SUPPORT_GRAPH_SOURCE.read_text(encoding="utf-8")

    assert "create_startup_support_graph(initial_splash=initial_splash)" in source
    assert "create_startup_shell_reload_state()" not in source
    assert "create_startup_shell_reload_state()" in support_graph_source
    assert "create_startup_shell_runtime_graph(" in source
    assert "create_bound_shell_reload_adapter(" not in source
    assert "StartupShellReloadState()" not in source
    assert "create_shell_reload_adapter(" not in source
    assert "shell_reload_state.bind_adapter(" not in source
    assert "current_shell_changed=shell_reload_state.set_shell_frame" not in source
    assert "ShellReloadAdapter(" not in source
    assert "def build_reloaded_shell" not in source
    assert "def hydrate_shell" not in source
    assert "def show_reloaded_shell" not in source
    assert "def show_reload_message" not in source
    assert "def attach_gui_reload_command" not in source
    assert "def request_comfy_restart_from_shell" not in source
    assert "def has_cancellable_generation_jobs" not in source
    assert "def save_session_before_cleanup" not in source
    assert "def update_shell_frame" not in source


class _AdapterState:
    """Hold shell reload adapter test collaborators."""

    def __init__(
        self,
        *,
        restart_launch_command: tuple[str, ...] = ("python", "main.py"),
    ) -> None:
        """Initialize fake adapter state."""

        self.events: list[str] = []
        self.main_windows: dict[object, object] = {}
        self.restart_handlers: dict[int, Callable[[], None]] = {}
        self.shutdown_requests: list[object | None] = []
        self.current_shell_changes: list[object | None] = []
        self.built_shell: object = object()
        self.shown_shell: object = object()
        self.show_kwargs: dict[str, object] = {}
        self.restart_launch_command = restart_launch_command
        self.runtime_services = SimpleNamespace(
            appearance_runtime=SimpleNamespace(
                apply_persisted_preferences=self.apply_persisted_preferences
            ),
            active_appearance_baseline=SimpleNamespace(
                record_applied_preferences=self.record_applied_preferences
            ),
        )

    def build_adapter(self) -> ShellReloadAdapter:
        """Build one adapter with fake collaborators."""

        return create_shell_reload_adapter(
            main_window_for_shell=lambda shell: self.main_windows.get(shell),
            build_main_window=self.build_main_window,
            show_built_main_window=self.show_built_main_window,
            comfy_runtime_actions_for=self.comfy_runtime_actions_for,
            installation_context=object(),
            comfy_output_stream=object(),
            shutdown_request=self.shutdown_requests.append,
            startup_timer=object(),
            runtime_services=self.runtime_services,
            managed_comfy_lease=ManagedComfyLease(_cleanup_result),
            restart_launch_command=self.restart_launch_command,
            current_shell_changed=self.current_shell_changes.append,
        )

    def build_main_window(self, *_args: object, **_kwargs: object) -> object:
        """Record shell rebuild."""

        self.events.append("build_main_window")
        return self.built_shell

    def apply_persisted_preferences(self) -> object:
        """Record full appearance application before GUI rebuild."""

        self.events.append("apply_appearance")
        return SimpleNamespace(requested="appearance")

    def record_applied_preferences(self, preferences: object) -> None:
        """Record the active appearance baseline update."""

        assert preferences == "appearance"
        self.events.append("record_appearance")

    def show_built_main_window(self, shell: object, **kwargs: object) -> object:
        """Record shell show."""

        self.events.append("show_built_main_window")
        self.show_kwargs = kwargs
        assert shell is self.built_shell
        return self.shown_shell

    def comfy_runtime_actions_for(
        self,
        main_window: object,
    ) -> ComfyRuntimeRestartActions:
        """Return a fake Comfy runtime action adapter."""

        return _FakeComfyRuntimeActions(
            events=self.events,
            restart_handlers=self.restart_handlers,
            main_window=main_window,
        )

    def restart_handler_for(self, main_window: object) -> Callable[[], None] | None:
        """Return the restart handler registered for one main window."""

        return self.restart_handlers.get(id(main_window))


class _FakeComfyRuntimeActions:
    """Record restart handlers registered through the runtime action port."""

    def __init__(
        self,
        *,
        events: list[str],
        restart_handlers: dict[int, Callable[[], None]],
        main_window: object,
    ) -> None:
        """Store mutable test state used by the fake action adapter."""

        self._events = events
        self._restart_handlers = restart_handlers
        self._main_window = main_window

    def set_comfy_restart_request_handler(
        self,
        handler: Callable[[], None],
    ) -> None:
        """Record the restart request handler registered by the adapter."""

        self._events.append("runtime_restart_handler")
        self._restart_handlers[id(self._main_window)] = handler


def _cleanup_result() -> ManagedComfyCleanupResult:
    """Return a successful managed cleanup result."""

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
        workspace=None,
        elapsed_ms=1,
        taskkill_timeout=False,
        verification_timeout=False,
        user_detail="Cleanup finished cleanly.",
        technical_detail="Test cleanup finished cleanly.",
        diagnostic_detail="Test cleanup finished cleanly.",
    )

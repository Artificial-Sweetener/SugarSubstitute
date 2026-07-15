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

"""Adapt startup shell construction to full GUI reload coordination."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from substitute.app.bootstrap.gui_reload_coordinator import (
    GuiReloadCoordinator,
    ShellFrameProtocol,
)
from substitute.app.bootstrap.startup_shutdown import ManagedComfyLease
from substitute.shared.logging.logger import get_logger, log_exception, log_info

_LOGGER = get_logger("app.bootstrap.shell_reload_adapter")


@dataclass(frozen=True, slots=True)
class _ShellGenerationActionSnapshot:
    """Preserve generation action state across one disposable shell replacement."""

    backend_state: str
    selected_mode: str


class ComfyRuntimeRestartActions(Protocol):
    """Describe shell-facing Comfy runtime restart wiring."""

    def set_comfy_restart_request_handler(
        self,
        handler: Callable[[], None],
    ) -> None:
        """Install the shell callback that requests a managed Comfy restart."""


class ShellReloadAdapter:
    """Own shell-frame reload wiring and Comfy restart requests."""

    def __init__(
        self,
        *,
        main_window_for_shell: Callable[[object], object | None],
        build_main_window: Callable[..., object],
        show_built_main_window: Callable[..., object],
        comfy_runtime_actions_for: Callable[[object], ComfyRuntimeRestartActions],
        installation_context: object,
        comfy_output_stream: object,
        shutdown_request: Callable[[object | None], None],
        startup_timer: object,
        runtime_services: object,
        managed_comfy_lease: ManagedComfyLease,
        restart_launch_command: Sequence[str],
        current_shell_changed: Callable[[object | None], None] | None = None,
    ) -> None:
        """Store ports required to rebuild and reload shell frames."""

        self._main_window_for_shell = main_window_for_shell
        self._build_main_window = build_main_window
        self._show_built_main_window = show_built_main_window
        self._comfy_runtime_actions_for = comfy_runtime_actions_for
        self._installation_context = installation_context
        self._comfy_output_stream = comfy_output_stream
        self._shutdown_request = shutdown_request
        self._startup_timer = startup_timer
        self._runtime_services = runtime_services
        self._restart_launch_command = tuple(restart_launch_command)
        self._current_shell_changed = current_shell_changed
        self._current_shell: object | None = None
        self._pending_generation_action_snapshot: (
            _ShellGenerationActionSnapshot | None
        ) = None
        self._restart_after_cleanup_requested = False
        self._gui_reload_coordinator = GuiReloadCoordinator(
            current_shell=cast(
                Callable[[], ShellFrameProtocol | None],
                self.current_shell,
            ),
            set_current_shell=cast(
                Callable[[ShellFrameProtocol | None], None],
                self.set_current_shell,
            ),
            main_window_for_shell=cast(
                Callable[[ShellFrameProtocol], object | None],
                self._main_window_for_shell,
            ),
            build_shell=cast(
                Callable[[], ShellFrameProtocol], self.build_reloaded_shell
            ),
            show_shell=cast(
                Callable[[ShellFrameProtocol], ShellFrameProtocol],
                self.show_reloaded_shell,
            ),
            hydrate_shell=cast(
                Callable[[ShellFrameProtocol], None],
                self.hydrate_shell,
            ),
            managed_comfy_lease=managed_comfy_lease,
            request_shutdown=cast(
                Callable[[ShellFrameProtocol | None], None],
                self._shutdown_request,
            ),
            has_cancellable_jobs=self.has_cancellable_generation_jobs,
            message_sink=self.show_reload_message,
        )

    @property
    def restart_after_cleanup_requested(self) -> bool:
        """Return whether a Comfy restart relaunch was requested."""

        return self._restart_after_cleanup_requested

    @property
    def restart_launch_command(self) -> tuple[str, ...]:
        """Return the prepared relaunch command."""

        return self._restart_launch_command

    def current_shell(self) -> object | None:
        """Return the currently visible shell frame."""

        return self._current_shell

    def set_current_shell(self, shell_frame: object | None) -> None:
        """Replace the currently visible shell frame."""

        if shell_frame is None and self._current_shell is not None:
            self._pending_generation_action_snapshot = (
                self._capture_generation_action_snapshot(self._current_shell)
            )
        self._current_shell = shell_frame
        if self._current_shell_changed is not None:
            self._current_shell_changed(shell_frame)
        if shell_frame is not None:
            self._restore_generation_action_snapshot(shell_frame)

    def _capture_generation_action_snapshot(
        self,
        shell_frame: object,
    ) -> _ShellGenerationActionSnapshot | None:
        """Capture action state that process readiness will not emit again."""

        main_window = self._main_window_for_shell(shell_frame)
        backend_state = getattr(main_window, "_backend_state", None)
        selected_mode = getattr(main_window, "_current_generate_mode", None)
        if backend_state not in {"starting", "ready", "unavailable"}:
            return None
        if selected_mode not in {"generate", "continuous"}:
            return None
        log_info(
            _LOGGER,
            "Captured generation action state for GUI reload",
            backend_state=backend_state,
            selected_mode=selected_mode,
        )
        return _ShellGenerationActionSnapshot(
            backend_state=backend_state,
            selected_mode=selected_mode,
        )

    def _restore_generation_action_snapshot(self, shell_frame: object) -> None:
        """Apply captured generation action state to one replacement shell."""

        snapshot = self._pending_generation_action_snapshot
        if snapshot is None:
            return
        self._pending_generation_action_snapshot = None
        main_window = self._main_window_for_shell(shell_frame)
        generation_action_controller = getattr(
            main_window,
            "generation_action_controller",
            None,
        )
        set_backend_state = getattr(
            generation_action_controller,
            "set_backend_state",
            None,
        )
        set_selected_mode = getattr(
            generation_action_controller,
            "set_generation_selected_mode",
            None,
        )
        if not callable(set_backend_state) or not callable(set_selected_mode):
            log_info(
                _LOGGER,
                "Skipped generation action state restore for incomplete shell",
                shell_type=type(shell_frame).__name__,
            )
            return
        set_backend_state(snapshot.backend_state)
        set_selected_mode(snapshot.selected_mode)
        log_info(
            _LOGGER,
            "Restored generation action state after GUI reload",
            backend_state=snapshot.backend_state,
            selected_mode=snapshot.selected_mode,
        )

    def save_session_before_cleanup(self) -> None:
        """Persist the live shell session before managed Comfy cleanup starts."""

        shell_frame = self.current_shell()
        if shell_frame is None:
            return
        main_window = self._main_window_for_shell(shell_frame)
        session_autosave_controller = getattr(
            main_window,
            "session_autosave_controller",
            None,
        )
        force_save = getattr(
            session_autosave_controller,
            "force_save_session_snapshot",
            None,
        )
        if callable(force_save):
            force_save()

    def has_cancellable_generation_jobs(self) -> bool:
        """Return whether the current shell has queue work unsafe for reload."""

        shell_frame = self.current_shell()
        if shell_frame is None:
            return False
        main_window = self._main_window_for_shell(shell_frame)
        queue_service = getattr(main_window, "generation_job_queue_service", None)
        has_cancellable_jobs = getattr(queue_service, "has_cancellable_jobs", None)
        return bool(has_cancellable_jobs()) if callable(has_cancellable_jobs) else False

    def build_reloaded_shell(self) -> object:
        """Build a new shell frame from process-lifetime runtime services."""

        log_info(_LOGGER, "startup build reloaded shell started")
        self._apply_persisted_appearance_for_reload()
        frame = self._build_main_window(
            self._installation_context,
            comfy_output_stream=self._comfy_output_stream,
            shutdown_request=self._shutdown_request,
            startup_timer=self._startup_timer,
            runtime_services=self._runtime_services,
        )
        self.attach_gui_reload_command(frame)
        log_info(
            _LOGGER,
            "startup build reloaded shell completed",
            frame_type=type(frame).__name__,
        )
        return frame

    def _apply_persisted_appearance_for_reload(self) -> None:
        """Apply saved appearance settings before constructing a reloaded shell."""

        appearance_runtime = getattr(self._runtime_services, "appearance_runtime", None)
        apply_preferences = getattr(
            appearance_runtime,
            "apply_persisted_preferences",
            None,
        )
        if not callable(apply_preferences):
            return
        resolved = apply_preferences()
        active_baseline = getattr(
            self._runtime_services,
            "active_appearance_baseline",
            None,
        )
        record_applied = getattr(active_baseline, "record_applied_preferences", None)
        requested = getattr(resolved, "requested", None)
        if callable(record_applied) and requested is not None:
            record_applied(requested)

    def hydrate_shell(self, frame: object) -> None:
        """Hydrate one rebuilt shell from the just-saved session snapshot."""

        main_window = self._main_window_for_shell(frame)
        log_info(
            _LOGGER,
            "startup hydrate reloaded shell",
            frame_type=type(frame).__name__,
            main_window_present=main_window is not None,
            main_window_type=type(main_window).__name__
            if main_window is not None
            else "",
        )
        workspace_restore_controller = getattr(
            main_window,
            "workspace_restore_controller",
            None,
        )
        hydrate = getattr(
            workspace_restore_controller, "hydrate_initial_workspace", None
        )
        if callable(hydrate):
            hydrate()
        log_info(_LOGGER, "startup hydrate reloaded shell completed")

    def show_reloaded_shell(self, frame: object) -> object:
        """Show a reloaded shell without overwriting restored geometry."""

        log_info(
            _LOGGER,
            "startup show reloaded shell",
            frame_type=type(frame).__name__,
            apply_default_geometry=False,
        )
        shown = self._show_built_main_window(
            frame,
            apply_default_geometry=False,
        )
        log_info(
            _LOGGER,
            "startup show reloaded shell completed",
            shown_type=type(shown).__name__,
        )
        return shown

    def show_reload_message(self, message: str) -> None:
        """Show one non-fatal GUI reload message."""

        try:
            from PySide6.QtWidgets import QMessageBox
            from PySide6.QtWidgets import QWidget

            parent = cast(QWidget | None, self.current_shell())
            QMessageBox.warning(parent, "Reload GUI", message)
        except Exception:
            log_exception(_LOGGER, "Failed to show GUI reload message")

    def attach_gui_reload_command(self, frame: object) -> None:
        """Expose reload and Comfy restart commands on the shell MainWindow."""

        main_window = self._main_window_for_shell(frame)
        if main_window is None:
            return
        setattr(
            main_window,
            "request_full_gui_reload",
            self._gui_reload_coordinator.reload_shell,
        )
        self._comfy_runtime_actions_for(main_window).set_comfy_restart_request_handler(
            self.request_comfy_restart_from_shell
        )

    def request_comfy_restart_from_shell(self) -> None:
        """Request full app relaunch so startup restarts ComfyUI with splash."""

        if self._restart_after_cleanup_requested:
            log_info(_LOGGER, "Duplicate ComfyUI restart request ignored")
            return
        self._restart_after_cleanup_requested = True
        log_info(
            _LOGGER,
            "ComfyUI restart requested from shell",
            command=self._restart_launch_command,
        )
        self._shutdown_request(self.current_shell())


class StartupShellReloadState:
    """Hold startup shell-frame state shared with shell reload coordination."""

    def __init__(self) -> None:
        """Initialize startup shell state before the reload adapter exists."""

        self.shell_frame: object | None = None
        self._adapter: ShellReloadAdapter | None = None

    def bind_adapter(self, adapter: ShellReloadAdapter) -> None:
        """Bind the concrete reload adapter after shutdown runtime creation."""

        self._adapter = adapter

    def set_shell_frame(self, frame: object | None) -> None:
        """Keep the startup lifetime shell-frame reference current."""

        self.shell_frame = frame

    def save_session_before_cleanup(self) -> None:
        """Persist the current shell session before managed Comfy cleanup."""

        if self._adapter is not None:
            self._adapter.save_session_before_cleanup()


def create_shell_reload_adapter(
    *,
    main_window_for_shell: Callable[[object], object | None],
    build_main_window: Callable[..., object],
    show_built_main_window: Callable[..., object],
    comfy_runtime_actions_for: Callable[[object], ComfyRuntimeRestartActions],
    installation_context: object,
    comfy_output_stream: object,
    shutdown_request: Callable[[object | None], None],
    startup_timer: object,
    runtime_services: object,
    managed_comfy_lease: ManagedComfyLease,
    restart_launch_command: Sequence[str],
    current_shell_changed: Callable[[object | None], None] | None = None,
) -> ShellReloadAdapter:
    """Create the concrete shell reload adapter."""

    return ShellReloadAdapter(
        main_window_for_shell=main_window_for_shell,
        build_main_window=build_main_window,
        show_built_main_window=show_built_main_window,
        comfy_runtime_actions_for=comfy_runtime_actions_for,
        installation_context=installation_context,
        comfy_output_stream=comfy_output_stream,
        shutdown_request=shutdown_request,
        startup_timer=startup_timer,
        runtime_services=runtime_services,
        managed_comfy_lease=managed_comfy_lease,
        restart_launch_command=restart_launch_command,
        current_shell_changed=current_shell_changed,
    )


def create_startup_shell_reload_state() -> StartupShellReloadState:
    """Create the startup shell reload state object."""

    return StartupShellReloadState()


def create_bound_shell_reload_adapter(
    *,
    state: StartupShellReloadState,
    main_window_for_shell: Callable[[object], object | None],
    build_main_window: Callable[..., object],
    show_built_main_window: Callable[..., object],
    comfy_runtime_actions_for: Callable[[object], ComfyRuntimeRestartActions],
    installation_context: object,
    comfy_output_stream: object,
    shutdown_request: Callable[[object | None], None],
    startup_timer: object,
    runtime_services: object,
    managed_comfy_lease: ManagedComfyLease,
    restart_launch_command: Sequence[str],
) -> ShellReloadAdapter:
    """Create and bind the shell reload adapter to startup shell state."""

    adapter = create_shell_reload_adapter(
        main_window_for_shell=main_window_for_shell,
        build_main_window=build_main_window,
        show_built_main_window=show_built_main_window,
        comfy_runtime_actions_for=comfy_runtime_actions_for,
        installation_context=installation_context,
        comfy_output_stream=comfy_output_stream,
        shutdown_request=shutdown_request,
        startup_timer=startup_timer,
        runtime_services=runtime_services,
        managed_comfy_lease=managed_comfy_lease,
        restart_launch_command=restart_launch_command,
        current_shell_changed=state.set_shell_frame,
    )
    state.bind_adapter(adapter)
    return adapter


__all__ = [
    "ShellReloadAdapter",
    "StartupShellReloadState",
    "create_bound_shell_reload_adapter",
    "create_shell_reload_adapter",
    "create_startup_shell_reload_state",
]

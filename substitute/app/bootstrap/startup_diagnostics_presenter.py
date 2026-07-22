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

"""Prepare and apply startup diagnostics titlebar state."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from substitute.app.bootstrap.startup_trace import trace_mark
from substitute.app.bootstrap.startup_trace import trace_span
from substitute.application.comfy_startup_diagnostics import (
    StartupDiagnosticsTitlebarState,
    prepare_startup_diagnostics_titlebar_state,
)
from substitute.application.execution import (
    ExecutionContext,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.application.ports.comfy_extension_metadata_provider import (
    ComfyExtensionMetadataProvider,
)
from substitute.application.ports.startup_diagnostics_ignore_repository import (
    StartupDiagnosticsIgnoreRepository,
)
from substitute.domain.comfy_startup_diagnostics import ComfyStartupIncident
from substitute.domain.onboarding import ComfyTargetMode, InstallationContext
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("app.bootstrap.startup_diagnostics_presenter")


class PreparedDiagnosticsSignalProtocol(Protocol):
    """Bridge prepared diagnostics state back to the GUI thread."""

    def connect(self, callback: Callable[[object], None]) -> object:
        """Connect one prepared-state callback."""

    def emit(self, state: object) -> None:
        """Emit one prepared diagnostics state."""


class PreparedDiagnosticsBridgeProtocol(Protocol):
    """Expose the prepared diagnostics signal from a GUI-thread bridge."""

    prepared: PreparedDiagnosticsSignalProtocol


def request_startup_diagnostics_titlebar_preparation(
    *,
    main_window: object,
    incidents: tuple[ComfyStartupIncident, ...],
    transcript: tuple[str, ...],
    ignore_repository: StartupDiagnosticsIgnoreRepository,
    metadata_providers: tuple[ComfyExtensionMetadataProvider, ...],
    bridge_factory: Callable[[], PreparedDiagnosticsBridgeProtocol],
    register_bridge: Callable[[PreparedDiagnosticsBridgeProtocol], None],
    submitter_factory: Callable[[], TaskSubmitter],
    register_submitter: Callable[[TaskSubmitter], None],
    startup_cancelled: Callable[[], bool],
    shell_frame_available: Callable[[], bool],
) -> bool:
    """Create startup diagnostics resources and request async titlebar prep."""

    bridge = bridge_factory()
    register_bridge(bridge)
    submitter = submitter_factory()
    register_submitter(submitter)
    return start_startup_diagnostics_preparation(
        main_window=main_window,
        incidents=incidents,
        transcript=transcript,
        ignore_repository=ignore_repository,
        metadata_providers=metadata_providers,
        prepared_signal=bridge.prepared,
        submitter=submitter,
        startup_cancelled=startup_cancelled,
        shell_frame_available=shell_frame_available,
    )


def apply_startup_diagnostics_titlebar_state(
    *,
    main_window: object | None,
    incidents: tuple[ComfyStartupIncident, ...],
    transcript: tuple[str, ...],
    ignore_repository: StartupDiagnosticsIgnoreRepository,
    metadata_providers: tuple[ComfyExtensionMetadataProvider, ...] = (),
) -> None:
    """Apply recoverable startup diagnostics to the shell titlebar if supported."""

    state = prepare_startup_diagnostics_titlebar_state_for_shell(
        incidents=incidents,
        transcript=transcript,
        ignore_repository=ignore_repository,
        metadata_providers=metadata_providers,
    )
    apply_prepared_startup_diagnostics_titlebar_state(
        main_window=main_window,
        state=state,
    )


def prepare_startup_diagnostics_titlebar_state_for_shell(
    *,
    incidents: tuple[ComfyStartupIncident, ...],
    transcript: tuple[str, ...],
    ignore_repository: StartupDiagnosticsIgnoreRepository,
    metadata_providers: tuple[ComfyExtensionMetadataProvider, ...] = (),
) -> StartupDiagnosticsTitlebarState | None:
    """Prepare startup diagnostics titlebar state without touching shell widgets."""

    ignored_fingerprints = ignore_repository.load_ignored_fingerprints()
    return prepare_startup_diagnostics_titlebar_state(
        incidents=incidents,
        transcript=transcript,
        ignored_fingerprints=ignored_fingerprints,
        metadata_providers=metadata_providers,
    )


def apply_prepared_startup_diagnostics_titlebar_state(
    *,
    main_window: object | None,
    state: StartupDiagnosticsTitlebarState | None,
) -> None:
    """Apply already-prepared startup diagnostics to the shell titlebar."""

    frame_integration_controller = getattr(
        main_window,
        "shell_frame_integration_controller",
        None,
    )
    set_state = getattr(
        frame_integration_controller,
        "set_startup_diagnostics_state",
        None,
    )
    if not callable(set_state):
        return
    with trace_span("post_show.apply_prepared_startup_diagnostics"):
        set_state(state)


def start_startup_diagnostics_preparation(
    *,
    main_window: object,
    incidents: tuple[ComfyStartupIncident, ...],
    transcript: tuple[str, ...],
    ignore_repository: StartupDiagnosticsIgnoreRepository,
    metadata_providers: tuple[ComfyExtensionMetadataProvider, ...],
    prepared_signal: PreparedDiagnosticsSignalProtocol,
    submitter: TaskSubmitter,
    startup_cancelled: Callable[[], bool],
    shell_frame_available: Callable[[], bool],
) -> bool:
    """Prepare recoverable startup diagnostics without delaying shell reveal."""

    if not incidents:
        trace_mark(
            "startup_diagnostics.prepare_titlebar_state_async.skip",
            reason="no_incidents",
        )
        return False

    def apply_prepared_state(state: object) -> None:
        """Apply async-prepared diagnostics state on the GUI thread."""

        if startup_cancelled() or not shell_frame_available():
            trace_mark(
                "startup_diagnostics.prepare_titlebar_state_async.apply_skip",
                reason="startup_cancelled" if startup_cancelled() else "no_shell_frame",
            )
            return
        apply_prepared_startup_diagnostics_titlebar_state(
            main_window=main_window,
            state=state
            if isinstance(state, StartupDiagnosticsTitlebarState) or state is None
            else None,
        )

    prepared_signal.connect(apply_prepared_state)

    def prepare_state() -> StartupDiagnosticsTitlebarState | None:
        """Prepare diagnostics titlebar state through the startup lane."""

        with trace_span(
            "startup_diagnostics.prepare_titlebar_state_async",
            incident_count=len(incidents),
            transcript_line_count=len(transcript),
        ):
            return prepare_startup_diagnostics_titlebar_state_for_shell(
                incidents=incidents,
                transcript=transcript,
                ignore_repository=ignore_repository,
                metadata_providers=metadata_providers,
            )

    def publish_prepared_state(
        outcome: TaskOutcome[StartupDiagnosticsTitlebarState | None],
    ) -> None:
        """Publish task outcome through the prepared-state signal."""

        scope.close(reason="startup_diagnostics_titlebar_prepared")
        if outcome.status != "succeeded":
            trace_mark("startup_diagnostics.prepare_titlebar_state_async.error")
            state = None
            if outcome.error is not None:
                log_warning(
                    _LOGGER,
                    "Failed to prepare startup diagnostics titlebar state",
                    error_type=type(outcome.error).__name__,
                    error=repr(outcome.error),
                )
        else:
            state = outcome.result
        prepared_signal.emit(state)

    trace_mark(
        "startup_diagnostics.prepare_titlebar_state_async.start_requested",
        incident_count=len(incidents),
    )
    request: TaskRequest[StartupDiagnosticsTitlebarState | None] = TaskRequest(
        identity=TaskIdentity(
            request_id=1,
            domain="startup_diagnostics",
        ),
        context=ExecutionContext(
            operation="startup_diagnostics_titlebar_preparation",
            reason="startup_diagnostics",
            lane="startup",
        ),
        work=lambda _token: prepare_state(),
    )
    scope = TaskScope(
        submitter=submitter,
        scope_id="startup_diagnostics_titlebar_preparation",
    )
    try:
        handle = scope.submit(request)
    except Exception:
        scope.close(reason="startup_diagnostics_titlebar_submit_failed")
        raise
    handle.add_done_callback(
        publish_prepared_state,
        reason="startup_diagnostics_titlebar_prepared",
    )
    return True


def startup_extension_metadata_providers(
    installation_context: InstallationContext,
) -> tuple[ComfyExtensionMetadataProvider, ...]:
    """Return metadata providers for the active Comfy startup target."""

    target = installation_context.comfy_target
    workspace = target.workspace_path or installation_context.managed_comfy_dir
    from substitute.infrastructure.comfy.comfy_manager_extension_metadata import (
        ComfyManagerExtensionMetadataProvider,
    )
    from substitute.infrastructure.comfy.local_custom_node_git_metadata import (
        LocalCustomNodeGitMetadataProvider,
    )
    from substitute.infrastructure.comfy.manager_runtime_probe import (
        detect_workspace_manager_runtime,
    )

    manager_kind = (
        None
        if target.mode is ComfyTargetMode.REMOTE
        else detect_workspace_manager_runtime(
            workspace,
            python_executable=(
                target.python_binding.executable
                if target.python_binding is not None
                else None
            ),
        ).kind
    )

    providers: list[ComfyExtensionMetadataProvider] = [
        ComfyManagerExtensionMetadataProvider(
            host=target.endpoint.host,
            port=target.endpoint.port,
            manager_kind=manager_kind,
            timeout_seconds=1.0,
        )
    ]
    custom_nodes_dir = workspace / "custom_nodes"
    if custom_nodes_dir.is_dir():
        providers.append(
            LocalCustomNodeGitMetadataProvider(
                custom_nodes_dir=custom_nodes_dir,
            )
        )
    return tuple(providers)


__all__ = [
    "apply_prepared_startup_diagnostics_titlebar_state",
    "apply_startup_diagnostics_titlebar_state",
    "prepare_startup_diagnostics_titlebar_state_for_shell",
    "PreparedDiagnosticsBridgeProtocol",
    "PreparedDiagnosticsSignalProtocol",
    "request_startup_diagnostics_titlebar_preparation",
    "start_startup_diagnostics_preparation",
    "startup_extension_metadata_providers",
]

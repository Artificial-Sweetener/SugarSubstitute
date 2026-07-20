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

"""Coordinate ready-shell startup task slices through explicit ports."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ContextManager, Protocol

from sugarsubstitute_shared.presentation.localization import (
    app_text,
    render_application_text,
)

from substitute.app.bootstrap.gui_startup_queue import GuiStartupTaskQueue
from substitute.app.bootstrap.no_comfy_ready_shell import (
    launch_no_comfy_ready_shell,
    publish_no_comfy_ready_shell_result,
)
from substitute.app.bootstrap.ready_shell_startup_tasks import (
    ReadyShellStartupTaskQueueProtocol,
    schedule_ready_shell_startup_tasks,
)
from substitute.app.bootstrap.pre_show_restore_projection import (
    PreShowRestoreProjectionStarter,
    PreShowRestoreProjectionState,
    start_pre_show_restore_projection_if_available,
)
from substitute.app.bootstrap.ready_shell_launch_gate import (
    ReadyShellLaunchGateState,
    try_begin_ready_shell_launch,
)
from substitute.app.bootstrap.ready_shell_restore_controller import (
    HydrationStartupTimerProtocol,
    ReadyShellPrehydrationResult,
    attach_restore_asset_preload_to_shell,
    hydrate_initial_workspace_after_show,
    log_visible_startup_summary,
    mark_minimum_shell_ready,
    prepare_hidden_restore_runtime_before_show,
    prehydrate_initial_workspace_before_show,
    schedule_post_show_hydration_after_reveal,
    update_shell_backend_state,
    warm_prompt_editor_gui_before_reveal,
)
from substitute.app.bootstrap.startup_failure_controller import (
    RuntimeCompatibilityProbeProtocol,
    SplashCloseProtocol,
    StartupFailClosedCleanupPortFactory,
    StartupFailureController,
    StartupTimerProtocol,
)
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.app.bootstrap.startup_trace import trace_mark, trace_span
from substitute.app.bootstrap.startup_warmup_controller import (
    StartupWarmupState,
    connect_restore_finalized_warmups,
)
from substitute.domain.comfy_startup_diagnostics import ComfyStartupIncident
from substitute.domain.onboarding import InstallationContext
from substitute.shared.logging.logger import get_logger, log_exception, log_info

_LOGGER = get_logger("app.bootstrap.ready_shell_controller")

if TYPE_CHECKING:
    from substitute.app.bootstrap.startup_model_metadata import (
        ModelMetadataUpdateSignalBridgeProtocol,
    )
else:
    ModelMetadataUpdateSignalBridgeProtocol = object


class StartupPhaseTimerProtocol(Protocol):
    """Measure one named startup phase."""

    def phase(self, name: str) -> ContextManager[None]:
        """Return a context manager for the named phase."""


class ReadyShellRevealTimerProtocol(StartupPhaseTimerProtocol, Protocol):
    """Measure and mark ready-shell reveal phases."""

    def mark(self, name: str) -> object:
        """Record one named startup milestone."""


class ReadyShellSplashProtocol(Protocol):
    """Close the launch splash when the ready shell becomes visible."""

    def close(self) -> object:
        """Close the splash surface."""


class StartupSplashLogProtocol(Protocol):
    """Append user-visible startup progress lines."""

    def append_log(self, line: str) -> None:
        """Append one startup progress line."""


class ReadyShellPrehydrationStateProtocol(Protocol):
    """Record ready-shell prehydration gate state."""

    prehydration_attempted: bool
    prehydration_succeeded: bool


class ReadyShellMinimumReadyStateProtocol(Protocol):
    """Record the ready-shell minimum-ready gate state."""

    minimum_shell_ready: bool


class ReadyShellActivationStateProtocol(Protocol):
    """Record whether ready-shell target activation has started."""

    comfy_activation_started: bool


class ReadyShellHydrationStateProtocol(Protocol):
    """Record whether ready-shell post-show hydration has started."""

    hydration_started: bool


class ReadyShellShowStateProtocol(Protocol):
    """Record whether ready-shell reveal has started."""

    main_window_shown: bool


class ReadyShellLaunchController:
    """Own ready-shell launch gating and top-level route branch selection."""

    def __init__(
        self,
        *,
        no_comfy: bool,
        startup_cancelled: Callable[[], bool],
        shell_frame_present: Callable[[], bool],
        splash: Callable[[], object | None],
        set_splash: Callable[[object | None], None],
        comfy_output_stream: object,
        shutdown_request: object,
        startup_timer: object,
        runtime_services: object,
        initial_shell_placement: object | None,
        initial_workspace: object | None,
        show_main_window: Callable[..., object],
        attach_gui_reload_command: Callable[[object], None],
        set_current_shell: Callable[[object], None],
        launch_managed_ready_shell: Callable[[InstallationContext], None],
        gate_state: ReadyShellLaunchGateState | None = None,
    ) -> None:
        """Store launch collaborators and initialize duplicate-launch state."""

        self._no_comfy = no_comfy
        self._startup_cancelled = startup_cancelled
        self._shell_frame_present = shell_frame_present
        self._splash = splash
        self._set_splash = set_splash
        self._comfy_output_stream = comfy_output_stream
        self._shutdown_request = shutdown_request
        self._startup_timer = startup_timer
        self._runtime_services = runtime_services
        self._initial_shell_placement = initial_shell_placement
        self._initial_workspace = initial_workspace
        self._show_main_window = show_main_window
        self._attach_gui_reload_command = attach_gui_reload_command
        self._set_current_shell = set_current_shell
        self._launch_managed_ready_shell = launch_managed_ready_shell
        self._gate_state = (
            ReadyShellLaunchGateState() if gate_state is None else gate_state
        )

    def launch(self, context: InstallationContext) -> None:
        """Launch the ready route once for either no-Comfy or managed startup."""

        target = getattr(context, "comfy_target")
        endpoint = getattr(target, "endpoint")
        if not try_begin_ready_shell_launch(
            self._gate_state,
            startup_cancelled=self._startup_cancelled(),
            shell_frame_present=self._shell_frame_present(),
            no_comfy=self._no_comfy,
            target_mode=getattr(target, "mode"),
            target_host=getattr(endpoint, "host"),
            target_port=getattr(endpoint, "port"),
        ):
            return
        if self._no_comfy:
            no_comfy_shell = launch_no_comfy_ready_shell(
                context=context,
                splash=self._splash(),
                comfy_output_stream=self._comfy_output_stream,
                shutdown_request=self._shutdown_request,
                startup_timer=self._startup_timer,
                runtime_services=self._runtime_services,
                initial_shell_placement=self._initial_shell_placement,
                initial_workspace=self._initial_workspace,
                show_main_window=self._show_main_window,
                attach_gui_reload_command=self._attach_gui_reload_command,
            )
            published_no_comfy_shell = publish_no_comfy_ready_shell_result(
                no_comfy_shell,
                set_current_shell=self._set_current_shell,
            )
            self._set_splash(published_no_comfy_shell.splash)
            return

        self._launch_managed_ready_shell(context)


def create_ready_shell_launch_controller(
    *,
    no_comfy: bool,
    startup_cancelled: Callable[[], bool],
    shell_frame_present: Callable[[], bool],
    splash: Callable[[], object | None],
    set_splash: Callable[[object | None], None],
    comfy_output_stream: object,
    shutdown_request: object,
    startup_timer: object,
    runtime_services: object,
    initial_shell_placement: object | None,
    initial_workspace: object | None,
    show_main_window: Callable[..., object],
    attach_gui_reload_command: Callable[[object], None],
    set_current_shell: Callable[[object], None],
    launch_managed_ready_shell: Callable[[InstallationContext], None],
    gate_state: ReadyShellLaunchGateState | None = None,
) -> ReadyShellLaunchController:
    """Create the concrete ready-shell launch controller."""

    return ReadyShellLaunchController(
        no_comfy=no_comfy,
        startup_cancelled=startup_cancelled,
        shell_frame_present=shell_frame_present,
        splash=splash,
        set_splash=set_splash,
        comfy_output_stream=comfy_output_stream,
        shutdown_request=shutdown_request,
        startup_timer=startup_timer,
        runtime_services=runtime_services,
        initial_shell_placement=initial_shell_placement,
        initial_workspace=initial_workspace,
        show_main_window=show_main_window,
        attach_gui_reload_command=attach_gui_reload_command,
        set_current_shell=set_current_shell,
        launch_managed_ready_shell=launch_managed_ready_shell,
        gate_state=gate_state,
    )


class ReadyShellManagedStartupPrelude:
    """Own pre-queue managed ready-shell startup wiring."""

    def __init__(
        self,
        *,
        connect_cancel_request: Callable[[Callable[[], None]], object],
        request_startup_cancel: Callable[[], None],
        initial_splash_cancel_connector: Callable[[Callable[[], None]], None] | None,
        emit_splash_cancel: Callable[[], None],
        splash: Callable[[], object | None],
        set_splash: Callable[[object | None], None],
        startup_timer: object,
        resolved_appearance: object,
        start_or_adopt_launch_splash: Callable[..., object],
    ) -> None:
        """Store ports for cancel wiring and launch splash startup."""

        self._connect_cancel_request = connect_cancel_request
        self._request_startup_cancel = request_startup_cancel
        self._initial_splash_cancel_connector = initial_splash_cancel_connector
        self._emit_splash_cancel = emit_splash_cancel
        self._splash = splash
        self._set_splash = set_splash
        self._startup_timer = startup_timer
        self._resolved_appearance = resolved_appearance
        self._start_or_adopt_launch_splash = start_or_adopt_launch_splash

    def run(self) -> None:
        """Wire cancel behavior and start or adopt the launch splash."""

        self._connect_cancel_request(self._request_startup_cancel)
        if self._initial_splash_cancel_connector is not None:
            self._initial_splash_cancel_connector(self._emit_splash_cancel)
        self._set_splash(
            self._start_or_adopt_launch_splash(
                splash=self._splash(),
                startup_timer=self._startup_timer,
                resolved_appearance=self._resolved_appearance,
                on_cancel_requested=self._emit_splash_cancel,
            )
        )


def create_ready_shell_managed_startup_prelude(
    *,
    connect_cancel_request: Callable[[Callable[[], None]], object],
    request_startup_cancel: Callable[[], None],
    initial_splash_cancel_connector: Callable[[Callable[[], None]], None] | None,
    emit_splash_cancel: Callable[[], None],
    splash: Callable[[], object | None],
    set_splash: Callable[[object | None], None],
    startup_timer: object,
    resolved_appearance: object,
    start_or_adopt_launch_splash: Callable[..., object],
) -> ReadyShellManagedStartupPrelude:
    """Create the live managed ready-shell startup prelude."""

    return ReadyShellManagedStartupPrelude(
        connect_cancel_request=connect_cancel_request,
        request_startup_cancel=request_startup_cancel,
        initial_splash_cancel_connector=initial_splash_cancel_connector,
        emit_splash_cancel=emit_splash_cancel,
        splash=splash,
        set_splash=set_splash,
        startup_timer=startup_timer,
        resolved_appearance=resolved_appearance,
        start_or_adopt_launch_splash=start_or_adopt_launch_splash,
    )


class ReadyShellFailureQueue:
    """Adapt ready-shell failure handling and GUI task queue construction."""

    def __init__(
        self,
        *,
        is_startup_cancelled: Callable[[], bool],
        mark_startup_cancelled: Callable[[], None],
        readiness_timers: Callable[[], Sequence[StartupTimerProtocol]],
        runtime_compatibility_probes: Callable[
            [], Sequence[RuntimeCompatibilityProbeProtocol]
        ],
        managed_comfy_state: Callable[[], object | None],
        splash: Callable[[], SplashCloseProtocol | None],
        cleanup: Callable[[], object],
        quit_app: Callable[[], None],
        trace_fields: Callable[[], dict[str, object]],
        managed_failure_report_factory: Callable[[ComfyStartupIncident], Any],
        present_startup_failure_report: Callable[[Any], None],
        scheduler: Callable[[int, Callable[[], None]], None],
        startup_timer: StartupTimer,
    ) -> None:
        """Create failure handling with a GUI queue that can be cancelled."""

        self._gui_queue: GuiStartupTaskQueue | None = None
        self._failure_controller = StartupFailureController(
            is_startup_cancelled=is_startup_cancelled,
            mark_startup_cancelled=mark_startup_cancelled,
            cleanup_ports=StartupFailClosedCleanupPortFactory(
                readiness_timers=readiness_timers,
                runtime_compatibility_probes=runtime_compatibility_probes,
                managed_comfy_state=managed_comfy_state,
                splash=splash,
                cleanup=cleanup,
                quit_app=quit_app,
                cancel_gui_queue=self.cancel_queue,
            ),
            trace_fields=trace_fields,
            managed_failure_report_factory=managed_failure_report_factory,
            present_startup_failure_report=present_startup_failure_report,
            quit_app=quit_app,
        )
        self._gui_queue = GuiStartupTaskQueue(
            scheduler=scheduler,
            startup_timer=startup_timer,
            failed=self._failure_controller.handle_gui_startup_failure,
        )

    def request_startup_cancel(self) -> None:
        """Forward a startup cancel request into fail-closed cleanup."""

        self._failure_controller.request_startup_cancel()

    def handle_managed_startup_failure(self, incident: object) -> None:
        """Forward a managed startup incident into fail-closed cleanup."""

        self._failure_controller.handle_managed_startup_failure(incident)

    def add_task(self, name: str, callback: Callable[[], None]) -> None:
        """Add one GUI startup task to the owned queue."""

        self._require_queue().add(name, callback)

    def start_queue(self) -> None:
        """Start the owned GUI startup queue."""

        self._require_queue().start()

    def cancel_queue(self) -> None:
        """Cancel the owned GUI startup queue."""

        self._require_queue().cancel()

    @property
    def queue(self) -> GuiStartupTaskQueue:
        """Return the owned GUI startup queue for startup task ordering helpers."""

        return self._require_queue()

    def _require_queue(self) -> GuiStartupTaskQueue:
        """Return the queue after construction has completed."""

        if self._gui_queue is None:
            raise RuntimeError("Ready-shell GUI startup queue is not available.")
        return self._gui_queue


def create_ready_shell_failure_queue(
    *,
    is_startup_cancelled: Callable[[], bool],
    mark_startup_cancelled: Callable[[], None],
    readiness_timers: Callable[[], Sequence[StartupTimerProtocol]],
    runtime_compatibility_probes: Callable[
        [], Sequence[RuntimeCompatibilityProbeProtocol]
    ],
    managed_comfy_state: Callable[[], object | None],
    splash: Callable[[], SplashCloseProtocol | None],
    cleanup: Callable[[], object],
    quit_app: Callable[[], None],
    trace_fields: Callable[[], dict[str, object]],
    managed_failure_report_factory: Callable[[ComfyStartupIncident], Any],
    present_startup_failure_report: Callable[[Any], None],
    scheduler: Callable[[int, Callable[[], None]], None],
    startup_timer: StartupTimer,
) -> ReadyShellFailureQueue:
    """Create the live ready-shell failure queue."""

    return ReadyShellFailureQueue(
        is_startup_cancelled=is_startup_cancelled,
        mark_startup_cancelled=mark_startup_cancelled,
        readiness_timers=readiness_timers,
        runtime_compatibility_probes=runtime_compatibility_probes,
        managed_comfy_state=managed_comfy_state,
        splash=splash,
        cleanup=cleanup,
        quit_app=quit_app,
        trace_fields=trace_fields,
        managed_failure_report_factory=managed_failure_report_factory,
        present_startup_failure_report=present_startup_failure_report,
        scheduler=scheduler,
        startup_timer=startup_timer,
    )


def schedule_ready_shell_controller_startup_tasks(
    *,
    queue: ReadyShellStartupTaskQueueProtocol,
    target_activation_task: ReadyShellTargetActivationTask,
    start_readiness_timer: Callable[[], None],
    shell_build_task: ReadyShellBuildTask,
    metadata_bridge_task: ReadyShellMetadataBridgeTask,
    prompt_editor_warmup_task: ReadyShellPromptEditorWarmupTask,
    initial_workspace_prehydration_task: ReadyShellInitialWorkspacePrehydrationTask,
    minimum_shell_ready_task: ReadyShellMinimumReadyTask,
) -> None:
    """Schedule live ready-shell task adapters through the canonical queue owner."""

    schedule_ready_shell_startup_tasks(
        queue=queue,
        activate_target=target_activation_task.run,
        start_readiness_timer=start_readiness_timer,
        build_main_window=shell_build_task.run,
        wire_metadata_bridge=metadata_bridge_task.run,
        warm_prompt_editor_gui=prompt_editor_warmup_task.run,
        prehydrate_initial_workspace=initial_workspace_prehydration_task.run,
        mark_minimum_shell_ready=minimum_shell_ready_task.run,
    )


class ReadyShellLocalEditorWarmupAdapter:
    """Adapt live startup state into the shell-build local editor warmup port."""

    def __init__(
        self,
        *,
        state: StartupWarmupState,
        startup_cancelled: Callable[[], bool],
        main_window_for_shell: Callable[[object], object],
        registry: object,
        trace_fields: Callable[[], Mapping[str, object]],
        start_local_editor_warmup: Callable[..., object],
    ) -> None:
        """Store live collaborators needed to start local editor warmup."""

        self._state = state
        self._startup_cancelled = startup_cancelled
        self._main_window_for_shell = main_window_for_shell
        self._registry = registry
        self._trace_fields = trace_fields
        self._start_local_editor_warmup = start_local_editor_warmup

    def start(self, shell_frame: object) -> object:
        """Start local editor warmup for the newly built shell frame."""

        return self._start_local_editor_warmup(
            state=self._state,
            startup_cancelled=self._startup_cancelled(),
            shell_frame=shell_frame,
            main_window_for_shell=self._main_window_for_shell,
            registry=self._registry,
            trace_fields=self._trace_fields,
        )


def create_ready_shell_local_editor_warmup_adapter(
    *,
    state: StartupWarmupState,
    startup_cancelled: Callable[[], bool],
    main_window_for_shell: Callable[[object], object],
    registry: object,
    trace_fields: Callable[[], Mapping[str, object]],
    start_local_editor_warmup: Callable[..., object],
) -> ReadyShellLocalEditorWarmupAdapter:
    """Create the live ready-shell local editor warmup adapter."""

    return ReadyShellLocalEditorWarmupAdapter(
        state=state,
        startup_cancelled=startup_cancelled,
        main_window_for_shell=main_window_for_shell,
        registry=registry,
        trace_fields=trace_fields,
        start_local_editor_warmup=start_local_editor_warmup,
    )


class ReadyShellStartupDiagnosticsUpdateAdapter:
    """Adapt live startup diagnostics state into the reveal diagnostics port."""

    def __init__(
        self,
        *,
        incidents: Callable[[], tuple[object, ...]],
        transcript: Callable[[], tuple[str, ...]],
        ignore_repository: object,
        installation_context: object,
        startup_resources: object,
        execution_runtime: object,
        execution_dispatcher_factory: Callable[[], object],
        startup_cancelled: Callable[[], bool],
        shell_frame_available: Callable[[], bool],
        request_update: Callable[..., bool],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> None:
        """Store live diagnostics collaborators for one ready-shell request."""

        self._incidents = incidents
        self._transcript = transcript
        self._ignore_repository = ignore_repository
        self._installation_context = installation_context
        self._startup_resources = startup_resources
        self._execution_runtime = execution_runtime
        self._execution_dispatcher_factory = execution_dispatcher_factory
        self._startup_cancelled = startup_cancelled
        self._shell_frame_available = shell_frame_available
        self._request_update = request_update
        self._trace_fields = trace_fields

    def request(self, main_window: object) -> bool:
        """Request the diagnostics titlebar update for the revealed shell."""

        return request_ready_shell_startup_diagnostics_update(
            main_window=main_window,
            incidents=self._incidents(),
            transcript=self._transcript(),
            ignore_repository=self._ignore_repository,
            installation_context=self._installation_context,
            startup_resources=self._startup_resources,
            execution_runtime=self._execution_runtime,
            execution_dispatcher_factory=self._execution_dispatcher_factory,
            startup_cancelled=self._startup_cancelled,
            shell_frame_available=self._shell_frame_available,
            request_update=self._request_update,
            trace_fields=self._trace_fields,
        )


def create_ready_shell_startup_diagnostics_update_adapter(
    *,
    incidents: Callable[[], tuple[object, ...]],
    transcript: Callable[[], tuple[str, ...]],
    ignore_repository: object,
    installation_context: object,
    startup_resources: object,
    execution_runtime: object,
    execution_dispatcher_factory: Callable[[], object],
    startup_cancelled: Callable[[], bool],
    shell_frame_available: Callable[[], bool],
    request_update: Callable[..., bool],
    trace_fields: Callable[[], Mapping[str, object]],
) -> ReadyShellStartupDiagnosticsUpdateAdapter:
    """Create the live ready-shell diagnostics update adapter."""

    return ReadyShellStartupDiagnosticsUpdateAdapter(
        incidents=incidents,
        transcript=transcript,
        ignore_repository=ignore_repository,
        installation_context=installation_context,
        startup_resources=startup_resources,
        execution_runtime=execution_runtime,
        execution_dispatcher_factory=execution_dispatcher_factory,
        startup_cancelled=startup_cancelled,
        shell_frame_available=shell_frame_available,
        request_update=request_update,
        trace_fields=trace_fields,
    )


@dataclass(frozen=True)
class ReadyShellTargetActivationResult:
    """Describe the outcome of one ready-shell target activation task."""

    started: bool
    comfy_state: object | None = None


@dataclass(frozen=True)
class ReadyShellRevealResult:
    """Return updated startup references after revealing the ready shell."""

    shell_frame: object
    splash: ReadyShellSplashProtocol | None


@dataclass(frozen=True)
class ReadyShellShowGateResult:
    """Describe the outcome of one ready-shell reveal gate attempt."""

    revealed: bool
    hidden_restore_runtime_prepared: bool | None = None
    pre_show_projection_deferred: bool = False


class ReadyShellPostShowController:
    """Adapt ready-shell post-show callbacks to explicit startup ports."""

    def __init__(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        shell_frame: Callable[[], object | None],
        main_window_for_shell: Callable[[object], object],
        state: ReadyShellHydrationStateProtocol,
        queue_named_task: Callable[[str, Callable[[], None]], None],
        start_queue: Callable[[], None],
        workspace: Callable[[], object | None],
        hidden_restore_runtime_prepared: Callable[[], bool],
        prehydration_succeeded: Callable[[], bool],
        startup_timer: StartupTimer,
        schedule_warmups: Callable[[str], None],
        schedule_visible_summary: Callable[[Callable[[], None]], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> None:
        """Store concrete startup ports for post-show shell work."""

        self._startup_cancelled = startup_cancelled
        self._shell_frame = shell_frame
        self._main_window_for_shell = main_window_for_shell
        self._state = state
        self._queue_named_task = queue_named_task
        self._start_queue = start_queue
        self._workspace = workspace
        self._hidden_restore_runtime_prepared = hidden_restore_runtime_prepared
        self._prehydration_succeeded = prehydration_succeeded
        self._startup_timer = startup_timer
        self._schedule_warmups = schedule_warmups
        self._schedule_visible_summary = schedule_visible_summary
        self._trace_fields = trace_fields

    def update_backend_state(self, state: str) -> bool:
        """Push one backend readiness state into the built shell."""

        return project_ready_shell_backend_state(
            state=state,
            startup_cancelled=self._startup_cancelled(),
            shell_frame=self._shell_frame(),
            main_window_for_shell=self._main_window_for_shell,
            trace_fields=self._trace_fields,
        )

    def schedule_hydration(self) -> bool:
        """Queue nonessential shell hydration after the window is visible."""

        return schedule_ready_shell_post_show_hydration(
            startup_cancelled=self._startup_cancelled(),
            hydration_started=self._state.hydration_started,
            mark_hydration_started=lambda: setattr(
                self._state,
                "hydration_started",
                True,
            ),
            queue_hydration_task=lambda: self._queue_named_task(
                "hydrate_initial_workspace",
                self.hydrate_initial_workspace,
            ),
            start_queue=self._start_queue,
            trace_fields=self._trace_fields,
        )

    def hydrate_initial_workspace(self) -> None:
        """Hydrate editor and workflow surfaces after first show."""

        hydrate_ready_shell_initial_workspace(
            startup_cancelled=self._startup_cancelled(),
            shell_frame=self._shell_frame(),
            main_window_for_shell=self._main_window_for_shell,
            workspace=self._workspace(),
            hidden_restore_runtime_prepared=self._hidden_restore_runtime_prepared(),
            prehydration_succeeded=self._prehydration_succeeded(),
            startup_timer=self._startup_timer,
            schedule_warmups=self._schedule_warmups,
            schedule_visible_summary=lambda: self._schedule_visible_summary(
                self.log_visible_startup_summary
            ),
            trace_fields=self._trace_fields,
        )

    def log_visible_startup_summary(self) -> None:
        """Log aggregate post-splash startup timing and restore context."""

        emit_ready_shell_visible_startup_summary(
            startup_timer=self._startup_timer,
            workspace=self._workspace(),
            trace_fields=self._trace_fields,
        )


def create_ready_shell_post_show_controller(
    *,
    startup_cancelled: Callable[[], bool],
    shell_frame: Callable[[], object | None],
    main_window_for_shell: Callable[[object], object],
    state: ReadyShellHydrationStateProtocol,
    queue_named_task: Callable[[str, Callable[[], None]], None],
    start_queue: Callable[[], None],
    workspace: Callable[[], object | None],
    hidden_restore_runtime_prepared: Callable[[], bool],
    prehydration_succeeded: Callable[[], bool],
    startup_timer: StartupTimer,
    schedule_warmups: Callable[[str], None],
    schedule_visible_summary: Callable[[Callable[[], None]], None],
    trace_fields: Callable[[], Mapping[str, object]],
) -> ReadyShellPostShowController:
    """Create the live ready-shell post-show controller."""

    return ReadyShellPostShowController(
        startup_cancelled=startup_cancelled,
        shell_frame=shell_frame,
        main_window_for_shell=main_window_for_shell,
        state=state,
        queue_named_task=queue_named_task,
        start_queue=start_queue,
        workspace=workspace,
        hidden_restore_runtime_prepared=hidden_restore_runtime_prepared,
        prehydration_succeeded=prehydration_succeeded,
        startup_timer=startup_timer,
        schedule_warmups=schedule_warmups,
        schedule_visible_summary=schedule_visible_summary,
        trace_fields=trace_fields,
    )


def create_bound_ready_shell_post_show_controller(
    *,
    backend_state_updater: "ReadyShellBackendStateUpdater",
    startup_cancelled: Callable[[], bool],
    shell_frame: Callable[[], object | None],
    main_window_for_shell: Callable[[object], object],
    state: ReadyShellHydrationStateProtocol,
    queue_named_task: Callable[[str, Callable[[], None]], None],
    start_queue: Callable[[], None],
    workspace: Callable[[], object | None],
    hidden_restore_runtime_prepared: Callable[[], bool],
    prehydration_succeeded: Callable[[], bool],
    startup_timer: StartupTimer,
    schedule_warmups: Callable[[str], None],
    schedule_visible_summary: Callable[[Callable[[], None]], None],
    trace_fields: Callable[[], Mapping[str, object]],
) -> ReadyShellPostShowController:
    """Create the post-show controller and bind backend-state updates."""

    controller = create_ready_shell_post_show_controller(
        startup_cancelled=startup_cancelled,
        shell_frame=shell_frame,
        main_window_for_shell=main_window_for_shell,
        state=state,
        queue_named_task=queue_named_task,
        start_queue=start_queue,
        workspace=workspace,
        hidden_restore_runtime_prepared=hidden_restore_runtime_prepared,
        prehydration_succeeded=prehydration_succeeded,
        startup_timer=startup_timer,
        schedule_warmups=schedule_warmups,
        schedule_visible_summary=schedule_visible_summary,
        trace_fields=trace_fields,
    )
    backend_state_updater.bind(controller.update_backend_state)
    return controller


class ReadyShellBackendStateUpdater:
    """Late-bind ready-shell backend-state updates across startup controllers."""

    def __init__(self) -> None:
        """Initialize without a backend-state update port."""

        self._update_backend_state: Callable[[str], object] | None = None

    def bind(self, update_backend_state: Callable[[str], object]) -> None:
        """Bind the post-show controller backend-state update port."""

        self._update_backend_state = update_backend_state

    def update(self, state: str) -> None:
        """Project one backend state through the bound update port."""

        if self._update_backend_state is None:
            raise RuntimeError("Ready-shell backend-state updater is not bound.")
        self._update_backend_state(state)


def activate_ready_shell_target(
    *,
    startup_cancelled: bool,
    splash: object | None,
    installation_context: object,
    comfy_output_stream: object,
    startup_diagnostics: object,
    startup_timer: StartupPhaseTimerProtocol,
    activate_target: Callable[..., object | None],
    mark_activation_started: Callable[[], None],
    trace_fields: Callable[[], Mapping[str, object]],
) -> ReadyShellTargetActivationResult:
    """Start the selected Comfy target for ready-shell startup."""

    trace_mark("activate_target_task.start", **dict(trace_fields()))
    if startup_cancelled:
        trace_mark("activate_target_task.skip", reason="startup_cancelled")
        return ReadyShellTargetActivationResult(started=False)
    mark_activation_started()
    with startup_timer.phase("startup.activate_target"):
        with trace_span("activate_target_task.activate"):
            comfy_state = activate_target(
                installation_context=installation_context,
                splash=splash,
                comfy_output_stream=comfy_output_stream,
                startup_diagnostics=startup_diagnostics,
            )
    trace_mark(
        "activate_target_task.end",
        comfy_state_present=comfy_state is not None,
        **dict(trace_fields()),
    )
    return ReadyShellTargetActivationResult(started=True, comfy_state=comfy_state)


def activate_ready_shell_target_task(
    *,
    startup_cancelled: bool,
    splash: object | None,
    installation_context: object,
    comfy_output_stream: object,
    startup_diagnostics: object,
    startup_timer: StartupPhaseTimerProtocol,
    activate_target: Callable[..., object | None],
    state: ReadyShellActivationStateProtocol,
    set_comfy_state: Callable[[object | None], None],
    trace_fields: Callable[[], Mapping[str, object]],
) -> ReadyShellTargetActivationResult:
    """Run ready-shell target activation and apply started-state output."""

    if state.comfy_activation_started:
        trace_mark("activate_target_task.start", **dict(trace_fields()))
        trace_mark("activate_target_task.skip", reason="already_started")
        return ReadyShellTargetActivationResult(started=False)
    activation_result = activate_ready_shell_target(
        startup_cancelled=startup_cancelled,
        splash=splash,
        installation_context=installation_context,
        comfy_output_stream=comfy_output_stream,
        startup_diagnostics=startup_diagnostics,
        startup_timer=startup_timer,
        activate_target=activate_target,
        mark_activation_started=lambda: setattr(
            state,
            "comfy_activation_started",
            True,
        ),
        trace_fields=trace_fields,
    )
    if activation_result.started:
        set_comfy_state(activation_result.comfy_state)
    return activation_result


class ReadyShellTargetActivationTask:
    """Adapt live startup state into the target activation queue task."""

    def __init__(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        splash: Callable[[], object | None],
        installation_context: object,
        comfy_output_stream: object,
        startup_diagnostics: object,
        startup_timer: StartupPhaseTimerProtocol,
        activate_target: Callable[..., object | None],
        state: ReadyShellActivationStateProtocol,
        set_comfy_state: Callable[[object | None], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> None:
        """Store ports required to activate the selected ready-shell target."""

        self._startup_cancelled = startup_cancelled
        self._splash = splash
        self._installation_context = installation_context
        self._comfy_output_stream = comfy_output_stream
        self._startup_diagnostics = startup_diagnostics
        self._startup_timer = startup_timer
        self._activate_target = activate_target
        self._state = state
        self._set_comfy_state = set_comfy_state
        self._trace_fields = trace_fields

    def run(self) -> None:
        """Run the queue-task callback and discard the activation result."""

        self.activate()

    def activate(self) -> ReadyShellTargetActivationResult:
        """Activate the ready-shell target using current startup state."""

        return activate_ready_shell_target_task(
            startup_cancelled=self._startup_cancelled(),
            splash=self._splash(),
            installation_context=self._installation_context,
            comfy_output_stream=self._comfy_output_stream,
            startup_diagnostics=self._startup_diagnostics,
            startup_timer=self._startup_timer,
            activate_target=self._activate_target,
            state=self._state,
            set_comfy_state=self._set_comfy_state,
            trace_fields=self._trace_fields,
        )


def create_ready_shell_target_activation_task(
    *,
    startup_cancelled: Callable[[], bool],
    splash: Callable[[], object | None],
    installation_context: object,
    comfy_output_stream: object,
    startup_diagnostics: object,
    startup_timer: StartupPhaseTimerProtocol,
    activate_target: Callable[..., object | None],
    state: ReadyShellActivationStateProtocol,
    set_comfy_state: Callable[[object | None], None],
    trace_fields: Callable[[], Mapping[str, object]],
) -> ReadyShellTargetActivationTask:
    """Create the live ready-shell target activation task."""

    return ReadyShellTargetActivationTask(
        startup_cancelled=startup_cancelled,
        splash=splash,
        installation_context=installation_context,
        comfy_output_stream=comfy_output_stream,
        startup_diagnostics=startup_diagnostics,
        startup_timer=startup_timer,
        activate_target=activate_target,
        state=state,
        set_comfy_state=set_comfy_state,
        trace_fields=trace_fields,
    )


def build_ready_shell_skeleton(
    *,
    startup_cancelled: bool,
    splash: StartupSplashLogProtocol | None,
    context: object,
    comfy_output_stream: object,
    shutdown_request: Callable[[object | None], None],
    startup_timer: StartupPhaseTimerProtocol,
    runtime_services: object,
    startup_diagnostics_ignore_repository: object,
    build_main_window: Callable[..., object],
    attach_gui_reload_command: Callable[[object], None],
    set_current_shell: Callable[[object], None],
    main_window_for_shell: Callable[[object], object],
    restore_asset_preload: object | None,
    comfy_http_ready: bool,
    set_backend_state: Callable[[str], object],
    trace_fields: Callable[[], Mapping[str, object]],
) -> object | None:
    """Build the minimum ready shell frame and wire first-show collaborators."""

    trace_mark("build_shell_task.start", **dict(trace_fields()))
    if startup_cancelled:
        trace_mark("build_shell_task.skip", reason="startup_cancelled")
        return None
    assert splash is not None
    splash.append_log(
        render_application_text(app_text("Preparing the application interface."))
    )
    with startup_timer.phase("startup.build_main_window"):
        with trace_span("build_shell_task.build_main_window"):
            shell_frame = build_main_window(
                context,
                comfy_output_stream=comfy_output_stream,
                shutdown_request=shutdown_request,
                startup_timer=startup_timer,
                runtime_services=runtime_services,
                startup_diagnostics_ignore_repository=(
                    startup_diagnostics_ignore_repository
                ),
            )
    attach_gui_reload_command(shell_frame)
    set_current_shell(shell_frame)
    main_window = main_window_for_shell(shell_frame)
    attach_restore_asset_preload_to_shell(
        main_window=main_window,
        restore_asset_preload=restore_asset_preload,
        trace_fields=trace_fields,
    )
    set_backend_state("ready" if comfy_http_ready else "starting")
    trace_mark("build_shell_task.end", **dict(trace_fields()))
    return shell_frame


def build_ready_shell_skeleton_task(
    *,
    startup_cancelled: bool,
    splash: StartupSplashLogProtocol | None,
    context: object,
    comfy_output_stream: object,
    shutdown_request: Callable[[object | None], None],
    startup_timer: StartupPhaseTimerProtocol,
    runtime_services: object,
    startup_diagnostics_ignore_repository: object,
    build_main_window: Callable[..., object],
    attach_gui_reload_command: Callable[[object], None],
    set_current_shell: Callable[[object], None],
    main_window_for_shell: Callable[[object], object],
    restore_asset_preload: object | None,
    comfy_http_ready: bool,
    set_backend_state: Callable[[str], object],
    set_shell_frame: Callable[[object], None],
    trace_fields: Callable[[], Mapping[str, object]],
) -> object | None:
    """Run ready-shell skeleton build and apply built shell-frame output."""

    shell_frame = build_ready_shell_skeleton(
        startup_cancelled=startup_cancelled,
        splash=splash,
        context=context,
        comfy_output_stream=comfy_output_stream,
        shutdown_request=shutdown_request,
        startup_timer=startup_timer,
        runtime_services=runtime_services,
        startup_diagnostics_ignore_repository=startup_diagnostics_ignore_repository,
        build_main_window=build_main_window,
        attach_gui_reload_command=attach_gui_reload_command,
        set_current_shell=set_current_shell,
        main_window_for_shell=main_window_for_shell,
        restore_asset_preload=restore_asset_preload,
        comfy_http_ready=comfy_http_ready,
        set_backend_state=set_backend_state,
        trace_fields=trace_fields,
    )
    if shell_frame is not None:
        set_shell_frame(shell_frame)
    return shell_frame


class ReadyShellBuildTask:
    """Adapt live startup state into the ready-shell skeleton build task."""

    def __init__(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        splash: Callable[[], StartupSplashLogProtocol | None],
        context: object,
        comfy_output_stream: object,
        shutdown_request: Callable[[object | None], None],
        startup_timer: StartupPhaseTimerProtocol,
        runtime_services: object,
        startup_diagnostics_ignore_repository: object,
        build_main_window: Callable[..., object],
        attach_gui_reload_command: Callable[[object], None],
        set_current_shell: Callable[[object], None],
        main_window_for_shell: Callable[[object], object],
        restore_asset_preload: Callable[[], object | None],
        comfy_http_ready: Callable[[], bool],
        set_backend_state: Callable[[str], object],
        set_shell_frame: Callable[[object], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> None:
        """Store ports required to build the minimum ready shell."""

        self._startup_cancelled = startup_cancelled
        self._splash = splash
        self._context = context
        self._comfy_output_stream = comfy_output_stream
        self._shutdown_request = shutdown_request
        self._startup_timer = startup_timer
        self._runtime_services = runtime_services
        self._startup_diagnostics_ignore_repository = (
            startup_diagnostics_ignore_repository
        )
        self._build_main_window = build_main_window
        self._attach_gui_reload_command = attach_gui_reload_command
        self._set_current_shell = set_current_shell
        self._main_window_for_shell = main_window_for_shell
        self._restore_asset_preload = restore_asset_preload
        self._comfy_http_ready = comfy_http_ready
        self._set_backend_state = set_backend_state
        self._set_shell_frame = set_shell_frame
        self._trace_fields = trace_fields

    def run(self) -> None:
        """Run the queue-task callback and discard the shell frame."""

        self.build()

    def build(self) -> object | None:
        """Build the shell using current startup state."""

        return build_ready_shell_skeleton_task(
            startup_cancelled=self._startup_cancelled(),
            splash=self._splash(),
            context=self._context,
            comfy_output_stream=self._comfy_output_stream,
            shutdown_request=self._shutdown_request,
            startup_timer=self._startup_timer,
            runtime_services=self._runtime_services,
            startup_diagnostics_ignore_repository=(
                self._startup_diagnostics_ignore_repository
            ),
            build_main_window=self._build_main_window,
            attach_gui_reload_command=self._attach_gui_reload_command,
            set_current_shell=self._set_current_shell,
            main_window_for_shell=self._main_window_for_shell,
            restore_asset_preload=self._restore_asset_preload(),
            comfy_http_ready=self._comfy_http_ready(),
            set_backend_state=self._set_backend_state,
            set_shell_frame=self._set_shell_frame,
            trace_fields=self._trace_fields,
        )


def create_ready_shell_build_task(
    *,
    startup_cancelled: Callable[[], bool],
    splash: Callable[[], StartupSplashLogProtocol | None],
    context: object,
    comfy_output_stream: object,
    shutdown_request: Callable[[object | None], None],
    startup_timer: StartupPhaseTimerProtocol,
    runtime_services: object,
    startup_diagnostics_ignore_repository: object,
    build_main_window: Callable[..., object],
    attach_gui_reload_command: Callable[[object], None],
    set_current_shell: Callable[[object], None],
    main_window_for_shell: Callable[[object], object],
    restore_asset_preload: Callable[[], object | None],
    comfy_http_ready: Callable[[], bool],
    set_backend_state: Callable[[str], object],
    set_shell_frame: Callable[[object], None],
    trace_fields: Callable[[], Mapping[str, object]],
) -> ReadyShellBuildTask:
    """Create the live ready-shell build task."""

    return ReadyShellBuildTask(
        startup_cancelled=startup_cancelled,
        splash=splash,
        context=context,
        comfy_output_stream=comfy_output_stream,
        shutdown_request=shutdown_request,
        startup_timer=startup_timer,
        runtime_services=runtime_services,
        startup_diagnostics_ignore_repository=startup_diagnostics_ignore_repository,
        build_main_window=build_main_window,
        attach_gui_reload_command=attach_gui_reload_command,
        set_current_shell=set_current_shell,
        main_window_for_shell=main_window_for_shell,
        restore_asset_preload=restore_asset_preload,
        comfy_http_ready=comfy_http_ready,
        set_backend_state=set_backend_state,
        set_shell_frame=set_shell_frame,
        trace_fields=trace_fields,
    )


def wire_ready_shell_metadata_bridge(
    *,
    startup_cancelled: bool,
    shell_frame: object | None,
    bridge_factory: Callable[[object], ModelMetadataUpdateSignalBridgeProtocol],
    register_bridge: Callable[[object], object],
    main_window_for_shell: Callable[[object], object],
    trace_fields: Callable[[], dict[str, object]],
) -> ModelMetadataUpdateSignalBridgeProtocol | None:
    """Wire ready-shell model metadata updates through the metadata owner."""

    from substitute.app.bootstrap.startup_model_metadata import (
        wire_model_metadata_update_bridge,
    )

    return wire_model_metadata_update_bridge(
        startup_cancelled=startup_cancelled,
        shell_frame=shell_frame,
        bridge_factory=bridge_factory,
        register_bridge=register_bridge,
        main_window_for_shell=main_window_for_shell,
        trace_fields=trace_fields,
    )


def wire_ready_shell_metadata_bridge_task(
    *,
    startup_cancelled: bool,
    shell_frame: object | None,
    bridge_factory: Callable[[object], ModelMetadataUpdateSignalBridgeProtocol],
    register_bridge: Callable[[object], object],
    main_window_for_shell: Callable[[object], object],
    set_metadata_update_bridge: Callable[
        [ModelMetadataUpdateSignalBridgeProtocol | None], None
    ],
    trace_fields: Callable[[], dict[str, object]],
) -> ModelMetadataUpdateSignalBridgeProtocol | None:
    """Run ready-shell metadata wiring and apply the bridge reference."""

    bridge = wire_ready_shell_metadata_bridge(
        startup_cancelled=startup_cancelled,
        shell_frame=shell_frame,
        bridge_factory=bridge_factory,
        register_bridge=register_bridge,
        main_window_for_shell=main_window_for_shell,
        trace_fields=trace_fields,
    )
    set_metadata_update_bridge(bridge)
    return bridge


class ReadyShellMetadataBridgeTask:
    """Adapt live shell state into the metadata bridge queue task."""

    def __init__(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        shell_frame: Callable[[], object | None],
        bridge_factory: Callable[[object], ModelMetadataUpdateSignalBridgeProtocol],
        register_bridge: Callable[[object], object],
        main_window_for_shell: Callable[[object], object],
        set_metadata_update_bridge: Callable[
            [ModelMetadataUpdateSignalBridgeProtocol | None], None
        ],
        trace_fields: Callable[[], dict[str, object]],
    ) -> None:
        """Store ports required to wire shell metadata updates."""

        self._startup_cancelled = startup_cancelled
        self._shell_frame = shell_frame
        self._bridge_factory = bridge_factory
        self._register_bridge = register_bridge
        self._main_window_for_shell = main_window_for_shell
        self._set_metadata_update_bridge = set_metadata_update_bridge
        self._trace_fields = trace_fields

    def run(self) -> None:
        """Run the queue-task callback and discard the bridge reference."""

        self.wire()

    def wire(self) -> ModelMetadataUpdateSignalBridgeProtocol | None:
        """Wire metadata updates using current shell state."""

        return wire_ready_shell_metadata_bridge_task(
            startup_cancelled=self._startup_cancelled(),
            shell_frame=self._shell_frame(),
            bridge_factory=self._bridge_factory,
            register_bridge=self._register_bridge,
            main_window_for_shell=self._main_window_for_shell,
            set_metadata_update_bridge=self._set_metadata_update_bridge,
            trace_fields=self._trace_fields,
        )


def create_ready_shell_metadata_bridge_task(
    *,
    startup_cancelled: Callable[[], bool],
    shell_frame: Callable[[], object | None],
    bridge_factory: Callable[[object], ModelMetadataUpdateSignalBridgeProtocol],
    register_bridge: Callable[[object], object],
    main_window_for_shell: Callable[[object], object],
    set_metadata_update_bridge: Callable[
        [ModelMetadataUpdateSignalBridgeProtocol | None], None
    ],
    trace_fields: Callable[[], dict[str, object]],
) -> ReadyShellMetadataBridgeTask:
    """Create the live ready-shell metadata bridge task."""

    return ReadyShellMetadataBridgeTask(
        startup_cancelled=startup_cancelled,
        shell_frame=shell_frame,
        bridge_factory=bridge_factory,
        register_bridge=register_bridge,
        main_window_for_shell=main_window_for_shell,
        set_metadata_update_bridge=set_metadata_update_bridge,
        trace_fields=trace_fields,
    )


def mark_ready_shell_minimum_ready_task(
    *,
    startup_cancelled: bool,
    state: ReadyShellMinimumReadyStateProtocol,
    try_show_main_window: Callable[[], None],
    trace_fields: Callable[[], Mapping[str, object]],
    after_mark_ready: Callable[[], object] | None = None,
) -> bool:
    """Run the ready-shell minimum-readiness queue task and update state."""

    return bool(
        mark_minimum_shell_ready(
            startup_cancelled=startup_cancelled,
            mark_ready=lambda: setattr(state, "minimum_shell_ready", True),
            try_show_main_window=try_show_main_window,
            trace_fields=trace_fields,
            after_mark_ready=after_mark_ready,
        )
    )


class ReadyShellMinimumReadyTask:
    """Adapt live startup state into the minimum-shell-ready queue task."""

    def __init__(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        state: ReadyShellMinimumReadyStateProtocol,
        try_show_main_window: Callable[[], None],
        trace_fields: Callable[[], Mapping[str, object]],
        after_mark_ready: Callable[[], object] | None = None,
    ) -> None:
        """Store ports required to mark and reveal the minimum ready shell."""

        self._startup_cancelled = startup_cancelled
        self._state = state
        self._try_show_main_window = try_show_main_window
        self._after_mark_ready = after_mark_ready
        self._trace_fields = trace_fields

    def run(self) -> None:
        """Run the queue-task callback and discard the mark result."""

        self.mark_ready()

    def mark_ready(self) -> bool:
        """Mark the shell ready using current startup cancellation state."""

        return mark_ready_shell_minimum_ready_task(
            startup_cancelled=self._startup_cancelled(),
            state=self._state,
            try_show_main_window=self._try_show_main_window,
            after_mark_ready=self._after_mark_ready,
            trace_fields=self._trace_fields,
        )


def create_ready_shell_minimum_ready_task(
    *,
    startup_cancelled: Callable[[], bool],
    state: ReadyShellMinimumReadyStateProtocol,
    try_show_main_window: Callable[[], None],
    trace_fields: Callable[[], Mapping[str, object]],
    after_mark_ready: Callable[[], object] | None = None,
) -> ReadyShellMinimumReadyTask:
    """Create the live ready-shell minimum-readiness task."""

    return ReadyShellMinimumReadyTask(
        startup_cancelled=startup_cancelled,
        state=state,
        try_show_main_window=try_show_main_window,
        after_mark_ready=after_mark_ready,
        trace_fields=trace_fields,
    )


def warm_ready_shell_prompt_editor_gui(
    *,
    startup_cancelled: bool,
    shell_frame: object | None,
    main_window_for_shell: Callable[[object], object | None],
    warm_prompt_editor_gui: Callable[[object], object],
    trace_fields: Callable[[], Mapping[str, object]],
) -> bool:
    """Run the ready-shell prompt editor GUI warmup queue task."""

    return bool(
        warm_prompt_editor_gui_before_reveal(
            startup_cancelled=startup_cancelled,
            shell_frame=shell_frame,
            main_window_for_shell=main_window_for_shell,
            warm_prompt_editor_gui=warm_prompt_editor_gui,
            trace_fields=trace_fields,
        )
    )


class ReadyShellPromptEditorWarmupTask:
    """Adapt live shell state into the prompt editor GUI warmup task."""

    def __init__(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        shell_frame: Callable[[], object | None],
        main_window_for_shell: Callable[[object], object | None],
        warm_prompt_editor_gui: Callable[[object], object],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> None:
        """Store ports required to warm prompt editor GUI construction."""

        self._startup_cancelled = startup_cancelled
        self._shell_frame = shell_frame
        self._main_window_for_shell = main_window_for_shell
        self._warm_prompt_editor_gui = warm_prompt_editor_gui
        self._trace_fields = trace_fields

    def run(self) -> None:
        """Run the queue-task callback and discard the warmup result."""

        self.warm()

    def warm(self) -> bool:
        """Warm prompt editor GUI construction using current shell state."""

        return warm_ready_shell_prompt_editor_gui(
            startup_cancelled=self._startup_cancelled(),
            shell_frame=self._shell_frame(),
            main_window_for_shell=self._main_window_for_shell,
            warm_prompt_editor_gui=self._warm_prompt_editor_gui,
            trace_fields=self._trace_fields,
        )


def create_ready_shell_prompt_editor_warmup_task(
    *,
    startup_cancelled: Callable[[], bool],
    shell_frame: Callable[[], object | None],
    main_window_for_shell: Callable[[object], object | None],
    warm_prompt_editor_gui: Callable[[object], object],
    trace_fields: Callable[[], Mapping[str, object]],
) -> ReadyShellPromptEditorWarmupTask:
    """Create the live ready-shell prompt editor warmup task."""

    return ReadyShellPromptEditorWarmupTask(
        startup_cancelled=startup_cancelled,
        shell_frame=shell_frame,
        main_window_for_shell=main_window_for_shell,
        warm_prompt_editor_gui=warm_prompt_editor_gui,
        trace_fields=trace_fields,
    )


class ReadyShellInitialWorkspacePrehydrationTask:
    """Adapt live shell state into the initial workspace prehydration task."""

    def __init__(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        shell_frame: Callable[[], object | None],
        main_window_for_shell: Callable[[object], object],
        workspace: Callable[[], object | None],
        startup_timer: StartupPhaseTimerProtocol,
        workspace_workflow_count: Callable[[object | None], int],
        state: ReadyShellPrehydrationStateProtocol,
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> None:
        """Store ports required to prehydrate a restored workspace before reveal."""

        self._startup_cancelled = startup_cancelled
        self._shell_frame = shell_frame
        self._main_window_for_shell = main_window_for_shell
        self._workspace = workspace
        self._startup_timer = startup_timer
        self._workspace_workflow_count = workspace_workflow_count
        self._state = state
        self._trace_fields = trace_fields

    def run(self) -> None:
        """Run the queue-task callback and discard the prehydration result."""

        self.prehydrate()

    def prehydrate(self) -> ReadyShellPrehydrationResult:
        """Prehydrate initial workspace chrome using current shell state."""

        return prehydrate_ready_shell_initial_workspace_task(
            startup_cancelled=self._startup_cancelled(),
            shell_frame=self._shell_frame(),
            main_window_for_shell=self._main_window_for_shell,
            workspace=self._workspace(),
            startup_timer=self._startup_timer,
            workspace_workflow_count=self._workspace_workflow_count,
            state=self._state,
            trace_fields=self._trace_fields,
        )


def create_ready_shell_initial_workspace_prehydration_task(
    *,
    startup_cancelled: Callable[[], bool],
    shell_frame: Callable[[], object | None],
    main_window_for_shell: Callable[[object], object],
    workspace: Callable[[], object | None],
    startup_timer: StartupPhaseTimerProtocol,
    workspace_workflow_count: Callable[[object | None], int],
    state: ReadyShellPrehydrationStateProtocol,
    trace_fields: Callable[[], Mapping[str, object]],
) -> ReadyShellInitialWorkspacePrehydrationTask:
    """Create the live ready-shell initial workspace prehydration task."""

    return ReadyShellInitialWorkspacePrehydrationTask(
        startup_cancelled=startup_cancelled,
        shell_frame=shell_frame,
        main_window_for_shell=main_window_for_shell,
        workspace=workspace,
        startup_timer=startup_timer,
        workspace_workflow_count=workspace_workflow_count,
        state=state,
        trace_fields=trace_fields,
    )


def prehydrate_ready_shell_initial_workspace(
    *,
    startup_cancelled: bool,
    shell_frame: object | None,
    main_window_for_shell: Callable[[object], object],
    workspace: object | None,
    startup_timer: StartupPhaseTimerProtocol,
    workspace_workflow_count: Callable[[object | None], int],
    trace_fields: Callable[[], Mapping[str, object]],
) -> ReadyShellPrehydrationResult:
    """Run the ready-shell initial workspace prehydration queue task."""

    return prehydrate_initial_workspace_before_show(
        startup_cancelled=startup_cancelled,
        shell_frame=shell_frame,
        main_window_for_shell=main_window_for_shell,
        workspace=workspace,
        startup_timer=startup_timer,
        workspace_workflow_count=workspace_workflow_count,
        trace_fields=trace_fields,
    )


def prehydrate_ready_shell_initial_workspace_task(
    *,
    startup_cancelled: bool,
    shell_frame: object | None,
    main_window_for_shell: Callable[[object], object],
    workspace: object | None,
    startup_timer: StartupPhaseTimerProtocol,
    workspace_workflow_count: Callable[[object | None], int],
    state: ReadyShellPrehydrationStateProtocol,
    trace_fields: Callable[[], Mapping[str, object]],
) -> ReadyShellPrehydrationResult:
    """Run pre-show workspace prehydration and record ready-shell gate state."""

    result = prehydrate_ready_shell_initial_workspace(
        startup_cancelled=startup_cancelled,
        shell_frame=shell_frame,
        main_window_for_shell=main_window_for_shell,
        workspace=workspace,
        startup_timer=startup_timer,
        workspace_workflow_count=workspace_workflow_count,
        trace_fields=trace_fields,
    )
    if result.attempted:
        state.prehydration_attempted = True
        state.prehydration_succeeded = result.succeeded
    return result


def project_ready_shell_backend_state(
    *,
    state: str,
    startup_cancelled: bool,
    shell_frame: object | None,
    main_window_for_shell: Callable[[object], object],
    trace_fields: Callable[[], Mapping[str, object]],
) -> bool:
    """Run the ready-shell backend-state projection helper."""

    return bool(
        update_shell_backend_state(
            state=state,
            startup_cancelled=startup_cancelled,
            shell_frame=shell_frame,
            main_window_for_shell=main_window_for_shell,
            trace_fields=trace_fields,
        )
    )


def request_ready_shell_startup_diagnostics_update(
    *,
    main_window: object,
    incidents: tuple[object, ...],
    transcript: tuple[str, ...],
    ignore_repository: object,
    installation_context: object,
    startup_resources: object,
    execution_runtime: object,
    execution_dispatcher_factory: Callable[[], object],
    startup_cancelled: Callable[[], bool],
    shell_frame_available: Callable[[], bool],
    request_update: Callable[..., bool],
    trace_fields: Callable[[], Mapping[str, object]],
) -> bool:
    """Request post-show diagnostics titlebar preparation for a ready shell."""

    started = request_update(
        main_window=main_window,
        incidents=incidents,
        transcript=transcript,
        ignore_repository=ignore_repository,
        installation_context=installation_context,
        startup_resources=startup_resources,
        execution_runtime=execution_runtime,
        execution_dispatcher_factory=execution_dispatcher_factory,
        startup_cancelled=startup_cancelled,
        shell_frame_available=shell_frame_available,
    )
    trace_mark("post_show.diagnostics.async_requested", **dict(trace_fields()))
    return started


def reveal_ready_shell_main_window(
    *,
    splash: ReadyShellSplashProtocol | None,
    shell_frame: object,
    initial_shell_placement: object | None,
    comfy_http_ready: bool,
    startup_timer: ReadyShellRevealTimerProtocol,
    show_built_main_window: Callable[..., object],
    set_current_shell: Callable[[object], None],
    update_backend_state: Callable[[str], object],
    connect_restore_finalized_warmups: Callable[[], object],
    request_startup_diagnostics_update: Callable[[], object],
    schedule_post_show_hydration: Callable[[], object],
    trace_fields: Callable[[], Mapping[str, object]],
) -> ReadyShellRevealResult:
    """Close splash, show the ready shell, and start post-show work."""

    active_splash = splash
    try:
        if active_splash is not None:
            with startup_timer.phase("startup.close_launch_splash"):
                with trace_span("launch_splash.close"):
                    active_splash.close()
            active_splash = None
            startup_timer.mark("splash_closed")
            trace_mark("launch_splash.closed", **dict(trace_fields()))
    except Exception:
        log_exception(
            _LOGGER,
            "Failed to close splash after readiness check",
        )

    with startup_timer.phase("startup.show_main_window"):
        with trace_span("main_shell.show"):
            revealed_shell_frame = show_built_main_window(
                shell_frame,
                initial_shell_placement=initial_shell_placement,
            )
    set_current_shell(revealed_shell_frame)
    startup_timer.mark("main_shell_shown")
    trace_mark("main_shell.shown", **dict(trace_fields()))
    update_backend_state("ready" if comfy_http_ready else "starting")
    log_info(
        _LOGGER,
        "Main shell revealed",
        comfy_http_ready=comfy_http_ready,
    )
    connect_restore_finalized_warmups()
    request_startup_diagnostics_update()
    schedule_post_show_hydration()
    return ReadyShellRevealResult(
        shell_frame=revealed_shell_frame,
        splash=active_splash,
    )


class ReadyShellRevealTask:
    """Adapt live startup state into the ready-shell reveal task."""

    def __init__(
        self,
        *,
        splash: Callable[[], ReadyShellSplashProtocol | None],
        shell_frame: Callable[[], object | None],
        initial_shell_placement: Callable[[], object | None],
        comfy_http_ready: Callable[[], bool],
        startup_timer: ReadyShellRevealTimerProtocol,
        show_built_main_window: Callable[..., object],
        set_current_shell: Callable[[object], None],
        update_backend_state: Callable[[str], object],
        startup_warmup_state: StartupWarmupState,
        schedule_warmups: Callable[[str], None],
        request_startup_diagnostics_update: Callable[[object], object],
        schedule_post_show_hydration: Callable[[], object],
        set_shell_frame: Callable[[object], None],
        set_splash: Callable[[ReadyShellSplashProtocol | None], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> None:
        """Store ports required to reveal the ready shell."""

        self._splash = splash
        self._shell_frame = shell_frame
        self._initial_shell_placement = initial_shell_placement
        self._comfy_http_ready = comfy_http_ready
        self._startup_timer = startup_timer
        self._show_built_main_window = show_built_main_window
        self._set_current_shell = set_current_shell
        self._update_backend_state = update_backend_state
        self._startup_warmup_state = startup_warmup_state
        self._schedule_warmups = schedule_warmups
        self._request_startup_diagnostics_update = request_startup_diagnostics_update
        self._schedule_post_show_hydration = schedule_post_show_hydration
        self._set_shell_frame = set_shell_frame
        self._set_splash = set_splash
        self._trace_fields = trace_fields

    def reveal(self, main_window: object) -> ReadyShellRevealResult:
        """Reveal the shell using current splash and shell-frame state."""

        shell_frame = self._shell_frame()
        assert shell_frame is not None
        reveal_result = reveal_ready_shell_main_window(
            splash=self._splash(),
            shell_frame=shell_frame,
            initial_shell_placement=self._initial_shell_placement(),
            comfy_http_ready=self._comfy_http_ready(),
            startup_timer=self._startup_timer,
            show_built_main_window=self._show_built_main_window,
            set_current_shell=self._set_current_shell,
            update_backend_state=self._update_backend_state,
            connect_restore_finalized_warmups=lambda: (
                connect_ready_shell_restore_finalized_warmups(
                    state=self._startup_warmup_state,
                    main_window=main_window,
                    schedule_warmups=self._schedule_warmups,
                    trace_fields=self._trace_fields,
                )
            ),
            request_startup_diagnostics_update=lambda: (
                self._request_startup_diagnostics_update(main_window)
            ),
            schedule_post_show_hydration=self._schedule_post_show_hydration,
            trace_fields=self._trace_fields,
        )
        self._set_shell_frame(reveal_result.shell_frame)
        self._set_splash(reveal_result.splash)
        return reveal_result


def create_ready_shell_reveal_task(
    *,
    splash: Callable[[], ReadyShellSplashProtocol | None],
    shell_frame: Callable[[], object | None],
    initial_shell_placement: Callable[[], object | None],
    comfy_http_ready: Callable[[], bool],
    startup_timer: ReadyShellRevealTimerProtocol,
    show_built_main_window: Callable[..., object],
    set_current_shell: Callable[[object], None],
    update_backend_state: Callable[[str], object],
    startup_warmup_state: StartupWarmupState,
    schedule_warmups: Callable[[str], None],
    request_startup_diagnostics_update: Callable[[object], object],
    schedule_post_show_hydration: Callable[[], object],
    set_shell_frame: Callable[[object], None],
    set_splash: Callable[[ReadyShellSplashProtocol | None], None],
    trace_fields: Callable[[], Mapping[str, object]],
) -> ReadyShellRevealTask:
    """Create the live ready-shell reveal task."""

    return ReadyShellRevealTask(
        splash=splash,
        shell_frame=shell_frame,
        initial_shell_placement=initial_shell_placement,
        comfy_http_ready=comfy_http_ready,
        startup_timer=startup_timer,
        show_built_main_window=show_built_main_window,
        set_current_shell=set_current_shell,
        update_backend_state=update_backend_state,
        startup_warmup_state=startup_warmup_state,
        schedule_warmups=schedule_warmups,
        request_startup_diagnostics_update=request_startup_diagnostics_update,
        schedule_post_show_hydration=schedule_post_show_hydration,
        set_shell_frame=set_shell_frame,
        set_splash=set_splash,
        trace_fields=trace_fields,
    )


class ReadyShellShowGateTask:
    """Adapt live startup state into the ready-shell reveal gate."""

    def __init__(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        state: ReadyShellShowStateProtocol,
        pre_show_projection_pending: Callable[[], bool],
        minimum_shell_ready: Callable[[], bool],
        comfy_http_ready: Callable[[], bool],
        shell_frame: Callable[[], object | None],
        comfy_state: Callable[[], object | None],
        fatal_incident_for_state: Callable[[object | None], object | None],
        handle_fatal_incident: Callable[[object], object],
        main_window_for_shell: Callable[[object], object],
        workspace: Callable[[], object | None],
        prehydration_succeeded: Callable[[], bool],
        startup_timer: StartupPhaseTimerProtocol,
        pre_show_projection_state: PreShowRestoreProjectionState,
        provisional_restore_projection: Callable[[], object | None],
        fallback_workflow_id: Callable[[], str],
        startup_cancelled_callback: Callable[[], bool],
        reveal_main_window: Callable[[object], object],
        scheduler: Callable[[int, Callable[[], None]], None],
        set_hidden_restore_runtime_prepared: Callable[[bool], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> None:
        """Store live-state ports required by the ready-shell reveal gate."""

        self._startup_cancelled = startup_cancelled
        self._state = state
        self._pre_show_projection_pending = pre_show_projection_pending
        self._minimum_shell_ready = minimum_shell_ready
        self._comfy_http_ready = comfy_http_ready
        self._shell_frame = shell_frame
        self._comfy_state = comfy_state
        self._fatal_incident_for_state = fatal_incident_for_state
        self._handle_fatal_incident = handle_fatal_incident
        self._main_window_for_shell = main_window_for_shell
        self._workspace = workspace
        self._prehydration_succeeded = prehydration_succeeded
        self._startup_timer = startup_timer
        self._pre_show_projection_state = pre_show_projection_state
        self._provisional_restore_projection = provisional_restore_projection
        self._fallback_workflow_id = fallback_workflow_id
        self._startup_cancelled_callback = startup_cancelled_callback
        self._reveal_main_window = reveal_main_window
        self._scheduler = scheduler
        self._set_hidden_restore_runtime_prepared = set_hidden_restore_runtime_prepared
        self._trace_fields = trace_fields

    def run(self) -> None:
        """Attempt to reveal the ready shell."""

        self.try_show()

    def try_show(self) -> ReadyShellShowGateResult:
        """Run the reveal gate against the latest startup state."""

        gate_result = try_reveal_ready_shell(
            startup_cancelled=self._startup_cancelled(),
            state=self._state,
            pre_show_projection_pending=self._pre_show_projection_pending(),
            minimum_shell_ready=self._minimum_shell_ready(),
            comfy_http_ready=self._comfy_http_ready(),
            shell_frame=self._shell_frame(),
            comfy_state=self._comfy_state(),
            fatal_incident_for_state=self._fatal_incident_for_state,
            handle_fatal_incident=self._handle_fatal_incident,
            main_window_for_shell=self._main_window_for_shell,
            workspace=self._workspace(),
            prehydration_succeeded=self._prehydration_succeeded(),
            startup_timer=self._startup_timer,
            pre_show_projection_state=self._pre_show_projection_state,
            provisional_restore_projection=self._provisional_restore_projection(),
            fallback_workflow_id=self._fallback_workflow_id(),
            startup_cancelled_callback=self._startup_cancelled_callback,
            reveal_main_window=self._reveal_main_window,
            scheduler=self._scheduler,
            trace_fields=self._trace_fields,
        )
        if gate_result.hidden_restore_runtime_prepared is not None:
            self._set_hidden_restore_runtime_prepared(
                gate_result.hidden_restore_runtime_prepared
            )
        return gate_result


def create_ready_shell_show_gate_task(
    *,
    startup_cancelled: Callable[[], bool],
    state: ReadyShellShowStateProtocol,
    pre_show_projection_pending: Callable[[], bool],
    minimum_shell_ready: Callable[[], bool],
    comfy_http_ready: Callable[[], bool],
    shell_frame: Callable[[], object | None],
    comfy_state: Callable[[], object | None],
    fatal_incident_for_state: Callable[[object | None], object | None],
    handle_fatal_incident: Callable[[object], object],
    main_window_for_shell: Callable[[object], object],
    workspace: Callable[[], object | None],
    prehydration_succeeded: Callable[[], bool],
    startup_timer: StartupPhaseTimerProtocol,
    pre_show_projection_state: PreShowRestoreProjectionState,
    provisional_restore_projection: Callable[[], object | None],
    fallback_workflow_id: Callable[[], str],
    startup_cancelled_callback: Callable[[], bool],
    reveal_main_window: Callable[[object], object],
    scheduler: Callable[[int, Callable[[], None]], None],
    set_hidden_restore_runtime_prepared: Callable[[bool], None],
    trace_fields: Callable[[], Mapping[str, object]],
) -> ReadyShellShowGateTask:
    """Create the live ready-shell show-gate task."""

    return ReadyShellShowGateTask(
        startup_cancelled=startup_cancelled,
        state=state,
        pre_show_projection_pending=pre_show_projection_pending,
        minimum_shell_ready=minimum_shell_ready,
        comfy_http_ready=comfy_http_ready,
        shell_frame=shell_frame,
        comfy_state=comfy_state,
        fatal_incident_for_state=fatal_incident_for_state,
        handle_fatal_incident=handle_fatal_incident,
        main_window_for_shell=main_window_for_shell,
        workspace=workspace,
        prehydration_succeeded=prehydration_succeeded,
        startup_timer=startup_timer,
        pre_show_projection_state=pre_show_projection_state,
        provisional_restore_projection=provisional_restore_projection,
        fallback_workflow_id=fallback_workflow_id,
        startup_cancelled_callback=startup_cancelled_callback,
        reveal_main_window=reveal_main_window,
        scheduler=scheduler,
        set_hidden_restore_runtime_prepared=set_hidden_restore_runtime_prepared,
        trace_fields=trace_fields,
    )


def try_reveal_ready_shell(
    *,
    startup_cancelled: bool,
    state: ReadyShellShowStateProtocol,
    pre_show_projection_pending: bool,
    minimum_shell_ready: bool,
    comfy_http_ready: bool,
    shell_frame: object | None,
    comfy_state: object | None,
    fatal_incident_for_state: Callable[[object | None], object | None],
    handle_fatal_incident: Callable[[object], object],
    main_window_for_shell: Callable[[object], object],
    workspace: object | None,
    prehydration_succeeded: bool,
    startup_timer: StartupPhaseTimerProtocol,
    pre_show_projection_state: PreShowRestoreProjectionState,
    provisional_restore_projection: object | None,
    fallback_workflow_id: str,
    startup_cancelled_callback: Callable[[], bool],
    reveal_main_window: Callable[[object], object],
    scheduler: Callable[[int, Callable[[], None]], None],
    trace_fields: Callable[[], Mapping[str, object]],
) -> ReadyShellShowGateResult:
    """Advance the ready-shell reveal gate when all startup prerequisites are met."""

    trace_mark("main_shell.try_show.enter", **dict(trace_fields()))
    fatal_incident = fatal_incident_for_state(comfy_state)
    if fatal_incident is not None:
        trace_mark(
            "main_shell.try_show.fatal_incident",
            incident_kind=getattr(fatal_incident, "kind", None),
            incident_severity=getattr(fatal_incident, "severity", None),
            **dict(trace_fields()),
        )
        handle_fatal_incident(fatal_incident)
        return ReadyShellShowGateResult(revealed=False)
    if (
        startup_cancelled
        or state.main_window_shown
        or pre_show_projection_pending
        or not minimum_shell_ready
        or not comfy_http_ready
        or shell_frame is None
    ):
        trace_mark("main_shell.try_show.blocked", **dict(trace_fields()))
        return ReadyShellShowGateResult(revealed=False)

    state.main_window_shown = True
    main_window = main_window_for_shell(shell_frame)
    trace_mark("post_comfy.restore_priority.begin", **dict(trace_fields()))
    warm_ready_shell_restored_cube_definitions(
        main_window=main_window,
        workspace=workspace,
        comfy_http_ready=comfy_http_ready,
        startup_timer=startup_timer,
        trace_fields=trace_fields,
    )
    hidden_restore_runtime_prepared = prepare_ready_shell_hidden_restore_runtime(
        main_window=main_window,
        comfy_http_ready=comfy_http_ready,
        prehydration_succeeded=prehydration_succeeded,
        startup_timer=startup_timer,
    )
    trace_mark("post_comfy.restore_priority.end", **dict(trace_fields()))

    restore_projection_controller = getattr(
        main_window,
        "restore_projection_controller",
        None,
    )
    start_pre_show_projection = getattr(
        restore_projection_controller,
        "start_pre_show_restore_projection",
        None,
    )
    pre_show_projection_deferred = start_ready_shell_pre_show_restore_projection(
        state=pre_show_projection_state,
        hidden_restore_runtime_prepared=hidden_restore_runtime_prepared,
        start_projection=start_pre_show_projection
        if callable(start_pre_show_projection)
        else None,
        provisional_restore_projection=provisional_restore_projection,
        fallback_workflow_id=fallback_workflow_id,
        startup_cancelled=startup_cancelled_callback,
        reveal_main_window=lambda: _reveal_ready_shell_after_projection(
            reveal_main_window,
            main_window,
        ),
        scheduler=scheduler,
        trace_fields=trace_fields,
    )
    if not pre_show_projection_deferred:
        reveal_main_window(main_window)
    return ReadyShellShowGateResult(
        revealed=True,
        hidden_restore_runtime_prepared=hidden_restore_runtime_prepared,
        pre_show_projection_deferred=pre_show_projection_deferred,
    )


def _reveal_ready_shell_after_projection(
    reveal_main_window: Callable[[object], object],
    main_window: object,
) -> None:
    """Adapt a main-window reveal port to the no-argument projection callback."""

    reveal_main_window(main_window)


def connect_ready_shell_restore_finalized_warmups(
    *,
    state: StartupWarmupState,
    main_window: object,
    schedule_warmups: Callable[[str], None],
    trace_fields: Callable[[], Mapping[str, object]],
) -> None:
    """Connect restore finalization to ready-shell background warmup scheduling."""

    connect_restore_finalized_warmups(
        state=state,
        main_window=main_window,
        schedule_warmups=schedule_warmups,
        trace_fields=lambda: dict(trace_fields()),
    )


def schedule_ready_shell_post_show_hydration(
    *,
    startup_cancelled: bool,
    hydration_started: bool,
    mark_hydration_started: Callable[[], None],
    queue_hydration_task: Callable[[], None],
    start_queue: Callable[[], None],
    trace_fields: Callable[[], Mapping[str, object]],
) -> bool:
    """Run the ready-shell post-show hydration scheduling helper."""

    return bool(
        schedule_post_show_hydration_after_reveal(
            startup_cancelled=startup_cancelled,
            hydration_started=hydration_started,
            mark_hydration_started=mark_hydration_started,
            queue_hydration_task=queue_hydration_task,
            start_queue=start_queue,
            trace_fields=trace_fields,
        )
    )


def hydrate_ready_shell_initial_workspace(
    *,
    startup_cancelled: bool,
    shell_frame: object | None,
    main_window_for_shell: Callable[[object], object],
    workspace: object | None,
    hidden_restore_runtime_prepared: bool,
    prehydration_succeeded: bool,
    startup_timer: HydrationStartupTimerProtocol,
    schedule_warmups: Callable[[str], None],
    schedule_visible_summary: Callable[[], None],
    trace_fields: Callable[[], Mapping[str, object]],
) -> None:
    """Run the ready-shell post-show initial workspace hydration task."""

    hydrate_initial_workspace_after_show(
        startup_cancelled=startup_cancelled,
        shell_frame=shell_frame,
        main_window_for_shell=main_window_for_shell,
        workspace=workspace,
        hidden_restore_runtime_prepared=hidden_restore_runtime_prepared,
        prehydration_succeeded=prehydration_succeeded,
        startup_timer=startup_timer,
        schedule_warmups=schedule_warmups,
        schedule_visible_summary=schedule_visible_summary,
        trace_fields=trace_fields,
    )


def emit_ready_shell_visible_startup_summary(
    *,
    startup_timer: StartupTimer,
    workspace: object | None,
    trace_fields: Callable[[], Mapping[str, object]],
) -> None:
    """Run the ready-shell visible startup summary task."""

    log_visible_startup_summary(
        startup_timer=startup_timer,
        workspace=workspace,
        trace_fields=trace_fields,
    )


def prepare_ready_shell_hidden_restore_runtime(
    *,
    main_window: object,
    comfy_http_ready: bool,
    prehydration_succeeded: bool,
    startup_timer: StartupPhaseTimerProtocol,
) -> bool:
    """Run the ready-shell hidden restore runtime preparation helper."""

    return bool(
        prepare_hidden_restore_runtime_before_show(
            main_window=main_window,
            comfy_http_ready=comfy_http_ready,
            prehydration_succeeded=prehydration_succeeded,
            startup_timer=startup_timer,
        )
    )


def warm_ready_shell_restored_cube_definitions(
    *,
    main_window: object,
    workspace: object | None,
    comfy_http_ready: bool,
    startup_timer: StartupPhaseTimerProtocol,
    trace_fields: Callable[[], Mapping[str, object]],
) -> bool:
    """Run ready-shell restored cube-definition warmup before reveal."""

    restore_warmup_controller = getattr(
        main_window,
        "shell_restore_warmup_controller",
        None,
    )
    warm_restored_cubes = getattr(
        restore_warmup_controller,
        "warm_restored_workspace_cube_definitions",
        None,
    )
    if not comfy_http_ready or not callable(warm_restored_cubes):
        trace_mark(
            "startup.restore_cube_definition_warmup.skip",
            reason="backend_not_ready"
            if not comfy_http_ready
            else "no_warmup_callable",
        )
        return False
    with startup_timer.phase("startup.restore_cube_definition_warmup"):
        with trace_span(
            "startup.restore_cube_definition_warmup",
            workspace_present=workspace is not None,
            **dict(trace_fields()),
        ):
            warm_restored_cubes(workspace)
    return True


def start_ready_shell_pre_show_restore_projection(
    *,
    state: PreShowRestoreProjectionState,
    hidden_restore_runtime_prepared: bool,
    start_projection: PreShowRestoreProjectionStarter | None,
    provisional_restore_projection: object | None,
    fallback_workflow_id: str,
    startup_cancelled: Callable[[], bool],
    reveal_main_window: Callable[[], None],
    scheduler: Callable[[int, Callable[[], None]], None],
    trace_fields: Callable[[], Mapping[str, object]],
) -> bool:
    """Run the ready-shell pre-show restore projection gate."""

    return bool(
        start_pre_show_restore_projection_if_available(
            state=state,
            hidden_restore_runtime_prepared=hidden_restore_runtime_prepared,
            start_projection=start_projection,
            provisional_restore_projection=provisional_restore_projection,
            fallback_workflow_id=fallback_workflow_id,
            startup_cancelled=startup_cancelled,
            reveal_main_window=reveal_main_window,
            scheduler=scheduler,
            trace_fields=trace_fields,
        )
    )


__all__ = [
    "ReadyShellBackendStateUpdater",
    "ReadyShellInitialWorkspacePrehydrationTask",
    "ReadyShellLaunchController",
    "ReadyShellManagedStartupPrelude",
    "ReadyShellMetadataBridgeTask",
    "ReadyShellMinimumReadyTask",
    "ReadyShellPromptEditorWarmupTask",
    "ReadyShellPostShowController",
    "ReadyShellMinimumReadyStateProtocol",
    "ReadyShellHydrationStateProtocol",
    "ReadyShellShowStateProtocol",
    "ReadyShellFailureQueue",
    "ReadyShellLocalEditorWarmupAdapter",
    "ReadyShellRevealResult",
    "ReadyShellRevealTask",
    "ReadyShellShowGateResult",
    "ReadyShellShowGateTask",
    "ReadyShellStartupDiagnosticsUpdateAdapter",
    "ReadyShellTargetActivationResult",
    "ReadyShellTargetActivationTask",
    "ReadyShellActivationStateProtocol",
    "ReadyShellBuildTask",
    "activate_ready_shell_target",
    "activate_ready_shell_target_task",
    "build_ready_shell_skeleton",
    "build_ready_shell_skeleton_task",
    "connect_ready_shell_restore_finalized_warmups",
    "create_bound_ready_shell_post_show_controller",
    "create_ready_shell_build_task",
    "create_ready_shell_failure_queue",
    "create_ready_shell_initial_workspace_prehydration_task",
    "create_ready_shell_launch_controller",
    "create_ready_shell_local_editor_warmup_adapter",
    "create_ready_shell_managed_startup_prelude",
    "create_ready_shell_metadata_bridge_task",
    "create_ready_shell_minimum_ready_task",
    "create_ready_shell_post_show_controller",
    "create_ready_shell_prompt_editor_warmup_task",
    "create_ready_shell_reveal_task",
    "create_ready_shell_show_gate_task",
    "create_ready_shell_startup_diagnostics_update_adapter",
    "create_ready_shell_target_activation_task",
    "emit_ready_shell_visible_startup_summary",
    "hydrate_ready_shell_initial_workspace",
    "mark_ready_shell_minimum_ready_task",
    "prepare_ready_shell_hidden_restore_runtime",
    "prehydrate_ready_shell_initial_workspace",
    "prehydrate_ready_shell_initial_workspace_task",
    "project_ready_shell_backend_state",
    "request_ready_shell_startup_diagnostics_update",
    "schedule_ready_shell_controller_startup_tasks",
    "reveal_ready_shell_main_window",
    "schedule_ready_shell_post_show_hydration",
    "start_ready_shell_pre_show_restore_projection",
    "try_reveal_ready_shell",
    "warm_ready_shell_restored_cube_definitions",
    "warm_ready_shell_prompt_editor_gui",
    "wire_ready_shell_metadata_bridge",
    "wire_ready_shell_metadata_bridge_task",
]

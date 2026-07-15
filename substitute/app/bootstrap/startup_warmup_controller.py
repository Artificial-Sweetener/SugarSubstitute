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

"""Coordinate startup warmup handle creation and launch."""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableSequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

from substitute.app.bootstrap.cube_icon_startup_warmup import (
    StartupCubeIconWarmupHandle,
)
from substitute.app.bootstrap.qpane_sam_startup_warmup import (
    QPaneSamStartupWarmupHandle,
)
from substitute.app.bootstrap.startup_resources import ShutdownResource
from substitute.app.bootstrap.startup_trace import trace_mark
from substitute.app.bootstrap.startup_model_metadata import (
    ModelMetadataUpdateBridgeProtocol,
    StartupModelMetadataRefreshHandleFactory,
    StartupModelMetadataRefreshHandleProtocol,
    StartupModelMetadataRefreshState,
    start_model_metadata_refresh,
)

DEFAULT_NONESSENTIAL_STARTUP_WARMUP_DELAY_MS = 2000


class _StartupWarmupExecutionDispatcher:
    """Satisfy execution runtime routing for fire-and-forget warmup tasks."""

    def publish(self, callback: Callable[[], None], *, reason: str) -> None:
        """Run callbacks directly; editor warmups do not register completions."""

        _ = reason
        callback()


def _startup_execution_kwargs(
    main_window: object,
    *,
    owner_id: str,
) -> dict[str, object] | None:
    """Return startup-lane submitter kwargs from the shell execution runtime."""

    execution_runtime = getattr(main_window, "execution_runtime", None)
    if execution_runtime is None:
        return None
    submitter = execution_runtime.submitter(
        "startup",
        owner_id=owner_id,
        dispatcher=_StartupWarmupExecutionDispatcher(),
    )
    return {
        "submitter": submitter,
        "close_submitter": submitter.close,
    }


class StartupWarmupRegistryProtocol(Protocol):
    """Register startup warmup handles for shutdown."""

    def register_cube_icon_warmup(
        self,
        warmup: ShutdownResource,
    ) -> ShutdownResource:
        """Register one cube icon warmup handle."""

    def register_qpane_sam_warmup(
        self,
        warmup: ShutdownResource,
    ) -> ShutdownResource:
        """Register one QPane SAM warmup handle."""

    def register_editor_startup_warmup(
        self,
        warmup: ShutdownResource,
    ) -> ShutdownResource:
        """Register one editor warmup handle."""


class NonessentialWarmupReadinessStateProtocol(Protocol):
    """Record nonessential warmups waiting for backend readiness."""

    nonessential_startup_warmups_pending_backend: bool


class NonessentialStartupWarmupLauncher:
    """Adapt live startup collaborators into nonessential warmup ports."""

    def __init__(
        self,
        *,
        state: StartupWarmupState,
        startup_cancelled: Callable[[], bool],
        comfy_http_ready: Callable[[], bool],
        readiness_state: NonessentialWarmupReadinessStateProtocol,
        metadata_update_bridge: Callable[[], ModelMetadataUpdateBridgeProtocol | None],
        shell_frame: Callable[[], object | None],
        main_window_for_shell: Callable[[object], object | None],
        registry: StartupWarmupRegistryProtocol,
        model_metadata_refresh_state: StartupModelMetadataRefreshState,
        model_metadata_refreshes: Callable[
            [], MutableSequence[StartupModelMetadataRefreshHandleProtocol]
        ],
        model_metadata_service_factory: Callable[[], Any],
        model_metadata_refresh_handle_factory: (
            StartupModelMetadataRefreshHandleFactory
        ),
        comfy_output_stream: Any,
        scheduler: Callable[[int, Callable[[], None]], None],
        trace_fields: Callable[[], dict[str, object]],
        coalescing_timeout_delay_ms: int = 30000,
        backend_editor_warmup: Callable[..., None] | None = None,
        cube_icon_warmup: Callable[..., None] | None = None,
        model_metadata_refresh: Callable[..., None] | None = None,
    ) -> None:
        """Store ports used to start post-ready nonessential warmups."""

        self._state = state
        self._startup_cancelled = startup_cancelled
        self._comfy_http_ready = comfy_http_ready
        self._readiness_state = readiness_state
        self._metadata_update_bridge = metadata_update_bridge
        self._shell_frame = shell_frame
        self._main_window_for_shell = main_window_for_shell
        self._registry = registry
        self._model_metadata_refresh_state = model_metadata_refresh_state
        self._model_metadata_refreshes = model_metadata_refreshes
        self._model_metadata_service_factory = model_metadata_service_factory
        self._model_metadata_refresh_handle_factory = (
            model_metadata_refresh_handle_factory
        )
        self._comfy_output_stream = comfy_output_stream
        self._scheduler = scheduler
        self._trace_fields = trace_fields
        self._coalescing_timeout_delay_ms = coalescing_timeout_delay_ms
        self._backend_editor_warmup = (
            start_backend_editor_startup_warmup
            if backend_editor_warmup is None
            else backend_editor_warmup
        )
        self._cube_icon_warmup = (
            start_cube_icon_startup_warmup
            if cube_icon_warmup is None
            else cube_icon_warmup
        )
        self._model_metadata_refresh = (
            start_model_metadata_refresh
            if model_metadata_refresh is None
            else model_metadata_refresh
        )

    def start(self) -> None:
        """Start nonessential warmups using current startup state."""

        start_nonessential_startup_warmups(
            state=self._state,
            comfy_http_ready=self._comfy_http_ready(),
            readiness_state=self._readiness_state,
            metadata_update_bridge=self._metadata_update_bridge(),
            coalescing_timeout_delay_ms=self._coalescing_timeout_delay_ms,
            scheduler=self._scheduler,
            start_backend_editor_warmup=self._start_backend_editor_warmup,
            start_cube_icon_warmup=self._start_cube_icon_warmup,
            start_model_metadata_refresh=self._start_model_metadata_refresh,
            trace_fields=self._trace_fields,
        )

    def _start_backend_editor_warmup(self) -> None:
        """Start backend editor warmup from current shell collaborators."""

        self._backend_editor_warmup(
            state=self._state,
            startup_cancelled=self._startup_cancelled(),
            shell_frame=self._shell_frame(),
            main_window_for_shell=self._main_window_for_shell,
            registry=self._registry,
            trace_fields=self._trace_fields,
        )

    def _start_cube_icon_warmup(self) -> None:
        """Start cube icon warmup from current shell collaborators."""

        self._cube_icon_warmup(
            state=self._state,
            startup_cancelled=self._startup_cancelled(),
            shell_frame=self._shell_frame(),
            main_window_for_shell=self._main_window_for_shell,
            registry=self._registry,
            trace_fields=self._trace_fields,
        )

    def _start_model_metadata_refresh(self) -> None:
        """Start model metadata refresh from current metadata bridge state."""

        self._model_metadata_refresh(
            state=self._model_metadata_refresh_state,
            startup_cancelled=self._startup_cancelled(),
            metadata_update_bridge=self._metadata_update_bridge(),
            refreshes=self._model_metadata_refreshes(),
            service_factory=self._model_metadata_service_factory,
            comfy_output_stream=self._comfy_output_stream,
            trace_fields=self._trace_fields,
            refresh_handle_factory=self._model_metadata_refresh_handle_factory,
        )


def create_nonessential_startup_warmup_launcher(
    *,
    state: StartupWarmupState,
    startup_cancelled: Callable[[], bool],
    comfy_http_ready: Callable[[], bool],
    readiness_state: NonessentialWarmupReadinessStateProtocol,
    metadata_update_bridge: Callable[[], ModelMetadataUpdateBridgeProtocol | None],
    shell_frame: Callable[[], object | None],
    main_window_for_shell: Callable[[object], object | None],
    registry: StartupWarmupRegistryProtocol,
    model_metadata_refresh_state: StartupModelMetadataRefreshState,
    model_metadata_refreshes: Callable[
        [], MutableSequence[StartupModelMetadataRefreshHandleProtocol]
    ],
    model_metadata_service_factory: Callable[[], Any],
    model_metadata_refresh_handle_factory: StartupModelMetadataRefreshHandleFactory,
    comfy_output_stream: Any,
    scheduler: Callable[[int, Callable[[], None]], None],
    trace_fields: Callable[[], dict[str, object]],
) -> NonessentialStartupWarmupLauncher:
    """Create the live nonessential startup warmup launcher."""

    return NonessentialStartupWarmupLauncher(
        state=state,
        startup_cancelled=startup_cancelled,
        comfy_http_ready=comfy_http_ready,
        readiness_state=readiness_state,
        metadata_update_bridge=metadata_update_bridge,
        shell_frame=shell_frame,
        main_window_for_shell=main_window_for_shell,
        registry=registry,
        model_metadata_refresh_state=model_metadata_refresh_state,
        model_metadata_refreshes=model_metadata_refreshes,
        model_metadata_service_factory=model_metadata_service_factory,
        model_metadata_refresh_handle_factory=model_metadata_refresh_handle_factory,
        comfy_output_stream=comfy_output_stream,
        scheduler=scheduler,
        trace_fields=trace_fields,
    )


class NonessentialStartupWarmupScheduler:
    """Bind nonessential warmup deferral policy to a reusable schedule port."""

    def __init__(
        self,
        *,
        scheduler: Callable[[int, Callable[[], None]], None],
        start_warmups: Callable[[], None],
        trace_fields: Callable[[], Mapping[str, object]],
        delay_ms: int = DEFAULT_NONESSENTIAL_STARTUP_WARMUP_DELAY_MS,
        schedule_warmups: Callable[..., None] | None = None,
    ) -> None:
        """Store live scheduler collaborators for deferred warmup starts."""

        self._scheduler = scheduler
        self._start_warmups = start_warmups
        self._trace_fields = trace_fields
        self._delay_ms = delay_ms
        self._schedule_warmups = (
            schedule_nonessential_startup_warmups
            if schedule_warmups is None
            else schedule_warmups
        )

    def schedule(self, reason: str) -> None:
        """Schedule nonessential warmups using the configured delay."""

        self._schedule_warmups(
            reason=reason,
            delay_ms=self._delay_ms,
            scheduler=self._scheduler,
            start_warmups=self._start_warmups,
            trace_fields=lambda: dict(self._trace_fields()),
        )


def create_nonessential_startup_warmup_scheduler(
    *,
    scheduler: Callable[[int, Callable[[], None]], None],
    start_warmups: Callable[[], None],
    trace_fields: Callable[[], Mapping[str, object]],
) -> NonessentialStartupWarmupScheduler:
    """Create the live nonessential startup warmup scheduler."""

    return NonessentialStartupWarmupScheduler(
        scheduler=scheduler,
        start_warmups=start_warmups,
        trace_fields=trace_fields,
    )


@dataclass(frozen=True, slots=True)
class NonessentialStartupWarmupRuntime:
    """Expose paired nonessential warmup start and schedule ports."""

    launcher: NonessentialStartupWarmupLauncher
    scheduler: NonessentialStartupWarmupScheduler

    def start(self) -> None:
        """Start nonessential warmups through the owned launcher."""

        self.launcher.start()

    def schedule(self, reason: str) -> None:
        """Schedule nonessential warmups through the owned scheduler."""

        self.scheduler.schedule(reason)


def create_nonessential_startup_warmup_runtime(
    *,
    state: StartupWarmupState,
    startup_cancelled: Callable[[], bool],
    comfy_http_ready: Callable[[], bool],
    readiness_state: NonessentialWarmupReadinessStateProtocol,
    metadata_update_bridge: Callable[[], ModelMetadataUpdateBridgeProtocol | None],
    shell_frame: Callable[[], object | None],
    main_window_for_shell: Callable[[object], object | None],
    registry: StartupWarmupRegistryProtocol,
    model_metadata_refresh_state: StartupModelMetadataRefreshState,
    model_metadata_refreshes: Callable[
        [], MutableSequence[StartupModelMetadataRefreshHandleProtocol]
    ],
    model_metadata_service_factory: Callable[[], Any],
    model_metadata_refresh_handle_factory: StartupModelMetadataRefreshHandleFactory,
    comfy_output_stream: Any,
    scheduler: Callable[[int, Callable[[], None]], None],
    trace_fields: Callable[[], dict[str, object]],
) -> NonessentialStartupWarmupRuntime:
    """Create paired nonessential warmup launcher and scheduler ports."""

    launcher = create_nonessential_startup_warmup_launcher(
        state=state,
        startup_cancelled=startup_cancelled,
        comfy_http_ready=comfy_http_ready,
        readiness_state=readiness_state,
        metadata_update_bridge=metadata_update_bridge,
        shell_frame=shell_frame,
        main_window_for_shell=main_window_for_shell,
        registry=registry,
        model_metadata_refresh_state=model_metadata_refresh_state,
        model_metadata_refreshes=model_metadata_refreshes,
        model_metadata_service_factory=model_metadata_service_factory,
        model_metadata_refresh_handle_factory=model_metadata_refresh_handle_factory,
        comfy_output_stream=comfy_output_stream,
        scheduler=scheduler,
        trace_fields=trace_fields,
    )
    warmup_scheduler = create_nonessential_startup_warmup_scheduler(
        scheduler=scheduler,
        start_warmups=launcher.start,
        trace_fields=trace_fields,
    )
    return NonessentialStartupWarmupRuntime(
        launcher=launcher,
        scheduler=warmup_scheduler,
    )


@dataclass
class StartupWarmupState:
    """Track one-shot startup warmup launch state."""

    cube_icon_started: bool = False
    qpane_sam_started: bool = False
    local_editor_started: bool = False
    backend_editor_started: bool = False
    nonessential_started: bool = False
    restore_finalized_warmups_connected: bool = False
    restore_finalized_warmups_callback: Callable[[], None] | None = None


def start_qpane_sam_startup_warmup(
    *,
    state: StartupWarmupState,
    startup_cancelled: bool,
    registry: StartupWarmupRegistryProtocol,
    trace_fields: Callable[[], dict[str, object]],
    execution_runtime: object | None = None,
    warmup_factory: Callable[..., ShutdownResource] | None = None,
) -> None:
    """Start QPane SAM warmup once during ready-shell startup."""

    trace_mark("qpane_sam_warmup.start_requested", **trace_fields())
    if startup_cancelled:
        trace_mark("qpane_sam_warmup.skip", reason="startup_cancelled")
        return
    if state.qpane_sam_started:
        trace_mark("qpane_sam_warmup.skip", reason="already_started")
        return
    warmup_kwargs: dict[str, object] = {}
    if warmup_factory is None:
        warmup_factory = QPaneSamStartupWarmupHandle
        if execution_runtime is None:
            trace_mark("qpane_sam_warmup.skip", reason="missing_execution_runtime")
            return
        submitter = cast(Any, execution_runtime).submitter(
            "startup",
            owner_id="qpane_sam_startup_warmup",
            dispatcher=_StartupWarmupExecutionDispatcher(),
        )
        warmup_kwargs = {
            "submitter": submitter,
            "close_submitter": submitter.close,
        }
    warmup = cast(Any, warmup_factory)(**warmup_kwargs)
    registry.register_qpane_sam_warmup(warmup)
    _start_warmup(warmup)
    state.qpane_sam_started = True
    trace_mark("qpane_sam_warmup.started")


def start_cube_icon_startup_warmup(
    *,
    state: StartupWarmupState,
    startup_cancelled: bool,
    shell_frame: object | None,
    main_window_for_shell: Callable[[object], object | None],
    registry: StartupWarmupRegistryProtocol,
    trace_fields: Callable[[], dict[str, object]],
    warmup_factory: Callable[..., ShutdownResource] | None = None,
) -> None:
    """Start cube icon warmup once when shell dependencies are available."""

    trace_mark("cube_icon_warmup.start_requested", **trace_fields())
    if startup_cancelled or state.cube_icon_started or shell_frame is None:
        trace_mark(
            "cube_icon_warmup.skip",
            reason="startup_cancelled"
            if startup_cancelled
            else "already_started"
            if state.cube_icon_started
            else "no_shell_frame",
        )
        return
    main_window = main_window_for_shell(shell_frame)
    if main_window is None:
        return
    cube_load_service = getattr(main_window, "cube_load_service", None)
    cube_icon_factory = getattr(main_window, "cube_icon_factory", None)
    if cube_load_service is None or cube_icon_factory is None:
        trace_mark("cube_icon_warmup.skip", reason="missing_dependencies")
        return
    if warmup_factory is None:
        warmup_factory = StartupCubeIconWarmupHandle
        execution_kwargs = _startup_execution_kwargs(
            main_window,
            owner_id="cube_icon_startup_warmup",
        )
        if execution_kwargs is None:
            trace_mark("cube_icon_warmup.skip", reason="missing_execution_runtime")
            return
        execution_kwargs["ui_receiver"] = main_window
    else:
        execution_kwargs = {}
    warmup = cast(Any, warmup_factory)(
        cube_load_service=cube_load_service,
        cube_icon_factory=cube_icon_factory,
        **execution_kwargs,
    )
    registry.register_cube_icon_warmup(warmup)
    _start_warmup(warmup)
    state.cube_icon_started = True
    trace_mark("cube_icon_warmup.started")


def start_local_editor_startup_warmup(
    *,
    state: StartupWarmupState,
    startup_cancelled: bool,
    shell_frame: object | None,
    main_window_for_shell: Callable[[object], object | None],
    registry: StartupWarmupRegistryProtocol,
    trace_fields: Callable[[], dict[str, object]],
    warmup_factory: Callable[..., ShutdownResource] | None = None,
) -> None:
    """Start backend-independent editor warmup once when the shell exists."""

    trace_mark("local_editor_warmup.start_requested", **trace_fields())
    if startup_cancelled:
        trace_mark("local_editor_warmup.skip", reason="startup_cancelled")
        return
    if state.local_editor_started or shell_frame is None:
        trace_mark(
            "local_editor_warmup.skip",
            reason="already_started"
            if state.local_editor_started
            else "no_shell_frame",
        )
        return
    main_window = main_window_for_shell(shell_frame)
    if main_window is None:
        return
    warmup_kwargs: dict[str, object] = {
        "prompt_autocomplete_gateway": getattr(
            main_window,
            "prompt_autocomplete_gateway",
            None,
        ),
        "prompt_wildcard_catalog_gateway": getattr(
            main_window,
            "prompt_wildcard_catalog_gateway",
            None,
        ),
        "prompt_lora_catalog_service": getattr(
            main_window,
            "prompt_lora_catalog_service",
            None,
        ),
        "prompt_spellcheck_service": getattr(
            main_window,
            "prompt_spellcheck_service",
            None,
        ),
    }
    if warmup_factory is None:
        from substitute.app.bootstrap.editor_startup_warmup import (
            LocalEditorStartupWarmupHandle,
        )

        warmup_factory = LocalEditorStartupWarmupHandle
        execution_kwargs = _startup_execution_kwargs(
            main_window,
            owner_id="local_editor_startup_warmup",
        )
        if execution_kwargs is None:
            trace_mark("local_editor_warmup.skip", reason="missing_execution_runtime")
            return
        warmup_kwargs.update(execution_kwargs)
    warmup = cast(Any, warmup_factory)(**warmup_kwargs)
    registry.register_editor_startup_warmup(warmup)
    _start_warmup(warmup)
    state.local_editor_started = True
    trace_mark("local_editor_warmup.started")


def start_backend_editor_startup_warmup(
    *,
    state: StartupWarmupState,
    startup_cancelled: bool,
    shell_frame: object | None,
    main_window_for_shell: Callable[[object], object | None],
    registry: StartupWarmupRegistryProtocol,
    trace_fields: Callable[[], dict[str, object]],
    warmup_factory: Callable[..., ShutdownResource] | None = None,
) -> None:
    """Start Comfy-dependent editor warmup once when the shell exists."""

    trace_mark("backend_editor_warmup.start_requested", **trace_fields())
    if startup_cancelled:
        trace_mark("backend_editor_warmup.skip", reason="startup_cancelled")
        return
    if state.backend_editor_started or shell_frame is None:
        trace_mark(
            "backend_editor_warmup.skip",
            reason="already_started"
            if state.backend_editor_started
            else "no_shell_frame",
        )
        return
    main_window = main_window_for_shell(shell_frame)
    if main_window is None:
        return
    warmup_kwargs = {
        "node_definition_gateway": getattr(
            main_window,
            "node_definition_gateway",
            None,
        ),
        "model_choice_resolver": getattr(
            main_window,
            "model_choice_resolver",
            None,
        ),
    }
    if warmup_factory is None:
        from substitute.app.bootstrap.editor_startup_warmup import (
            BackendEditorStartupWarmupHandle,
        )

        warmup_factory = BackendEditorStartupWarmupHandle
        execution_kwargs = _startup_execution_kwargs(
            main_window,
            owner_id="backend_editor_startup_warmup",
        )
        if execution_kwargs is None:
            trace_mark("backend_editor_warmup.skip", reason="missing_execution_runtime")
            return
        warmup_kwargs.update(execution_kwargs)
    warmup = cast(Any, warmup_factory)(**warmup_kwargs)
    registry.register_editor_startup_warmup(warmup)
    _start_warmup(warmup)
    state.backend_editor_started = True
    trace_mark("backend_editor_warmup.started")


def schedule_nonessential_startup_warmups(
    *,
    reason: str,
    delay_ms: int,
    scheduler: Callable[[int, Callable[[], None]], None],
    start_warmups: Callable[[], None],
    trace_fields: Callable[[], dict[str, object]],
) -> None:
    """Defer nonessential warmups out of the first interactive startup burst."""

    trace_mark(
        "post_comfy.nonessential_warmups.deferred",
        reason=reason,
        delay_ms=delay_ms,
        **trace_fields(),
    )
    trace_mark(
        "post_comfy.nonessential_warmups.deferred_start",
        delay_ms=delay_ms,
    )
    scheduler(delay_ms, start_warmups)


def start_nonessential_startup_warmups(
    *,
    state: StartupWarmupState,
    comfy_http_ready: bool,
    readiness_state: NonessentialWarmupReadinessStateProtocol,
    metadata_update_bridge: object | None,
    coalescing_timeout_delay_ms: int,
    scheduler: Callable[[int, Callable[[], None]], None],
    start_backend_editor_warmup: Callable[[], None],
    start_cube_icon_warmup: Callable[[], None],
    start_model_metadata_refresh: Callable[[], None],
    trace_fields: Callable[[], dict[str, object]],
) -> None:
    """Start post-restore warmups that should not delay first usability."""

    trace_mark("post_comfy.nonessential_warmups.begin", **trace_fields())
    if state.nonessential_started:
        trace_mark(
            "post_comfy.nonessential_warmups.skip",
            reason="already_started",
        )
        return
    if not comfy_http_ready:
        readiness_state.nonessential_startup_warmups_pending_backend = True
        trace_mark(
            "post_comfy.nonessential_warmups.wait_backend_ready",
            **trace_fields(),
        )
        return
    state.nonessential_started = True
    begin_metadata_coalescing = getattr(
        metadata_update_bridge,
        "begin_startup_coalescing",
        None,
    )
    if callable(begin_metadata_coalescing):
        begin_metadata_coalescing()
    start_backend_editor_warmup()
    start_cube_icon_warmup()
    start_model_metadata_refresh()
    timeout_metadata_coalescing = getattr(
        metadata_update_bridge,
        "timeout_startup_coalescing",
        None,
    )
    if callable(timeout_metadata_coalescing):
        trace_mark(
            "metadata_update_bridge.startup_coalescing_timeout",
            delay_ms=coalescing_timeout_delay_ms,
        )
        scheduler(coalescing_timeout_delay_ms, timeout_metadata_coalescing)
    trace_mark("post_comfy.nonessential_warmups.end", **trace_fields())


def connect_restore_finalized_warmups(
    *,
    state: StartupWarmupState,
    main_window: object,
    schedule_warmups: Callable[[str], None],
    trace_fields: Callable[[], dict[str, object]],
) -> None:
    """Connect restored-shell finalization to deferred nonessential warmups."""

    if state.restore_finalized_warmups_connected:
        return
    restore_finalized = getattr(main_window, "restore_finalized", None)
    connect = getattr(restore_finalized, "connect", None)
    if not callable(connect):
        trace_mark("post_comfy.nonessential_warmups.restore_signal_unavailable")
        return

    def start_after_restore_finalized() -> None:
        """Start background warmups once restore has reached running state."""

        trace_mark(
            "post_comfy.nonessential_warmups.restore_finalized",
            **trace_fields(),
        )
        schedule_warmups("restore_finalized")

    state.restore_finalized_warmups_callback = start_after_restore_finalized
    connect(state.restore_finalized_warmups_callback)
    state.restore_finalized_warmups_connected = True
    trace_mark(
        "post_comfy.nonessential_warmups.wait_restore_finalized",
        **trace_fields(),
    )


def _start_warmup(warmup: ShutdownResource) -> None:
    """Start one warmup handle through its common port."""

    start = getattr(warmup, "start", None)
    if callable(start):
        start()


__all__ = [
    "DEFAULT_NONESSENTIAL_STARTUP_WARMUP_DELAY_MS",
    "NonessentialStartupWarmupLauncher",
    "NonessentialStartupWarmupRuntime",
    "NonessentialStartupWarmupScheduler",
    "NonessentialWarmupReadinessStateProtocol",
    "StartupWarmupRegistryProtocol",
    "StartupWarmupState",
    "connect_restore_finalized_warmups",
    "create_nonessential_startup_warmup_launcher",
    "create_nonessential_startup_warmup_runtime",
    "create_nonessential_startup_warmup_scheduler",
    "schedule_nonessential_startup_warmups",
    "start_backend_editor_startup_warmup",
    "start_cube_icon_startup_warmup",
    "start_local_editor_startup_warmup",
    "start_nonessential_startup_warmups",
    "start_qpane_sam_startup_warmup",
]

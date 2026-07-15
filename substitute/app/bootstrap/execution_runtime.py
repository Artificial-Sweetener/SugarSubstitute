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

"""Compose process-lifetime execution lanes for the application."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from threading import Lock
from typing import TypeVar

from substitute.application.execution import (
    CancellationToken,
    ExecutionContext,
    ExecutionLane,
    TaskHandle,
    TaskIdentity,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.infrastructure.execution import LongLivedTaskHandle
from substitute.infrastructure.execution.long_lived_task import (
    LongLivedDispatcher,
    LongLivedWork,
)
from substitute.infrastructure.execution.thread_pool_lane import CompletionDispatcher
from substitute.infrastructure.execution.thread_pool_lane import ThreadPoolExecutionLane
from substitute.shared.logging.logger import get_logger, log_info, log_warning

TResult = TypeVar("TResult")

_LOGGER = get_logger("app.bootstrap.execution_runtime")
_QUEUE_CAPACITY_MULTIPLIER = 4


@dataclass(frozen=True, slots=True)
class ExecutionLaneConfig:
    """Describe one process-lifetime short-task execution lane."""

    name: str
    max_workers: int
    queue_capacity: int
    thread_name_prefix: str


def _require_non_blank(value: str, *, field_name: str) -> None:
    """Reject blank runtime labels."""

    if not value.strip():
        raise ValueError(f"{field_name} must not be blank.")


def _lane_config(name: str, *, max_workers: int) -> ExecutionLaneConfig:
    """Build one default lane config."""

    _require_non_blank(name, field_name="name")
    if max_workers <= 0:
        raise ValueError("max_workers must be positive.")
    return ExecutionLaneConfig(
        name=name,
        max_workers=max_workers,
        queue_capacity=max_workers * _QUEUE_CAPACITY_MULTIPLIER,
        thread_name_prefix=f"substitute-{name.replace('_', '-')}",
    )


def _lane_config_with_capacity(
    name: str,
    *,
    max_workers: int,
    queue_capacity: int,
) -> ExecutionLaneConfig:
    """Build one lane config with explicit burst capacity."""

    _require_non_blank(name, field_name="name")
    if max_workers <= 0:
        raise ValueError("max_workers must be positive.")
    if queue_capacity <= 0:
        raise ValueError("queue_capacity must be positive.")
    return ExecutionLaneConfig(
        name=name,
        max_workers=max_workers,
        queue_capacity=queue_capacity,
        thread_name_prefix=f"substitute-{name.replace('_', '-')}",
    )


def _validate_lane_config(config: ExecutionLaneConfig) -> None:
    """Validate one externally supplied execution lane config."""

    _require_non_blank(config.name, field_name="name")
    _require_non_blank(config.thread_name_prefix, field_name="thread_name_prefix")
    if config.max_workers <= 0:
        raise ValueError("max_workers must be positive.")
    if config.queue_capacity <= 0:
        raise ValueError("queue_capacity must be positive.")


DEFAULT_EXECUTION_LANE_CONFIGS = (
    _lane_config_with_capacity("prompt_editor", max_workers=2, queue_capacity=128),
    _lane_config("settings_io", max_workers=2),
    _lane_config("package_maintenance", max_workers=1),
    _lane_config("onboarding_provisioning", max_workers=1),
    _lane_config("generation_dispatch", max_workers=1),
    _lane_config("generation_preparation", max_workers=1),
    _lane_config("cube_load", max_workers=2),
    _lane_config("cube_library_update", max_workers=1),
    _lane_config("model_catalog", max_workers=1),
    _lane_config("model_metadata", max_workers=1),
    _lane_config("node_definition", max_workers=2),
    _lane_config("recipe_model_resolution", max_workers=1),
    _lane_config("danbooru_refresh", max_workers=2),
    _lane_config("image_decode", max_workers=2),
    _lane_config_with_capacity(
        "thumbnail_decode",
        max_workers=4,
        queue_capacity=64,
    ),
    _lane_config("disk_io_low_priority", max_workers=1),
    _lane_config("model_download", max_workers=2),
    _lane_config("startup", max_workers=2),
    _lane_config("shutdown", max_workers=1),
)
LONG_LIVED_EXECUTION_REGISTRIES = frozenset(
    {
        "backend_event_listener",
        "generation_listener",
        "process_pump",
    }
)


class ExecutionRuntime:
    """Own application-wide execution lanes and long-lived task registries."""

    def __init__(
        self,
        *,
        lane_configs: tuple[
            ExecutionLaneConfig,
            ...,
        ] = DEFAULT_EXECUTION_LANE_CONFIGS,
    ) -> None:
        """Create all process-lifetime short-task lanes."""

        if not lane_configs:
            raise ValueError("lane_configs must not be empty.")
        seen_names: set[str] = set()
        for config in lane_configs:
            _validate_lane_config(config)
            if config.name in seen_names:
                raise ValueError("execution lane names must be unique.")
            seen_names.add(config.name)
        self._dispatchers: dict[tuple[str, str], CompletionDispatcher] = {}
        self._long_lived: dict[str, dict[str, LongLivedTaskHandle[object]]] = {
            name: {} for name in sorted(LONG_LIVED_EXECUTION_REGISTRIES)
        }
        self._is_shutdown = False
        self._lock = Lock()
        self._lanes = {
            config.name: ThreadPoolExecutionLane(
                name=config.name,
                max_workers=config.max_workers,
                queue_capacity=config.queue_capacity,
                thread_name_prefix=config.thread_name_prefix,
                dispatcher_factory=self._dispatcher_for_request,
            )
            for config in lane_configs
        }
        for config in lane_configs:
            log_info(
                _LOGGER,
                "Execution lane configured",
                lane=config.name,
                max_workers=config.max_workers,
                queue_capacity=config.queue_capacity,
                thread_name_prefix=config.thread_name_prefix,
            )

    @property
    def lane_names(self) -> tuple[str, ...]:
        """Return configured short-task lane names."""

        return tuple(self._lanes)

    @property
    def long_lived_registry_names(self) -> tuple[str, ...]:
        """Return configured long-lived registry names."""

        return tuple(self._long_lived)

    @property
    def prompt_editor(self) -> ExecutionLane:
        """Return the prompt-editor execution lane."""

        return self.lane("prompt_editor")

    @property
    def settings_io(self) -> ExecutionLane:
        """Return the settings IO execution lane."""

        return self.lane("settings_io")

    @property
    def package_maintenance(self) -> ExecutionLane:
        """Return the package-maintenance execution lane."""

        return self.lane("package_maintenance")

    @property
    def onboarding_provisioning(self) -> ExecutionLane:
        """Return the onboarding-provisioning execution lane."""

        return self.lane("onboarding_provisioning")

    @property
    def generation_dispatch(self) -> ExecutionLane:
        """Return the generation-dispatch execution lane."""

        return self.lane("generation_dispatch")

    @property
    def generation_preparation(self) -> ExecutionLane:
        """Return the generation-preparation execution lane."""

        return self.lane("generation_preparation")

    @property
    def cube_load(self) -> ExecutionLane:
        """Return the cube-load execution lane."""

        return self.lane("cube_load")

    @property
    def cube_library_update(self) -> ExecutionLane:
        """Return the Cube Library update execution lane."""

        return self.lane("cube_library_update")

    @property
    def model_catalog(self) -> ExecutionLane:
        """Return the model-catalog execution lane."""

        return self.lane("model_catalog")

    @property
    def model_metadata(self) -> ExecutionLane:
        """Return the model-metadata execution lane."""

        return self.lane("model_metadata")

    @property
    def node_definition(self) -> ExecutionLane:
        """Return the node-definition execution lane."""

        return self.lane("node_definition")

    @property
    def recipe_model_resolution(self) -> ExecutionLane:
        """Return the recipe model resolution execution lane."""

        return self.lane("recipe_model_resolution")

    @property
    def danbooru_refresh(self) -> ExecutionLane:
        """Return the danbooru-refresh execution lane."""

        return self.lane("danbooru_refresh")

    @property
    def image_decode(self) -> ExecutionLane:
        """Return the image-decode execution lane."""

        return self.lane("image_decode")

    @property
    def thumbnail_decode(self) -> ExecutionLane:
        """Return the opportunistic thumbnail-decode execution lane."""

        return self.lane("thumbnail_decode")

    @property
    def disk_io_low_priority(self) -> ExecutionLane:
        """Return the low-priority disk IO execution lane."""

        return self.lane("disk_io_low_priority")

    @property
    def model_download(self) -> ExecutionLane:
        """Return the model-download execution lane."""

        return self.lane("model_download")

    @property
    def startup(self) -> ExecutionLane:
        """Return the startup execution lane."""

        return self.lane("startup")

    @property
    def shutdown_execution(self) -> ExecutionLane:
        """Return the shutdown execution lane."""

        return self.lane("shutdown")

    def lane(self, name: str) -> ExecutionLane:
        """Return one configured short-task lane by name."""

        _require_non_blank(name, field_name="name")
        try:
            return self._lanes[name]
        except KeyError as error:
            raise ValueError(f"Unknown execution lane: {name}") from error

    def scope(
        self,
        name: str,
        *,
        owner_id: str,
        dispatcher: CompletionDispatcher,
    ) -> "RuntimeExecutionScope":
        """Create one owner-scoped task scope for a named lane."""

        _require_non_blank(owner_id, field_name="owner_id")
        lane = self.lane(name)
        key = (name, owner_id)
        with self._lock:
            if self._is_shutdown:
                raise RuntimeError("Execution runtime is shut down.")
            if key in self._dispatchers:
                raise RuntimeError(
                    f"Execution dispatcher already registered for {name}:{owner_id}."
                )
            self._dispatchers[key] = dispatcher
        task_scope = TaskScope(
            submitter=_OwnerScopedSubmitter(
                lane=lane,
                lane_name=name,
                owner_id=owner_id,
                scope_id=owner_id,
            ),
            scope_id=owner_id,
        )
        return RuntimeExecutionScope(
            task_scope=task_scope,
            on_close=lambda: self._unregister_dispatcher(key),
        )

    def submitter(
        self,
        name: str,
        *,
        owner_id: str,
        dispatcher: CompletionDispatcher,
    ) -> "RuntimeExecutionSubmitter":
        """Create one owner-scoped submitter for caller-owned cancellation."""

        _require_non_blank(owner_id, field_name="owner_id")
        lane = self.lane(name)
        key = (name, owner_id)
        with self._lock:
            if self._is_shutdown:
                raise RuntimeError("Execution runtime is shut down.")
            if key in self._dispatchers:
                raise RuntimeError(
                    f"Execution dispatcher already registered for {name}:{owner_id}."
                )
            self._dispatchers[key] = dispatcher
        return RuntimeExecutionSubmitter(
            submitter=_OwnerScopedSubmitter(
                lane=lane,
                lane_name=name,
                owner_id=owner_id,
                scope_id=owner_id,
            ),
            on_close=lambda: self._unregister_dispatcher(key),
        )

    def start_long_lived(
        self,
        registry_name: str,
        key: str,
        *,
        identity: TaskIdentity,
        context: ExecutionContext,
        work: LongLivedWork[TResult],
        dispatcher: LongLivedDispatcher,
        close_hook: Callable[[], None] | None = None,
        join_timeout_seconds: float = 1.0,
        thread_name: str,
    ) -> LongLivedTaskHandle[TResult]:
        """Start and register one long-lived task after runtime acceptance."""

        _require_non_blank(key, field_name="key")
        registry = self._long_lived_registry(registry_name)
        with self._lock:
            if self._is_shutdown:
                raise RuntimeError("Execution runtime is shut down.")
            existing = registry.get(key)
            if existing is not None and not existing.is_finished:
                raise RuntimeError(
                    f"Long-lived task already registered for {registry_name}:{key}."
                )
            handle: LongLivedTaskHandle[TResult] = LongLivedTaskHandle(
                identity=identity,
                context=context,
                work=work,
                dispatcher=dispatcher,
                close_hook=close_hook,
                join_timeout_seconds=join_timeout_seconds,
                thread_name=thread_name,
            )
            registry[key] = _as_object_long_lived_handle(handle)
        return handle

    def stop_long_lived(self, registry_name: str, key: str, *, reason: str) -> None:
        """Stop and remove one registered long-lived task when present."""

        _require_non_blank(reason, field_name="reason")
        registry = self._long_lived_registry(registry_name)
        with self._lock:
            handle = registry.pop(key, None)
        if handle is not None:
            handle.stop(reason=reason)

    def shutdown_lane(self, name: str) -> None:
        """Shut down one short-task lane or long-lived registry."""

        _require_non_blank(name, field_name="name")
        if name in self._lanes:
            self._lanes[name].shutdown(wait=False, cancel_futures=True)
            return
        if name in self._long_lived:
            self._stop_long_lived_registry(name, reason="lane_shutdown")
            return
        raise ValueError(f"Unknown execution lane: {name}")

    def shutdown(self) -> None:
        """Stop long-lived handles and release every short-task lane."""

        with self._lock:
            if self._is_shutdown:
                return
            self._is_shutdown = True
        for registry_name in tuple(self._long_lived):
            self._stop_long_lived_registry(registry_name, reason="runtime_shutdown")
        for lane in self._lanes.values():
            lane.shutdown(wait=False, cancel_futures=True)
        with self._lock:
            self._dispatchers.clear()

    def _dispatcher_for_request(
        self,
        request: TaskRequest[object],
    ) -> CompletionDispatcher:
        """Return the owner dispatcher registered for a submitted request."""

        lane_name = request.context.lane
        owner_id = request.context.owner_id
        if owner_id is None:
            raise RuntimeError(
                f"Execution request for lane {lane_name} has no owner_id."
            )
        with self._lock:
            if self._is_shutdown:
                raise RuntimeError("Execution runtime is shut down.")
            dispatcher = self._dispatchers.get((lane_name, owner_id))
        if dispatcher is None:
            raise RuntimeError(
                f"No execution dispatcher registered for {lane_name}:{owner_id}."
            )
        return dispatcher

    def _long_lived_registry(
        self,
        registry_name: str,
    ) -> dict[str, LongLivedTaskHandle[object]]:
        """Return one long-lived registry by name."""

        _require_non_blank(registry_name, field_name="registry_name")
        try:
            return self._long_lived[registry_name]
        except KeyError as error:
            raise ValueError(
                f"Unknown long-lived execution registry: {registry_name}"
            ) from error

    def _stop_long_lived_registry(self, registry_name: str, *, reason: str) -> None:
        """Stop all handles in one long-lived registry."""

        registry = self._long_lived_registry(registry_name)
        with self._lock:
            handles = tuple(registry.items())
            registry.clear()
        for key, handle in handles:
            try:
                handle.stop(reason=reason)
            except Exception as error:
                log_warning(
                    _LOGGER,
                    "Long-lived execution task stop failed",
                    registry=registry_name,
                    key=key,
                    error_type=type(error).__name__,
                )

    def _unregister_dispatcher(self, key: tuple[str, str]) -> None:
        """Remove one owner dispatcher from routing."""

        with self._lock:
            self._dispatchers.pop(key, None)


class RuntimeExecutionScope:
    """Expose scoped execution while unregistering dispatchers on close."""

    def __init__(
        self,
        *,
        task_scope: TaskScope,
        on_close: Callable[[], None],
    ) -> None:
        """Store the wrapped task scope and dispatcher cleanup callback."""

        self._task_scope = task_scope
        self._on_close = on_close

    @property
    def scope_id(self) -> str:
        """Return the wrapped task-scope identifier."""

        return self._task_scope.scope_id

    @property
    def is_closed(self) -> bool:
        """Return whether this runtime scope has closed."""

        return self._task_scope.is_closed

    def has_pending_work(self) -> bool:
        """Return whether this scope still has unfinished handles."""

        return self._task_scope.has_pending_work()

    def submit(self, request: TaskRequest[TResult]) -> TaskHandle[TResult]:
        """Submit one request through the wrapped task scope."""

        return self._task_scope.submit(request)

    def cancel_all(self, *, reason: str) -> None:
        """Cancel every tracked handle without closing the dispatcher route."""

        self._task_scope.cancel_all(reason=reason)

    def close(self, *, reason: str) -> None:
        """Close this scope, cancel active work, and unregister dispatching."""

        was_closed = self._task_scope.is_closed
        self._task_scope.close(reason=reason)
        if not was_closed:
            self._on_close()


class RuntimeExecutionSubmitter(TaskSubmitter):
    """Expose owner-scoped submission with caller-owned cancellation."""

    def __init__(
        self,
        *,
        submitter: TaskSubmitter,
        on_close: Callable[[], None],
    ) -> None:
        """Store the submitter and dispatcher cleanup callback."""

        self._submitter = submitter
        self._on_close = on_close
        self._is_closed = False
        self._lock = Lock()

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> TaskHandle[TResult]:
        """Submit one request unless this submitter has closed."""

        with self._lock:
            if self._is_closed:
                raise RuntimeError("Execution submitter is closed.")
        return self._submitter.submit(request, cancellation=cancellation)

    def close(self) -> None:
        """Unregister this submitter's dispatcher route."""

        with self._lock:
            if self._is_closed:
                return
            self._is_closed = True
        self._on_close()


class _OwnerScopedSubmitter(TaskSubmitter):
    """Stamp runtime owner context before submitting to a process lane."""

    def __init__(
        self,
        *,
        lane: ExecutionLane,
        lane_name: str,
        owner_id: str,
        scope_id: str,
    ) -> None:
        """Store the lane and owner context."""

        self._lane = lane
        self._lane_name = lane_name
        self._owner_id = owner_id
        self._scope_id = scope_id

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> TaskHandle[TResult]:
        """Submit one request after applying runtime scope context."""

        scoped_context = replace(
            request.context,
            lane=self._lane_name,
            owner_id=self._owner_id,
            scope_id=self._scope_id,
        )
        return self._lane.submit(
            TaskRequest(
                identity=request.identity,
                context=scoped_context,
                work=request.work,
            ),
            cancellation=cancellation,
        )


def _as_object_long_lived_handle(
    handle: LongLivedTaskHandle[TResult],
) -> LongLivedTaskHandle[object]:
    """Return a long-lived handle widened for registry storage."""

    return handle  # type: ignore[return-value]


__all__ = [
    "DEFAULT_EXECUTION_LANE_CONFIGS",
    "LONG_LIVED_EXECUTION_REGISTRIES",
    "ExecutionLaneConfig",
    "ExecutionRuntime",
    "RuntimeExecutionScope",
    "RuntimeExecutionSubmitter",
]

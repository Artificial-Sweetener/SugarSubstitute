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

"""Provide typed process-lifetime runtime fakes for startup route contracts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


class _RuntimeSubmitter:
    """Accept startup work without creating a background execution lane."""

    def close(self) -> None:
        """Release the no-op submitter."""

    def submit(self, _request: object) -> None:
        """Accept one shutdown or persistence request."""


class _ExecutionRuntime:
    """Avoid process-lifetime execution and localization network work."""

    def shutdown(self) -> None:
        """Finish the no-op execution runtime."""

    def submitter(self, *_args: object, **_kwargs: object) -> _RuntimeSubmitter:
        """Return a no-op owner submitter."""

        return _RuntimeSubmitter()


class _PersistentCacheRuntime:
    """Accept cache-runtime teardown for route-level startup proof."""

    def close(self) -> None:
        """Finish the no-op cache runtime."""


class _ManagedComfyRuntimeOwner:
    """Accept managed Comfy owner teardown for route-level startup proof."""

    def __init__(self) -> None:
        """Initialize empty managed state and no observer."""

        self.state: object | None = None
        self._observer: Callable[[object | None], None] | None = None

    def bind_state_observer(
        self,
        observer: Callable[[object | None], None],
    ) -> None:
        """Capture the ready-shell state mirror."""

        self._observer = observer

    def set_state(self, state: object | None) -> None:
        """Publish managed state through the ready-shell mirror."""

        self.state = state
        if self._observer is not None:
            self._observer(state)

    def close(self) -> None:
        """Finish the no-op managed Comfy runtime owner."""


class _SessionFinalizationService:
    """Accept route shutdown persistence without writing a session."""

    def persist(self) -> None:
        """Accept the shutdown persistence request."""


@dataclass(frozen=True, slots=True)
class StartupRuntimeServicesFake:
    """Expose the runtime-service boundary used by application route startup."""

    execution_runtime: _ExecutionRuntime
    persistent_cache_runtime: _PersistentCacheRuntime
    managed_comfy_runtime_owner: _ManagedComfyRuntimeOwner
    session_finalization_service: _SessionFinalizationService
    session_persistence_submitter: _RuntimeSubmitter


def build_startup_runtime_services_fake() -> StartupRuntimeServicesFake:
    """Build isolated no-op process-lifetime services for one route test."""

    return StartupRuntimeServicesFake(
        execution_runtime=_ExecutionRuntime(),
        persistent_cache_runtime=_PersistentCacheRuntime(),
        managed_comfy_runtime_owner=_ManagedComfyRuntimeOwner(),
        session_finalization_service=_SessionFinalizationService(),
        session_persistence_submitter=_RuntimeSubmitter(),
    )

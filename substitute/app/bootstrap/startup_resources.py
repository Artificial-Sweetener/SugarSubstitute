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

"""Register and shut down long-lived startup resources."""

from __future__ import annotations

from collections.abc import MutableSequence
from typing import Protocol, TypeVar

from substitute.app.bootstrap.startup_trace import trace_mark


class ShutdownResource(Protocol):
    """Release one startup-owned resource."""

    def shutdown(self) -> None:
        """Release resource state."""


class StartupModelMetadataRefreshResource(ShutdownResource, Protocol):
    """Cancel and release one startup metadata refresh resource."""

    def cancel(self) -> None:
        """Request refresh cancellation."""


class RuntimeCompatibilityProbeResource(Protocol):
    """Cancel and release one runtime compatibility probe."""

    def cancel_current(self) -> None:
        """Cancel an in-flight compatibility assessment."""

    def shutdown(self) -> None:
        """Release probe resources."""


_ResourceT = TypeVar("_ResourceT")


class StartupResourceRegistry:
    """Retain and shut down startup-lifetime resources."""

    def __init__(self) -> None:
        """Create empty resource collections."""

        self.model_metadata_refreshes: list[StartupModelMetadataRefreshResource] = []
        self.cube_icon_warmups: list[ShutdownResource] = []
        self.qpane_sam_warmups: list[ShutdownResource] = []
        self.editor_startup_warmups: list[ShutdownResource] = []
        self.workspace_restore_asset_preloads: list[ShutdownResource] = []
        self.startup_diagnostics_tasks: list[ShutdownResource] = []
        self.startup_diagnostics_bridges: list[object] = []
        self.readiness_probes: list[ShutdownResource] = []
        self.runtime_compatibility_probes: list[RuntimeCompatibilityProbeResource] = []
        self.metadata_update_bridges: list[object] = []

    def metadata_refreshes(
        self,
    ) -> MutableSequence[StartupModelMetadataRefreshResource]:
        """Return the owned metadata refresh collection for startup append ports."""

        return self.model_metadata_refreshes

    def first_workspace_restore_asset_preload(self) -> object | None:
        """Return the first registered restore asset preload when available."""

        if not self.workspace_restore_asset_preloads:
            return None
        return self.workspace_restore_asset_preloads[0]

    def register_model_metadata_refresh(
        self,
        refresh: StartupModelMetadataRefreshResource,
    ) -> StartupModelMetadataRefreshResource:
        """Register one startup metadata refresh handle."""

        return self._append(self.model_metadata_refreshes, refresh)

    def register_cube_icon_warmup(
        self,
        warmup: ShutdownResource,
    ) -> ShutdownResource:
        """Register one cube icon warmup handle."""

        return self._append(self.cube_icon_warmups, warmup)

    def register_qpane_sam_warmup(
        self,
        warmup: ShutdownResource,
    ) -> ShutdownResource:
        """Register one QPane SAM warmup handle."""

        return self._append(self.qpane_sam_warmups, warmup)

    def register_editor_startup_warmup(
        self,
        warmup: ShutdownResource,
    ) -> ShutdownResource:
        """Register one editor startup warmup handle."""

        return self._append(self.editor_startup_warmups, warmup)

    def register_workspace_restore_asset_preload(
        self,
        preload: ShutdownResource,
    ) -> ShutdownResource:
        """Register one workspace restore asset preload handle."""

        return self._append(self.workspace_restore_asset_preloads, preload)

    def register_startup_diagnostics_task(
        self,
        task: ShutdownResource,
    ) -> ShutdownResource:
        """Register one startup diagnostics execution task resource."""

        return self._append(self.startup_diagnostics_tasks, task)

    def register_startup_diagnostics_bridge(self, bridge: object) -> object:
        """Retain one startup diagnostics Qt bridge for startup lifetime."""

        return self._append(self.startup_diagnostics_bridges, bridge)

    def register_readiness_probe(
        self,
        probe: ShutdownResource,
    ) -> ShutdownResource:
        """Register one readiness probe task."""

        return self._append(self.readiness_probes, probe)

    def register_runtime_compatibility_probe(
        self,
        probe: RuntimeCompatibilityProbeResource,
    ) -> RuntimeCompatibilityProbeResource:
        """Register one runtime compatibility probe task."""

        return self._append(self.runtime_compatibility_probes, probe)

    def register_metadata_update_bridge(self, bridge: object) -> object:
        """Retain one metadata update Qt bridge for startup lifetime."""

        return self._append(self.metadata_update_bridges, bridge)

    def shutdown_all(self) -> None:
        """Shut down registered resources in startup cleanup order."""

        trace_mark(
            "startup_resources.shutdown.start",
            metadata_refresh_count=len(self.model_metadata_refreshes),
            cube_icon_warmup_count=len(self.cube_icon_warmups),
            qpane_sam_warmup_count=len(self.qpane_sam_warmups),
            editor_warmup_count=len(self.editor_startup_warmups),
            diagnostics_task_count=len(self.startup_diagnostics_tasks),
            readiness_probe_count=len(self.readiness_probes),
            runtime_compatibility_probe_count=len(self.runtime_compatibility_probes),
            restore_asset_preload_count=len(self.workspace_restore_asset_preloads),
        )
        for refresh in self.model_metadata_refreshes:
            refresh.cancel()
            refresh.shutdown()
        for resource in self.cube_icon_warmups:
            resource.shutdown()
        for resource in self.qpane_sam_warmups:
            resource.shutdown()
        for resource in self.editor_startup_warmups:
            resource.shutdown()
        for task in self.startup_diagnostics_tasks:
            task.shutdown()
        for probe in self.readiness_probes:
            probe.shutdown()
        for probe in self.runtime_compatibility_probes:
            probe.shutdown()
        for preload in self.workspace_restore_asset_preloads:
            preload.shutdown()
        trace_mark("startup_resources.shutdown.end")

    def keep_alive_references(self) -> tuple[object, ...]:
        """Return retained references that must survive for startup lifetime."""

        return (
            self.metadata_update_bridges,
            self.qpane_sam_warmups,
            self.startup_diagnostics_bridges,
            self.startup_diagnostics_tasks,
            self.readiness_probes,
            self.runtime_compatibility_probes,
            self.cube_icon_warmups,
            self.workspace_restore_asset_preloads,
        )

    def _append(
        self,
        resources: list[_ResourceT],
        resource: _ResourceT,
    ) -> _ResourceT:
        """Append and return one startup resource."""

        resources.append(resource)
        return resource


def create_startup_resource_registry() -> StartupResourceRegistry:
    """Create the startup-lifetime resource registry."""

    return StartupResourceRegistry()


__all__ = [
    "RuntimeCompatibilityProbeResource",
    "ShutdownResource",
    "StartupModelMetadataRefreshResource",
    "StartupResourceRegistry",
    "create_startup_resource_registry",
]

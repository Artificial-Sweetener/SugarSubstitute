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

"""Preload restored workspace image file bytes outside visible startup."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from substitute.application.execution import (
    ExecutionContext,
    TaskHandle,
    TaskIdentity,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.domain.workspace_snapshot import WorkspaceSnapshot
from substitute.app.bootstrap.startup_trace import trace_mark, trace_span
from substitute.shared.logging.logger import get_logger, log_debug, log_info

_LOGGER = get_logger("app.bootstrap.workspace_restore_asset_preload")


@dataclass
class WorkspaceRestoreAssetPreloadHandle:
    """Read restored image bytes in the background for later GUI-thread decode."""

    snapshot: WorkspaceSnapshot
    submitter: TaskSubmitter
    close_submitter: object | None = None

    def __post_init__(self) -> None:
        """Initialize cache and execution state."""

        self._handle: TaskHandle[None] | None = None
        self._scope = TaskScope(
            submitter=self.submitter,
            scope_id=f"workspace_restore_asset_preload_{id(self):x}",
        )
        self._shutdown_requested = False
        self._lock = RLock()
        self._cache: dict[Path, bytes] = {}
        self._failed_paths: set[Path] = set()

    def start(self) -> None:
        """Start preloading once without blocking startup."""

        trace_mark(
            "workspace_restore_asset_preload.start_requested",
            already_started=self._handle is not None,
            shutdown_requested=self._shutdown_requested,
        )
        if self._handle is not None or self._shutdown_requested:
            return
        request: TaskRequest[None] = TaskRequest(
            identity=TaskIdentity(
                request_id=1,
                domain="workspace_restore_asset_preload",
            ),
            context=ExecutionContext(
                operation="workspace_restore_asset_preload",
                reason="startup_restore",
                lane="disk_io_low_priority",
            ),
            work=lambda _token: self._run_preload(),
        )
        self._handle = self._scope.submit(request)

    def shutdown(self) -> None:
        """Release executor resources without blocking application shutdown."""

        trace_mark("workspace_restore_asset_preload.shutdown_requested")
        if self._shutdown_requested:
            return
        self._shutdown_requested = True
        self._scope.close(reason="workspace_restore_asset_preload_shutdown")
        close = getattr(self.close_submitter, "__call__", None)
        if callable(close):
            close()

    def image_bytes(self, path: Path) -> bytes | None:
        """Return preloaded bytes for one path when available."""

        with self._lock:
            payload = self._cache.get(Path(path))
        trace_mark(
            "workspace_restore_asset_preload.lookup",
            path_suffix=Path(path).suffix,
            hit=payload is not None,
        )
        return payload

    def _run_preload(self) -> None:
        """Read each unique restored image path into memory."""

        paths = _restored_image_paths(self.snapshot)
        loaded_count = 0
        failed_count = 0
        trace_mark(
            "workspace_restore_asset_preload.task.start",
            requested_count=len(paths),
        )
        for path in paths:
            if self._shutdown_requested:
                break
            try:
                with trace_span(
                    "workspace_restore_asset_preload.read_path",
                    path_suffix=Path(path).suffix,
                ):
                    payload = Path(path).read_bytes()
            except OSError as error:
                failed_count += 1
                with self._lock:
                    self._failed_paths.add(path)
                log_debug(
                    _LOGGER,
                    "Skipped restore asset preload",
                    path=str(path),
                    error=repr(error),
                )
                continue
            with self._lock:
                self._cache[path] = payload
            loaded_count += 1
            trace_mark(
                "workspace_restore_asset_preload.read_path.loaded",
                path_suffix=Path(path).suffix,
                byte_count=len(payload),
            )
        log_info(
            _LOGGER,
            "Completed workspace restore asset preload",
            requested_count=len(paths),
            loaded_count=loaded_count,
            failed_count=failed_count,
        )
        trace_mark(
            "workspace_restore_asset_preload.task.end",
            requested_count=len(paths),
            loaded_count=loaded_count,
            failed_count=failed_count,
        )


def _restored_image_paths(snapshot: WorkspaceSnapshot) -> tuple[Path, ...]:
    """Return unique input/output image paths referenced by one workspace."""

    paths: dict[Path, None] = {}
    for workflow in snapshot.workflows:
        for input_reference in workflow.input_images:
            paths[Path(input_reference.path)] = None
        for output_reference in workflow.output_images:
            paths[Path(output_reference.path)] = None
    return tuple(paths)


__all__ = ["WorkspaceRestoreAssetPreloadHandle"]

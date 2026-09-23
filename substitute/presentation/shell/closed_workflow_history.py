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

"""Own closed-workflow snapshot retention and permanent resource cleanup."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Protocol, cast
from uuid import uuid4

from substitute.application.workflows import (
    ClosedWorkflowBuffer,
    ClosedWorkflowPushResult,
    ClosedWorkflowRecord,
    ClosedWorkflowSnapshotError,
    ClosedWorkflowSnapshotService,
)
from substitute.domain.workflow import WorkflowState
from substitute.domain.workspace_snapshot import (
    EditorViewportSnapshot,
    InputImageReference,
    InputMaskReference,
    OutputImageReference,
    WorkflowSnapshot,
)
from substitute.presentation.workflows.workflow_tabs_view import (
    workflow_tab_source_text,
)
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("presentation.shell.closed_workflow_history")


class WorkflowSnapshotCaptureProtocol(Protocol):
    """Capture presentation state required for a reopenable workflow snapshot."""

    def workflow_tab_label(self, workflow_id: str) -> str:
        """Return the current workflow tab label."""

    def active_cube_alias(self, workflow_id: str) -> str | None:
        """Return the active cube alias for one workflow."""

    def editor_viewport_snapshot(
        self,
        workflow_id: str,
    ) -> EditorViewportSnapshot | None:
        """Return the workflow editor viewport state."""

    def input_image_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[InputImageReference, ...]:
        """Return persisted input image references."""

    def input_mask_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[InputMaskReference, ...]:
        """Return persisted input mask references."""

    def output_image_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[OutputImageReference, ...]:
        """Return persisted output image references."""


class ClosedWorkflowHistoryView(Protocol):
    """Describe the shell state needed by closed-workflow history."""

    workflow_session_service: object
    workflow_tabbar: object
    input_asset_cleanup: object
    output_canvas_projection_coordinator: object
    session_snapshot_capture_adapter: WorkflowSnapshotCaptureProtocol


class ClosedWorkflowHistory:
    """Retain reopenable workflow snapshots and clean evicted resources."""

    def __init__(
        self,
        view: ClosedWorkflowHistoryView,
        *,
        buffer: ClosedWorkflowBuffer,
        snapshot_service: ClosedWorkflowSnapshotService,
    ) -> None:
        """Store snapshot persistence and cleanup collaborators."""

        self._view = view
        self._buffer = buffer
        self._snapshot_service = snapshot_service

    def buffer_workflow(
        self,
        workflow_id: str,
        ordered_ids: list[str],
    ) -> ClosedWorkflowPushResult | None:
        """Serialize and retain one closing workflow before destructive cleanup."""

        workflow = self._workflow_for_close(workflow_id)
        if workflow is None:
            log_warning(
                _LOGGER,
                "Skipped closed workflow buffering because workflow was missing",
                operation="close_workflow_buffer",
                workflow_id=workflow_id,
            )
            return None
        tab_label = self._workflow_tab_label(workflow_id)
        tab_index = self._workflow_tab_index(workflow_id, ordered_ids)
        snapshot_capture = self._snapshot_capture_adapter()
        try:
            snapshot = WorkflowSnapshot(
                workflow_id=workflow_id,
                tab_label=tab_label,
                workflow=workflow,
                active_cube_alias=(
                    snapshot_capture.active_cube_alias(workflow_id)
                    if snapshot_capture is not None
                    else None
                ),
                input_images=(
                    snapshot_capture.input_image_references(workflow_id, workflow)
                    if snapshot_capture is not None
                    else ()
                ),
                input_masks=(
                    snapshot_capture.input_mask_references(workflow_id, workflow)
                    if snapshot_capture is not None
                    else ()
                ),
                output_images=(
                    snapshot_capture.output_image_references(workflow_id, workflow)
                    if snapshot_capture is not None
                    else ()
                ),
                editor_viewport=(
                    snapshot_capture.editor_viewport_snapshot(workflow_id)
                    if snapshot_capture is not None
                    else None
                ),
            )
            payload = self._snapshot_service.encode(snapshot)
        except (ClosedWorkflowSnapshotError, TypeError, ValueError) as error:
            log_warning(
                _LOGGER,
                "Failed to capture closed workflow snapshot",
                operation="close_workflow_buffer",
                workflow_id=workflow_id,
                tab_label=tab_label,
                tab_index=tab_index,
                error=repr(error),
            )
            return None
        record = ClosedWorkflowRecord(
            close_id=uuid4().hex,
            workflow_id=workflow_id,
            tab_label=tab_label,
            tab_index=tab_index,
            snapshot_payload=payload,
            payload_size_bytes=len(payload),
            closed_at=datetime.now(UTC),
        )
        result = self._buffer.push(record)
        log_info(
            _LOGGER,
            "Closed workflow buffer push completed",
            operation="close_workflow_buffer",
            close_id=record.close_id,
            workflow_id=workflow_id,
            tab_label=tab_label,
            tab_index=tab_index,
            payload_size_bytes=record.payload_size_bytes,
            accepted=result.accepted,
            evicted_count=len(result.evicted_records),
            buffer_total_bytes=self._buffer.total_bytes,
            buffer_budget_bytes=self._buffer.budget_bytes,
        )
        self.sync_reopen_availability()
        return result

    def pop_latest(self) -> ClosedWorkflowRecord | None:
        """Remove and return the most recently closed workflow record."""

        return self._buffer.pop_latest()

    def pop(self, close_id: str) -> ClosedWorkflowRecord | None:
        """Remove and return one identified closed workflow record."""

        return self._buffer.pop(close_id)

    def decode_for_reopen(
        self,
        record: ClosedWorkflowRecord,
    ) -> WorkflowSnapshot | None:
        """Decode one retained snapshot and report corrupt records as unavailable."""

        try:
            return self._snapshot_service.decode(record.snapshot_payload)
        except ClosedWorkflowSnapshotError as error:
            log_warning(
                _LOGGER,
                "Failed to decode closed workflow for reopen",
                operation="reopen_closed_workflow",
                close_id=record.close_id,
                workflow_id=record.workflow_id,
                tab_label=record.tab_label,
                payload_size_bytes=record.payload_size_bytes,
                error=repr(error),
            )
            return None

    def rekey_snapshot(
        self,
        snapshot: WorkflowSnapshot,
        *,
        new_workflow_id: str,
    ) -> WorkflowSnapshot:
        """Rekey a retained snapshot after an open-workflow identity collision."""

        return self._snapshot_service.rekey_snapshot(
            snapshot,
            new_workflow_id=new_workflow_id,
        )

    def cleanup_evicted(self, records: tuple[ClosedWorkflowRecord, ...]) -> None:
        """Finalize resources for closed workflows that are no longer reopenable."""

        for record in records:
            try:
                snapshot = self._snapshot_service.decode(record.snapshot_payload)
            except ClosedWorkflowSnapshotError as error:
                log_warning(
                    _LOGGER,
                    "Failed to decode evicted closed workflow for cleanup",
                    operation="closed_workflow_eviction_cleanup",
                    close_id=record.close_id,
                    workflow_id=record.workflow_id,
                    tab_label=record.tab_label,
                    payload_size_bytes=record.payload_size_bytes,
                    error=repr(error),
                )
                continue
            self.prune_workflow_images(snapshot.workflow_id, snapshot.workflow)

    def prune_workflow_images(self, workflow_id: str, workflow: object) -> None:
        """Prune canvas image records for a workflow no longer reopenable."""

        session = self._view.workflow_session_service
        workflows = getattr(session, "workflows", {})
        input_cleanup = getattr(self._view.input_asset_cleanup, "prune_closed_workflow")
        input_cleanup(workflow, workflows)
        output_cleanup = getattr(
            self._view.output_canvas_projection_coordinator,
            "prune_closed_workflow_images",
        )
        output_cleanup(workflow_id, workflow, workflows)

    def sync_reopen_availability(self) -> None:
        """Project whether a closed workflow is available for reopening."""

        frame_controller = getattr(
            self._view,
            "shell_frame_integration_controller",
            None,
        )
        set_enabled = getattr(
            frame_controller,
            "set_reopen_closed_workflow_enabled",
            None,
        )
        if callable(set_enabled):
            set_enabled(bool(self._buffer.summaries()))

    def _workflow_for_close(self, workflow_id: str) -> WorkflowState | None:
        """Return live workflow state for close-time snapshot capture."""

        session = self._view.workflow_session_service
        get_workflow = getattr(session, "get_workflow", None)
        if callable(get_workflow):
            workflow = get_workflow(workflow_id)
            return workflow if isinstance(workflow, WorkflowState) else None
        workflows = getattr(session, "workflows", {})
        if isinstance(workflows, Mapping):
            workflow = workflows.get(workflow_id)
            return workflow if isinstance(workflow, WorkflowState) else None
        return None

    def _workflow_tab_label(self, workflow_id: str) -> str:
        """Return current tab label with a stable fallback."""

        snapshot_capture = self._snapshot_capture_adapter()
        if snapshot_capture is not None:
            return snapshot_capture.workflow_tab_label(workflow_id)
        item_map = getattr(self._view.workflow_tabbar, "itemMap", {})
        item = item_map.get(workflow_id)
        if item is None:
            return workflow_id
        return workflow_tab_source_text(item)

    def _workflow_tab_index(self, workflow_id: str, ordered_ids: list[str]) -> int:
        """Return current workflow tab index with ordered-id fallback."""

        workflow_tab_index = getattr(
            self._view.workflow_tabbar,
            "workflow_tab_index",
            None,
        )
        if callable(workflow_tab_index):
            index = int(workflow_tab_index(workflow_id))
            if index >= 0:
                return index
        try:
            return ordered_ids.index(workflow_id)
        except ValueError:
            return max(0, len(ordered_ids))

    def _snapshot_capture_adapter(self) -> WorkflowSnapshotCaptureProtocol | None:
        """Return the composed snapshot capture adapter when available."""

        snapshot_capture = getattr(self._view, "session_snapshot_capture_adapter", None)
        if snapshot_capture is None:
            return None
        return cast(WorkflowSnapshotCaptureProtocol, snapshot_capture)


__all__ = ["ClosedWorkflowHistory", "ClosedWorkflowHistoryView"]

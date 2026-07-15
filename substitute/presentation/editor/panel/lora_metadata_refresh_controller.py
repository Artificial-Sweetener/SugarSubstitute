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

"""Coordinate panel and global prompt LoRA metadata refresh."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, Protocol, cast

from PySide6.QtCore import QObject, Slot

from substitute.application.model_metadata import ModelCatalogSnapshot
from substitute.application.prompt_editor import (
    PromptLoraCatalogService,
    PromptLoraCatalogSnapshot,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptAsyncRequest,
    PromptAsyncRequestContext,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptEditorCancellationController,
    PromptEditorCancellationSource,
    PromptEditorExecutor,
    PromptEditorMainThreadDispatcher,
    PromptEditorTaskHandle,
    QtPromptEditorMainThreadDispatcher,
    log_prompt_async_warning,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
)

_LOGGER = get_logger("presentation.editor.panel.lora_metadata_refresh_controller")
_LORA_KIND = "loras"


class EditorPanelLoraMetadataRefreshHost(Protocol):
    """Expose prompt-editor discovery for one editor panel."""

    def findChildren(self, widget_type: type[PromptEditor]) -> list[PromptEditor]:
        """Return child prompt editors matching the requested widget type."""


class PanelLoraMetadataEditorPanel(Protocol):
    """Describe editor-panel LoRA metadata hooks used by the global controller."""

    def mark_lora_metadata_dirty(self) -> None:
        """Mark contained prompt editors as needing LoRA metadata refresh."""

    def refresh_visible_lora_metadata(self) -> int:
        """Refresh currently visible dirty prompt editors and return the count."""


class EditorPanelLoraMetadataRefreshController:
    """Route panel-local LoRA metadata refresh to prompt editor public APIs."""

    def __init__(self, host: EditorPanelLoraMetadataRefreshHost) -> None:
        """Store the editor panel host used for prompt-editor discovery."""

        self._host = host

    def mark_lora_metadata_dirty(self) -> None:
        """Mark prompt editor LoRA metadata dirty without rebuilding projections."""

        for editor in self._prompt_editors():
            editor.mark_lora_metadata_dirty()

    def refresh_visible_lora_metadata(self) -> int:
        """Refresh dirty visible prompt editors that need LoRA metadata."""

        refreshed_count = 0
        for editor in self._prompt_editors():
            if editor.refresh_lora_metadata_if_visible():
                refreshed_count += 1
        return refreshed_count

    def _prompt_editors(self) -> tuple[PromptEditor, ...]:
        """Return prompt editors rendered inside the host panel."""

        return tuple(self._host.findChildren(PromptEditor))


class PanelLoraMetadataRefreshController(QObject):
    """Adapt canonical LoRA model snapshots for prompt-editor rendering."""

    def __init__(
        self,
        *,
        catalog_service: PromptLoraCatalogService,
        editor_panels: Callable[[], Iterable[PanelLoraMetadataEditorPanel]],
        parent: QObject | None = None,
        executor: PromptEditorExecutor | None = None,
        executor_shutdown: Callable[[], None] | None = None,
        dispatcher: PromptEditorMainThreadDispatcher | None = None,
    ) -> None:
        """Store collaborators and prepare stale-safe async refresh state."""

        super().__init__(parent)
        self._catalog_service = catalog_service
        self._editor_panels = editor_panels
        self._dispatcher = dispatcher or QtPromptEditorMainThreadDispatcher(
            cast(Any, parent)
        )
        if executor is None:
            raise TypeError("executor is required for LoRA metadata refresh.")
        self._executor = executor
        self._executor_shutdown = executor_shutdown
        self._cancellation_controller = PromptEditorCancellationController()
        self._refresh_scheduled = False
        self._refresh_running = False
        self._queued_snapshot: ModelCatalogSnapshot | None = None
        self._running_generation: int | None = None
        self._shutdown_requested = False
        self._active_request_id = 0
        self._active_source: PromptEditorCancellationSource | None = None
        self._active_handle: (
            PromptEditorTaskHandle[PromptLoraCatalogSnapshot] | None
        ) = None
        self._pending_visible_refresh_panels: list[PanelLoraMetadataEditorPanel] = []
        self._visible_refresh_scheduled = False
        if parent is not None:
            parent.destroyed.connect(self.shutdown)

    def request_lora_snapshot_adaptation(
        self,
        snapshot: ModelCatalogSnapshot,
    ) -> None:
        """Adapt one canonical LoRA snapshot and refresh visible editors."""

        if self._shutdown_requested or snapshot.kind != _LORA_KIND:
            return
        self.mark_lora_metadata_dirty()
        if self._refresh_running:
            if snapshot.generation != self._running_generation:
                self._queue_snapshot(snapshot)
            return
        self._queue_snapshot(snapshot)
        if self._refresh_scheduled:
            return
        self._refresh_scheduled = True
        self._dispatcher.publish(
            self._start_scheduled_refresh,
            reason="lora_metadata_start_refresh",
        )

    def mark_lora_metadata_dirty(self) -> None:
        """Mark every known editor panel dirty without rebuilding projections."""

        for panel in tuple(self._editor_panels()):
            panel.mark_lora_metadata_dirty()

    @Slot()
    def shutdown(self) -> None:
        """Stop accepting refresh requests and release owned execution resources."""

        if self._shutdown_requested:
            return
        self._shutdown_requested = True
        self._refresh_scheduled = False
        self._queued_snapshot = None
        self._pending_visible_refresh_panels.clear()
        self._visible_refresh_scheduled = False
        self._refresh_running = False
        self._running_generation = None
        if self._active_source is not None:
            self._active_source.cancel(reason="lora_metadata_shutdown")
        if self._active_handle is not None:
            self._active_handle.cancel(reason="lora_metadata_shutdown")
        self._active_source = None
        self._active_handle = None
        if self._executor_shutdown is not None:
            self._executor_shutdown()

    def _start_scheduled_refresh(self) -> None:
        """Submit one background prompt snapshot adaptation if requested."""

        if self._shutdown_requested:
            self._refresh_scheduled = False
            return
        if self._refresh_running:
            self._refresh_scheduled = False
            return
        snapshot = self._queued_snapshot
        self._queued_snapshot = None
        if snapshot is None:
            self._refresh_scheduled = False
            return
        self._refresh_scheduled = False
        self._refresh_running = True
        self._running_generation = snapshot.generation
        self._active_request_id += 1
        request_id = self._active_request_id
        source = self._cancellation_controller.next_source()
        request = self._build_snapshot_request(
            snapshot=snapshot,
            request_id=request_id,
            cancellation_generation=source.generation,
        )
        handle = self._executor.submit(request, cancellation=source)
        self._active_source = source
        self._active_handle = handle
        handle.add_done_callback(
            self._deliver_completed_refresh,
            reason="lora_metadata_refresh_completed",
        )
        log_debug(
            _LOGGER,
            "Started LoRA prompt snapshot adaptation task",
            request_id=request_id,
            model_generation=snapshot.generation,
        )

    def _build_snapshot_request(
        self,
        *,
        snapshot: ModelCatalogSnapshot,
        request_id: int,
        cancellation_generation: int,
    ) -> PromptAsyncRequest[PromptLoraCatalogSnapshot]:
        """Build one prompt-safe async request for LoRA snapshot adaptation."""

        return PromptAsyncRequest(
            identity=PromptAsyncResultIdentity(
                request_id=request_id,
                query_identity=(_LORA_KIND, snapshot.generation),
                cancellation_generation=cancellation_generation,
            ),
            context=PromptAsyncRequestContext(
                operation="lora_metadata_snapshot_adaptation",
                reason="model_catalog_snapshot",
                safe_fields=(
                    ("model_generation", snapshot.generation),
                    ("model_count", len(snapshot.items)),
                ),
            ),
            work=lambda _token: self._catalog_service.prepare_snapshot_from_models(
                snapshot.items,
                model_generation=snapshot.generation,
            ),
        )

    def _deliver_completed_refresh(
        self,
        outcome: PromptAsyncTaskOutcome[PromptLoraCatalogSnapshot],
    ) -> None:
        """Install a completed snapshot and refresh visible dirty editors."""

        request_id = outcome.identity.request_id
        if request_id != self._active_request_id or self._shutdown_requested:
            return
        self._refresh_running = False
        self._active_source = None
        self._active_handle = None
        running_generation = self._running_generation
        self._running_generation = None
        if outcome.cancelled:
            self._start_followup_refresh_if_requested()
            return
        if outcome.error is not None:
            log_prompt_async_warning(
                _LOGGER,
                "LoRA prompt snapshot adaptation task failed",
                error=outcome.error,
                operation="lora_metadata_snapshot_adaptation",
                reason="model_catalog_snapshot",
                request_id=request_id,
            )
            self._start_followup_refresh_if_requested()
            return
        prompt_snapshot = outcome.result
        if prompt_snapshot is None:
            self._start_followup_refresh_if_requested()
            return
        if self._queued_snapshot_is_newer_than(prompt_snapshot.model_generation):
            self._start_followup_refresh_if_requested()
            return
        if running_generation is not None and (
            prompt_snapshot.model_generation != running_generation
        ):
            self._start_followup_refresh_if_requested()
            return
        self._catalog_service.install_snapshot(prompt_snapshot)
        refreshed_count = self._schedule_visible_lora_metadata_refresh()
        log_debug(
            _LOGGER,
            "Completed LoRA prompt snapshot adaptation",
            request_id=request_id,
            catalog_revision=self._catalog_service.cache_revision,
            model_generation=prompt_snapshot.model_generation,
            visible_editors_refreshed=refreshed_count,
        )
        self._start_followup_refresh_if_requested()

    def _schedule_visible_lora_metadata_refresh(self) -> int:
        """Schedule bounded visible prompt-editor metadata refresh batches."""

        panels = list(self._editor_panels())
        if not panels:
            return 0
        self._pending_visible_refresh_panels.extend(panels)
        if not self._visible_refresh_scheduled:
            self._visible_refresh_scheduled = True
            self._dispatcher.publish(
                self._refresh_next_visible_lora_metadata_batch,
                reason="lora_metadata_visible_refresh",
            )
        return len(panels)

    def _refresh_next_visible_lora_metadata_batch(self) -> None:
        """Refresh a small batch of visible prompt editors from the GUI event loop."""

        self._visible_refresh_scheduled = False
        if self._shutdown_requested:
            self._pending_visible_refresh_panels.clear()
            return
        if not self._pending_visible_refresh_panels:
            return
        panel = self._pending_visible_refresh_panels.pop(0)
        refreshed_count = panel.refresh_visible_lora_metadata()
        log_debug(
            _LOGGER,
            "Refreshed visible LoRA prompt metadata batch",
            visible_editors_refreshed=refreshed_count,
            remaining_panel_count=len(self._pending_visible_refresh_panels),
        )
        if self._pending_visible_refresh_panels:
            self._visible_refresh_scheduled = True
            self._dispatcher.publish(
                self._refresh_next_visible_lora_metadata_batch,
                reason="lora_metadata_visible_refresh",
            )

    def _start_followup_refresh_if_requested(self) -> None:
        """Start a new adaptation when a newer canonical snapshot is queued."""

        if self._queued_snapshot is None or self._shutdown_requested:
            return
        self._refresh_scheduled = True
        self._dispatcher.publish(
            self._start_scheduled_refresh,
            reason="lora_metadata_followup_refresh",
        )

    def _queue_snapshot(self, snapshot: ModelCatalogSnapshot) -> None:
        """Store the newest canonical LoRA snapshot requested for adaptation."""

        if snapshot.kind != _LORA_KIND:
            return
        queued = self._queued_snapshot
        if queued is None or snapshot.generation >= queued.generation:
            self._queued_snapshot = snapshot

    def _queued_snapshot_is_newer_than(self, generation: int) -> bool:
        """Return whether a newer canonical snapshot is waiting to adapt."""

        queued = self._queued_snapshot
        return queued is not None and queued.generation > generation


__all__ = [
    "EditorPanelLoraMetadataRefreshController",
    "EditorPanelLoraMetadataRefreshHost",
    "PanelLoraMetadataEditorPanel",
    "PanelLoraMetadataRefreshController",
]

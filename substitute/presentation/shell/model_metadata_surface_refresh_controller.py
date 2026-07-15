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

"""Refresh editor surfaces after model metadata changes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QTimer

from substitute.application.execution import TaskSubmitter
from substitute.application.model_metadata import (
    ModelCatalogSnapshot,
    ModelMetadataRefreshEvent,
)
from substitute.presentation.shell.model_catalog_snapshot_refresh_coordinator import (
    ModelCatalogSnapshotRefreshCoordinator,
)
from substitute.shared.logging.logger import get_logger, log_debug
from substitute.shared.startup_trace import trace_mark, trace_span

_LOGGER = get_logger("presentation.shell.model_metadata_surface_refresh_controller")
_INITIAL_LORA_MODEL_CATALOG_REFRESH_RETRY_DELAYS_MS = (2_000, 7_000, 20_000)


class ModelMetadataSurfaceRefreshController:
    """Coordinate model metadata refreshes for editor and prompt surfaces."""

    def __init__(
        self,
        shell: Any,
        *,
        parent: QObject | None = None,
        retry_delays_ms: tuple[
            int, ...
        ] = _INITIAL_LORA_MODEL_CATALOG_REFRESH_RETRY_DELAYS_MS,
        snapshot_refresh_submitter: TaskSubmitter,
        close_snapshot_refresh_submitter: Callable[[], None] | None = None,
    ) -> None:
        """Create LoRA snapshot refresh state for one shell."""

        self._shell = shell
        self._initial_lora_refresh_requested = False
        self._initial_lora_refresh_retry_attempt = 0
        self._retry_delays_ms = retry_delays_ms
        self.lora_refresh_coordinator = ModelCatalogSnapshotRefreshCoordinator(
            model_catalog=shell.model_catalog_service,
            completed=self.handle_lora_model_catalog_snapshot_refreshed,
            parent=parent,
            submitter=snapshot_refresh_submitter,
            close_submitter=close_snapshot_refresh_submitter,
        )

    def request_initial_lora_model_catalog_refresh(self, reason: str) -> None:
        """Request one startup LoRA metadata pass after prompt editors exist."""

        if self._initial_lora_refresh_requested:
            return
        self._initial_lora_refresh_requested = True
        self.lora_refresh_coordinator.request_refresh("loras", reason)
        self._schedule_initial_lora_model_catalog_refresh_retry_if_needed()
        trace_mark(
            "main_window.initial_lora_model_catalog_refresh.requested",
            reason=reason,
        )

    def handle_model_metadata_updated(self, event: object) -> None:
        """Invalidate cached catalogs and refresh model-backed editor surfaces."""

        trace_mark(
            "main_window.model_metadata_updated.start",
            event_type=type(event).__name__,
        )
        if not isinstance(event, ModelMetadataRefreshEvent):
            trace_mark(
                "main_window.model_metadata_updated.skip",
                reason="invalid_event",
            )
            return
        with trace_span(
            "main_window.model_metadata_updated.handle",
            kind=event.kind,
            thumbnail_updated=event.thumbnail_updated,
            editor_panel_count=len(self._shell.editor_panels),
        ):
            thumbnail_caches_cleared = 0
            if event.kind == "loras":
                self.lora_refresh_coordinator.request_refresh(
                    "loras",
                    event,
                )
                model_surfaces_refreshed = 0
            else:
                self._shell.model_catalog_service.invalidate(event.kind)
                invalidate_rich_choices = getattr(
                    getattr(self._shell, "model_choice_resolver", None),
                    "invalidate",
                    None,
                )
                if callable(invalidate_rich_choices):
                    invalidate_rich_choices(event.kind)
                thumbnail_caches_cleared = self._clear_thumbnail_caches_for_event(event)
                model_surfaces_refreshed = 0
                for editor_panel in self._shell.editor_panels.values():
                    model_surfaces_refreshed += (
                        editor_panel.refresh_model_metadata_for_event(event)
                    )
        trace_mark(
            "main_window.model_metadata_updated.end",
            kind=event.kind,
            model_surfaces_refreshed=model_surfaces_refreshed,
            lora_refresh_requested=event.kind == "loras",
            thumbnail_caches_cleared=thumbnail_caches_cleared,
        )
        log_debug(
            _LOGGER,
            "Handled live model metadata update",
            kind=event.kind,
            value=event.value,
            thumbnail_updated=event.thumbnail_updated,
            model_surfaces_refreshed=model_surfaces_refreshed,
            lora_refresh_requested=event.kind == "loras",
            thumbnail_caches_cleared=thumbnail_caches_cleared,
        )

    def handle_lora_model_catalog_snapshot_refreshed(
        self,
        snapshot: ModelCatalogSnapshot,
        context: object | None,
    ) -> None:
        """Fan out one canonical LoRA model snapshot to model and prompt surfaces."""

        if snapshot.kind != "loras":
            return
        invalidate_rich_choices = getattr(
            getattr(self._shell, "model_choice_resolver", None),
            "invalidate",
            None,
        )
        if callable(invalidate_rich_choices):
            invalidate_rich_choices(snapshot.kind)
        event = context if isinstance(context, ModelMetadataRefreshEvent) else None
        thumbnail_caches_cleared = (
            self._clear_thumbnail_caches_for_event(event) if event is not None else 0
        )
        self._shell._lora_metadata_refresh_coordinator.request_lora_snapshot_adaptation(
            snapshot
        )
        if event is None:
            return
        model_surfaces_refreshed = 0
        for editor_panel in self._shell.editor_panels.values():
            model_surfaces_refreshed += editor_panel.refresh_model_metadata_for_event(
                event
            )
        trace_mark(
            "main_window.lora_model_catalog_snapshot_refreshed",
            kind=snapshot.kind,
            generation=snapshot.generation,
            model_surfaces_refreshed=model_surfaces_refreshed,
            thumbnail_caches_cleared=thumbnail_caches_cleared,
        )

    def _clear_thumbnail_caches_for_event(
        self,
        event: ModelMetadataRefreshEvent,
    ) -> int:
        """Clear rendered thumbnail caches affected by one image update event."""

        if not event.thumbnail_updated:
            return 0
        cleared_count = 0
        for panel_key, editor_panel in self._shell.editor_panels.items():
            clear_model_caches = getattr(
                editor_panel,
                "clear_model_thumbnail_caches_for_event",
                None,
            )
            if callable(clear_model_caches):
                panel_cleared = clear_model_caches(event)
                cleared_count += panel_cleared
            if event.kind != "loras":
                continue
            clear_lora_caches = getattr(
                editor_panel,
                "clear_lora_thumbnail_caches",
                None,
            )
            if callable(clear_lora_caches):
                panel_cleared = clear_lora_caches()
                cleared_count += panel_cleared
        return cleared_count

    def _schedule_initial_lora_model_catalog_refresh_retry_if_needed(self) -> None:
        """Retry startup LoRA refresh while only bootstrap metadata is available."""

        if not self._lora_catalog_needs_authoritative_startup_refresh():
            return
        attempt = self._initial_lora_refresh_retry_attempt
        if attempt >= len(self._retry_delays_ms):
            return
        delay_ms = self._retry_delays_ms[attempt]
        self._initial_lora_refresh_retry_attempt = attempt + 1
        retry_reason = f"initial_lora_model_catalog_retry_{attempt + 1}"
        QTimer.singleShot(
            delay_ms,
            lambda reason=retry_reason: self._retry_initial_lora_model_catalog_refresh(
                reason
            ),
        )
        trace_mark(
            "main_window.initial_lora_model_catalog_refresh.retry_scheduled",
            reason=retry_reason,
            delay_ms=delay_ms,
        )

    def _retry_initial_lora_model_catalog_refresh(self, reason: str) -> None:
        """Request another startup LoRA refresh if backend has not hydrated metadata."""

        if not self._lora_catalog_needs_authoritative_startup_refresh():
            return
        self.lora_refresh_coordinator.request_refresh("loras", reason)
        self._schedule_initial_lora_model_catalog_refresh_retry_if_needed()
        trace_mark(
            "main_window.initial_lora_model_catalog_refresh.retry_requested",
            reason=reason,
        )

    def _lora_catalog_needs_authoritative_startup_refresh(self) -> bool:
        """Return whether the prompt LoRA catalog still needs backend authority."""

        catalog = getattr(self._shell, "prompt_lora_catalog_service", None)
        can_report_absence = getattr(catalog, "can_report_lora_absence", None)
        if not callable(can_report_absence):
            return False
        try:
            return not bool(can_report_absence())
        except (RuntimeError, TypeError, ValueError):
            _LOGGER.warning(
                "Failed to inspect LoRA catalog authority for startup retry",
                exc_info=True,
            )
            return True


__all__ = [
    "ModelMetadataSurfaceRefreshController",
]

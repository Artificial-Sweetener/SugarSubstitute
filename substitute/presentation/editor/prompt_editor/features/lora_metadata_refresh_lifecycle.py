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

"""Own bounded LoRA metadata refresh scheduling and dirty lifecycle state."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.presentation.editor.prompt_editor.async_work import (
    PromptEditorMainThreadDispatcher,
)
from substitute.shared.logging.logger import get_logger, log_warning_exception

from .lora_metadata_presentation import PromptLoraMetadataPresentation
from .lora_picker_snapshots import PromptLoraPickerRefreshResult

_LOGGER = get_logger("presentation.editor.prompt_editor.features.lora_metadata_refresh")


@dataclass(frozen=True, slots=True)
class PromptLoraMetadataRefreshBindings:
    """Declare the mounted state and render operations used by refresh work."""

    is_visible: Callable[[], bool]
    has_lora_spans: Callable[[], bool]
    refresh_render_metadata: Callable[[str], bool]


class PromptLoraMetadataRefreshLifecycle:
    """Own dirty state and latest-one refresh publication for LoRA metadata."""

    def __init__(
        self,
        *,
        bindings: PromptLoraMetadataRefreshBindings,
        presentation: PromptLoraMetadataPresentation,
        dispatcher: PromptEditorMainThreadDispatcher,
    ) -> None:
        """Bind one lifecycle to its render host and prepared presentation owner."""

        self._bindings = bindings
        self._presentation = presentation
        self._dispatcher = dispatcher
        self._dirty = False
        self._refresh_pending = False
        self._catchup_pending = False

    @property
    def dirty(self) -> bool:
        """Return whether catalog-backed LoRA metadata remains stale."""

        return self._dirty

    def mark_dirty(self) -> None:
        """Mark prepared metadata stale without scheduling immediate render work."""

        self._dirty = True
        self._presentation.mark_picker_dirty()
        self._publish(stale=True)

    def refresh_if_visible(self) -> bool:
        """Refresh dirty metadata only while its editor remains visible."""

        if not self._dirty or not self._bindings.is_visible():
            return False
        picker_refreshed = False
        try:
            picker_refreshed = self._presentation.refresh_picker_from_cache()
            if not self._bindings.has_lora_spans():
                self._dirty = False
                self._publish(stale=False)
                return picker_refreshed
            projection_refreshed = self.schedule_render_metadata_refresh(
                reason="lora_metadata"
            )
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            self._dirty = True
            self._publish(stale=True, unavailable_reason="refresh_failed")
            log_warning_exception(
                _LOGGER,
                "LoRA metadata refresh failed; leaving metadata dirty",
                error=error,
                picker_refreshed=picker_refreshed,
            )
            return picker_refreshed
        if self._refresh_pending:
            self._dirty = not projection_refreshed
        self._publish(stale=self._dirty)
        return projection_refreshed or picker_refreshed

    def refresh_after_catalog_update(self) -> bool:
        """Queue one visible render refresh after catalog rows change."""

        self._dirty = True
        self._presentation.refresh_picker_from_cache()
        self._publish(stale=True)
        if not self._bindings.is_visible():
            return False
        if not self._bindings.has_lora_spans():
            self._dirty = False
            self._publish(stale=False)
            return False
        projection_refreshed = self.schedule_render_metadata_refresh(
            reason="lora_metadata"
        )
        if self._refresh_pending:
            self._dirty = not projection_refreshed
        self._publish(stale=self._dirty)
        return projection_refreshed

    def schedule_catchup_if_needed(self) -> None:
        """Queue at most one deferred refresh for currently stale metadata."""

        if not self._dirty or self._catchup_pending:
            return
        self._catchup_pending = True
        self._dispatcher.publish(
            self._run_catchup,
            reason="lora_metadata_catchup",
        )

    def schedule_render_metadata_refresh(self, *, reason: str) -> bool:
        """Queue at most one render refresh on the main-thread dispatcher."""

        if self._refresh_pending:
            return True
        self._refresh_pending = True
        self._dispatcher.publish(
            lambda: self._flush_render_metadata_refresh(reason=reason),
            reason="lora_render_metadata_refresh",
        )
        return True

    def refresh_lora_picker_snapshot_now(
        self,
        *,
        reason: str,
    ) -> PromptLoraPickerRefreshResult:
        """Refresh picker rows and propagate catalog-revision consequences."""

        try:
            result = self._presentation.refresh_picker_now()
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            snapshot = self._presentation.record_picker_refresh_failure()
            self._dirty = True
            self._publish(
                stale=snapshot.identity.stale,
                unavailable_reason=snapshot.status.unavailable_reason,
            )
            log_warning_exception(
                _LOGGER,
                "Failed to refresh LoRA catalog rows for prompt picker",
                error=error,
                reason=reason,
            )
            return PromptLoraPickerRefreshResult(
                snapshot=snapshot,
                rows_changed=False,
                revision_changed=False,
            )
        self._publish(stale=self._dirty)
        if result.revision_changed:
            self.refresh_after_catalog_update()
        return result

    def _run_catchup(self) -> None:
        """Run one queued visible-editor metadata catchup."""

        self._catchup_pending = False
        self.refresh_if_visible()

    def _flush_render_metadata_refresh(self, *, reason: str) -> None:
        """Apply the queued render refresh only when the editor is visible."""

        self._refresh_pending = False
        if not self._bindings.is_visible():
            self._dirty = True
            self._publish(stale=True)
            return
        try:
            refreshed = self._bindings.refresh_render_metadata(reason)
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            self._dirty = True
            self._publish(stale=True, unavailable_reason="refresh_failed")
            log_warning_exception(
                _LOGGER,
                "LoRA render metadata refresh failed; leaving metadata dirty",
                error=error,
            )
            return
        self._dirty = not refreshed
        self._publish(stale=self._dirty)

    def _publish(
        self,
        *,
        stale: bool,
        unavailable_reason: str | None = None,
    ) -> None:
        """Publish current lifecycle state through the sole presentation owner."""

        self._presentation.publish(
            dirty=self._dirty,
            stale=stale,
            unavailable_reason=unavailable_reason,
        )


__all__ = [
    "PromptLoraMetadataRefreshBindings",
    "PromptLoraMetadataRefreshLifecycle",
]

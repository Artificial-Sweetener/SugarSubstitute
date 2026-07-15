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

"""Own prompt-editor LoRA metadata refresh, picker state, and action snapshots."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass
from functools import partial
from typing import Any, Protocol, cast

from substitute.application.prompt_editor import (
    PromptLoraCatalogItem,
    PromptLoraCatalogLookup,
    PromptLoraScheduleService,
    PromptScheduledLoraService,
)
from substitute.presentation.widgets.media_wall import MediaThumbnailReadiness
from substitute.shared.logging.logger import (
    get_logger,
    log_warning_exception,
)

from ..async_work import (
    PromptEditorMainThreadDispatcher,
    QtPromptEditorMainThreadDispatcher,
)
from ..commands import PromptCommandSourceIdentity, PromptFeatureSnapshotIdentity
from .catalog_snapshots import CatalogSnapshotIdentity, CatalogSnapshotStatus
from .feature_profile_controller import PromptFeatureProfileController
from .lora_context_menu import (
    PromptLoraContextActionController,
    PromptLoraModelPageAction,
    PromptLoraTokenContext,
)
from .lora_picker_snapshots import (
    PromptLoraPickerRefreshResult,
    PromptLoraPickerSnapshot,
    PromptLoraPickerSnapshotController,
)

_LOGGER = get_logger("presentation.editor.prompt_editor.features.lora_metadata")


class PromptLoraMetadataHost(Protocol):
    """Describe editor hooks needed by the LoRA feature controller."""

    def toPlainText(self) -> str:
        """Return the current raw prompt source."""

    def isVisible(self) -> bool:  # noqa: N802
        """Return whether this editor is currently visible."""

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity | None:
        """Return current source identity for prepared feature snapshots."""

    def has_lora_spans_for_metadata(self) -> bool:
        """Return whether the current semantic snapshot contains LoRA spans."""

    def refresh_lora_render_metadata_now(self, *, reason: str) -> bool:
        """Refresh catalog-backed LoRA render metadata on the GUI thread."""


@dataclass(frozen=True, slots=True)
class PromptLoraMetadataSnapshot:
    """Publish prepared LoRA feature state for foreground consumers."""

    identity: PromptFeatureSnapshotIdentity
    catalog_revision: object | None
    picker_items: tuple[PromptLoraCatalogItem, ...]
    picker_status: CatalogSnapshotStatus
    thumbnail_readiness: tuple[MediaThumbnailReadiness, ...]
    dirty: bool
    stale: bool
    action_ready: bool
    unavailable_reason: str | None = None


class PromptLoraMetadataFeatureController:
    """Coordinate LoRA metadata state and prepared menu/picker actions."""

    def __init__(
        self,
        *,
        host: PromptLoraMetadataHost,
        feature_profile: PromptFeatureProfileController,
        lora_catalog: PromptLoraCatalogLookup | None,
        lora_schedule_service: PromptLoraScheduleService,
        scheduled_lora_service: PromptScheduledLoraService,
        thumbnail_repository_available: bool = False,
        parent: object | None = None,
        main_thread_dispatcher: PromptEditorMainThreadDispatcher | None = None,
    ) -> None:
        """Store LoRA feature collaborators without touching slow catalog state."""

        self._host = host
        self._feature_profile = feature_profile
        self._lora_catalog = lora_catalog
        self._lora_schedule_service = lora_schedule_service
        self._scheduled_lora_service = scheduled_lora_service
        self._context_actions = PromptLoraContextActionController(
            scheduled_lora_service=scheduled_lora_service,
        )
        self._dispatcher = main_thread_dispatcher or QtPromptEditorMainThreadDispatcher(
            cast(Any, parent)
        )
        self._dirty = False
        self._refresh_pending = False
        self._catchup_pending = False
        self._picker_snapshots = PromptLoraPickerSnapshotController(
            lora_catalog=lora_catalog,
            picker_enabled=lambda: self._feature_profile.lora_picker_enabled,
            identity_provider=partial(
                prompt_lora_picker_snapshot_identity,
                host=self._host,
                feature_profile=self._feature_profile,
            ),
            thumbnail_repository_available=lambda: thumbnail_repository_available,
        )
        self._publish_snapshot(stale=False)

    @property
    def snapshot(self) -> PromptLoraMetadataSnapshot:
        """Return the latest prepared LoRA metadata snapshot."""

        return self._snapshot

    @property
    def dirty(self) -> bool:
        """Return whether catalog-backed LoRA metadata is marked stale."""

        return self._dirty

    @property
    def lora_picker_ready(self) -> bool:
        """Return whether the foreground may offer the LoRA picker action."""

        return self._picker_snapshots.picker_available

    @property
    def lora_picker_snapshot(self) -> PromptLoraPickerSnapshot:
        """Return the latest foreground-safe LoRA picker snapshot."""

        return self._picker_snapshots.snapshot

    def mark_dirty(self) -> None:
        """Mark catalog-backed LoRA metadata as stale for this editor."""

        self._dirty = True
        self._picker_snapshots.mark_dirty()
        self._publish_snapshot(stale=True)

    def refresh_if_visible(self) -> bool:
        """Refresh dirty LoRA metadata when this editor is visible."""

        if not self._dirty or not self._host.isVisible():
            return False
        picker_refreshed = False
        try:
            picker_refreshed = self.refresh_visible_picker_data()
            if not self._host.has_lora_spans_for_metadata():
                self._dirty = False
                self._publish_snapshot(stale=False)
                return picker_refreshed
            projection_refreshed = self.schedule_render_metadata_refresh(
                reason="lora_metadata"
            )
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            self._dirty = True
            self._publish_snapshot(stale=True, unavailable_reason="refresh_failed")
            log_warning_exception(
                _LOGGER,
                "LoRA metadata refresh failed; leaving metadata dirty",
                error=error,
                picker_refreshed=picker_refreshed,
            )
            return picker_refreshed
        if self._refresh_pending:
            self._dirty = not projection_refreshed
        self._publish_snapshot(stale=self._dirty)
        return projection_refreshed or picker_refreshed

    def refresh_after_catalog_update(self) -> bool:
        """Queue a render metadata refresh after catalog rows change."""

        self._dirty = True
        self._picker_snapshots.refresh_from_cache()
        self._publish_snapshot(stale=True)
        if not self._host.isVisible():
            return False
        if not self._host.has_lora_spans_for_metadata():
            self._dirty = False
            self._publish_snapshot(stale=False)
            return False
        projection_refreshed = self.schedule_render_metadata_refresh(
            reason="lora_metadata"
        )
        if self._refresh_pending:
            self._dirty = not projection_refreshed
        self._publish_snapshot(stale=self._dirty)
        return projection_refreshed

    def schedule_catchup_if_needed(self) -> None:
        """Queue a visible-editor metadata catchup through the async boundary."""

        if not self._dirty or self._catchup_pending:
            return
        self._catchup_pending = True
        self._dispatcher.publish(
            self._run_catchup,
            reason="lora_metadata_catchup",
        )

    def schedule_render_metadata_refresh(self, *, reason: str) -> bool:
        """Coalesce LoRA render metadata refresh publication on the GUI thread."""

        if self._refresh_pending:
            return True
        self._refresh_pending = True
        self._dispatcher.publish(
            lambda: self._flush_render_metadata_refresh(reason=reason),
            reason="lora_render_metadata_refresh",
        )
        return True

    def refresh_visible_picker_data(self) -> bool:
        """Prepare current picker rows when a visible picker asks for refresh data."""

        refreshed = self._picker_snapshots.refresh_from_cache()
        self._publish_snapshot(stale=self._dirty)
        return refreshed

    def refresh_lora_picker_snapshot_now(
        self,
        *,
        reason: str,
    ) -> PromptLoraPickerRefreshResult:
        """Explicitly refresh LoRA picker rows outside popup-open paths."""

        _ = reason
        try:
            result = self._picker_snapshots.refresh_now()
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            snapshot = self._picker_snapshots.record_refresh_failure()
            self._dirty = True
            self._publish_snapshot(
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
        self._publish_snapshot(stale=self._dirty)
        if result.revision_changed:
            self.refresh_after_catalog_update()
        return result

    def schedule_text_for_lora(self, selected_lora: PromptLoraCatalogItem) -> str:
        """Return the source schedule text for a selected LoRA catalog item."""

        return self._lora_schedule_service.schedule_text(selected_lora)

    def model_page_action_for_token(
        self,
        token_context: PromptLoraTokenContext,
    ) -> PromptLoraModelPageAction | None:
        """Return a prepared model-page action for one inline LoRA token."""

        if not self._feature_profile.lora_syntax_enabled:
            return None
        catalog_identity = CatalogSnapshotIdentity(
            source_revision=self._snapshot_identity(stale=False).source_revision,
            feature_profile_id=self._feature_profile.identity.feature_profile_id,
            catalog_revision=self._picker_snapshots.snapshot.catalog_revision,
            request_identity=(
                "lora_model_page",
                token_context.backend_value,
                token_context.model_page_url,
            ),
            query_identity=("lora_model_page", token_context.backend_value),
        )
        return self._context_actions.model_page_action_for_token(
            token_context,
            identity=PromptFeatureSnapshotIdentity(
                source_revision=catalog_identity.source_revision,
                feature_profile_id=catalog_identity.feature_profile_id,
                catalog_revision=catalog_identity.catalog_revision,
                query_identity=(
                    "lora_model_page",
                    catalog_identity.catalog_revision,
                    catalog_identity.request_identity,
                ),
            ),
            snapshot_identity=catalog_identity,
        )

    def _run_catchup(self) -> None:
        """Run a queued visible-editor metadata catchup."""

        self._catchup_pending = False
        self.refresh_if_visible()

    def _flush_render_metadata_refresh(self, *, reason: str) -> None:
        """Publish a coalesced render metadata refresh if still applicable."""

        self._refresh_pending = False
        if not self._host.isVisible():
            self._dirty = True
            self._publish_snapshot(stale=True)
            return
        try:
            refreshed = self._host.refresh_lora_render_metadata_now(reason=reason)
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            self._dirty = True
            self._publish_snapshot(stale=True, unavailable_reason="refresh_failed")
            log_warning_exception(
                _LOGGER,
                "LoRA render metadata refresh failed; leaving metadata dirty",
                error=error,
            )
            return
        self._dirty = not refreshed
        self._publish_snapshot(stale=self._dirty)

    def _snapshot_identity(self, *, stale: bool) -> PromptFeatureSnapshotIdentity:
        """Return the current source/profile identity for LoRA snapshots."""

        source_identity = self._host.prompt_command_source_identity()
        return PromptFeatureSnapshotIdentity(
            source_revision=(
                None if source_identity is None else source_identity.source_revision
            ),
            feature_profile_id=self._feature_profile.identity.feature_profile_id,
            stale=stale,
        )

    def _publish_snapshot(
        self,
        *,
        stale: bool,
        unavailable_reason: str | None = None,
    ) -> None:
        """Store the latest prepared LoRA metadata snapshot."""

        catalog_revision = self._picker_snapshots.snapshot.catalog_revision
        self._snapshot = PromptLoraMetadataSnapshot(
            identity=self._snapshot_identity(stale=stale),
            catalog_revision=catalog_revision,
            picker_items=self._picker_snapshots.snapshot.items,
            picker_status=self._picker_snapshots.snapshot.status,
            thumbnail_readiness=self._picker_snapshots.snapshot.thumbnail_readiness,
            dirty=self._dirty,
            stale=stale,
            action_ready=self._feature_profile.lora_trigger_words_enabled
            or self._feature_profile.lora_picker_enabled,
            unavailable_reason=unavailable_reason,
        )


def prompt_lora_picker_snapshot_identity(
    *,
    host: PromptLoraMetadataHost,
    feature_profile: PromptFeatureProfileController,
    catalog_revision: Hashable | None,
    stale: bool,
    unavailable_reason: str | None,
) -> CatalogSnapshotIdentity:
    """Return catalog freshness identity for LoRA picker snapshots."""

    source_identity = host.prompt_command_source_identity()
    return CatalogSnapshotIdentity(
        source_revision=(
            None if source_identity is None else source_identity.source_revision
        ),
        feature_profile_id=feature_profile.identity.feature_profile_id,
        catalog_revision=catalog_revision,
        stale=stale,
        unavailable_reason=unavailable_reason,
    )


__all__ = [
    "PromptLoraMetadataFeatureController",
    "PromptLoraMetadataHost",
    "PromptLoraMetadataSnapshot",
]

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

"""Own prepared LoRA metadata, picker, and model-page presentation state."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass
from functools import partial
from typing import Protocol

from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
    PromptLoraCatalogLookup,
)
from substitute.application.prompt_editor.lora.schedule import PromptLoraScheduleService
from substitute.application.prompt_editor.lora.scheduled import (
    PromptScheduledLoraService,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)
from substitute.presentation.widgets.media_wall import MediaThumbnailReadiness

from ..commands.feature_commands import PromptFeatureSnapshotIdentity
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


class PromptLoraMetadataIdentityPort(Protocol):
    """Expose source identity required by prepared LoRA metadata."""

    def prompt_command_source_identity(self) -> PromptSourceIdentity | None:
        """Return the source identity used by prepared feature snapshots."""


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


class PromptLoraMetadataPresentation:
    """Own foreground-safe LoRA picker, metadata, and model-page state."""

    def __init__(
        self,
        *,
        identity_port: PromptLoraMetadataIdentityPort,
        feature_profile: PromptFeatureProfileController,
        lora_catalog: PromptLoraCatalogLookup | None,
        lora_schedule_service: PromptLoraScheduleService,
        scheduled_lora_service: PromptScheduledLoraService,
        thumbnail_repository_available: bool,
    ) -> None:
        """Construct prepared metadata state without dispatcher or render work."""

        self._identity_port = identity_port
        self._feature_profile = feature_profile
        self._lora_schedule_service = lora_schedule_service
        self._context_actions = PromptLoraContextActionController(
            scheduled_lora_service=scheduled_lora_service,
        )
        self._picker_snapshots = PromptLoraPickerSnapshotController(
            lora_catalog=lora_catalog,
            picker_enabled=lambda: self._feature_profile.lora_picker_enabled,
            identity_provider=partial(
                prompt_lora_picker_snapshot_identity,
                identity_port=self._identity_port,
                feature_profile=self._feature_profile,
            ),
            thumbnail_repository_available=lambda: thumbnail_repository_available,
        )
        self.publish(dirty=False, stale=False)

    @property
    def snapshot(self) -> PromptLoraMetadataSnapshot:
        """Return the latest foreground-safe LoRA metadata snapshot."""

        return self._snapshot

    @property
    def lora_picker_ready(self) -> bool:
        """Return whether the foreground may offer the LoRA picker action."""

        return self._picker_snapshots.picker_available

    @property
    def lora_picker_snapshot(self) -> PromptLoraPickerSnapshot:
        """Return the latest foreground-safe LoRA picker snapshot."""

        return self._picker_snapshots.snapshot

    def mark_picker_dirty(self) -> None:
        """Mark prepared picker rows stale without touching the catalog."""

        self._picker_snapshots.mark_dirty()

    def refresh_picker_from_cache(self) -> bool:
        """Refresh prepared picker rows from the catalog cache only."""

        return self._picker_snapshots.refresh_from_cache()

    def refresh_picker_now(self) -> PromptLoraPickerRefreshResult:
        """Run one explicitly requested picker catalog refresh."""

        return self._picker_snapshots.refresh_now()

    def record_picker_refresh_failure(self) -> PromptLoraPickerSnapshot:
        """Preserve stale picker rows after an explicit refresh failure."""

        return self._picker_snapshots.record_refresh_failure()

    def schedule_text_for_lora(self, selected_lora: PromptLoraCatalogItem) -> str:
        """Return scheduler-safe source text for one selected LoRA."""

        return self._lora_schedule_service.schedule_text(selected_lora)

    def model_page_action_for_token(
        self,
        token_context: PromptLoraTokenContext,
    ) -> PromptLoraModelPageAction | None:
        """Return one prepared model-page action for an inline LoRA token."""

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

    def publish(
        self,
        *,
        dirty: bool,
        stale: bool,
        unavailable_reason: str | None = None,
    ) -> None:
        """Publish prepared foreground metadata from current picker state."""

        picker_snapshot = self._picker_snapshots.snapshot
        self._snapshot = PromptLoraMetadataSnapshot(
            identity=self._snapshot_identity(stale=stale),
            catalog_revision=picker_snapshot.catalog_revision,
            picker_items=picker_snapshot.items,
            picker_status=picker_snapshot.status,
            thumbnail_readiness=picker_snapshot.thumbnail_readiness,
            dirty=dirty,
            stale=stale,
            action_ready=self._feature_profile.lora_trigger_words_enabled
            or self._feature_profile.lora_picker_enabled,
            unavailable_reason=unavailable_reason,
        )

    def _snapshot_identity(self, *, stale: bool) -> PromptFeatureSnapshotIdentity:
        """Return the source/profile identity for one prepared metadata snapshot."""

        source_identity = self._identity_port.prompt_command_source_identity()
        return PromptFeatureSnapshotIdentity(
            source_revision=(
                None if source_identity is None else source_identity.source_revision
            ),
            feature_profile_id=self._feature_profile.identity.feature_profile_id,
            stale=stale,
        )


def prompt_lora_picker_snapshot_identity(
    *,
    identity_port: PromptLoraMetadataIdentityPort,
    feature_profile: PromptFeatureProfileController,
    catalog_revision: Hashable | None,
    stale: bool,
    unavailable_reason: str | None,
) -> CatalogSnapshotIdentity:
    """Return catalog freshness identity for LoRA picker snapshots."""

    source_identity = identity_port.prompt_command_source_identity()
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
    "PromptLoraMetadataIdentityPort",
    "PromptLoraMetadataPresentation",
    "PromptLoraMetadataSnapshot",
    "prompt_lora_picker_snapshot_identity",
]

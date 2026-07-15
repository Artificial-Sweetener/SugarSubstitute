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

"""Own prepared prompt context-menu snapshots and freshness identity."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from substitute.shared.logging.logger import get_logger, log_debug
from substitute.presentation.editor.catalog.snapshots import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
)

from ..commands import PromptCommandSourceIdentity
from .danbooru_actions import PromptDanbooruActionSnapshot
from .diagnostics_controller import (
    PromptContextMenuAction,
    PromptDiagnosticMenuActionSnapshot,
    PromptDiagnosticsSnapshot,
)
from ..commands import PromptFeatureSnapshotIdentity
from .lora_action_snapshots import PromptLoraActionSnapshot
from .lora_context_menu import PromptLoraTriggerWordsAction
from .lora_metadata_controller import PromptLoraMetadataSnapshot
from .prompt_segment_preset_models import PromptSegmentPresetSnapshot
from .scene_controller import (
    PromptSceneContextSnapshot,
    PromptScenePositionContext,
    PromptScenePositionContextSnapshot,
)

_LOGGER = get_logger("presentation.editor.prompt_editor.features.context_menu_snapshot")


@dataclass(frozen=True, slots=True)
class PromptContextMenuSnapshotRequest:
    """Describe cheap per-open state used to read a prepared menu snapshot."""

    source_position: int
    selected_text: str
    selection_range: tuple[int, int] | None
    read_only: bool
    rich_prompt_rendering_enabled: bool

    def __post_init__(self) -> None:
        """Reject impossible menu request positions before identity publication."""

        if self.source_position < 0:
            raise ValueError("source_position must be non-negative.")


@dataclass(frozen=True, slots=True)
class PromptContextMenuActionSnapshot:
    """Publish prompt-specific context-menu actions without constructing Qt widgets."""

    source_position: int
    selected_text: str
    scene_context: PromptScenePositionContext
    diagnostic_actions: tuple[PromptContextMenuAction, ...]
    lora_picker_ready: bool
    lora_trigger_word_actions: tuple[PromptLoraTriggerWordsAction, ...]
    segment_snapshot: PromptSegmentPresetSnapshot
    danbooru_snapshot: PromptDanbooruActionSnapshot
    read_only: bool
    rich_prompt_rendering_enabled: bool

    @property
    def queue_scene_key(self) -> str | None:
        """Return the scene key that may be queued from this menu opening."""

        return self.scene_context.queueable_scene_key

    @property
    def effective_prompt_text(self) -> str:
        """Return the scene-aware prompt text used by feature actions."""

        return self.scene_context.effective_prompt_text


@dataclass(frozen=True, slots=True)
class PromptContextMenuSnapshotIdentity:
    """Identify a prepared prompt context-menu snapshot and its dependencies."""

    source_revision: int | None
    source_position: int
    selected_text_identity: tuple[str, int, int]
    selection_range_identity: tuple[int, int] | None
    feature_profile_id: Hashable | None
    cube_context_id: Hashable | None
    scene_context_id: Hashable | None
    scene_snapshot_identity: PromptFeatureSnapshotIdentity | None
    scene_position_snapshot_identity: PromptFeatureSnapshotIdentity | None
    diagnostics_snapshot_identity: PromptFeatureSnapshotIdentity | None
    diagnostic_action_snapshot_identity: PromptFeatureSnapshotIdentity | None
    lora_catalog_revision: Hashable | None
    lora_action_identity: CatalogSnapshotIdentity | None
    prompt_segment_catalog_identity: CatalogSnapshotIdentity
    danbooru_snapshot_identity: PromptFeatureSnapshotIdentity | None
    read_only: bool
    rich_prompt_rendering_enabled: bool

    def __post_init__(self) -> None:
        """Reject impossible identity values before menu code trusts them."""

        if self.source_revision is not None and self.source_revision < 0:
            raise ValueError("source_revision must be non-negative.")
        if self.source_position < 0:
            raise ValueError("source_position must be non-negative.")


class PromptContextMenuConcern(StrEnum):
    """Name independently prepared concerns inside a context-menu snapshot."""

    SCENE = "scene"
    DIAGNOSTICS = "diagnostics"
    LORA = "lora"
    PROMPT_SEGMENT = "prompt_segment"
    DANBOORU = "danbooru"
    EDITING_STATE = "editing_state"
    RENDERING_STATE = "rendering_state"


@dataclass(frozen=True, slots=True)
class PromptContextMenuConcernReadiness:
    """Publish readiness for one context-menu concern."""

    concern: PromptContextMenuConcern
    ready: bool
    stale: bool = False
    unavailable_reason: str | None = None
    identity: Hashable | None = None

    def __post_init__(self) -> None:
        """Reject ambiguous concern readiness state."""

        if self.ready and self.unavailable_reason is not None:
            raise ValueError("ready concerns must not carry an unavailable reason.")
        if self.unavailable_reason == "":
            raise ValueError("unavailable_reason must not be blank.")


@dataclass(frozen=True, slots=True)
class PromptContextMenuSnapshotReadiness:
    """Publish per-concern readiness for one context-menu snapshot."""

    concerns: tuple[PromptContextMenuConcernReadiness, ...]

    def concern(
        self,
        concern: PromptContextMenuConcern,
    ) -> PromptContextMenuConcernReadiness:
        """Return readiness for one prepared menu concern."""

        for item in self.concerns:
            if item.concern is concern:
                return item
        raise KeyError(concern)


@dataclass(frozen=True, slots=True)
class PromptContextMenuSnapshot:
    """Publish one identity-bearing prepared context-menu snapshot."""

    identity: PromptContextMenuSnapshotIdentity
    readiness: PromptContextMenuSnapshotReadiness
    actions: PromptContextMenuActionSnapshot


class PromptContextMenuDiagnosticsPort(Protocol):
    """Describe diagnostics data consumed by the context-menu snapshot owner."""

    @property
    def snapshot(self) -> PromptDiagnosticsSnapshot:
        """Return the latest prepared diagnostics snapshot."""

    def prepared_menu_actions_for_source_position(
        self,
        source_position: int,
    ) -> PromptDiagnosticMenuActionSnapshot:
        """Return prepared diagnostic actions for one source position."""


class PromptContextMenuLoraMetadataPort(Protocol):
    """Describe LoRA catalog metadata consumed by context menus."""

    @property
    def snapshot(self) -> PromptLoraMetadataSnapshot:
        """Return the latest prepared LoRA metadata snapshot."""

    @property
    def lora_picker_ready(self) -> bool:
        """Return whether the LoRA picker action may be offered."""


class PromptContextMenuLoraTriggerWordPort(Protocol):
    """Describe trigger-word state consumed by context menus."""

    def snapshot_for_prompt(
        self,
        *,
        prompt_text: str,
    ) -> PromptLoraActionSnapshot:
        """Project LoRA trigger actions from authoritative cached context."""

    def prewarm_prompt(self, prompt_text: str) -> bool:
        """Request context preparation for one effective prompt."""

    def unavailable_snapshot(
        self,
        *,
        unavailable_reason: str,
    ) -> PromptLoraActionSnapshot:
        """Return an unavailable LoRA action snapshot for stale menu context."""


class PromptContextMenuScenePort(Protocol):
    """Describe scene data consumed by the context-menu snapshot owner."""

    @property
    def snapshot(self) -> PromptSceneContextSnapshot:
        """Return the latest prepared scene snapshot."""

    def prepared_position_context(
        self,
        source_position: int,
    ) -> PromptScenePositionContextSnapshot:
        """Return prepared scene context for one source position without computing."""

    def prepare_position_context(
        self,
        source_position: int,
        *,
        reason: str,
    ) -> PromptScenePositionContextSnapshot:
        """Prepare scene context for one source position."""


class PromptContextMenuSegmentPort(Protocol):
    """Describe prompt-segment data consumed by the context-menu snapshot owner."""

    @property
    def snapshot(self) -> PromptSegmentPresetSnapshot:
        """Return the latest prepared prompt-segment snapshot."""

    def prepared_menu_snapshot_for_selection(
        self,
        *,
        selected_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
    ) -> PromptSegmentPresetSnapshot:
        """Return prepared selected-text segment state without deriving it."""

    def prepare_menu_snapshot_for_selection(
        self,
        *,
        selected_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
        reason: str,
    ) -> PromptSegmentPresetSnapshot:
        """Prepare selected-text segment state before menu snapshot reads."""


class PromptContextMenuDanbooruPort(Protocol):
    """Describe Danbooru data consumed by the context-menu snapshot owner."""

    @property
    def snapshot(self) -> PromptDanbooruActionSnapshot:
        """Return the latest prepared Danbooru snapshot."""

    def prepared_menu_snapshot_for_selection(
        self,
        *,
        selection_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
    ) -> PromptDanbooruActionSnapshot:
        """Return prepared selected-text Danbooru state without deriving it."""

    def prepare_menu_snapshot_for_selection(
        self,
        *,
        selection_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
        reason: str,
    ) -> PromptDanbooruActionSnapshot:
        """Prepare selected-text Danbooru state before menu snapshot reads."""


class PromptContextMenuSnapshotController:
    """Own prompt context-menu snapshot identity and concern readiness."""

    def __init__(
        self,
        *,
        diagnostics: PromptContextMenuDiagnosticsPort,
        lora_metadata: PromptContextMenuLoraMetadataPort,
        lora_trigger_words: PromptContextMenuLoraTriggerWordPort,
        scene: PromptContextMenuScenePort,
        segment_presets: PromptContextMenuSegmentPort,
        danbooru: PromptContextMenuDanbooruPort,
        source_identity_provider: Callable[[], PromptCommandSourceIdentity | None],
        feature_profile_id_provider: Callable[[], Hashable | None],
    ) -> None:
        """Store feature snapshot publishers used to build menu snapshots."""

        self._diagnostics = diagnostics
        self._lora_metadata = lora_metadata
        self._lora_trigger_words = lora_trigger_words
        self._scene = scene
        self._segment_presets = segment_presets
        self._danbooru = danbooru
        self._source_identity_provider = source_identity_provider
        self._feature_profile_id_provider = feature_profile_id_provider

    def snapshot_for_menu(
        self,
        request: PromptContextMenuSnapshotRequest,
    ) -> PromptContextMenuSnapshot:
        """Return one identity-bearing prompt context-menu snapshot."""

        scene_snapshot = self._scene.snapshot
        diagnostics_snapshot = self._diagnostics.snapshot
        lora_snapshot = self._lora_metadata.snapshot
        segment_base_snapshot = self._segment_presets.snapshot
        danbooru_base_snapshot = self._danbooru.snapshot
        scene_position_snapshot = self._scene.prepared_position_context(
            request.source_position
        )
        scene_context = _scene_context_from_snapshot(
            request=request,
            snapshot=scene_position_snapshot,
        )
        diagnostic_action_snapshot = (
            self._diagnostics.prepared_menu_actions_for_source_position(
                request.source_position
            )
        )
        if _scene_position_context_ready(scene_position_snapshot):
            lora_action_snapshot = self._lora_trigger_words.snapshot_for_prompt(
                prompt_text=scene_context.effective_prompt_text
            )
        else:
            lora_action_snapshot = self._lora_trigger_words.unavailable_snapshot(
                unavailable_reason=(
                    scene_position_snapshot.unavailable_reason
                    or "scene_position_context_unprepared"
                )
            )
        segment_snapshot = self._segment_presets.prepared_menu_snapshot_for_selection(
            selected_text=request.selected_text,
            selection_range=request.selection_range,
            read_only=request.read_only,
        )
        danbooru_snapshot = self._danbooru.prepared_menu_snapshot_for_selection(
            selection_text=request.selected_text,
            selection_range=request.selection_range,
            read_only=request.read_only,
        )
        actions = PromptContextMenuActionSnapshot(
            source_position=request.source_position,
            selected_text=request.selected_text,
            scene_context=scene_context,
            diagnostic_actions=diagnostic_action_snapshot.actions,
            lora_picker_ready=self._lora_metadata.lora_picker_ready,
            lora_trigger_word_actions=tuple(lora_action_snapshot.trigger_word_actions),
            segment_snapshot=segment_snapshot,
            danbooru_snapshot=danbooru_snapshot,
            read_only=request.read_only,
            rich_prompt_rendering_enabled=request.rich_prompt_rendering_enabled,
        )
        identity = self._snapshot_identity(
            request=request,
            scene_snapshot=scene_snapshot,
            scene_position_snapshot=scene_position_snapshot,
            diagnostics_snapshot=diagnostics_snapshot,
            diagnostic_action_snapshot=diagnostic_action_snapshot,
            lora_snapshot=lora_snapshot,
            lora_action_snapshot=lora_action_snapshot,
            segment_base_snapshot=segment_base_snapshot,
            segment_snapshot=segment_snapshot,
            danbooru_base_snapshot=danbooru_base_snapshot,
            danbooru_snapshot=danbooru_snapshot,
        )
        snapshot = PromptContextMenuSnapshot(
            identity=identity,
            readiness=self._snapshot_readiness(
                scene_snapshot=scene_snapshot,
                scene_position_snapshot=scene_position_snapshot,
                diagnostics_snapshot=diagnostics_snapshot,
                diagnostic_action_snapshot=diagnostic_action_snapshot,
                lora_snapshot=lora_snapshot,
                lora_action_snapshot=lora_action_snapshot,
                segment_snapshot=segment_snapshot,
                danbooru_snapshot=danbooru_snapshot,
                request=request,
            ),
            actions=actions,
        )
        _log_unavailable_concerns(snapshot)
        return snapshot

    def prepare_menu_selection(
        self,
        *,
        selected_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
        reason: str,
    ) -> None:
        """Prepare selected-text menu concerns before snapshot reads."""

        self._segment_presets.prepare_menu_snapshot_for_selection(
            selected_text=selected_text,
            selection_range=selection_range,
            read_only=read_only,
            reason=reason,
        )
        self._danbooru.prepare_menu_snapshot_for_selection(
            selection_text=selected_text,
            selection_range=selection_range,
            read_only=read_only,
            reason=reason,
        )

    def prepare_menu_opening(self, *, source_position: int, reason: str) -> None:
        """Prepare source-position menu concerns before snapshot reads."""

        scene_position_snapshot = self._scene.prepare_position_context(
            source_position,
            reason=reason,
        )
        if _scene_position_context_ready(scene_position_snapshot):
            context = scene_position_snapshot.context
            assert context is not None
            self._lora_trigger_words.prewarm_prompt(context.effective_prompt_text)

    def _snapshot_identity(
        self,
        *,
        request: PromptContextMenuSnapshotRequest,
        scene_snapshot: PromptSceneContextSnapshot,
        scene_position_snapshot: PromptScenePositionContextSnapshot,
        diagnostics_snapshot: PromptDiagnosticsSnapshot,
        diagnostic_action_snapshot: PromptDiagnosticMenuActionSnapshot,
        lora_snapshot: PromptLoraMetadataSnapshot,
        lora_action_snapshot: PromptLoraActionSnapshot,
        segment_base_snapshot: PromptSegmentPresetSnapshot,
        segment_snapshot: PromptSegmentPresetSnapshot,
        danbooru_base_snapshot: PromptDanbooruActionSnapshot,
        danbooru_snapshot: PromptDanbooruActionSnapshot,
    ) -> PromptContextMenuSnapshotIdentity:
        """Return freshness identity for one context-menu snapshot."""

        source_identity = self._source_identity_provider()
        scene_identity = scene_snapshot.identity
        feature_profile_id = self._feature_profile_id_provider()
        return PromptContextMenuSnapshotIdentity(
            source_revision=(
                None if source_identity is None else source_identity.source_revision
            ),
            source_position=request.source_position,
            selected_text_identity=_selected_text_identity(request.selected_text),
            selection_range_identity=request.selection_range,
            feature_profile_id=feature_profile_id,
            cube_context_id=scene_identity.cube_context_id,
            scene_context_id=scene_identity.scene_context_id,
            scene_snapshot_identity=scene_identity,
            scene_position_snapshot_identity=scene_position_snapshot.identity,
            diagnostics_snapshot_identity=diagnostics_snapshot.identity,
            diagnostic_action_snapshot_identity=diagnostic_action_snapshot.identity,
            lora_catalog_revision=lora_snapshot.catalog_revision,
            lora_action_identity=_catalog_identity_from_snapshot(lora_action_snapshot),
            prompt_segment_catalog_identity=_segment_catalog_identity(
                base_snapshot=segment_base_snapshot,
                selected_snapshot=segment_snapshot,
            ),
            danbooru_snapshot_identity=_danbooru_identity(
                base_snapshot=danbooru_base_snapshot,
                selection_snapshot=danbooru_snapshot,
            ),
            read_only=request.read_only,
            rich_prompt_rendering_enabled=request.rich_prompt_rendering_enabled,
        )

    def _snapshot_readiness(
        self,
        *,
        scene_snapshot: PromptSceneContextSnapshot,
        scene_position_snapshot: PromptScenePositionContextSnapshot,
        diagnostics_snapshot: PromptDiagnosticsSnapshot,
        diagnostic_action_snapshot: PromptDiagnosticMenuActionSnapshot,
        lora_snapshot: PromptLoraMetadataSnapshot,
        lora_action_snapshot: PromptLoraActionSnapshot,
        segment_snapshot: PromptSegmentPresetSnapshot,
        danbooru_snapshot: PromptDanbooruActionSnapshot,
        request: PromptContextMenuSnapshotRequest,
    ) -> PromptContextMenuSnapshotReadiness:
        """Return per-concern readiness for one context-menu snapshot."""

        lora_status = _status_from_snapshot(lora_action_snapshot)
        segment_status = segment_snapshot.status
        return PromptContextMenuSnapshotReadiness(
            concerns=(
                _feature_concern_readiness(
                    concern=PromptContextMenuConcern.SCENE,
                    identity=scene_position_snapshot.identity,
                    unavailable_reason=(
                        scene_position_snapshot.unavailable_reason
                        or scene_snapshot.unavailable_reason
                    ),
                ),
                _feature_concern_readiness(
                    concern=PromptContextMenuConcern.DIAGNOSTICS,
                    identity=diagnostic_action_snapshot.identity,
                    unavailable_reason=(
                        diagnostic_action_snapshot.unavailable_reason
                        or diagnostics_snapshot.unavailable_reason
                    ),
                ),
                PromptContextMenuConcernReadiness(
                    concern=PromptContextMenuConcern.LORA,
                    ready=(
                        not lora_snapshot.stale
                        and lora_snapshot.unavailable_reason is None
                        and lora_status.consumable
                    ),
                    stale=lora_snapshot.stale,
                    unavailable_reason=(
                        lora_snapshot.unavailable_reason
                        or lora_status.unavailable_reason
                    ),
                    identity=_catalog_identity_from_snapshot(lora_action_snapshot),
                ),
                PromptContextMenuConcernReadiness(
                    concern=PromptContextMenuConcern.PROMPT_SEGMENT,
                    ready=segment_status.consumable,
                    stale=segment_status.readiness is CatalogSnapshotReadiness.STALE,
                    unavailable_reason=segment_status.unavailable_reason,
                    identity=segment_snapshot.catalog_identity,
                ),
                _feature_concern_readiness(
                    concern=PromptContextMenuConcern.DANBOORU,
                    identity=danbooru_snapshot.identity,
                    unavailable_reason=danbooru_snapshot.unavailable_reason,
                ),
                PromptContextMenuConcernReadiness(
                    concern=PromptContextMenuConcern.EDITING_STATE,
                    ready=True,
                    identity=(request.selection_range, request.read_only),
                ),
                PromptContextMenuConcernReadiness(
                    concern=PromptContextMenuConcern.RENDERING_STATE,
                    ready=True,
                    identity=request.rich_prompt_rendering_enabled,
                ),
            )
        )


def _feature_concern_readiness(
    *,
    concern: PromptContextMenuConcern,
    identity: PromptFeatureSnapshotIdentity,
    unavailable_reason: str | None,
) -> PromptContextMenuConcernReadiness:
    """Return concern readiness from a feature snapshot identity."""

    reason = unavailable_reason
    if reason is None and identity.stale:
        reason = "stale_snapshot"
    return PromptContextMenuConcernReadiness(
        concern=concern,
        ready=not identity.stale and reason is None,
        stale=identity.stale,
        unavailable_reason=reason,
        identity=identity,
    )


def _log_unavailable_concerns(snapshot: PromptContextMenuSnapshot) -> None:
    """Log prompt-safe context when prepared menu concerns are omitted."""

    unavailable = tuple(
        concern
        for concern in snapshot.readiness.concerns
        if not concern.ready and concern.unavailable_reason is not None
    )
    if not unavailable:
        return
    log_debug(
        _LOGGER,
        "context_menu_snapshot.prepared_concern_unavailable",
        operation="context_menu_snapshot",
        reason="prepared_concern_unavailable",
        source_revision=snapshot.identity.source_revision,
        feature_profile_id=snapshot.identity.feature_profile_id,
        scene_context_id=snapshot.identity.scene_context_id,
        cube_context_id=snapshot.identity.cube_context_id,
        unavailable_count=len(unavailable),
        stale_outcome=any(concern.stale for concern in unavailable),
        concern_status=";".join(
            f"{concern.concern.value}:{concern.unavailable_reason}"
            for concern in unavailable
        ),
    )


def _scene_context_from_snapshot(
    *,
    request: PromptContextMenuSnapshotRequest,
    snapshot: PromptScenePositionContextSnapshot,
) -> PromptScenePositionContext:
    """Return prepared scene context or an empty stale-safe menu context."""

    if snapshot.context is not None and snapshot.ready and not snapshot.stale:
        return snapshot.context
    return PromptScenePositionContext(
        source_position=request.source_position,
        scene_key=None,
        queueable_scene_key=None,
        effective_prompt_text="",
    )


def _scene_position_context_ready(snapshot: PromptScenePositionContextSnapshot) -> bool:
    """Return whether a prepared scene-position context may feed menu actions."""

    return snapshot.context is not None and snapshot.ready and not snapshot.stale


def _selected_text_identity(selected_text: str) -> tuple[str, int, int]:
    """Return a prompt-safe selected-text identity."""

    return ("selected_text", len(selected_text), hash(selected_text))


def _status_from_snapshot(snapshot: PromptLoraActionSnapshot) -> CatalogSnapshotStatus:
    """Return catalog readiness from a LoRA action snapshot."""

    return snapshot.status


def _catalog_identity_from_snapshot(
    snapshot: PromptLoraActionSnapshot,
) -> CatalogSnapshotIdentity:
    """Return catalog identity from a LoRA action snapshot."""

    return snapshot.identity


def _segment_catalog_identity(
    *,
    base_snapshot: PromptSegmentPresetSnapshot,
    selected_snapshot: PromptSegmentPresetSnapshot,
) -> CatalogSnapshotIdentity:
    """Return segment identity, preferring the selected-text menu snapshot."""

    if selected_snapshot.catalog_identity != CatalogSnapshotIdentity():
        return selected_snapshot.catalog_identity
    return base_snapshot.catalog_identity


def _danbooru_identity(
    *,
    base_snapshot: PromptDanbooruActionSnapshot,
    selection_snapshot: PromptDanbooruActionSnapshot,
) -> PromptFeatureSnapshotIdentity:
    """Return Danbooru identity, preferring selected-text snapshot identity."""

    if selection_snapshot.identity != base_snapshot.identity:
        return selection_snapshot.identity
    return base_snapshot.identity


__all__ = [
    "PromptContextMenuActionSnapshot",
    "PromptContextMenuConcern",
    "PromptContextMenuConcernReadiness",
    "PromptContextMenuSnapshot",
    "PromptContextMenuSnapshotController",
    "PromptContextMenuSnapshotIdentity",
    "PromptContextMenuSnapshotReadiness",
    "PromptContextMenuSnapshotRequest",
]

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

"""Tests for prepared prompt context-menu action snapshots."""

from __future__ import annotations

from typing import Any, cast

from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.features import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
    PromptContextMenuAction,
    PromptContextMenuActionController,
    PromptDanbooruActionController,
    PromptDanbooruActionSnapshot,
    PromptDanbooruUrlImportState,
    PromptDiagnosticMenuActionSnapshot,
    PromptDiagnosticsSnapshot,
    PromptDiagnosticsFeatureController,
    PromptFeatureActionState,
    PromptFeatureCommandRequest,
    PromptFeatureSnapshotIdentity,
    PromptLoraActionSnapshot,
    PromptLoraMetadataFeatureController,
    PromptLoraMetadataSnapshot,
    PromptLoraTriggerWordsPayload,
    PromptSceneAutocompleteState,
    PromptSceneContextSnapshot,
    PromptSceneFeatureController,
    PromptScenePositionContext,
    PromptScenePositionContextSnapshot,
    PromptSceneQueueActionState,
    PromptSegmentPresetController,
    PromptSegmentPresetSaveState,
    PromptSegmentPresetSnapshot,
)


class _Diagnostics:
    """Return prepared diagnostics menu actions."""

    def __init__(self, diagnostic: str | None = "diagnostic") -> None:
        """Initialize call observations."""

        self.diagnostic = diagnostic
        self._snapshot = PromptDiagnosticsSnapshot(
            identity=PromptFeatureSnapshotIdentity(source_revision=9),
            diagnostics=(),
            visible_diagnostics=(),
            action_ready=diagnostic is not None,
            active_word_policy="hide_active_word",
        )

    @property
    def snapshot(self) -> PromptDiagnosticsSnapshot:
        """Return fake prepared diagnostics state."""

        return self._snapshot

    def prepared_menu_actions_for_source_position(
        self,
        source_position: int,
    ) -> PromptDiagnosticMenuActionSnapshot:
        """Return one fake prepared diagnostic action snapshot."""

        if self.diagnostic is None:
            return PromptDiagnosticMenuActionSnapshot(
                identity=PromptFeatureSnapshotIdentity(
                    source_revision=9,
                    query_identity=("diagnostic_menu_actions", source_position),
                ),
                source_position=source_position,
                diagnostic_id=None,
                source_range=None,
                actions=(),
                ready=True,
            )
        return PromptDiagnosticMenuActionSnapshot(
            identity=PromptFeatureSnapshotIdentity(
                source_revision=9,
                query_identity=(
                    "diagnostic_menu_actions",
                    source_position,
                    self.diagnostic,
                ),
            ),
            source_position=source_position,
            diagnostic_id=self.diagnostic,
            source_range=(source_position, source_position + 1),
            actions=(
                PromptContextMenuAction(label="Fix", callback=None, enabled=False),
            ),
            ready=True,
        )


class _LoraMetadata:
    """Provide cached LoRA action readiness."""

    def __init__(
        self, *, picker_ready: bool = True, actions_ready: bool = True
    ) -> None:
        """Initialize fake LoRA action readiness."""

        self._picker_ready = picker_ready
        self._actions_ready = actions_ready
        self._snapshot = PromptLoraMetadataSnapshot(
            identity=PromptFeatureSnapshotIdentity(source_revision=9),
            catalog_revision="lora-catalog",
            picker_items=(),
            picker_status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
            thumbnail_readiness=(),
            dirty=False,
            stale=False,
            action_ready=picker_ready or actions_ready,
        )

    @property
    def snapshot(self) -> PromptLoraMetadataSnapshot:
        """Return fake prepared LoRA metadata state."""

        return self._snapshot

    @property
    def lora_picker_ready(self) -> bool:
        """Return fake picker readiness."""

        return self._picker_ready

    def snapshot_for_prompt(
        self,
        *,
        prompt_text: str,
    ) -> PromptLoraActionSnapshot:
        """Return one prepared trigger-word snapshot for the effective prompt."""

        if not self._actions_ready:
            actions: tuple[
                PromptFeatureActionState[PromptLoraTriggerWordsPayload], ...
            ] = ()
        else:
            actions = (
                PromptFeatureActionState(
                    action_id="lora.trigger_words:test",
                    label="Trigger words: Test",
                    ready=True,
                    command_request=PromptFeatureCommandRequest(
                        command_name="lora_insert_trigger_words",
                        identity=PromptFeatureSnapshotIdentity(source_revision=9),
                        payload=PromptLoraTriggerWordsPayload(
                            insertion_text=prompt_text,
                            display_name="Test",
                            full_label="Trigger words: Test",
                        ),
                    ),
                ),
            )
        return PromptLoraActionSnapshot(
            identity=CatalogSnapshotIdentity(
                source_revision=9,
                catalog_revision=self._snapshot.catalog_revision,
                prompt_context_token=("prompt", len(prompt_text), hash(prompt_text)),
                query_identity=("lora_trigger_words",),
            ),
            status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
            trigger_word_actions=actions,
        )

    def prewarm_prompt(self, prompt_text: str) -> bool:
        """Accept effective prompt preparation for the fake."""

        _ = prompt_text
        return True

    def unavailable_snapshot(
        self,
        *,
        unavailable_reason: str,
    ) -> PromptLoraActionSnapshot:
        """Return unavailable LoRA action state for stale scene context."""

        return PromptLoraActionSnapshot(
            identity=CatalogSnapshotIdentity(
                source_revision=9,
                catalog_revision=self._snapshot.catalog_revision,
                prompt_context_token=(unavailable_reason, 0, hash("")),
                query_identity=("lora_trigger_words", unavailable_reason),
                stale=True,
                unavailable_reason=unavailable_reason,
            ),
            status=CatalogSnapshotStatus(
                CatalogSnapshotReadiness.UNAVAILABLE,
                unavailable_reason=unavailable_reason,
            ),
            trigger_word_actions=(),
        )


class _Scene:
    """Return one prepared source-position scene context."""

    def __init__(
        self,
        *,
        scene_key: str | None = "portrait",
        queueable_scene_key: str | None = "portrait",
        effective_prompt_text: str = "scene prompt",
    ) -> None:
        """Initialize fake source-position scene context."""

        self._scene_key = scene_key
        self._queueable_scene_key = queueable_scene_key
        self._effective_prompt_text = effective_prompt_text
        self._snapshot = PromptSceneContextSnapshot(
            identity=PromptFeatureSnapshotIdentity(source_revision=9),
            autocomplete=PromptSceneAutocompleteState(titles=(), ready=False),
            queue_action=PromptSceneQueueActionState(
                queueable_scene_keys=frozenset(
                    {queueable_scene_key} if queueable_scene_key is not None else ()
                ),
                action_ready=queueable_scene_key is not None,
                scene_key=queueable_scene_key,
            ),
        )
        self._position_snapshot = PromptScenePositionContextSnapshot(
            identity=PromptFeatureSnapshotIdentity(
                source_revision=9,
                query_identity=("scene_position_context", scene_key),
            ),
            source_position=0,
            context=PromptScenePositionContext(
                source_position=0,
                scene_key=self._scene_key,
                queueable_scene_key=self._queueable_scene_key,
                effective_prompt_text=self._effective_prompt_text,
            ),
            ready=True,
        )

    @property
    def snapshot(self) -> PromptSceneContextSnapshot:
        """Return fake prepared scene state."""

        return self._snapshot

    def prepared_position_context(
        self,
        source_position: int,
    ) -> PromptScenePositionContextSnapshot:
        """Return fake prepared scene context for the supplied source position."""

        return PromptScenePositionContextSnapshot(
            identity=self._position_snapshot.identity,
            source_position=source_position,
            context=PromptScenePositionContext(
                source_position=source_position,
                scene_key=self._scene_key,
                queueable_scene_key=self._queueable_scene_key,
                effective_prompt_text=self._effective_prompt_text,
            ),
            ready=True,
        )


class _Segments:
    """Return one prompt segment preset snapshot."""

    def __init__(
        self, *, source_available: bool = True, insert_ready: bool = True
    ) -> None:
        """Initialize fake segment preset readiness."""

        self._source_available = source_available
        self._insert_ready = insert_ready
        self._snapshot = PromptSegmentPresetSnapshot(
            identity=PromptFeatureSnapshotIdentity(source_revision=9),
            menu_model=None,
            save_state=PromptSegmentPresetSaveState(
                source_available=source_available,
                selected_text="",
                ready=source_available,
            ),
            insert_ready=insert_ready,
            unavailable_reason=(
                None if source_available else "preset_source_unavailable"
            ),
            status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
        )

    @property
    def snapshot(self) -> PromptSegmentPresetSnapshot:
        """Return fake base segment state."""

        return self._snapshot

    def prepare_menu_snapshot_for_selection(
        self,
        *,
        selected_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
        reason: str,
    ) -> PromptSegmentPresetSnapshot:
        """Prepare fake prompt segment menu state."""

        _ = (selection_range, read_only, reason)
        self._snapshot = self._selected_snapshot(selected_text)
        return self._snapshot

    def prepared_menu_snapshot_for_selection(
        self,
        *,
        selected_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
    ) -> PromptSegmentPresetSnapshot:
        """Return fake prompt segment menu state."""

        _ = (selection_range, read_only)
        return self._snapshot

    def _selected_snapshot(self, selected_text: str) -> PromptSegmentPresetSnapshot:
        """Return fake prompt segment state for selected text."""

        return PromptSegmentPresetSnapshot(
            identity=self._snapshot.identity,
            menu_model=self._snapshot.menu_model,
            save_state=PromptSegmentPresetSaveState(
                source_available=self._source_available,
                selected_text=selected_text,
                ready=self._source_available,
            ),
            insert_ready=self._insert_ready,
            unavailable_reason=self._snapshot.unavailable_reason,
            status=self._snapshot.status,
        )


class _Danbooru:
    """Return one Danbooru action snapshot."""

    def __init__(self) -> None:
        """Initialize fake Danbooru state."""

        self._snapshot = PromptDanbooruActionSnapshot(
            identity=PromptFeatureSnapshotIdentity(source_revision=9),
            wiki_lookup_action=None,
            url_import_state=PromptDanbooruUrlImportState(
                service_available=False,
                enabled=False,
                ready=False,
                disabled_reason="service_unavailable",
            ),
        )

    @property
    def snapshot(self) -> PromptDanbooruActionSnapshot:
        """Return fake base Danbooru state."""

        return self._snapshot

    def prepare_menu_snapshot_for_selection(
        self,
        *,
        selection_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
        reason: str,
    ) -> PromptDanbooruActionSnapshot:
        """Prepare fake Danbooru readiness for selected text."""

        _ = (selection_text, selection_range, read_only, reason)
        return self._snapshot

    def prepared_menu_snapshot_for_selection(
        self,
        *,
        selection_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
    ) -> PromptDanbooruActionSnapshot:
        """Return prepared fake Danbooru readiness for selected text."""

        _ = (selection_text, selection_range, read_only)
        return self._snapshot


def test_context_menu_action_controller_composes_prepared_snapshot() -> None:
    """Context menu snapshots should gather feature state without Qt widgets."""

    lora = _LoraMetadata()
    controller = PromptContextMenuActionController(
        diagnostics=cast(PromptDiagnosticsFeatureController, _Diagnostics()),
        lora_metadata=cast(PromptLoraMetadataFeatureController, lora),
        lora_trigger_words=cast(Any, lora),
        scene=cast(PromptSceneFeatureController, _Scene()),
        segment_presets=cast(PromptSegmentPresetController, _Segments()),
        danbooru=cast(PromptDanbooruActionController, _Danbooru()),
        source_identity_provider=lambda: PromptCommandSourceIdentity(
            source_revision=9,
            source_length=40,
        ),
        feature_profile_id_provider=lambda: "profile-a",
    )

    controller.prepare_menu_selection(
        selected_text="selected",
        selection_range=None,
        read_only=False,
        reason="test",
    )
    snapshot = controller.prepared_action_snapshot_for_menu(
        source_position=12,
        selected_text="selected",
        read_only=False,
        rich_prompt_rendering_enabled=True,
    )

    assert snapshot.source_position == 12
    assert snapshot.queue_scene_key == "portrait"
    assert snapshot.effective_prompt_text == "scene prompt"
    assert snapshot.diagnostic_actions[0].label == "Fix"
    assert snapshot.lora_picker_ready is True
    assert snapshot.lora_trigger_word_actions[0].command_request is not None
    assert (
        snapshot.lora_trigger_word_actions[0].command_request.payload.insertion_text
        == "scene prompt"
    )
    assert snapshot.segment_snapshot.save_state.selected_text == "selected"
    assert snapshot.danbooru_snapshot.url_import_state.ready is False


def test_phase24_1_context_menu_snapshot_records_unavailable_concerns() -> None:
    """Menu snapshots should expose stale-safe absent states without Qt widgets."""

    lora = _LoraMetadata(picker_ready=False, actions_ready=False)
    controller = PromptContextMenuActionController(
        diagnostics=cast(PromptDiagnosticsFeatureController, _Diagnostics(None)),
        lora_metadata=cast(
            PromptLoraMetadataFeatureController,
            lora,
        ),
        lora_trigger_words=cast(Any, lora),
        scene=cast(
            PromptSceneFeatureController,
            _Scene(
                scene_key=None,
                queueable_scene_key=None,
                effective_prompt_text="source prompt",
            ),
        ),
        segment_presets=cast(
            PromptSegmentPresetController,
            _Segments(source_available=False, insert_ready=False),
        ),
        danbooru=cast(PromptDanbooruActionController, _Danbooru()),
        source_identity_provider=lambda: PromptCommandSourceIdentity(
            source_revision=9,
            source_length=40,
        ),
        feature_profile_id_provider=lambda: "profile-a",
    )

    controller.prepare_menu_selection(
        selected_text="",
        selection_range=None,
        read_only=True,
        reason="test",
    )
    snapshot = controller.prepared_action_snapshot_for_menu(
        source_position=0,
        selected_text="",
        read_only=True,
        rich_prompt_rendering_enabled=False,
    )

    assert snapshot.source_position == 0
    assert snapshot.selected_text == ""
    assert snapshot.queue_scene_key is None
    assert snapshot.effective_prompt_text == "source prompt"
    assert snapshot.diagnostic_actions == ()
    assert snapshot.lora_picker_ready is False
    assert snapshot.lora_trigger_word_actions == ()
    assert snapshot.segment_snapshot.insert_ready is False
    assert snapshot.segment_snapshot.unavailable_reason == "preset_source_unavailable"
    assert snapshot.danbooru_snapshot.wiki_lookup_action is None
    assert snapshot.read_only is True
    assert snapshot.rich_prompt_rendering_enabled is False

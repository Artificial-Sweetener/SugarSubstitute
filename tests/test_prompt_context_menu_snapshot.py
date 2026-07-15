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

"""Tests for prompt context-menu snapshot identity ownership."""

from __future__ import annotations

import logging
from collections.abc import Hashable
from dataclasses import replace
from typing import cast

import pytest

from substitute.presentation.editor.catalog.snapshots import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptContextMenuAction,
    PromptDanbooruActionSnapshot,
    PromptDanbooruUrlImportState,
    PromptDiagnosticMenuActionSnapshot,
    PromptDiagnosticsSnapshot,
    PromptFeatureActionState,
    PromptFeatureCommandRequest,
    PromptFeatureSnapshotIdentity,
    PromptLoraActionSnapshot,
    PromptLoraMetadataSnapshot,
    PromptLoraTriggerWordsPayload,
    PromptSceneContextSnapshot,
    PromptScenePositionContext,
    PromptScenePositionContextSnapshot,
    PromptSceneAutocompleteState,
    PromptSceneQueueActionState,
    PromptSegmentPresetSaveState,
    PromptSegmentPresetSnapshot,
)
from substitute.presentation.editor.prompt_editor.features.context_menu_snapshot import (
    PromptContextMenuConcern,
    PromptContextMenuDanbooruPort,
    PromptContextMenuDiagnosticsPort,
    PromptContextMenuLoraMetadataPort,
    PromptContextMenuLoraTriggerWordPort,
    PromptContextMenuScenePort,
    PromptContextMenuSegmentPort,
    PromptContextMenuSnapshotController,
    PromptContextMenuSnapshotRequest,
)


class _Diagnostics:
    """Provide prepared diagnostics state and prepared menu actions."""

    def __init__(
        self,
        *,
        identity: PromptFeatureSnapshotIdentity,
        action_ready: bool = True,
        action_stale: bool = False,
        action_unavailable_reason: str | None = None,
    ) -> None:
        """Initialize fake diagnostics state."""

        self._snapshot = PromptDiagnosticsSnapshot(
            identity=identity,
            diagnostics=(),
            visible_diagnostics=(),
            action_ready=action_ready,
            active_word_policy="hide_active_word",
        )
        effective_action_stale = action_stale or identity.stale
        self._action_snapshot = PromptDiagnosticMenuActionSnapshot(
            identity=replace(
                identity,
                stale=effective_action_stale,
                query_identity=(
                    "diagnostic_menu_actions",
                    action_ready,
                    effective_action_stale,
                    action_unavailable_reason,
                ),
            ),
            source_position=12,
            diagnostic_id=("diagnostic" if action_ready else None),
            source_range=((10, 20) if action_ready else None),
            actions=(
                (PromptContextMenuAction(label="Fix", callback=None, enabled=False),)
                if action_ready
                else ()
            ),
            ready=action_ready and not effective_action_stale,
            stale=effective_action_stale,
            unavailable_reason=action_unavailable_reason,
        )

    @property
    def snapshot(self) -> PromptDiagnosticsSnapshot:
        """Return prepared diagnostics state."""

        return self._snapshot

    def prepared_menu_actions_for_source_position(
        self,
        source_position: int,
    ) -> PromptDiagnosticMenuActionSnapshot:
        """Return prepared diagnostic actions for one source position."""

        return replace(self._action_snapshot, source_position=source_position)


class _LoraMetadata:
    """Provide prepared LoRA state and prepared trigger rows."""

    def __init__(
        self,
        *,
        identity: PromptFeatureSnapshotIdentity,
        catalog_revision: Hashable | None = "lora-catalog-1",
        unavailable_reason: str | None = None,
    ) -> None:
        """Initialize fake LoRA metadata state."""

        self._snapshot = PromptLoraMetadataSnapshot(
            identity=identity,
            catalog_revision=catalog_revision,
            picker_items=(),
            picker_status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
            thumbnail_readiness=(),
            dirty=identity.stale,
            stale=identity.stale,
            action_ready=True,
            unavailable_reason=unavailable_reason,
        )
        self.prompt_texts: list[str] = []

    @property
    def snapshot(self) -> PromptLoraMetadataSnapshot:
        """Return prepared LoRA metadata state."""

        return self._snapshot

    @property
    def lora_picker_ready(self) -> bool:
        """Return whether the LoRA picker row is ready."""

        return not self._snapshot.stale

    def snapshot_for_prompt(
        self,
        *,
        prompt_text: str,
    ) -> PromptLoraActionSnapshot:
        """Return an object carrying prepared action identity."""

        self.prompt_texts.append(prompt_text)
        return PromptLoraActionSnapshot(
            identity=CatalogSnapshotIdentity(
                source_revision=self._snapshot.identity.source_revision,
                feature_profile_id=self._snapshot.identity.feature_profile_id,
                catalog_revision=self._snapshot.catalog_revision,
                prompt_context_token=("prompt", len(prompt_text), hash(prompt_text)),
                query_identity=("lora_trigger_words",),
            ),
            status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
            trigger_word_actions=(
                PromptFeatureActionState(
                    action_id="lora.trigger_words:test",
                    label="Trigger words: Test",
                    ready=True,
                    command_request=PromptFeatureCommandRequest(
                        command_name="lora_insert_trigger_words",
                        identity=self._snapshot.identity,
                        payload=PromptLoraTriggerWordsPayload(
                            insertion_text=prompt_text,
                            display_name="Test",
                            full_label="Trigger words: Test",
                        ),
                    ),
                ),
            ),
        )

    def prewarm_prompt(self, prompt_text: str) -> bool:
        """Record effective prompt preparation requests."""

        self.prompt_texts.append(prompt_text)
        return True

    def unavailable_snapshot(
        self,
        *,
        unavailable_reason: str,
    ) -> PromptLoraActionSnapshot:
        """Return an unavailable prepared action snapshot."""

        return PromptLoraActionSnapshot(
            identity=CatalogSnapshotIdentity(
                source_revision=self._snapshot.identity.source_revision,
                feature_profile_id=self._snapshot.identity.feature_profile_id,
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
    """Provide scene snapshots and prepared source-position context."""

    def __init__(
        self,
        *,
        identity: PromptFeatureSnapshotIdentity,
        position_ready: bool = True,
        position_stale: bool = False,
        position_unavailable_reason: str | None = None,
    ) -> None:
        """Initialize fake scene state."""

        self._snapshot = PromptSceneContextSnapshot(
            identity=identity,
            autocomplete=PromptSceneAutocompleteState(titles=(), ready=False),
            queue_action=PromptSceneQueueActionState(
                queueable_scene_keys=frozenset({"portrait"}),
                action_ready=True,
                scene_key="portrait",
            ),
        )
        position_context = (
            None
            if not position_ready
            else PromptScenePositionContext(
                source_position=12,
                scene_key="portrait",
                queueable_scene_key="portrait",
                effective_prompt_text="scene prompt",
            )
        )
        self._position_snapshot = PromptScenePositionContextSnapshot(
            identity=replace(
                identity,
                stale=position_stale,
                query_identity=(
                    "scene_position_context",
                    position_ready,
                    position_stale,
                    position_unavailable_reason,
                ),
            ),
            source_position=12,
            context=position_context,
            ready=position_ready and not position_stale,
            stale=position_stale,
            unavailable_reason=position_unavailable_reason,
        )

    @property
    def snapshot(self) -> PromptSceneContextSnapshot:
        """Return prepared scene state."""

        return self._snapshot

    def prepared_position_context(
        self,
        source_position: int,
    ) -> PromptScenePositionContextSnapshot:
        """Return prepared source-position scene context."""

        return replace(
            self._position_snapshot,
            source_position=source_position,
            context=(
                None
                if self._position_snapshot.context is None
                else replace(
                    self._position_snapshot.context,
                    source_position=source_position,
                )
            ),
        )


class _Segments:
    """Provide prompt segment snapshots."""

    def __init__(
        self,
        *,
        identity: PromptFeatureSnapshotIdentity,
        catalog_identity: CatalogSnapshotIdentity,
        status: CatalogSnapshotStatus | None = None,
    ) -> None:
        """Initialize fake segment snapshot state."""

        self._snapshot = PromptSegmentPresetSnapshot(
            identity=identity,
            menu_model=None,
            save_state=PromptSegmentPresetSaveState(
                source_available=True,
                selected_text="",
                ready=False,
            ),
            insert_ready=False,
            catalog_identity=catalog_identity,
            status=status or CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
        )
        self.prepared_requests: list[tuple[str, tuple[int, int] | None, bool]] = []

    @property
    def snapshot(self) -> PromptSegmentPresetSnapshot:
        """Return latest segment snapshot."""

        return self._snapshot

    def prepare_menu_snapshot_for_selection(
        self,
        *,
        selected_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
        reason: str,
    ) -> PromptSegmentPresetSnapshot:
        """Prepare a selected-text segment snapshot."""

        _ = reason
        self._snapshot = replace(
            self._snapshot,
            save_state=replace(self._snapshot.save_state, selected_text=selected_text),
            selected_text_identity=(
                "selected_text",
                len(selected_text),
                hash(selected_text),
            ),
            selection_range=selection_range,
            read_only=read_only,
        )
        self.prepared_requests.append((selected_text, selection_range, read_only))
        return self._snapshot

    def prepared_menu_snapshot_for_selection(
        self,
        *,
        selected_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
    ) -> PromptSegmentPresetSnapshot:
        """Return a prepared selected-text segment snapshot."""

        _ = (selected_text, selection_range, read_only)
        return replace(
            self._snapshot,
            save_state=replace(self._snapshot.save_state, selected_text=selected_text),
        )


class _Danbooru:
    """Provide Danbooru snapshots."""

    def __init__(self, *, identity: PromptFeatureSnapshotIdentity) -> None:
        """Initialize fake Danbooru state."""

        self._snapshot = PromptDanbooruActionSnapshot(
            identity=identity,
            wiki_lookup_action=None,
            url_import_state=PromptDanbooruUrlImportState(
                service_available=False,
                enabled=False,
                ready=False,
                disabled_reason="service_unavailable",
            ),
        )
        self.prepared_requests: list[tuple[str, tuple[int, int] | None, bool]] = []

    @property
    def snapshot(self) -> PromptDanbooruActionSnapshot:
        """Return prepared Danbooru state."""

        return self._snapshot

    def prepare_menu_snapshot_for_selection(
        self,
        *,
        selection_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
        reason: str,
    ) -> PromptDanbooruActionSnapshot:
        """Prepare a selected-text Danbooru snapshot."""

        _ = reason
        self._snapshot = replace(
            self._snapshot,
            selected_text_identity=(
                "selected_text",
                len(selection_text),
                hash(selection_text),
            ),
            selection_range=selection_range,
            read_only=read_only,
        )
        self.prepared_requests.append((selection_text, selection_range, read_only))
        return self._snapshot

    def prepared_menu_snapshot_for_selection(
        self,
        *,
        selection_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
    ) -> PromptDanbooruActionSnapshot:
        """Return a prepared selected-text Danbooru snapshot."""

        _ = (selection_text, selection_range, read_only)
        return self._snapshot


def test_context_menu_snapshot_identity_includes_all_phase24_2_inputs() -> None:
    """The context-menu snapshot owner should aggregate freshness identities."""

    controller = _controller()

    snapshot = controller.snapshot_for_menu(
        PromptContextMenuSnapshotRequest(
            source_position=12,
            selected_text="selected prompt",
            selection_range=(2, 17),
            read_only=False,
            rich_prompt_rendering_enabled=True,
        )
    )

    assert snapshot.identity.source_revision == 42
    assert snapshot.identity.source_position == 12
    assert snapshot.identity.selected_text_identity[0] == "selected_text"
    assert snapshot.identity.selected_text_identity[1] == len("selected prompt")
    assert "selected prompt" not in repr(snapshot.identity.selected_text_identity)
    assert snapshot.identity.selection_range_identity == (2, 17)
    assert snapshot.identity.feature_profile_id == "profile-a"
    assert snapshot.identity.cube_context_id == "cube-a"
    assert snapshot.identity.scene_context_id == "scene-a"
    assert snapshot.identity.scene_snapshot_identity is not None
    assert snapshot.identity.scene_position_snapshot_identity is not None
    assert snapshot.identity.diagnostics_snapshot_identity is not None
    assert snapshot.identity.diagnostic_action_snapshot_identity is not None
    assert snapshot.identity.lora_catalog_revision == "lora-catalog-1"
    assert snapshot.identity.lora_action_identity is not None
    assert snapshot.identity.prompt_segment_catalog_identity.catalog_revision == (
        "segment-catalog-1"
    )
    assert snapshot.identity.danbooru_snapshot_identity is not None
    assert snapshot.identity.read_only is False
    assert snapshot.identity.rich_prompt_rendering_enabled is True
    assert snapshot.actions.queue_scene_key == "portrait"
    assert snapshot.actions.effective_prompt_text == "scene prompt"
    assert snapshot.readiness.concern(PromptContextMenuConcern.SCENE).ready is True
    assert snapshot.readiness.concern(PromptContextMenuConcern.LORA).ready is True


def test_context_menu_snapshot_identity_changes_for_invalidation_inputs() -> None:
    """Every Phase 24.2 identity input should affect snapshot identity."""

    base = _controller().snapshot_for_menu(_request()).identity

    variants = (
        _controller(source_revision=43).snapshot_for_menu(_request()).identity,
        _controller()
        .snapshot_for_menu(replace(_request(), source_position=13))
        .identity,
        _controller()
        .snapshot_for_menu(replace(_request(), selected_text="different"))
        .identity,
        _controller()
        .snapshot_for_menu(replace(_request(), selection_range=(0, 4)))
        .identity,
        _controller(feature_profile_id="profile-b")
        .snapshot_for_menu(_request())
        .identity,
        _controller(cube_context_id="cube-b").snapshot_for_menu(_request()).identity,
        _controller(scene_context_id="scene-b").snapshot_for_menu(_request()).identity,
        _controller(scene_position_stale=True).snapshot_for_menu(_request()).identity,
        _controller(diagnostics_stale=True).snapshot_for_menu(_request()).identity,
        _controller(diagnostic_action_stale=True)
        .snapshot_for_menu(_request())
        .identity,
        _controller(lora_catalog_revision="lora-catalog-2")
        .snapshot_for_menu(_request())
        .identity,
        _controller(segment_catalog_revision="segment-catalog-2")
        .snapshot_for_menu(_request())
        .identity,
        _controller(danbooru_source_revision=44).snapshot_for_menu(_request()).identity,
        _controller().snapshot_for_menu(replace(_request(), read_only=True)).identity,
        _controller()
        .snapshot_for_menu(replace(_request(), rich_prompt_rendering_enabled=False))
        .identity,
    )

    assert all(variant != base for variant in variants)


def test_context_menu_snapshot_records_per_concern_unavailable_state() -> None:
    """One stale concern should not invalidate unrelated prepared menu concerns."""

    snapshot = _controller(
        diagnostics_stale=True,
        lora_unavailable_reason="refresh_failed",
        segment_status=CatalogSnapshotStatus(
            CatalogSnapshotReadiness.REFRESH_FAILED,
            unavailable_reason="refresh_failed",
        ),
    ).snapshot_for_menu(_request())

    diagnostics = snapshot.readiness.concern(PromptContextMenuConcern.DIAGNOSTICS)
    lora = snapshot.readiness.concern(PromptContextMenuConcern.LORA)
    segment = snapshot.readiness.concern(PromptContextMenuConcern.PROMPT_SEGMENT)
    editing = snapshot.readiness.concern(PromptContextMenuConcern.EDITING_STATE)

    assert diagnostics.ready is False
    assert diagnostics.stale is True
    assert diagnostics.unavailable_reason == "stale_snapshot"
    assert lora.ready is False
    assert lora.unavailable_reason == "refresh_failed"
    assert segment.ready is False
    assert segment.unavailable_reason == "refresh_failed"
    assert editing.ready is True


def test_context_menu_snapshot_logs_prompt_safe_unavailable_concerns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unavailable prepared menu concerns should log only structural context."""

    logger_name = (
        "sugarsubstitute.presentation.editor.prompt_editor.features."
        "context_menu_snapshot"
    )
    caplog.set_level(logging.DEBUG, logger=logger_name)

    _controller(
        scene_position_ready=False,
        scene_position_stale=True,
        scene_position_unavailable_reason="scene_position_context_unprepared",
        diagnostics_stale=True,
        lora_unavailable_reason="refresh_failed",
        segment_status=CatalogSnapshotStatus(
            CatalogSnapshotReadiness.REFRESH_FAILED,
            unavailable_reason="refresh_failed",
        ),
    ).snapshot_for_menu(_request())

    messages = [record.getMessage() for record in caplog.records]

    assert any(
        "context_menu_snapshot.prepared_concern_unavailable" in message
        for message in messages
    )
    log_output = "\n".join(messages)
    assert "operation=context_menu_snapshot" in log_output
    assert "reason=prepared_concern_unavailable" in log_output
    assert "source_revision=42" in log_output
    assert "feature_profile_id=profile-a" in log_output
    assert "scene_context_id=scene-a" in log_output
    assert "cube_context_id=cube-a" in log_output
    assert "unavailable_count=" in log_output
    assert "scene:scene_position_context_unprepared" in log_output
    assert "lora:refresh_failed" in log_output
    assert "diagnostics:stale_snapshot" in log_output
    assert "selected prompt" not in log_output
    assert "scene prompt" not in log_output


def test_context_menu_snapshot_does_not_log_when_all_concerns_are_ready(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Fresh prepared snapshots should not produce omission diagnostics."""

    logger_name = (
        "sugarsubstitute.presentation.editor.prompt_editor.features."
        "context_menu_snapshot"
    )
    caplog.set_level(logging.DEBUG, logger=logger_name)

    _controller().snapshot_for_menu(_request())

    assert not [
        record
        for record in caplog.records
        if "context_menu_snapshot.prepared_concern_unavailable" in record.getMessage()
    ]


def test_context_menu_snapshot_omits_scene_actions_when_position_context_is_stale() -> (
    None
):
    """Missing prepared scene-position context should not compute on menu open."""

    snapshot = _controller(
        scene_position_ready=False,
        scene_position_stale=True,
        scene_position_unavailable_reason="scene_position_context_unprepared",
    ).snapshot_for_menu(_request())

    scene = snapshot.readiness.concern(PromptContextMenuConcern.SCENE)

    assert snapshot.actions.queue_scene_key is None
    assert snapshot.actions.effective_prompt_text == ""
    assert snapshot.actions.lora_trigger_word_actions == ()
    assert scene.ready is False
    assert scene.stale is True
    assert scene.unavailable_reason == "scene_position_context_unprepared"
    lora = snapshot.readiness.concern(PromptContextMenuConcern.LORA)
    assert lora.ready is False
    assert lora.stale is False
    assert lora.unavailable_reason == "scene_position_context_unprepared"


def test_context_menu_snapshot_consumes_prepared_lora_actions() -> None:
    """LoRA trigger-word rows should come from prepared action snapshots only."""

    snapshot = _controller().snapshot_for_menu(_request())

    lora = snapshot.readiness.concern(PromptContextMenuConcern.LORA)

    assert lora.ready is True
    assert len(snapshot.actions.lora_trigger_word_actions) == 1
    action = snapshot.actions.lora_trigger_word_actions[0]
    assert action.command_request is not None
    assert action.command_request.payload.insertion_text == "scene prompt"


def test_context_menu_snapshot_consumes_prepared_diagnostic_actions() -> None:
    """Diagnostic rows should come from prepared action snapshots only."""

    snapshot = _controller().snapshot_for_menu(_request())

    diagnostics = snapshot.readiness.concern(PromptContextMenuConcern.DIAGNOSTICS)

    assert [action.label for action in snapshot.actions.diagnostic_actions] == ["Fix"]
    assert diagnostics.ready is True
    assert diagnostics.unavailable_reason is None


def test_context_menu_snapshot_marks_stale_diagnostic_action_snapshot() -> None:
    """Stale diagnostic action snapshots should omit diagnostic menu rows."""

    snapshot = _controller(
        diagnostic_action_ready=False,
        diagnostic_action_stale=True,
        diagnostic_action_unavailable_reason="stale_diagnostics_snapshot",
    ).snapshot_for_menu(_request())

    diagnostics = snapshot.readiness.concern(PromptContextMenuConcern.DIAGNOSTICS)

    assert snapshot.actions.diagnostic_actions == ()
    assert diagnostics.ready is False
    assert diagnostics.stale is True
    assert diagnostics.unavailable_reason == "stale_diagnostics_snapshot"


def _controller(
    *,
    source_revision: int = 42,
    feature_profile_id: Hashable = "profile-a",
    cube_context_id: Hashable = "cube-a",
    scene_context_id: Hashable = "scene-a",
    scene_position_ready: bool = True,
    scene_position_stale: bool = False,
    scene_position_unavailable_reason: str | None = None,
    diagnostics_stale: bool = False,
    diagnostic_action_ready: bool = True,
    diagnostic_action_stale: bool = False,
    diagnostic_action_unavailable_reason: str | None = None,
    lora_catalog_revision: Hashable | None = "lora-catalog-1",
    lora_unavailable_reason: str | None = None,
    segment_catalog_revision: Hashable | None = "segment-catalog-1",
    segment_status: CatalogSnapshotStatus | None = None,
    danbooru_source_revision: int = 42,
) -> PromptContextMenuSnapshotController:
    """Return a context-menu snapshot controller with fake collaborators."""

    scene_identity = PromptFeatureSnapshotIdentity(
        source_revision=source_revision,
        feature_profile_id=feature_profile_id,
        scene_context_id=scene_context_id,
        cube_context_id=cube_context_id,
    )
    lora = _LoraMetadata(
        identity=PromptFeatureSnapshotIdentity(
            source_revision=source_revision,
            feature_profile_id=feature_profile_id,
        ),
        catalog_revision=lora_catalog_revision,
        unavailable_reason=lora_unavailable_reason,
    )
    return PromptContextMenuSnapshotController(
        diagnostics=cast(
            PromptContextMenuDiagnosticsPort,
            _Diagnostics(
                identity=PromptFeatureSnapshotIdentity(
                    source_revision=source_revision,
                    feature_profile_id=feature_profile_id,
                    stale=diagnostics_stale,
                ),
                action_ready=diagnostic_action_ready,
                action_stale=diagnostic_action_stale,
                action_unavailable_reason=diagnostic_action_unavailable_reason,
            ),
        ),
        lora_metadata=cast(
            PromptContextMenuLoraMetadataPort,
            lora,
        ),
        lora_trigger_words=cast(PromptContextMenuLoraTriggerWordPort, lora),
        scene=cast(
            PromptContextMenuScenePort,
            _Scene(
                identity=scene_identity,
                position_ready=scene_position_ready,
                position_stale=scene_position_stale,
                position_unavailable_reason=scene_position_unavailable_reason,
            ),
        ),
        segment_presets=cast(
            PromptContextMenuSegmentPort,
            _Segments(
                identity=PromptFeatureSnapshotIdentity(
                    source_revision=source_revision,
                    feature_profile_id=feature_profile_id,
                ),
                catalog_identity=CatalogSnapshotIdentity(
                    source_revision=source_revision,
                    feature_profile_id=feature_profile_id,
                    catalog_revision=segment_catalog_revision,
                ),
                status=segment_status,
            ),
        ),
        danbooru=cast(
            PromptContextMenuDanbooruPort,
            _Danbooru(
                identity=PromptFeatureSnapshotIdentity(
                    source_revision=danbooru_source_revision,
                    feature_profile_id=feature_profile_id,
                )
            ),
        ),
        source_identity_provider=lambda: PromptCommandSourceIdentity(
            source_revision=source_revision,
            source_length=100,
        ),
        feature_profile_id_provider=lambda: feature_profile_id,
    )


def _request() -> PromptContextMenuSnapshotRequest:
    """Return the default request used by snapshot identity tests."""

    return PromptContextMenuSnapshotRequest(
        source_position=12,
        selected_text="selected prompt",
        selection_range=(2, 17),
        read_only=False,
        rich_prompt_rendering_enabled=True,
    )

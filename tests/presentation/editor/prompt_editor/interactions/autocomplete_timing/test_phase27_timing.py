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

"""Baseline Phase 27 autocomplete behavior before SOC extraction."""

from __future__ import annotations


from typing import Any, cast

from PySide6.QtCore import Qt

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.domain.prompt.features.models import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptAutocompleteQueryController,
    PromptAutocompleteQueryResultLifecycle,
    PromptFeatureProfileController,
)
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_timing import (
    PromptAutocompleteSourceSnapshotController,
    PromptAutocompleteTimingController,
)


from tests.presentation.editor.prompt_editor.autocomplete.phase27_support import (
    _FakeTimer,
    _QueryEditor,
    _TimingPublication,
    _TimingResultController,
    _TimingSceneContextController,
    _key_event,
)


def test_phase27_query_timing_preserves_debounce_selection_and_lora_prefix() -> None:
    """Timing should coalesce refreshes and route query precedence through snapshots."""

    editor = _QueryEditor("<lo")
    publication = _TimingPublication()
    fake_timer = _FakeTimer()
    feature_profile = PromptFeatureProfileController(
        PromptEditorFeatureProfile.enabled_profile(
            (
                PromptEditorFeature.LORA_AUTOCOMPLETE,
                PromptEditorFeature.WILDCARD_AUTOCOMPLETE,
            )
        )
    )
    query_refresh = PromptAutocompleteQueryResultLifecycle(
        query_controller=PromptAutocompleteQueryController(
            document_service=PromptDocumentService(),
            feature_profile=feature_profile,
            minimum_prefix_length=2,
        ),
        result_controller=cast(Any, _TimingResultController()),
        scene_context_controller=cast(Any, _TimingSceneContextController()),
        publication=cast(Any, publication),
        current_source_identity=editor.prompt_command_source_identity,
        lora_autocomplete_enabled=lambda: feature_profile.lora_autocomplete_enabled,
        lora_thumbnail_cache_available=lambda: False,
    )
    source_snapshots = PromptAutocompleteSourceSnapshotController(
        cursor_state=lambda: (
            (cursor := editor.textCursor()).position(),
            cursor.hasSelection(),
        ),
        document_view_provider=lambda: PromptDocumentService().build_document_view(
            editor.text
        ),
        feature_profile=feature_profile,
        source_identity=editor.prompt_command_source_identity,
        source_text=editor.toPlainText,
    )
    controller = PromptAutocompleteTimingController(
        source_snapshots=source_snapshots,
        lifecycle_requester=query_refresh,
        lora_autocomplete_enabled=lambda: feature_profile.lora_autocomplete_enabled,
        timer_factory=lambda: cast(Any, fake_timer),
    )

    controller.handle_post_key_press(_key_event(Qt.Key.Key_O))

    assert fake_timer.started_delays == [0]

    fake_timer.fire()

    assert publication.published[-1][0].mode == "tag"
    assert editor.text_reads >= 1

    editor.text = "alpha"
    editor.cursor_position = len("alpha")
    controller.schedule_caret_refresh()
    controller.schedule_caret_refresh()

    assert fake_timer.started_delays[-2:] == [
        controller.caret_settle_delay_ms,
        controller.caret_settle_delay_ms,
    ]

    lifecycle_transition_count = len(publication.published) + len(publication.dismissed)
    fake_timer.fire()

    assert len(publication.published) + len(publication.dismissed) == (
        lifecycle_transition_count + 1
    )
    assert publication.dismissed[-1] == "no_query"

    selected_editor = _QueryEditor("<lora:mid", has_selection=True)
    selected_publication = _TimingPublication()
    selected_feature_profile = PromptFeatureProfileController(
        PromptEditorFeatureProfile.enabled_profile(
            (PromptEditorFeature.LORA_AUTOCOMPLETE,)
        )
    )
    selected_query_refresh = PromptAutocompleteQueryResultLifecycle(
        query_controller=PromptAutocompleteQueryController(
            document_service=PromptDocumentService(),
            feature_profile=selected_feature_profile,
            minimum_prefix_length=2,
        ),
        result_controller=cast(Any, _TimingResultController()),
        scene_context_controller=cast(Any, _TimingSceneContextController()),
        publication=cast(Any, selected_publication),
        current_source_identity=selected_editor.prompt_command_source_identity,
        lora_autocomplete_enabled=(
            lambda: selected_feature_profile.lora_autocomplete_enabled
        ),
        lora_thumbnail_cache_available=lambda: False,
    )
    selected_source_snapshots = PromptAutocompleteSourceSnapshotController(
        cursor_state=lambda: (
            (cursor := selected_editor.textCursor()).position(),
            cursor.hasSelection(),
        ),
        document_view_provider=lambda: PromptDocumentService().build_document_view(
            selected_editor.text
        ),
        feature_profile=selected_feature_profile,
        source_identity=selected_editor.prompt_command_source_identity,
        source_text=selected_editor.toPlainText,
    )
    selected_controller = PromptAutocompleteTimingController(
        source_snapshots=selected_source_snapshots,
        lifecycle_requester=selected_query_refresh,
        lora_autocomplete_enabled=(
            lambda: selected_feature_profile.lora_autocomplete_enabled
        ),
        timer_factory=lambda: cast(Any, _FakeTimer()),
    )

    selected_controller.refresh_from_current_state()

    assert selected_publication.published == []
    assert selected_publication.dismissed == ["no_query"]

    controller.clear_for_non_text_interaction()

    assert fake_timer.stop_calls == 1
    assert publication.dismissed[-1] == "incompatible_query"

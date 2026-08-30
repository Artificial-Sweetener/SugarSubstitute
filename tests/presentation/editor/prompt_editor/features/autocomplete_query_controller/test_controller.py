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

"""Verify prompt autocomplete query construction ownership."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from substitute.application.prompt_editor.autocomplete.queries import (
    PromptAutocompleteFallbackQuery,
    PromptAutocompleteQuery,
    PromptSceneAutocompleteQuery,
    PromptWildcardAutocompleteQuery,
)
from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.lora.autocomplete import (
    PromptLoraAutocompleteQuery,
)
from substitute.domain.prompt.features.models import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptAutocompleteQueryController,
    PromptAutocompleteQueryState,
    PromptFeatureProfileController,
    PromptFeatureSnapshotIdentity,
)
from substitute.presentation.editor.prompt_editor.autocomplete_refresh_intent import (
    PromptAutocompleteRefreshIntent,
)


@dataclass(frozen=True, slots=True)
class _SourceSnapshot:
    """Provide prepared source state for query-controller tests."""

    source_revision: int
    source_length: int
    source_text: str
    cursor_position: int
    has_selection: bool
    source_identity: object | None
    document_view: PromptDocumentView
    feature_profile_identity: PromptFeatureSnapshotIdentity
    refresh_intent: PromptAutocompleteRefreshIntent = "programmatic"


@dataclass(frozen=True, slots=True)
class _QueryCall:
    """Record one fake document-service query call."""

    kind: str
    text: str
    cursor_position: int
    has_selection: bool
    document_view: PromptDocumentView | None = None
    minimum_prefix_length: int | None = None


class _FakeDocumentService:
    """Return deterministic query results while recording query construction calls."""

    def __init__(self) -> None:
        """Initialize empty fake results and call history."""

        self.calls: list[_QueryCall] = []
        self.tag_query: PromptAutocompleteQuery | None = None
        self.lora_query: PromptLoraAutocompleteQuery | None = None
        self.wildcard_query: PromptWildcardAutocompleteQuery | None = None
        self.scene_query: PromptSceneAutocompleteQuery | None = None

    def lora_autocomplete_query_at_cursor(
        self,
        *,
        text: str,
        cursor_position: int,
        has_selection: bool,
    ) -> PromptLoraAutocompleteQuery | None:
        """Record and return the configured LoRA query."""

        self.calls.append(
            _QueryCall("lora", text, cursor_position, has_selection),
        )
        return self.lora_query

    def wildcard_autocomplete_query_at_cursor(
        self,
        *,
        text: str,
        cursor_position: int,
        has_selection: bool,
    ) -> PromptWildcardAutocompleteQuery | None:
        """Record and return the configured wildcard query."""

        self.calls.append(
            _QueryCall("wildcard", text, cursor_position, has_selection),
        )
        return self.wildcard_query

    def scene_autocomplete_query_at_cursor(
        self,
        *,
        text: str,
        cursor_position: int,
        has_selection: bool,
    ) -> PromptSceneAutocompleteQuery | None:
        """Record and return the configured scene query."""

        self.calls.append(
            _QueryCall("scene", text, cursor_position, has_selection),
        )
        return self.scene_query

    def autocomplete_query_at_cursor(
        self,
        document_view: PromptDocumentView,
        *,
        text: str,
        cursor_position: int,
        has_selection: bool,
        minimum_prefix_length: int,
    ) -> PromptAutocompleteQuery | None:
        """Record and return the configured tag query."""

        self.calls.append(
            _QueryCall(
                "tag",
                text,
                cursor_position,
                has_selection,
                document_view=document_view,
                minimum_prefix_length=minimum_prefix_length,
            ),
        )
        return self.tag_query


def _feature_profile(
    *features: PromptEditorFeature,
) -> PromptFeatureProfileController:
    """Return a feature-profile controller with selected features enabled."""

    return PromptFeatureProfileController(
        PromptEditorFeatureProfile.enabled_profile(features),
    )


def _snapshot(
    feature_profile: PromptFeatureProfileController,
    *,
    text: str = "alpha beta gamma",
    cursor_position: int = 10,
    has_selection: bool = False,
    source_identity: object | None = None,
) -> _SourceSnapshot:
    """Return a source snapshot using a real document view for identity checks."""

    document_view = PromptDocumentService().build_document_view(text)
    return _SourceSnapshot(
        source_revision=42,
        source_length=len(text),
        source_text=text,
        cursor_position=cursor_position,
        has_selection=has_selection,
        source_identity=source_identity,
        document_view=document_view,
        feature_profile_identity=feature_profile.identity,
    )


def _controller(
    service: _FakeDocumentService,
    feature_profile: PromptFeatureProfileController,
    *,
    minimum_prefix_length: int = 3,
) -> PromptAutocompleteQueryController:
    """Return a query controller backed by the fake document service."""

    return PromptAutocompleteQueryController(
        document_service=cast(PromptDocumentService, service),
        feature_profile=feature_profile,
        minimum_prefix_length=minimum_prefix_length,
    )


def _lora_query() -> PromptLoraAutocompleteQuery:
    """Return a deterministic LoRA autocomplete query."""

    return PromptLoraAutocompleteQuery(
        query_text="mid",
        token_start=0,
        token_end=10,
        name_start=6,
        name_end=9,
        replacement_start=0,
        replacement_end=10,
        typed_weight_text=None,
        has_closing_bracket=False,
    )


def _wildcard_query() -> PromptWildcardAutocompleteQuery:
    """Return a deterministic wildcard autocomplete query."""

    return PromptWildcardAutocompleteQuery(
        prefix="land",
        opener_start=0,
        content_start=1,
        cursor_position=5,
        replacement_end=5,
    )


def _scene_query() -> PromptSceneAutocompleteQuery:
    """Return a deterministic scene autocomplete query."""

    return PromptSceneAutocompleteQuery(
        prefix="intro",
        marker_start=0,
        title_start=8,
        cursor_position=13,
        replacement_end=13,
    )


def _query_state(
    *,
    tag_query: PromptAutocompleteQuery | None = None,
    lora_query: PromptLoraAutocompleteQuery | None = None,
    wildcard_query: PromptWildcardAutocompleteQuery | None = None,
    scene_query: PromptSceneAutocompleteQuery | None = None,
) -> PromptAutocompleteQueryState:
    """Return a prepared query state for refresh-routing tests."""

    return PromptAutocompleteQueryState(
        source_revision=7,
        source_length=11,
        source_text="source text",
        cursor_position=5,
        has_selection=False,
        query_identity=("query", 1),
        tag_query=tag_query,
        lora_query=lora_query,
        wildcard_query=wildcard_query,
        scene_query=scene_query,
    )


def test_query_controller_builds_lora_query_first() -> None:
    """LoRA autocomplete takes precedence over every other query kind."""

    service = _FakeDocumentService()
    service.lora_query = _lora_query()
    service.wildcard_query = _wildcard_query()
    service.scene_query = _scene_query()
    service.tag_query = PromptAutocompleteQuery(
        prefix="alp",
        word_start=0,
        word_end=3,
        active_tag_end=5,
    )
    feature_profile = _feature_profile(
        PromptEditorFeature.LORA_AUTOCOMPLETE,
        PromptEditorFeature.WILDCARD_AUTOCOMPLETE,
    )

    state = _controller(service, feature_profile).query_state_from_source_snapshot(
        _snapshot(feature_profile),
    )

    assert state.lora_query == service.lora_query
    assert state.query_identity == ("lora", "mid")
    assert [call.kind for call in service.calls] == ["lora"]


def test_query_controller_builds_wildcard_before_scene_and_tag() -> None:
    """Wildcard autocomplete takes precedence after absent LoRA queries."""

    service = _FakeDocumentService()
    service.wildcard_query = _wildcard_query()
    service.scene_query = _scene_query()
    feature_profile = _feature_profile(
        PromptEditorFeature.LORA_AUTOCOMPLETE,
        PromptEditorFeature.WILDCARD_AUTOCOMPLETE,
    )

    state = _controller(service, feature_profile).query_state_from_source_snapshot(
        _snapshot(feature_profile),
    )

    assert state.wildcard_query == service.wildcard_query
    assert state.query_identity == ("wildcard", "land")
    assert [call.kind for call in service.calls] == ["lora", "wildcard"]


def test_query_controller_builds_scene_before_tag() -> None:
    """Scene autocomplete takes precedence after absent LoRA and wildcard queries."""

    service = _FakeDocumentService()
    service.scene_query = _scene_query()
    feature_profile = _feature_profile(
        PromptEditorFeature.LORA_AUTOCOMPLETE,
        PromptEditorFeature.WILDCARD_AUTOCOMPLETE,
    )

    state = _controller(service, feature_profile).query_state_from_source_snapshot(
        _snapshot(feature_profile),
    )

    assert state.scene_query == service.scene_query
    assert state.query_identity == ("scene", "intro")
    assert [call.kind for call in service.calls] == ["lora", "wildcard", "scene"]


def test_query_controller_builds_tag_query_with_minimum_prefix_and_view() -> None:
    """Tag fallback uses the prepared document view and configured prefix length."""

    service = _FakeDocumentService()
    fallback_query = PromptAutocompleteFallbackQuery(
        prefix="bet",
        word_start=6,
        word_end=9,
        active_tag_end=10,
    )
    service.tag_query = PromptAutocompleteQuery(
        prefix="gam",
        word_start=11,
        word_end=14,
        active_tag_end=16,
        fallback_query=fallback_query,
    )
    feature_profile = _feature_profile(
        PromptEditorFeature.LORA_AUTOCOMPLETE,
        PromptEditorFeature.WILDCARD_AUTOCOMPLETE,
    )
    snapshot = _snapshot(feature_profile)

    state = _controller(
        service,
        feature_profile,
        minimum_prefix_length=4,
    ).query_state_from_source_snapshot(snapshot)

    assert state.tag_query == service.tag_query
    assert state.tag_query is not None
    assert state.tag_query.fallback_query == fallback_query
    assert state.query_identity == ("tag", "gam", 11, 14, 16)
    assert [call.kind for call in service.calls] == [
        "lora",
        "wildcard",
        "scene",
        "tag",
    ]
    tag_call = service.calls[-1]
    assert tag_call.document_view is snapshot.document_view
    assert tag_call.minimum_prefix_length == 4


def test_query_controller_skips_disabled_lora_and_wildcard_queries() -> None:
    """Disabled feature gates prevent LoRA and wildcard query construction."""

    service = _FakeDocumentService()
    service.scene_query = _scene_query()
    feature_profile = _feature_profile()

    state = _controller(service, feature_profile).query_state_from_source_snapshot(
        _snapshot(feature_profile),
    )

    assert state.scene_query == service.scene_query
    assert [call.kind for call in service.calls] == ["scene"]


def test_query_controller_preserves_selection_behavior_in_service_calls() -> None:
    """Selection state is passed through so document-service rules remain canonical."""

    service = _FakeDocumentService()
    feature_profile = _feature_profile(
        PromptEditorFeature.LORA_AUTOCOMPLETE,
        PromptEditorFeature.WILDCARD_AUTOCOMPLETE,
    )

    state = _controller(service, feature_profile).query_state_from_source_snapshot(
        _snapshot(feature_profile, has_selection=True),
    )

    assert state.has_selection is True
    assert state.query_identity is None
    assert state.tag_query is None
    assert [call.kind for call in service.calls] == [
        "lora",
        "wildcard",
        "scene",
        "tag",
    ]
    assert all(call.has_selection for call in service.calls)


def test_query_controller_preserves_source_and_feature_identity() -> None:
    """Query state carries source and feature identity for stale rejection."""

    service = _FakeDocumentService()
    service.tag_query = PromptAutocompleteQuery(
        prefix="bet",
        word_start=6,
        word_end=9,
        active_tag_end=10,
    )
    source_identity = object()
    feature_profile = _feature_profile()
    snapshot = _snapshot(
        feature_profile,
        text="alpha beta gamma",
        cursor_position=9,
        source_identity=source_identity,
    )

    state = _controller(service, feature_profile).query_state_from_source_snapshot(
        snapshot,
    )

    assert state.source_revision == snapshot.source_revision
    assert state.source_length == snapshot.source_length
    assert state.cursor_position == snapshot.cursor_position
    assert state.source_identity is source_identity
    assert state.feature_profile_identity == feature_profile.identity
    assert state.refresh_intent == "programmatic"
    assert state.query_identity == ("tag", "bet", 6, 9, 10)


def test_query_controller_uses_prompt_safe_query_identity() -> None:
    """Query identity must not contain the full prompt text."""

    service = _FakeDocumentService()
    service.tag_query = PromptAutocompleteQuery(
        prefix="bet",
        word_start=6,
        word_end=9,
        active_tag_end=10,
    )
    feature_profile = _feature_profile()
    source_text = "alpha beta gamma"

    state = _controller(service, feature_profile).query_state_from_source_snapshot(
        _snapshot(feature_profile, text=source_text, cursor_position=9),
    )

    assert state.query_identity is not None
    assert source_text not in repr(state.query_identity)

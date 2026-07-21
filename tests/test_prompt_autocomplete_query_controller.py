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

"""Verify Phase 27.3 pure autocomplete query construction ownership."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from PySide6.QtCore import Qt

from substitute.application.prompt_editor import (
    PromptAutocompleteFallbackQuery,
    PromptAutocompleteQuery,
    PromptDocumentService,
    PromptDocumentView,
    PromptEditorFeature,
    PromptEditorFeatureProfile,
    PromptLoraAutocompleteQuery,
    PromptSceneAutocompleteQuery,
    PromptWildcardAutocompleteQuery,
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
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_controller import (
    PromptAutocompleteQueryRefreshController,
)
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_timing import (
    PromptAutocompleteRefreshTimer,
    PromptAutocompleteSourceSnapshot,
    PromptAutocompleteSourceSnapshotController,
    PromptAutocompleteTimingController,
)
from tests.prompt_editor_controller_test_helpers import key_event


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


class _FakeTimeoutSignal:
    """Record one timeout callback for deterministic timer tests."""

    def __init__(self) -> None:
        """Initialize an empty signal double."""

        self.callback: Callable[[], None] | None = None

    def connect(self, callback: Callable[[], None]) -> None:
        """Store the timeout callback."""

        self.callback = callback

    def emit(self) -> None:
        """Run the connected callback."""

        assert self.callback is not None
        self.callback()


class _FakeRefreshTimer:
    """Provide a deterministic refresh timer for timing-controller tests."""

    def __init__(self) -> None:
        """Initialize timer state."""

        self.timeout = _FakeTimeoutSignal()
        self.single_shot = False
        self.started_intervals: list[int] = []
        self.stop_calls = 0

    def setSingleShot(self, single_shot: bool) -> None:  # noqa: N802
        """Record single-shot configuration."""

        self.single_shot = single_shot

    def start(self, delay_ms: int) -> None:
        """Record one start interval."""

        self.started_intervals.append(delay_ms)

    def stop(self) -> None:
        """Record one cancellation."""

        self.stop_calls += 1

    def fire(self) -> None:
        """Trigger the connected timeout callback."""

        self.timeout.emit()


class _TimingCursor:
    """Expose cursor position and selection state for timing tests."""

    def __init__(self, *, position: int, has_selection: bool = False) -> None:
        """Store cursor state."""

        self._position = position
        self._has_selection = has_selection

    def position(self) -> int:
        """Return the configured cursor position."""

        return self._position

    def hasSelection(self) -> bool:  # noqa: N802
        """Return whether the cursor has a selection."""

        return self._has_selection


class _TimingEditor:
    """Expose prompt text without projection-flush behavior for timing tests."""

    def __init__(self, text: str) -> None:
        """Store prompt text and initialize flush accounting."""

        self.text = text
        self.flush_calls: list[str] = []

    def toPlainText(self) -> str:  # noqa: N802
        """Return the configured prompt text."""

        return self.text

    def textCursor(self) -> _TimingCursor:  # noqa: N802
        """Return a cursor at the end of the prompt text."""

        return _TimingCursor(position=len(self.text))

    def prompt_command_source_identity(self) -> None:
        """Return no source identity for timing tests."""

        return None

    def flush_pending_projection_update(self, *, reason: str) -> None:
        """Record unexpected projection flushes."""

        self.flush_calls.append(reason)


class _LifecycleRequester:
    """Record lifecycle snapshots requested by timing tests."""

    def __init__(self) -> None:
        """Initialize snapshot accounting."""

        self.retarget_snapshots: list[PromptAutocompleteSourceSnapshot] = []
        self.refresh_snapshots: list[PromptAutocompleteSourceSnapshot] = []
        self.dismiss_reasons: list[str] = []

    def retarget_from_source_snapshot(
        self,
        snapshot: PromptAutocompleteSourceSnapshot,
    ) -> bool:
        """Record one retarget snapshot."""

        self.retarget_snapshots.append(snapshot)
        return True

    def refresh_results_from_source_snapshot(
        self,
        snapshot: PromptAutocompleteSourceSnapshot,
    ) -> None:
        """Record one snapshot refresh."""

        self.refresh_snapshots.append(snapshot)

    def dismiss_autocomplete(self, reason: str) -> None:
        """Record one dismiss reason."""

        self.dismiss_reasons.append(reason)


class _FakeQueryController:
    """Return a prepared query state while recording supplied snapshots."""

    def __init__(self, state: PromptAutocompleteQueryState) -> None:
        """Store the query state returned to the refresh controller."""

        self.state = state
        self.snapshots: list[object] = []

    def query_state_from_source_snapshot(
        self,
        snapshot: object,
    ) -> PromptAutocompleteQueryState:
        """Record the source snapshot and return the configured state."""

        self.snapshots.append(snapshot)
        return self.state


class _AutocompleteTarget:
    """Record query-refresh routing into the autocomplete coordinator API."""

    def __init__(self, *, active_session: bool = False) -> None:
        """Initialize call accounting."""

        self.active_session = active_session
        self.tag_calls: list[tuple[PromptAutocompleteQuery | None, str]] = []
        self.lora_calls: list[PromptLoraAutocompleteQuery] = []
        self.wildcard_calls: list[PromptWildcardAutocompleteQuery] = []
        self.scene_calls: list[PromptSceneAutocompleteQuery] = []
        self.retargeted_states: list[PromptAutocompleteQueryState] = []
        self.dismiss_reasons: list[str] = []

    def has_active_session(self) -> bool:
        """Return whether retargeting has an active autocomplete consumer."""

        return self.active_session

    def refresh_for_query(
        self,
        query: PromptAutocompleteQuery | None,
        *,
        source_text: str,
        **_kwargs: Any,
    ) -> None:
        """Record one tag-query refresh."""

        self.tag_calls.append((query, source_text))

    def refresh_for_lora_query(
        self,
        query: PromptLoraAutocompleteQuery,
        **_kwargs: Any,
    ) -> None:
        """Record one LoRA-query refresh."""

        self.lora_calls.append(query)

    def refresh_for_wildcard_query(
        self,
        query: PromptWildcardAutocompleteQuery,
        **_kwargs: Any,
    ) -> None:
        """Record one wildcard-query refresh."""

        self.wildcard_calls.append(query)

    def refresh_for_scene_query(
        self,
        query: PromptSceneAutocompleteQuery,
        **_kwargs: Any,
    ) -> None:
        """Record one scene-query refresh."""

        self.scene_calls.append(query)

    def retarget_from_query_state(
        self,
        query_state: PromptAutocompleteQueryState,
    ) -> bool:
        """Record one lifecycle retarget request."""

        self.retargeted_states.append(query_state)
        return True

    def dismiss_autocomplete(self, reason: str) -> None:
        """Record one autocomplete dismissal."""

        self.dismiss_reasons.append(reason)


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


def _timing_controller(
    editor: _TimingEditor,
    *,
    lifecycle: _LifecycleRequester,
    timers: list[_FakeRefreshTimer],
    lora_enabled: bool = False,
) -> PromptAutocompleteTimingController:
    """Return an autocomplete timing controller backed by deterministic fakes."""

    feature_profile = (
        _feature_profile(PromptEditorFeature.LORA_AUTOCOMPLETE)
        if lora_enabled
        else _feature_profile()
    )
    document_view = PromptDocumentService().build_document_view(editor.text)

    def timer_factory() -> PromptAutocompleteRefreshTimer:
        """Create and record one fake timer."""

        timer = _FakeRefreshTimer()
        timers.append(timer)
        return cast(PromptAutocompleteRefreshTimer, timer)

    return PromptAutocompleteTimingController(
        source_snapshots=PromptAutocompleteSourceSnapshotController(
            editor,
            document_view_provider=lambda: document_view,
            feature_profile=feature_profile,
        ),
        lifecycle_requester=lifecycle,
        lora_autocomplete_enabled=lambda: lora_enabled,
        timer_factory=timer_factory,
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


def test_timing_post_key_refresh_uses_prepared_snapshot_without_projection_flush() -> (
    None
):
    """Post-key refresh uses source snapshots without flushing projection work."""

    editor = _TimingEditor("1girl, blue")
    lifecycle = _LifecycleRequester()
    timers: list[_FakeRefreshTimer] = []
    controller = _timing_controller(
        editor,
        lifecycle=lifecycle,
        timers=timers,
    )

    controller.handle_post_key_press(key_event(Qt.Key.Key_E, text="e"))

    assert lifecycle.refresh_snapshots == []
    assert len(timers) == 1
    assert timers[-1].started_intervals == [0]

    timers[-1].fire()

    assert lifecycle.refresh_snapshots[-1].source_text == "1girl, blue"
    assert lifecycle.refresh_snapshots[-1].cursor_position == len("1girl, blue")
    assert lifecycle.refresh_snapshots[-1].refresh_intent == "typing"
    assert editor.flush_calls == []


def test_timing_navigation_key_clears_without_reopening_autocomplete() -> None:
    """Caret-navigation keys dismiss autocomplete without scheduling refresh work."""

    editor = _TimingEditor("1girl, blue")
    lifecycle = _LifecycleRequester()
    timers: list[_FakeRefreshTimer] = []
    controller = _timing_controller(
        editor,
        lifecycle=lifecycle,
        timers=timers,
    )

    controller.handle_post_key_press(key_event(Qt.Key.Key_Right))

    assert lifecycle.dismiss_reasons == ["caret_left_query"]
    assert lifecycle.refresh_snapshots == []
    assert timers == []


def test_timing_backspace_retargets_and_debounces_autocomplete_refresh() -> None:
    """Backspace retargets active autocomplete and delays heavy result refresh."""

    editor = _TimingEditor("1girl, blue")
    lifecycle = _LifecycleRequester()
    timers: list[_FakeRefreshTimer] = []
    controller = _timing_controller(
        editor,
        lifecycle=lifecycle,
        timers=timers,
    )

    controller.handle_post_key_press(key_event(Qt.Key.Key_Backspace))

    assert lifecycle.retarget_snapshots[-1].query_reason == "edit_retarget"
    assert lifecycle.dismiss_reasons == []
    assert lifecycle.refresh_snapshots == []
    assert timers[-1].started_intervals == [controller.edit_settle_delay_ms]

    timers[-1].fire()

    assert lifecycle.refresh_snapshots[-1].source_text == "1girl, blue"
    assert lifecycle.refresh_snapshots[-1].refresh_intent == "typing"


def test_timing_lora_prefix_refreshes_without_edit_delay() -> None:
    """Unclosed LoRA prefix edits refresh immediately when LoRA autocomplete is enabled."""

    for text in ("<", "<l", "<lora:"):
        editor = _TimingEditor(text)
        lifecycle = _LifecycleRequester()
        timers: list[_FakeRefreshTimer] = []
        controller = _timing_controller(
            editor,
            lifecycle=lifecycle,
            timers=timers,
            lora_enabled=True,
        )

        controller.handle_post_key_press(key_event(Qt.Key.Key_A, text=text[-1]))

        assert timers[-1].started_intervals == [0]


def test_query_refresh_routes_lora_before_tag_autocomplete() -> None:
    """Query refresh gives LoRA query state priority over tag query state."""

    tag_query = PromptAutocompleteQuery(
        prefix="<lora:Civ",
        word_start=0,
        word_end=9,
        active_tag_end=9,
    )
    lora_query = _lora_query()
    target = _AutocompleteTarget()
    source_snapshot = object()
    query_controller = _FakeQueryController(
        _query_state(tag_query=tag_query, lora_query=lora_query)
    )

    PromptAutocompleteQueryRefreshController(
        autocomplete=cast(Any, target),
        query_controller=cast(Any, query_controller),
    ).refresh_results_from_source_snapshot(cast(Any, source_snapshot))

    assert query_controller.snapshots == [source_snapshot]
    assert target.lora_calls == [lora_query]
    assert target.tag_calls == []


def test_query_retarget_skips_query_construction_without_active_session() -> None:
    """Dormant autocomplete should stay out of the synchronous edit path."""

    target = _AutocompleteTarget(active_session=False)
    source_snapshot = object()
    query_controller = _FakeQueryController(_query_state())
    query_refresh = PromptAutocompleteQueryRefreshController(
        autocomplete=cast(Any, target),
        query_controller=cast(Any, query_controller),
    )

    retargeted = query_refresh.retarget_from_source_snapshot(cast(Any, source_snapshot))

    assert retargeted is False
    assert query_controller.snapshots == []
    assert target.retargeted_states == []


def test_query_retarget_builds_query_for_active_session() -> None:
    """Active autocomplete should still retarget on each compatible source edit."""

    target = _AutocompleteTarget(active_session=True)
    source_snapshot = object()
    query_state = _query_state()
    query_controller = _FakeQueryController(query_state)
    query_refresh = PromptAutocompleteQueryRefreshController(
        autocomplete=cast(Any, target),
        query_controller=cast(Any, query_controller),
    )

    retargeted = query_refresh.retarget_from_source_snapshot(cast(Any, source_snapshot))

    assert retargeted is True
    assert query_controller.snapshots == [source_snapshot]
    assert target.retargeted_states == [query_state]


def test_query_refresh_routes_wildcard_before_tag_autocomplete() -> None:
    """Query refresh gives wildcard query state priority over tag query state."""

    tag_query = PromptAutocompleteQuery(
        prefix="{",
        word_start=0,
        word_end=1,
        active_tag_end=1,
    )
    wildcard_query = _wildcard_query()
    target = _AutocompleteTarget()
    query_controller = _FakeQueryController(
        _query_state(tag_query=tag_query, wildcard_query=wildcard_query)
    )

    PromptAutocompleteQueryRefreshController(
        autocomplete=cast(Any, target),
        query_controller=cast(Any, query_controller),
    ).refresh_results_from_source_snapshot(cast(Any, object()))

    assert target.wildcard_calls == [wildcard_query]
    assert target.tag_calls == []

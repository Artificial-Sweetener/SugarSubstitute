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

from collections.abc import Callable, Hashable
from typing import Any, cast

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor import (
    PromptAutocompleteFallbackQuery,
    PromptAutocompleteQuery,
    PromptDocumentService,
    PromptEditorFeature,
    PromptEditorFeatureProfile,
    PromptLoraAutocompleteCandidate,
    PromptLoraAutocompleteQuery,
    PromptLoraCatalogItem,
    PromptScheduledLora,
)
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptAsyncRequest,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptEditorCancellationToken,
    PromptEditorTaskHandle,
    PromptScheduledLoraContextCoordinator,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandResult,
    PromptCommandSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptAutocompleteQueryController,
    PromptAutocompleteResultController,
    PromptAutocompleteResultSnapshot,
    PromptAutocompleteResultSourceIdentity,
    PromptAutocompleteTagContext,
    PromptAutocompleteTriggerWordResult,
    PromptFeatureProfileController,
)
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_controller import (
    PromptAutocompleteQueryRefreshController,
)
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_acceptance import (
    PromptAutocompleteAcceptanceController,
)
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_session import (
    PromptAutocompleteSessionController,
)
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_timing import (
    PromptAutocompleteSourceSnapshotController,
    PromptAutocompleteTimingController,
)
from substitute.presentation.editor.prompt_editor.models import AutocompleteSession
from tests.prompt_autocomplete_test_helpers import (
    RecordingPromptAutocompleteGateway,
    build_test_autocomplete_coordinator,
)


class _Cursor:
    """Provide the minimal cursor API used by autocomplete timing tests."""

    def __init__(self, *, position: int, has_selection: bool = False) -> None:
        """Store deterministic cursor state."""

        self._position = position
        self._has_selection = has_selection

    def position(self) -> int:
        """Return the cursor position."""

        return self._position

    def hasSelection(self) -> bool:  # noqa: N802
        """Return whether this cursor carries a selection."""

        return self._has_selection


class _QueryEditor:
    """Expose source and cursor state to the autocomplete timing controller."""

    def __init__(self, text: str, *, has_selection: bool = False) -> None:
        """Store mutable source state."""

        self.text = text
        self.cursor_position = len(text)
        self.has_selection = has_selection
        self.source_revision = 0
        self.text_reads = 0

    def toPlainText(self) -> str:  # noqa: N802
        """Return source text while recording one read."""

        self.text_reads += 1
        return self.text

    def textCursor(self) -> _Cursor:  # noqa: N802
        """Return current cursor state."""

        return _Cursor(
            position=self.cursor_position,
            has_selection=self.has_selection,
        )

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity:
        """Return source identity for stale-safe query snapshots."""

        return PromptCommandSourceIdentity(
            source_revision=self.source_revision,
            source_length=len(self.text),
        )


class _AutocompleteRecorder:
    """Record autocomplete timing callbacks without rendering UI."""

    def __init__(self) -> None:
        """Initialize callback storage."""

        self.calls: list[
            tuple[str, object, PromptCommandSourceIdentity | None, str | None]
        ] = []
        self.clear_calls = 0
        self.clear_unfocused_calls = 0

    def refresh_for_lora_query(
        self,
        query: object,
        *,
        source_identity: PromptCommandSourceIdentity | None = None,
        ghost_text_source_snapshot: object | None = None,
        refresh_intent: object = "programmatic",
    ) -> None:
        """Record one LoRA query refresh."""

        _ = (ghost_text_source_snapshot, refresh_intent)
        self.calls.append(("lora", query, source_identity, None))

    def refresh_for_wildcard_query(
        self,
        query: object,
        *,
        source_identity: PromptCommandSourceIdentity | None = None,
        ghost_text_source_snapshot: object | None = None,
        refresh_intent: object = "programmatic",
    ) -> None:
        """Record one wildcard query refresh."""

        _ = (ghost_text_source_snapshot, refresh_intent)
        self.calls.append(("wildcard", query, source_identity, None))

    def refresh_for_scene_query(
        self,
        query: object,
        *,
        source_identity: PromptCommandSourceIdentity | None = None,
        ghost_text_source_snapshot: object | None = None,
        refresh_intent: object = "programmatic",
    ) -> None:
        """Record one scene query refresh."""

        _ = (ghost_text_source_snapshot, refresh_intent)
        self.calls.append(("scene", query, source_identity, None))

    def refresh_for_query(
        self,
        query: object,
        *,
        source_text: str,
        source_identity: PromptCommandSourceIdentity | None = None,
        feature_profile_identity: object | None = None,
        query_identity: Hashable | None = None,
        ghost_text_source_snapshot: object | None = None,
        refresh_intent: object = "programmatic",
    ) -> None:
        """Record one tag query refresh."""

        _ = (
            feature_profile_identity,
            query_identity,
            ghost_text_source_snapshot,
            refresh_intent,
        )
        self.calls.append(("tag", query, source_identity, source_text))

    def retarget_from_query_state(self, query_state: object) -> bool:
        """Accept one lifecycle retarget request."""

        _ = query_state
        return True

    def has_active_session(self) -> bool:
        """Report that the recorder has no mounted autocomplete session."""

        return False

    def dismiss_autocomplete(self, reason: object) -> None:
        """Record one presentation dismissal request."""

        _ = reason
        self.clear_calls += 1


class _FakeTimerSignal:
    """Expose a Qt-like signal connect method for fake timers."""

    def __init__(self, timer: "_FakeTimer") -> None:
        """Store the owning fake timer."""

        self._timer = timer

    def connect(self, callback: Callable[[], None]) -> None:
        """Record the timeout callback."""

        self._timer.callback = callback


class _FakeTimer:
    """Provide deterministic timer behavior for debounce tests."""

    def __init__(self) -> None:
        """Initialize timer state."""

        self.timeout = _FakeTimerSignal(self)
        self.callback: Callable[[], None] | None = None
        self.started_delays: list[int] = []
        self.stop_calls = 0
        self.single_shot = False

    def setSingleShot(self, single_shot: bool) -> None:  # noqa: N802
        """Record whether the timer is single-shot."""

        self.single_shot = single_shot

    def start(self, delay_ms: int) -> None:
        """Record one scheduled delay."""

        self.started_delays.append(delay_ms)

    def stop(self) -> None:
        """Record one cancellation."""

        self.stop_calls += 1

    def fire(self) -> None:
        """Run the recorded timeout callback."""

        if self.callback is not None:
            self.callback()


class _ScheduledLoraTaskHandle(PromptEditorTaskHandle[tuple[PromptScheduledLora, ...]]):
    """Store a scheduled-LoRA async request for deterministic completion."""

    def __init__(
        self,
        request: PromptAsyncRequest[tuple[PromptScheduledLora, ...]],
    ) -> None:
        """Store request state."""

        self.request = request
        self.callbacks: list[
            Callable[
                [PromptAsyncTaskOutcome[tuple[PromptScheduledLora, ...]]],
                None,
            ]
        ] = []
        self._outcome: (
            PromptAsyncTaskOutcome[tuple[PromptScheduledLora, ...]] | None
        ) = None

    @property
    def identity(self) -> PromptAsyncResultIdentity:
        """Return the request identity."""

        return self.request.identity

    @property
    def is_finished(self) -> bool:
        """Return whether this task has completed."""

        return self._outcome is not None

    @property
    def outcome(self) -> PromptAsyncTaskOutcome[tuple[PromptScheduledLora, ...]] | None:
        """Return the completed outcome when available."""

        return self._outcome

    def add_done_callback(
        self,
        callback: Callable[
            [PromptAsyncTaskOutcome[tuple[PromptScheduledLora, ...]]],
            None,
        ],
        *,
        reason: str,
    ) -> None:
        """Record one completion callback."""

        _ = reason
        self.callbacks.append(callback)

    def cancel(self, *, reason: str) -> None:
        """Accept cancellation without changing explicit test completion."""

        _ = reason

    def complete(
        self,
        *,
        result: tuple[PromptScheduledLora, ...] | None = None,
        error: BaseException | None = None,
    ) -> None:
        """Publish a deterministic task outcome."""

        self._outcome = PromptAsyncTaskOutcome(
            identity=self.request.identity,
            context=self.request.context,
            result=result,
            error=error,
        )
        callbacks = tuple(self.callbacks)
        self.callbacks.clear()
        for callback in callbacks:
            callback(self._outcome)


class _ScheduledLoraExecutor:
    """Record scheduled-LoRA async requests."""

    def __init__(self) -> None:
        """Initialize submitted handle storage."""

        self.handles: list[_ScheduledLoraTaskHandle] = []

    def submit(
        self,
        request: PromptAsyncRequest[tuple[PromptScheduledLora, ...]],
        *,
        cancellation: PromptEditorCancellationToken,
    ) -> PromptEditorTaskHandle[tuple[PromptScheduledLora, ...]]:
        """Record one async request."""

        _ = cancellation
        handle = _ScheduledLoraTaskHandle(request)
        self.handles.append(handle)
        return handle


class _Token:
    """Provide a never-cancelled token for scheduled-LoRA test work."""

    generation = 0
    is_cancelled = False
    reason: str | None = None


class _ScheduledLoraResolver:
    """Resolve scheduled LoRAs while exposing a stable context token."""

    scheduled_lora_context_token = "phase27-token"

    def __init__(self, result: tuple[PromptScheduledLora, ...]) -> None:
        """Store deterministic resolver output."""

        self._result = result
        self.calls: list[str] = []

    def __call__(self, prompt_text: str) -> tuple[PromptScheduledLora, ...]:
        """Record one resolver call and return configured scheduled LoRAs."""

        self.calls.append(prompt_text)
        return self._result


class _PromptLoraCatalog:
    """Expose cached LoRA rows while failing blocking foreground reads."""

    def __init__(
        self,
        rows: tuple[PromptLoraCatalogItem, ...] | None,
    ) -> None:
        """Store cached row state."""

        self.rows = rows
        self.cached_calls = 0
        self.list_calls = 0
        self.refresh_calls = 0

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return cached rows."""

        self.cached_calls += 1
        return self.rows

    def find_lora(self, prompt_name: str) -> PromptLoraCatalogItem | None:
        """Return a cached LoRA row matching one prompt name."""

        if self.rows is None:
            return None
        normalized_prompt_name = prompt_name.replace("\\", "/").casefold()
        for row in self.rows:
            if row.prompt_name.replace("\\", "/").casefold() == normalized_prompt_name:
                return row
        return None

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Fail if autocomplete attempts passive catalog loading."""

        self.list_calls += 1
        raise AssertionError("LoRA autocomplete must not call list_loras().")

    def refresh_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Fail if autocomplete attempts foreground refresh."""

        self.refresh_calls += 1
        raise AssertionError("LoRA autocomplete must not call refresh_loras().")


def test_phase27_tag_results_preserve_suffix_fallback_noop_filter_and_merge_order() -> (
    None
):
    """Tag autocomplete should preserve fallback, filtering, and trigger merge order."""

    gateway = RecordingPromptAutocompleteGateway(
        {
            "very long prompt 1g": (),
            "1g": (
                PromptAutocompleteSuggestion("1girl", 100),
                PromptAutocompleteSuggestion("1girls", 50),
            ),
        }
    )

    class _TriggerProvider:
        """Provide trigger-word rows that should merge before file rows."""

        def trigger_word_suggestions(
            self,
            prefix: str,
            prompt_text: str,
            *,
            source_text: str,
            source_identity: PromptAutocompleteResultSourceIdentity | None,
            query_identity: Hashable | None,
        ) -> PromptAutocompleteTriggerWordResult:
            """Return one duplicate row and one trigger-only row."""

            _ = (prompt_text, source_text, source_identity, query_identity)
            if prefix != "1g":
                return PromptAutocompleteTriggerWordResult(
                    suggestions=(),
                    scheduled_lora_signature=(),
                )
            return PromptAutocompleteTriggerWordResult(
                suggestions=(
                    PromptAutocompleteSuggestion(
                        "1girl",
                        popularity=None,
                        source_label="Trigger LoRA",
                        source_kind="lora_trigger",
                    ),
                    PromptAutocompleteSuggestion("1g trigger", popularity=None),
                ),
                scheduled_lora_signature=(("lora", "backend", "Trigger LoRA", (), ""),),
            )

    controller = PromptAutocompleteResultController(
        prompt_autocomplete_gateway=gateway,
        trigger_word_provider=_TriggerProvider(),
        limit=10,
    )
    source_text = "very long prompt 1g"

    result = controller.result_for_tag_query(
        PromptAutocompleteQuery(
            prefix=source_text,
            word_start=0,
            word_end=len(source_text),
            active_tag_end=len(source_text),
            fallback_query=PromptAutocompleteFallbackQuery(
                prefix="1g",
                word_start=source_text.rindex("1g"),
                word_end=len(source_text),
                active_tag_end=len(source_text),
            ),
        ),
        context=PromptAutocompleteTagContext(
            source_text=source_text,
            effective_prompt_text=source_text,
        ),
        source_identity=PromptCommandSourceIdentity(
            source_revision=4,
            source_length=len(source_text),
        ),
    )

    assert gateway.calls == [(source_text, 10), ("1g", 10)]
    assert [suggestion.tag for suggestion in result.suggestions] == [
        "1girl",
        "1g trigger",
        "1girls",
    ]
    assert result.prefix == "1g"
    assert result.had_candidates is True

    no_op_result = controller.result_for_tag_query(
        PromptAutocompleteQuery(
            prefix="1girl",
            word_start=0,
            word_end=len("1girl"),
            active_tag_end=len("1girl"),
        ),
        context=PromptAutocompleteTagContext(
            source_text="1girl",
            effective_prompt_text="1girl",
        ),
        source_identity=PromptCommandSourceIdentity(
            source_revision=5,
            source_length=len("1girl"),
        ),
    )

    assert all(suggestion.tag != "1girl" for suggestion in no_op_result.suggestions)


def test_phase27_lora_results_use_cached_catalog_and_respect_disabled_state() -> None:
    """LoRA autocomplete should consume cached rows only and fail closed when disabled."""

    cached_catalog = _PromptLoraCatalog((_lora_item(),))
    controller = PromptAutocompleteResultController(
        prompt_autocomplete_gateway=RecordingPromptAutocompleteGateway({}),
        prompt_lora_catalog_service=cached_catalog,
        limit=10,
    )
    query = PromptLoraAutocompleteQuery(
        query_text="mid",
        token_start=0,
        token_end=9,
        name_start=6,
        name_end=9,
        replacement_start=0,
        replacement_end=9,
        typed_weight_text=None,
        has_closing_bracket=False,
    )

    result = controller.result_for_lora_query(
        query,
        source_identity=None,
        enabled=True,
        thumbnail_cache_available=True,
    )

    assert result.status == "ready"
    assert result.mode == "lora"
    assert cached_catalog.cached_calls == 1
    assert cached_catalog.list_calls == 0
    assert cached_catalog.refresh_calls == 0

    disabled_result = controller.result_for_lora_query(
        query,
        source_identity=None,
        enabled=False,
        thumbnail_cache_available=True,
    )

    assert disabled_result.status == "empty"
    assert cached_catalog.cached_calls == 1


def test_phase27_scheduled_lora_context_warm_cold_stale_failed_and_disabled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Scheduled-LoRA autocomplete context should be cached, async, and stale-safe."""

    scheduled_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Friendly Midna",
        trained_words=("imp princess", "twilight imp"),
        source="cube_field",
    )
    resolver = _ScheduledLoraResolver((scheduled_lora,))
    executor = _ScheduledLoraExecutor()
    provider = PromptScheduledLoraContextCoordinator(
        resolver=resolver,
        enabled=True,
        executor=cast(Any, executor),
    )
    refresh_calls = 0

    def record_refresh() -> None:
        """Record one visible autocomplete refresh."""

        nonlocal refresh_calls
        refresh_calls += 1

    source_identity = PromptCommandSourceIdentity(source_revision=7, source_length=2)
    cold = provider.trigger_word_result(
        prefix="imp",
        prompt_text="mi",
        source_text="mi",
        source_identity=source_identity,
        query_identity=("tag", 0, 2, 2, 10),
        current_source_text=lambda: "mi",
        current_query_identity=lambda: ("tag", 0, 2, 2, 10),
        refresh_current_query=record_refresh,
    )

    assert cold.suggestions == ()
    assert len(executor.handles) == 1

    resolved_loras = executor.handles[0].request.work(_Token())
    executor.handles[0].complete(result=resolved_loras)

    warm = provider.trigger_word_result(
        prefix="imp",
        prompt_text="mi",
        source_text="mi",
        source_identity=source_identity,
        query_identity=("tag", 0, 2, 2, 10),
        current_source_text=lambda: "mi",
        current_query_identity=lambda: ("tag", 0, 2, 2, 10),
        refresh_current_query=record_refresh,
    )

    assert [suggestion.tag for suggestion in warm.suggestions] == ["imp princess"]
    assert resolver.calls == ["mi"]
    assert refresh_calls == 1

    stale_key = provider.cache_key_for_prompt("stale prompt")
    provider.complete_for_tests(
        cache_key=stale_key,
        prompt_text="stale prompt",
        source_text="stale prompt",
        source_identity=PromptCommandSourceIdentity(
            source_revision=8,
            source_length=len("stale prompt"),
        ),
        query_identity=("tag", 0, 12, 12, 10),
        scheduled_loras=(scheduled_lora,),
        current_source_text=lambda: "changed prompt",
        current_query_identity=lambda: ("tag", 0, 12, 12, 10),
        refresh_current_query=record_refresh,
    )

    assert refresh_calls == 1
    assert stale_key in provider.cached_cache_keys()

    failing_key = provider.cache_key_for_prompt("secret prompt")
    provider.fail_for_tests(
        cache_key=failing_key,
        prompt_text="secret prompt",
        error=RuntimeError("secret prompt leaked"),
    )

    assert failing_key not in provider.pending_cache_keys()
    assert failing_key not in provider.cached_cache_keys()
    assert "scheduled_lora_context.refresh.failed" in caplog.text
    assert "secret prompt leaked" not in caplog.text

    disabled_executor = _ScheduledLoraExecutor()
    disabled_provider = PromptScheduledLoraContextCoordinator(
        resolver=resolver,
        enabled=False,
        executor=cast(Any, disabled_executor),
    )

    disabled = disabled_provider.trigger_word_result(
        prefix="imp",
        prompt_text="mi",
        source_text="mi",
        source_identity=source_identity,
        query_identity=("tag", 0, 2, 2, 10),
        current_source_text=lambda: "mi",
        current_query_identity=lambda: ("tag", 0, 2, 2, 10),
        refresh_current_query=record_refresh,
    )

    assert disabled.suggestions == ()
    assert disabled_executor.handles == []


def test_phase27_query_timing_preserves_debounce_selection_and_lora_prefix() -> None:
    """Timing should coalesce refreshes and route query precedence through snapshots."""

    editor = _QueryEditor("<lo")
    autocomplete = _AutocompleteRecorder()
    fake_timer = _FakeTimer()
    feature_profile = PromptFeatureProfileController(
        PromptEditorFeatureProfile.enabled_profile(
            (
                PromptEditorFeature.LORA_AUTOCOMPLETE,
                PromptEditorFeature.WILDCARD_AUTOCOMPLETE,
            )
        )
    )
    query_refresh = PromptAutocompleteQueryRefreshController(
        autocomplete=cast(Any, autocomplete),
        query_controller=PromptAutocompleteQueryController(
            document_service=PromptDocumentService(),
            feature_profile=feature_profile,
            minimum_prefix_length=2,
        ),
    )
    source_snapshots = PromptAutocompleteSourceSnapshotController(
        editor,
        document_view_provider=lambda: PromptDocumentService().build_document_view(
            editor.text
        ),
        feature_profile=feature_profile,
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

    assert autocomplete.calls
    assert autocomplete.calls[-1][0] == "tag"
    assert editor.text_reads >= 1

    editor.text = "alpha"
    editor.cursor_position = len("alpha")
    controller.schedule_caret_refresh()
    controller.schedule_caret_refresh()

    assert fake_timer.started_delays[-2:] == [
        controller.caret_settle_delay_ms,
        controller.caret_settle_delay_ms,
    ]

    call_count = len(autocomplete.calls)
    fake_timer.fire()

    assert len(autocomplete.calls) == call_count + 1

    selected_editor = _QueryEditor("<lora:mid", has_selection=True)
    selected_autocomplete = _AutocompleteRecorder()
    selected_feature_profile = PromptFeatureProfileController(
        PromptEditorFeatureProfile.enabled_profile(
            (PromptEditorFeature.LORA_AUTOCOMPLETE,)
        )
    )
    selected_query_refresh = PromptAutocompleteQueryRefreshController(
        autocomplete=cast(Any, selected_autocomplete),
        query_controller=PromptAutocompleteQueryController(
            document_service=PromptDocumentService(),
            feature_profile=selected_feature_profile,
            minimum_prefix_length=2,
        ),
    )
    selected_source_snapshots = PromptAutocompleteSourceSnapshotController(
        selected_editor,
        document_view_provider=lambda: PromptDocumentService().build_document_view(
            selected_editor.text
        ),
        feature_profile=selected_feature_profile,
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

    assert selected_autocomplete.calls == [
        (
            "tag",
            None,
            PromptCommandSourceIdentity(
                source_revision=0,
                source_length=len("<lora:mid"),
            ),
            "<lora:mid",
        )
    ]

    controller.clear_for_non_text_interaction()

    assert fake_timer.stop_calls == 1
    assert autocomplete.clear_calls >= 1


def test_phase27_acceptance_rejects_stale_source_and_commits_lora_after_success() -> (
    None
):
    """Autocomplete session acceptance should stay command-owned and stale-safe."""

    accepted: list[object] = []
    commit_calls = 0

    class _Editor:
        """Provide the command seam consumed by the acceptance controller."""

        def __init__(self) -> None:
            """Initialize current source identity."""

            self.identity = PromptCommandSourceIdentity(
                source_revision=2,
                source_length=9,
            )

        def prompt_command_source_identity(self) -> PromptCommandSourceIdentity:
            """Return current source identity."""

            return self.identity

        def execute_autocomplete_acceptance(self, acceptance: object) -> object:
            """Record one command-boundary acceptance."""

            accepted.append(acceptance)
            return PromptCommandResult.completed("accept_autocomplete")

        def commit_lora_autocomplete_replacement(self) -> None:
            """Record LoRA post-accept projection commit."""

            nonlocal commit_calls
            commit_calls += 1

    editor = _Editor()
    controller = PromptAutocompleteAcceptanceController(editor=cast(Any, editor))
    stale_session = AutocompleteSession(
        suggestions=(PromptAutocompleteSuggestion("midna helmet"),),
        selected_index=0,
        word_start=0,
        word_end=5,
        active_tag_end=5,
        prefix="midna",
    )

    stale = controller.accept_session(
        stale_session,
        source_identity=PromptCommandSourceIdentity(source_revision=1, source_length=9),
        add_comma=False,
    )

    assert stale.status == "rejected"
    assert stale.reason == "stale_source"
    assert accepted == []

    item = _lora_item()
    lora_session = AutocompleteSession(
        mode="lora",
        selected_index=0,
        lora_candidates=(
            PromptLoraAutocompleteCandidate(
                item=item,
                score=10,
                display_text="Midna",
                display_completion_suffix="na",
                replacement_text="<lora:midna:1>",
                match_kind="display",
            ),
        ),
        lora_query=PromptLoraAutocompleteQuery(
            query_text="mid",
            token_start=0,
            token_end=9,
            name_start=6,
            name_end=9,
            replacement_start=0,
            replacement_end=9,
            typed_weight_text=None,
            has_closing_bracket=False,
        ),
    )

    accepted_outcome = controller.accept_session(
        lora_session,
        source_identity=editor.identity,
        add_comma=False,
    )

    assert accepted_outcome.status == "accepted"
    assert len(accepted) == 1
    assert commit_calls == 1


def test_phase27_coordinator_focus_navigation_mouse_and_clear_state() -> None:
    """Coordinator session behavior should preserve keyboard, mouse, and clear semantics."""

    class _Presenter:
        """Record panel operations without constructing widgets."""

        def __init__(self) -> None:
            """Initialize presenter state."""

            self.hidden = 0
            self.presented: list[object] = []
            self.activation_handler: Callable[[object], None] | None = None
            self.selection_handler: Callable[[int], None] | None = None

        @property
        def panel(self) -> None:
            """Return no live panel widget."""

            return None

        def present_session(self, session: object) -> bool:
            """Record one rendered session and report visible presentation."""

            self.presented.append(session)
            return True

        def set_activation_handler(
            self,
            handler: Callable[[object], None] | None,
        ) -> None:
            """Store activation callback."""

            self.activation_handler = handler

        def set_selection_changed_handler(
            self,
            handler: Callable[[int], None] | None,
        ) -> None:
            """Store selection callback."""

            self.selection_handler = handler

        def set_visibility_changed_handler(
            self,
            handler: Callable[[bool], None] | None,
        ) -> None:
            """Accept visibility handler wiring."""

            _ = handler

        def current_index(self) -> int:
            """Return the first row as selected."""

            return 0

        def move_lora_selection(self, direction: str) -> int | None:
            """Decline LoRA wall movement in this baseline test."""

            _ = direction
            return None

        def panel_under_mouse(self) -> bool:
            """Return that the mouse is outside the panel."""

            return False

        def panel_visible(self) -> bool:
            """Return that panel presentation is visible during active sessions."""

            return True

        def hide(self) -> None:
            """Record one hide request."""

            self.hidden += 1

    class _Editor:
        """Provide focus and acceptance seams for coordinator tests."""

        def __init__(self) -> None:
            """Initialize command recording."""

            self.focus_calls = 0
            self.accepted: list[object] = []

        def setFocus(self) -> None:  # noqa: N802
            """Record focus restoration."""

            self.focus_calls += 1

        def execute_autocomplete_acceptance(self, acceptance: object) -> object:
            """Record accepted command payload."""

            self.accepted.append(acceptance)
            return PromptCommandResult.completed("accept_autocomplete")

        def prompt_command_source_identity(self) -> None:
            """Return no source identity."""

            return None

    presenter = _Presenter()
    editor = _Editor()
    session_controller = PromptAutocompleteSessionController()
    session_controller.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="tag",
            status="ready",
            suggestions=(
                PromptAutocompleteSuggestion("1girl", 100),
                PromptAutocompleteSuggestion("1girls", 50),
            ),
            word_start=0,
            word_end=2,
            active_tag_end=2,
            prefix="1g",
        ),
        source_identity=None,
        ghost_text_source_snapshot=None,
    )
    coordinator = build_test_autocomplete_coordinator(
        cast(Any, editor),
        prompt_autocomplete_gateway=RecordingPromptAutocompleteGateway({}),
        autocomplete_presenter=cast(Any, presenter),
        autocomplete_session_controller=session_controller,
    )

    assert coordinator.handle_key_press(_key_event(Qt.Key.Key_Down)) is True
    assert session_controller.session.selected_index == 1
    assert presenter.presented

    assert coordinator.handle_key_press(_key_event(Qt.Key.Key_Down)) is True
    assert session_controller.session.selected_index == 0
    assert session_controller.session.mode == "tag"
    assert presenter.hidden == 0

    session_controller.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="tag",
            status="ready",
            suggestions=(PromptAutocompleteSuggestion("1girl", 100),),
            word_start=0,
            word_end=2,
            active_tag_end=2,
            prefix="1g",
        ),
        source_identity=None,
        ghost_text_source_snapshot=None,
    )
    assert coordinator.handle_key_press(_key_event(Qt.Key.Key_Left)) is False
    assert session_controller.session.mode == "none"
    assert presenter.hidden >= 1

    session_controller.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="tag",
            status="ready",
            suggestions=(PromptAutocompleteSuggestion("1girl", 100),),
            word_start=0,
            word_end=2,
            active_tag_end=2,
            prefix="1g",
        ),
        source_identity=None,
        ghost_text_source_snapshot=None,
    )
    coordinator.activate_suggestion(0)

    assert editor.focus_calls == 1
    assert editor.accepted
    assert presenter.hidden >= 1

    coordinator.dismiss_autocomplete("escape")

    assert session_controller.session.mode == "none"
    assert presenter.hidden >= 2


def test_phase27_coordinator_lora_vertical_boundaries_stay_handled() -> None:
    """LoRA autocomplete should keep vertical boundary arrows inside the picker."""

    class _Presenter:
        """Record panel operations while declining wall-owned movement."""

        def __init__(self) -> None:
            """Initialize hidden counter and handler storage."""

            self.hidden = 0

        @property
        def panel(self) -> None:
            """Return no live panel widget."""

            return None

        def present_session(self, session: object) -> bool:
            """Accept render requests and report visible presentation."""

            _ = session
            return True

        def set_activation_handler(
            self,
            handler: Callable[[object], None] | None,
        ) -> None:
            """Accept activation handler wiring."""

            _ = handler

        def set_selection_changed_handler(
            self,
            handler: Callable[[int], None] | None,
        ) -> None:
            """Accept selection handler wiring."""

            _ = handler

        def set_visibility_changed_handler(
            self,
            handler: Callable[[bool], None] | None,
        ) -> None:
            """Accept visibility handler wiring."""

            _ = handler

        def current_index(self) -> int:
            """Return the current first-row index."""

            return 0

        def move_lora_selection(self, direction: str) -> int | None:
            """Decline presenter-owned LoRA movement."""

            _ = direction
            return None

        def panel_under_mouse(self) -> bool:
            """Return that the pointer is outside the panel."""

            return False

        def panel_visible(self) -> bool:
            """Return that panel presentation is visible during active sessions."""

            return True

        def hide(self) -> None:
            """Record one hide request."""

            self.hidden += 1

    class _Editor:
        """Provide command seams required by the coordinator."""

        def execute_autocomplete_acceptance(self, acceptance: object) -> object:
            """Return a completed command result."""

            _ = acceptance
            return PromptCommandResult.completed("accept_autocomplete")

        def prompt_command_source_identity(self) -> None:
            """Return no source identity."""

            return None

        def commit_lora_autocomplete_replacement(self) -> None:
            """Accept LoRA post-commit calls."""

        def setFocus(self) -> None:  # noqa: N802
            """Accept focus restoration calls."""

    query = PromptLoraAutocompleteQuery(
        query_text="mid",
        token_start=0,
        token_end=9,
        name_start=6,
        name_end=9,
        replacement_start=0,
        replacement_end=9,
        typed_weight_text=None,
        has_closing_bracket=False,
    )
    session_controller = PromptAutocompleteSessionController()
    session_controller.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="lora",
            status="ready",
            lora_candidates=(
                PromptLoraAutocompleteCandidate(
                    item=_lora_item(),
                    score=1,
                    display_text="Midna",
                    display_completion_suffix="na",
                    replacement_text="<lora:midna:1>",
                    match_kind="display",
                ),
                PromptLoraAutocompleteCandidate(
                    item=_lora_item(prompt_name="midna_alt"),
                    score=2,
                    display_text="Midna Alt",
                    display_completion_suffix="na Alt",
                    replacement_text="<lora:midna_alt:1>",
                    match_kind="display",
                ),
            ),
            lora_query=query,
        ),
        source_identity=None,
        ghost_text_source_snapshot=None,
    )
    presenter = _Presenter()
    coordinator = build_test_autocomplete_coordinator(
        cast(Any, _Editor()),
        prompt_autocomplete_gateway=RecordingPromptAutocompleteGateway({}),
        autocomplete_presenter=cast(Any, presenter),
        autocomplete_session_controller=session_controller,
        lora_thumbnail_cache_available=True,
    )

    assert coordinator.handle_key_press(_key_event(Qt.Key.Key_Up)) is True
    assert session_controller.session.selected_index == 0
    assert session_controller.session.mode == "lora"
    assert presenter.hidden == 0

    session_controller.replace_result(
        PromptAutocompleteResultSnapshot(
            mode="lora",
            status="ready",
            lora_candidates=(
                PromptLoraAutocompleteCandidate(
                    item=_lora_item(),
                    score=1,
                    display_text="Midna",
                    display_completion_suffix="na",
                    replacement_text="<lora:midna:1>",
                    match_kind="display",
                ),
                PromptLoraAutocompleteCandidate(
                    item=_lora_item(prompt_name="midna_alt"),
                    score=2,
                    display_text="Midna Alt",
                    display_completion_suffix="na Alt",
                    replacement_text="<lora:midna_alt:1>",
                    match_kind="display",
                ),
            ),
            lora_query=query,
        ),
        source_identity=None,
        ghost_text_source_snapshot=None,
    )

    assert coordinator.handle_key_press(_key_event(Qt.Key.Key_Down)) is True
    assert session_controller.session.selected_index == 1
    assert coordinator.handle_key_press(_key_event(Qt.Key.Key_Down)) is True
    assert session_controller.session.selected_index == 1
    assert session_controller.session.mode == "lora"
    assert presenter.hidden == 0


def _autocomplete_module() -> Any:
    """Import the transitional autocomplete interaction module."""

    import importlib

    return importlib.import_module(
        "substitute.presentation.editor.prompt_editor.interactions.autocomplete_controller"
    )


def _key_event(key: Qt.Key) -> QKeyEvent:
    """Return a key event suitable for autocomplete key-path tests."""

    return QKeyEvent(
        QKeyEvent.Type.KeyPress,
        int(key),
        Qt.KeyboardModifier.NoModifier,
    )


def _lora_item(*, prompt_name: str = "midna") -> PromptLoraCatalogItem:
    """Return one deterministic LoRA catalog item."""

    return PromptLoraCatalogItem(
        display_name="Midna",
        display_subtitle=None,
        prompt_name=prompt_name,
        backend_value=f"{prompt_name}.safetensors",
        relative_path=f"{prompt_name}.safetensors",
        folder="",
        basename=prompt_name,
        extension=".safetensors",
        thumbnail_variants=(),
        base_model="Illustrious",
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key=prompt_name,
        collision_count=1,
        has_collision=False,
        search_text="midna",
    )

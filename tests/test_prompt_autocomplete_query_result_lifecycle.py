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

"""Verify autocomplete query/result lifecycle ownership and hot-path boundaries."""

from __future__ import annotations

from dataclasses import dataclass, replace
from types import SimpleNamespace
from typing import Any, cast

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor.autocomplete.queries import (
    PromptAutocompleteQuery,
    PromptWildcardAutocompleteQuery,
)
from substitute.application.prompt_editor.lora.autocomplete import (
    PromptLoraAutocompleteQuery,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptAutocompleteQueryResultLifecycle,
    PromptAutocompleteQueryState,
    PromptAutocompleteResultSnapshot,
)


class _QueryController:
    """Return one prepared state while recording query-construction demand."""

    def __init__(self, state: PromptAutocompleteQueryState) -> None:
        """Store the deterministic query state."""

        self.state = state
        self.calls: list[object] = []

    def query_state_from_source_snapshot(
        self,
        snapshot: object,
    ) -> PromptAutocompleteQueryState:
        """Record the source snapshot and return its configured query state."""

        self.calls.append(snapshot)
        return self.state


class _Publication:
    """Record immutable result publication without presenting a Qt surface."""

    def __init__(self, *, active: bool = False) -> None:
        """Initialize a passive or active session publication boundary."""

        self.active = active
        self.published: list[
            tuple[PromptAutocompleteResultSnapshot, PromptAutocompleteQueryState]
        ] = []
        self.retargeted: list[PromptAutocompleteQueryState] = []
        self.dismissed: list[str] = []

    def has_active_session(self) -> bool:
        """Return the configured session activity state."""

        return self.active

    def retarget_from_query_state(
        self, query_state: PromptAutocompleteQueryState
    ) -> bool:
        """Record a session retarget request."""

        self.retargeted.append(query_state)
        return True

    def publish_result(
        self,
        result: PromptAutocompleteResultSnapshot,
        query_state: PromptAutocompleteQueryState,
    ) -> None:
        """Record one immutable result/query transition."""

        self.published.append((result, query_state))

    def dismiss_autocomplete(self, reason: str) -> None:
        """Record one lifecycle dismissal."""

        self.dismissed.append(reason)


class _ResultController:
    """Return one ready tag result without gateway or cache dependencies."""

    def __init__(self, result: PromptAutocompleteResultSnapshot) -> None:
        """Store the result consumed by the lifecycle."""

        self.result = result
        self.tag_calls = 0
        self.lora_calls = 0
        self.wildcard_calls = 0

    def result_for_tag_query(self, **_kwargs: Any) -> PromptAutocompleteResultSnapshot:
        """Return the prepared tag result while recording one result request."""

        self.tag_calls += 1
        return self.result

    def safe_tag_query_identity(
        self, query: PromptAutocompleteQuery
    ) -> tuple[str, str]:
        """Return the query identity used by async stale rejection."""

        return ("tag", query.prefix)

    def result_for_lora_query(
        self, *_args: Any, **_kwargs: Any
    ) -> PromptAutocompleteResultSnapshot:
        """Return the configured LoRA result while recording precedence routing."""

        self.lora_calls += 1
        return self.result

    def result_for_wildcard_query(
        self, *_args: Any, **_kwargs: Any
    ) -> PromptAutocompleteResultSnapshot:
        """Return the configured wildcard result while recording precedence routing."""

        self.wildcard_calls += 1
        return self.result

    @property
    def limit(self) -> int:
        """Return the deterministic wildcard result limit."""

        return 10

    def wildcard_feature_identity(self) -> str:
        """Return the deterministic wildcard feature identity."""

        return "wildcards"


@dataclass(frozen=True, slots=True)
class _SceneContextController:
    """Return a tag context without consulting a scene feature."""

    def context_for_tag_query(self, *_args: Any, **_kwargs: Any) -> object:
        """Provide the exact tag context shape consumed by the result owner."""

        return SimpleNamespace(
            tag_context=SimpleNamespace(
                source_text="1gi",
                effective_prompt_text="1gi",
            )
        )


def _tag_state(*, refresh_intent: str = "typing") -> PromptAutocompleteQueryState:
    """Return one prepared tag query state for lifecycle ownership tests."""

    return PromptAutocompleteQueryState(
        source_revision=7,
        source_length=3,
        source_text="1gi",
        cursor_position=3,
        has_selection=False,
        refresh_intent=cast(Any, refresh_intent),
        tag_query=PromptAutocompleteQuery(
            prefix="1gi",
            word_start=0,
            word_end=3,
            active_tag_end=3,
        ),
    )


def _lifecycle(
    *,
    query_controller: _QueryController,
    result_controller: _ResultController,
    publication: _Publication,
    current_source_calls: list[None],
) -> PromptAutocompleteQueryResultLifecycle:
    """Build a lifecycle with explicit non-Qt fakes at every boundary."""

    def current_source_identity() -> None:
        """Record any forbidden live source read."""

        current_source_calls.append(None)
        return None

    return PromptAutocompleteQueryResultLifecycle(
        query_controller=cast(Any, query_controller),
        result_controller=cast(Any, result_controller),
        scene_context_controller=cast(Any, _SceneContextController()),
        publication=cast(Any, publication),
        current_source_identity=current_source_identity,
        lora_autocomplete_enabled=lambda: True,
        lora_thumbnail_cache_available=lambda: True,
    )


def test_query_result_lifecycle_publishes_prepared_result_without_live_source_read() -> (
    None
):
    """A refresh consumes the prepared snapshot and publishes one immutable transition."""

    state = _tag_state()
    query_controller = _QueryController(state)
    result = PromptAutocompleteResultSnapshot(
        mode="tag",
        status="ready",
        suggestions=(PromptAutocompleteSuggestion("1girl", 1),),
        tag_query=state.tag_query,
    )
    result_controller = _ResultController(result)
    publication = _Publication()
    current_source_calls: list[None] = []
    lifecycle = _lifecycle(
        query_controller=query_controller,
        result_controller=result_controller,
        publication=publication,
        current_source_calls=current_source_calls,
    )
    snapshot = object()

    lifecycle.refresh_results_from_source_snapshot(cast(Any, snapshot))

    assert query_controller.calls == [snapshot]
    assert result_controller.tag_calls == 1
    assert publication.published == [(result, state)]
    assert publication.dismissed == []
    assert current_source_calls == []


def test_query_result_lifecycle_skips_dormant_retarget_query_work() -> None:
    """Inactive sessions keep synchronous edit retargeting out of the query path."""

    query_controller = _QueryController(_tag_state())
    result_controller = _ResultController(PromptAutocompleteResultSnapshot.empty())
    publication = _Publication(active=False)
    lifecycle = _lifecycle(
        query_controller=query_controller,
        result_controller=result_controller,
        publication=publication,
        current_source_calls=[],
    )

    retargeted = lifecycle.retarget_from_source_snapshot(cast(Any, object()))

    assert retargeted is False
    assert query_controller.calls == []
    assert publication.retargeted == []


def test_query_result_lifecycle_retargets_active_session_from_prepared_snapshot() -> (
    None
):
    """Active sessions construct exactly one query state and receive that state."""

    state = _tag_state()
    query_controller = _QueryController(state)
    publication = _Publication(active=True)
    lifecycle = _lifecycle(
        query_controller=query_controller,
        result_controller=_ResultController(PromptAutocompleteResultSnapshot.empty()),
        publication=publication,
        current_source_calls=[],
    )
    snapshot = object()

    retargeted = lifecycle.retarget_from_source_snapshot(cast(Any, snapshot))

    assert retargeted is True
    assert query_controller.calls == [snapshot]
    assert publication.retargeted == [state]
    assert lifecycle.latest_query_state == state


def test_query_result_lifecycle_passive_snapshot_dismisses_without_result_work() -> (
    None
):
    """Caret navigation clears a session without touching query or result services."""

    query_controller = _QueryController(_tag_state(refresh_intent="caret_navigation"))
    result_controller = _ResultController(PromptAutocompleteResultSnapshot.empty())
    publication = _Publication()
    lifecycle = _lifecycle(
        query_controller=query_controller,
        result_controller=result_controller,
        publication=publication,
        current_source_calls=[],
    )

    lifecycle.refresh_results_from_source_snapshot(cast(Any, object()))

    assert result_controller.tag_calls == 0
    assert publication.published == []
    assert publication.dismissed == ["no_query"]


def test_query_result_lifecycle_routes_lora_before_tag_result_work() -> None:
    """Give complete LoRA syntax priority over overlapping ordinary tag text."""

    tag_state = _tag_state()
    lora_query = PromptLoraAutocompleteQuery(
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
    state = replace(tag_state, lora_query=lora_query)
    result = PromptAutocompleteResultSnapshot(
        mode="lora",
        status="ready",
        lora_candidates=(cast(Any, object()),),
    )
    query_controller = _QueryController(state)
    result_controller = _ResultController(result)
    publication = _Publication()
    lifecycle = _lifecycle(
        query_controller=query_controller,
        result_controller=result_controller,
        publication=publication,
        current_source_calls=[],
    )

    lifecycle.refresh_results_from_source_snapshot(cast(Any, object()))

    assert result_controller.lora_calls == 1
    assert result_controller.tag_calls == 0
    assert publication.published == [(result, state)]


def test_query_result_lifecycle_routes_wildcard_before_tag_result_work() -> None:
    """Give wildcard syntax priority over overlapping ordinary tag text."""

    tag_state = _tag_state()
    wildcard_query = PromptWildcardAutocompleteQuery(
        prefix="ani",
        opener_start=0,
        content_start=1,
        cursor_position=4,
        replacement_end=5,
    )
    state = replace(tag_state, wildcard_query=wildcard_query)
    result = PromptAutocompleteResultSnapshot(
        mode="wildcard",
        status="ready",
        suggestions=(PromptAutocompleteSuggestion("animal", 1),),
    )
    result_controller = _ResultController(result)
    publication = _Publication()
    lifecycle = _lifecycle(
        query_controller=_QueryController(state),
        result_controller=result_controller,
        publication=publication,
        current_source_calls=[],
    )

    lifecycle.refresh_results_from_source_snapshot(cast(Any, object()))

    assert result_controller.wildcard_calls == 1
    assert result_controller.tag_calls == 0
    assert publication.published == [(result, state)]

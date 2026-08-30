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

"""Verify wildcard autocomplete presentation ownership."""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.domain.prompt.features.models import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
)
from substitute.presentation.editor.prompt_editor.features import (
    CatalogSnapshotReadiness,
    PromptFeatureProfileController,
    PromptWildcardAutocompletePresentation,
)
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptAsyncRequest,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptEditorTaskHandle,
)

from ..support import WildcardGatewayDouble

TResult = TypeVar("TResult")


class _RequestHandle(Generic[TResult]):
    """Store async callbacks until tests explicitly complete a request."""

    def __init__(self, request: PromptAsyncRequest[TResult]) -> None:
        """Store the request and initialize callback state."""

        self.request = request
        self.callbacks: list[Callable[[PromptAsyncTaskOutcome[TResult]], None]] = []
        self.cancel_reasons: list[str] = []
        self._outcome: PromptAsyncTaskOutcome[TResult] | None = None

    @property
    def identity(self) -> PromptAsyncResultIdentity:
        """Return the request identity."""

        return self.request.identity

    @property
    def is_finished(self) -> bool:
        """Return whether this fake handle has completed."""

        return self._outcome is not None

    @property
    def outcome(self) -> PromptAsyncTaskOutcome[TResult] | None:
        """Return the completed outcome when present."""

        return self._outcome

    def add_done_callback(
        self,
        callback: Callable[[PromptAsyncTaskOutcome[TResult]], None],
        *,
        reason: str,
    ) -> None:
        """Record a done callback for explicit completion."""

        _ = reason
        if self._outcome is not None:
            callback(self._outcome)
            return
        self.callbacks.append(callback)

    def cancel(self, *, reason: str) -> None:
        """Record cancellation requests."""

        self.cancel_reasons.append(reason)

    def complete(self) -> None:
        """Run the request work and publish its outcome."""

        try:
            result = self.request.work(_Token())
        except BaseException as error:  # noqa: BLE001
            self.fail(error)
            return
        self._publish(
            PromptAsyncTaskOutcome(
                identity=self.request.identity,
                context=self.request.context,
                result=result,
            )
        )

    def fail(self, error: BaseException) -> None:
        """Publish a failed request outcome."""

        self._publish(
            PromptAsyncTaskOutcome(
                identity=self.request.identity,
                context=self.request.context,
                error=error,
            )
        )

    def _publish(self, outcome: PromptAsyncTaskOutcome[TResult]) -> None:
        """Publish one fake completion to all registered callbacks."""

        self._outcome = outcome
        for callback in tuple(self.callbacks):
            callback(outcome)


class _Token:
    """Provide a never-cancelled token for wildcard tests."""

    generation = 0
    is_cancelled = False
    reason: str | None = None


class _RequestChannel(Generic[TResult]):
    """Capture latest-wins async requests for wildcard tests."""

    def __init__(self) -> None:
        """Initialize empty request storage."""

        self.handles: list[_RequestHandle[TResult]] = []
        self.cancel_reasons: list[str] = []

    def submit_latest(
        self,
        request: PromptAsyncRequest[TResult],
    ) -> PromptEditorTaskHandle[TResult]:
        """Store one request and return a controllable handle."""

        handle = _RequestHandle(request)
        self.handles.append(handle)
        return handle

    def cancel_pending(self, *, reason: str) -> None:
        """Record pending cancellation."""

        self.cancel_reasons.append(reason)

    def latest_handle(self) -> _RequestHandle[TResult]:
        """Return the most recently submitted handle."""

        return self.handles[-1]


class _ImmediateRequestChannel(_RequestChannel[TResult]):
    """Complete submitted wildcard requests before returning their handle."""

    def submit_latest(
        self,
        request: PromptAsyncRequest[TResult],
    ) -> PromptEditorTaskHandle[TResult]:
        """Run one request synchronously to exercise settled-handle ordering."""

        handle = _RequestHandle(request)
        self.handles.append(handle)
        handle.complete()
        return handle


def _autocomplete_presentation(
    features: tuple[PromptEditorFeature, ...],
    *,
    gateway: WildcardGatewayDouble | None = None,
    request_channel: _RequestChannel[tuple[PromptAutocompleteSuggestion, ...]]
    | None = None,
) -> PromptWildcardAutocompletePresentation:
    """Return a wildcard autocomplete owner with deterministic feature gates."""

    return PromptWildcardAutocompletePresentation(
        feature_profile=PromptFeatureProfileController(
            PromptEditorFeatureProfile.enabled_profile(features)
        ),
        wildcard_catalog_gateway=gateway or WildcardGatewayDouble(),
        request_channel=request_channel or _RequestChannel(),
    )


def test_wildcard_autocomplete_schedules_cold_query_without_foreground_search() -> None:
    """Cold wildcard autocomplete should schedule search without blocking foreground."""

    gateway = WildcardGatewayDouble()
    channel: _RequestChannel[tuple[PromptAutocompleteSuggestion, ...]] = (
        _RequestChannel()
    )
    controller = _autocomplete_presentation(
        (PromptEditorFeature.WILDCARD_AUTOCOMPLETE,),
        gateway=gateway,
        request_channel=channel,
    )

    suggestions = controller.wildcard_autocomplete_suggestions("a", limit=10)

    assert suggestions == ()
    assert gateway.search_calls == []
    assert len(channel.handles) == 1
    assert controller.snapshot.status is not None
    assert controller.snapshot.status.readiness is CatalogSnapshotReadiness.COLD
    assert controller.pending_autocomplete_cache_keys()


def test_wildcard_autocomplete_publishes_completed_query_snapshot() -> None:
    """Completed wildcard refresh should publish warm prepared query rows."""

    gateway = WildcardGatewayDouble()
    channel: _RequestChannel[tuple[PromptAutocompleteSuggestion, ...]] = (
        _RequestChannel()
    )
    refreshed: list[None] = []
    controller = _autocomplete_presentation(
        (PromptEditorFeature.WILDCARD_AUTOCOMPLETE,),
        gateway=gateway,
        request_channel=channel,
    )

    assert (
        controller.wildcard_autocomplete_suggestions(
            "a",
            limit=10,
            query_identity=("wildcard", "a", 10),
            current_query_identity=lambda: ("wildcard", "a", 10),
            refresh_current_query=lambda: refreshed.append(None),
        )
        == ()
    )
    channel.latest_handle().complete()

    assert gateway.search_calls == [("a", 10)]
    assert refreshed == [None]
    assert [
        row.tag for row in controller.wildcard_autocomplete_suggestions("a", limit=10)
    ] == ["aanimal"]
    assert controller.snapshot.cached_query_count == 1
    assert controller.snapshot.status is not None
    assert controller.snapshot.status.readiness is CatalogSnapshotReadiness.WARM


def test_wildcard_autocomplete_preserves_immediately_completed_warm_snapshot() -> None:
    """Return warm rows when a refresh settles during request submission."""

    gateway = WildcardGatewayDouble()
    channel: _ImmediateRequestChannel[tuple[PromptAutocompleteSuggestion, ...]] = (
        _ImmediateRequestChannel()
    )
    controller = _autocomplete_presentation(
        (PromptEditorFeature.WILDCARD_AUTOCOMPLETE,),
        gateway=gateway,
        request_channel=channel,
    )

    snapshot = controller.wildcard_autocomplete_snapshot(
        prefix="a",
        limit=10,
        query_identity=("wildcard", "a", 10),
        current_query_identity=lambda: ("wildcard", "a", 10),
    )

    assert snapshot.status.readiness is CatalogSnapshotReadiness.WARM
    assert [row.tag for row in snapshot.suggestions] == ["aanimal"]
    assert controller.snapshot.status is not None
    assert controller.snapshot.status.readiness is CatalogSnapshotReadiness.WARM


def test_wildcard_autocomplete_requeries_when_catalog_revision_changes() -> None:
    """Wildcard autocomplete cache identity should include catalog revision."""

    gateway = WildcardGatewayDouble()
    channel: _RequestChannel[tuple[PromptAutocompleteSuggestion, ...]] = (
        _RequestChannel()
    )
    controller = _autocomplete_presentation(
        (PromptEditorFeature.WILDCARD_AUTOCOMPLETE,),
        gateway=gateway,
        request_channel=channel,
    )

    assert controller.wildcard_autocomplete_suggestions("a", limit=10) == ()
    channel.latest_handle().complete()
    gateway.cache_revision = 8
    stale = controller.wildcard_autocomplete_suggestions("a", limit=10)

    assert [row.tag for row in stale] == ["aanimal"]
    assert gateway.search_calls == [("a", 10)]
    assert len(channel.handles) == 2
    channel.latest_handle().complete()
    assert gateway.search_calls == [("a", 10), ("a", 10)]
    assert controller.snapshot.catalog_identity == (
        "WildcardGatewayDouble",
        id(gateway),
        8,
    )


def test_wildcard_autocomplete_disabled_does_not_search_catalog() -> None:
    """Disabled wildcard autocomplete should produce a cheap empty state."""

    gateway = WildcardGatewayDouble()
    channel: _RequestChannel[tuple[PromptAutocompleteSuggestion, ...]] = (
        _RequestChannel()
    )
    controller = _autocomplete_presentation(
        (),
        gateway=gateway,
        request_channel=channel,
    )

    assert controller.wildcard_autocomplete_suggestions("a", limit=10) == ()

    assert gateway.search_calls == []
    assert channel.handles == []
    assert controller.snapshot.disabled_reason == "wildcard_autocomplete_disabled"


def test_wildcard_autocomplete_records_catalog_failure_without_raising() -> None:
    """Wildcard autocomplete failures should publish failed prepared state."""

    gateway = WildcardGatewayDouble()
    gateway.fail_search = True
    channel: _RequestChannel[tuple[PromptAutocompleteSuggestion, ...]] = (
        _RequestChannel()
    )
    controller = _autocomplete_presentation(
        (PromptEditorFeature.WILDCARD_AUTOCOMPLETE,),
        gateway=gateway,
        request_channel=channel,
    )

    assert controller.wildcard_autocomplete_suggestions("a", limit=10) == ()
    channel.latest_handle().complete()

    assert gateway.search_calls == [("a", 10)]
    assert controller.pending_autocomplete_cache_keys() == ()
    assert controller.snapshot.status is not None
    assert (
        controller.snapshot.status.readiness is CatalogSnapshotReadiness.REFRESH_FAILED
    )


def test_wildcard_autocomplete_bounds_cache() -> None:
    """Wildcard autocomplete cache should evict the oldest prepared query rows."""

    controller = _autocomplete_presentation(
        (PromptEditorFeature.WILDCARD_AUTOCOMPLETE,)
    )

    for index in range(65):
        prefix = f"w{index}"
        controller.complete_autocomplete_refresh_for_tests(
            prefix=prefix,
            limit=10,
            suggestions=(
                PromptAutocompleteSuggestion(
                    tag=prefix,
                    source_label="TXT wildcard",
                    source_kind="wildcard",
                ),
            ),
        )

    keys = controller.cached_autocomplete_cache_keys()
    assert len(keys) == 64
    assert keys[0][1] == "w1"
    assert keys[-1][1] == "w64"

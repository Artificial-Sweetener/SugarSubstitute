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

"""Own prompt wildcard presentation readiness and prepared wildcard actions."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from typing import Protocol

from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardCatalogGateway,
)
from substitute.application.prompt_editor import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDiagnosticProvider,
    PromptWildcardDiagnosticProvider,
)
from substitute.shared.logging.logger import get_logger

from ..async_work import (
    PromptAsyncRequest,
    PromptAsyncRequestContext,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptEditorMainThreadDispatcher,
    PromptEditorRequestChannel,
    log_prompt_async_warning,
)
from ..commands import PromptCommandSourceIdentity

from .catalog_snapshots import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
)
from ..commands import PromptFeatureSnapshotIdentity
from .feature_profile_controller import PromptFeatureProfileController

_AUTOCOMPLETE_CACHE_LIMIT = 64
_WILDCARD_AUTOCOMPLETE_OPERATION = "wildcard_autocomplete_query"
_WILDCARD_AUTOCOMPLETE_COMPLETION_REASON = "wildcard_autocomplete_query_completed"
_LOGGER = get_logger("presentation.editor.prompt_editor.features.wildcard_controller")

PromptWildcardAutocompleteCacheKey = tuple[Hashable, str, int]
PromptWildcardAutocompleteRefreshCallback = Callable[[], None]
PromptWildcardAutocompleteQueryIdentityProvider = Callable[[], Hashable | None]


@dataclass(frozen=True, slots=True)
class PromptWildcardContextAction:
    """Describe one wildcard-owned context action without binding to Qt widgets."""

    label: str
    callback_ready: bool = False
    disabled_reason: str | None = None


@dataclass(frozen=True, slots=True)
class PromptWildcardDiagnosticsState:
    """Publish wildcard diagnostic provider and action readiness."""

    enabled: bool
    provider_ready: bool
    action_ready: bool
    disabled_reason: str | None = None


@dataclass(frozen=True, slots=True)
class PromptWildcardAutocompleteState:
    """Publish wildcard autocomplete readiness and cache identity."""

    enabled: bool
    catalog_identity: Hashable
    cached_query_count: int
    disabled_reason: str | None = None
    status: CatalogSnapshotStatus | None = None
    query_identity: Hashable | None = None
    pending_query_count: int = 0


@dataclass(frozen=True, slots=True)
class PromptWildcardAutocompleteQuerySnapshot:
    """Publish prepared wildcard autocomplete rows for one query."""

    identity: CatalogSnapshotIdentity
    status: CatalogSnapshotStatus
    prefix: str
    limit: int
    suggestions: tuple[PromptAutocompleteSuggestion, ...]
    cache_key: PromptWildcardAutocompleteCacheKey | None = None
    pending: bool = False

    @property
    def consumable(self) -> bool:
        """Return whether foreground code may display the prepared suggestions."""

        return self.status.consumable


@dataclass(frozen=True, slots=True)
class PromptWildcardAutocompleteRequest:
    """Carry one wildcard autocomplete request without prompt text."""

    identity: PromptAsyncResultIdentity
    cache_key: PromptWildcardAutocompleteCacheKey
    prefix: str
    limit: int
    source_identity: PromptCommandSourceIdentity | None
    current_query_identity: PromptWildcardAutocompleteQueryIdentityProvider | None
    refresh_current_query: PromptWildcardAutocompleteRefreshCallback | None


@dataclass(frozen=True, slots=True)
class PromptWildcardNumericStepState:
    """Publish wildcard numeric stepping policy for prepared renderer state."""

    enabled: bool
    mutates_through_commands: bool
    source: str
    disabled_reason: str | None = None


@dataclass(frozen=True, slots=True)
class PromptWildcardPresentationSnapshot:
    """Publish prepared wildcard presentation state for foreground consumers."""

    identity: PromptFeatureSnapshotIdentity
    catalog_identity: Hashable
    diagnostics: PromptWildcardDiagnosticsState
    autocomplete: PromptWildcardAutocompleteState
    numeric_step: PromptWildcardNumericStepState
    unavailable_reason: str | None = None


class PromptWildcardSourceHost(Protocol):
    """Describe source identity reads used by wildcard presentation snapshots."""

    def prompt_command_source_identity(self) -> object | None:
        """Return the current source identity when the host can provide it."""


class PromptWildcardFeatureController:
    """Coordinate wildcard feature readiness for diagnostics and autocomplete."""

    def __init__(
        self,
        *,
        feature_profile: PromptFeatureProfileController,
        wildcard_catalog_gateway: PromptWildcardCatalogGateway,
        host: PromptWildcardSourceHost | None = None,
        parent: object | None = None,
        request_channel: PromptEditorRequestChannel[
            tuple[PromptAutocompleteSuggestion, ...]
        ]
        | None = None,
        main_thread_dispatcher: PromptEditorMainThreadDispatcher | None = None,
    ) -> None:
        """Store wildcard dependencies and publish an initial readiness snapshot."""

        self._feature_profile = feature_profile
        self._wildcard_catalog_gateway = wildcard_catalog_gateway
        self._host = host
        self._autocomplete_cache: OrderedDict[
            PromptWildcardAutocompleteCacheKey,
            tuple[PromptAutocompleteSuggestion, ...],
        ] = OrderedDict()
        self._autocomplete_snapshots: dict[
            PromptWildcardAutocompleteCacheKey,
            PromptWildcardAutocompleteQuerySnapshot,
        ] = {}
        self._pending_autocomplete_requests: set[PromptWildcardAutocompleteCacheKey] = (
            set()
        )
        self._request_id = 0
        _ = parent, main_thread_dispatcher
        if request_channel is None:
            raise TypeError(
                "request_channel is required for prompt wildcard autocomplete."
            )
        self._request_channel = request_channel
        self._snapshot = self._build_snapshot(stale=False)

    @property
    def snapshot(self) -> PromptWildcardPresentationSnapshot:
        """Return the last prepared wildcard presentation snapshot."""

        return self._snapshot

    def diagnostic_provider_ready(self) -> bool:
        """Return whether wildcard diagnostics should be included."""

        return self._feature_profile.wildcard_syntax_enabled

    def diagnostic_providers(self) -> tuple[PromptDiagnosticProvider, ...]:
        """Return prepared wildcard diagnostic providers for diagnostics refresh."""

        if not self.diagnostic_provider_ready():
            return ()
        self._snapshot = self._build_snapshot(stale=False)
        return (PromptWildcardDiagnosticProvider(self._wildcard_catalog_gateway),)

    def actions_for_diagnostic(
        self,
        diagnostic: PromptDiagnostic,
    ) -> tuple[PromptWildcardContextAction, ...]:
        """Return prepared context actions for one wildcard diagnostic."""

        if diagnostic.kind is not PromptDiagnosticKind.WILDCARD:
            return ()
        self._snapshot = self._build_snapshot(stale=False, wildcard_action_ready=True)
        return (
            PromptWildcardContextAction(
                label="Wildcard not found",
                callback_ready=False,
                disabled_reason="missing_wildcard",
            ),
        )

    def wildcard_autocomplete_enabled(self) -> bool:
        """Return whether wildcard autocomplete may present suggestions."""

        return self._feature_profile.wildcard_autocomplete_enabled

    def wildcard_autocomplete_suggestions(
        self,
        prefix: str,
        *,
        limit: int,
        source_identity: PromptCommandSourceIdentity | None = None,
        query_identity: Hashable | None = None,
        current_query_identity: (
            PromptWildcardAutocompleteQueryIdentityProvider | None
        ) = None,
        refresh_current_query: PromptWildcardAutocompleteRefreshCallback | None = None,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return cached wildcard autocomplete suggestions for one query."""

        query_snapshot = self.wildcard_autocomplete_snapshot(
            prefix=prefix,
            limit=limit,
            source_identity=source_identity,
            query_identity=query_identity,
            current_query_identity=current_query_identity,
            refresh_current_query=refresh_current_query,
        )
        if not query_snapshot.consumable:
            return ()
        return query_snapshot.suggestions

    def wildcard_autocomplete_snapshot(
        self,
        *,
        prefix: str,
        limit: int,
        source_identity: PromptCommandSourceIdentity | None = None,
        query_identity: Hashable | None = None,
        current_query_identity: (
            PromptWildcardAutocompleteQueryIdentityProvider | None
        ) = None,
        refresh_current_query: PromptWildcardAutocompleteRefreshCallback | None = None,
    ) -> PromptWildcardAutocompleteQuerySnapshot:
        """Return prepared wildcard autocomplete rows and queue cold refreshes."""

        if not self.wildcard_autocomplete_enabled():
            snapshot = self._query_snapshot(
                prefix=prefix,
                limit=limit,
                status=CatalogSnapshotStatus(
                    CatalogSnapshotReadiness.DISABLED,
                    unavailable_reason="wildcard_autocomplete_disabled",
                ),
                suggestions=(),
                query_identity=query_identity,
            )
            self._publish_presentation_snapshot(
                query_snapshot=snapshot,
                unavailable_reason="wildcard_autocomplete_disabled",
            )
            return snapshot
        if limit <= 0:
            snapshot = self._query_snapshot(
                prefix=prefix,
                limit=limit,
                status=CatalogSnapshotStatus(
                    CatalogSnapshotReadiness.UNAVAILABLE,
                    unavailable_reason="invalid_limit",
                ),
                suggestions=(),
                query_identity=query_identity,
            )
            self._publish_presentation_snapshot(
                query_snapshot=snapshot,
                unavailable_reason="invalid_limit",
            )
            return snapshot

        cache_key = self._autocomplete_cache_key(prefix=prefix, limit=limit)
        cached = self._autocomplete_cache.get(cache_key)
        if cached is not None:
            self._autocomplete_cache.move_to_end(cache_key)
            snapshot = self._query_snapshot(
                prefix=prefix,
                limit=limit,
                status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
                suggestions=cached,
                cache_key=cache_key,
                query_identity=query_identity,
            )
            self._autocomplete_snapshots[cache_key] = snapshot
            self._publish_presentation_snapshot(query_snapshot=snapshot)
            return snapshot

        stale_snapshot = self._stale_snapshot_for_query(
            prefix=prefix,
            limit=limit,
            query_identity=query_identity,
        )
        self.request_wildcard_autocomplete_refresh(
            prefix=prefix,
            limit=limit,
            source_identity=source_identity,
            query_identity=query_identity,
            current_query_identity=current_query_identity,
            refresh_current_query=refresh_current_query,
        )
        if stale_snapshot is not None:
            self._publish_presentation_snapshot(
                query_snapshot=stale_snapshot,
                unavailable_reason=stale_snapshot.status.unavailable_reason,
            )
            return stale_snapshot

        snapshot = self._query_snapshot(
            prefix=prefix,
            limit=limit,
            status=CatalogSnapshotStatus(CatalogSnapshotReadiness.COLD),
            suggestions=(),
            cache_key=cache_key,
            query_identity=query_identity,
            pending=cache_key in self._pending_autocomplete_requests,
        )
        self._autocomplete_snapshots[cache_key] = snapshot
        self._publish_presentation_snapshot(query_snapshot=snapshot)
        return snapshot

    def request_wildcard_autocomplete_refresh(
        self,
        *,
        prefix: str,
        limit: int,
        source_identity: PromptCommandSourceIdentity | None = None,
        query_identity: Hashable | None = None,
        current_query_identity: (
            PromptWildcardAutocompleteQueryIdentityProvider | None
        ) = None,
        refresh_current_query: PromptWildcardAutocompleteRefreshCallback | None = None,
    ) -> bool:
        """Schedule one wildcard autocomplete catalog query outside foreground paths."""

        if not self.wildcard_autocomplete_enabled() or limit <= 0:
            return False
        cache_key = self._autocomplete_cache_key(prefix=prefix, limit=limit)
        if cache_key in self._pending_autocomplete_requests:
            return False
        self._pending_autocomplete_requests.add(cache_key)
        self._request_id += 1
        request_identity = self._async_identity(
            request_id=self._request_id,
            source_identity=source_identity,
            query_identity=query_identity,
        )
        refresh_request = PromptWildcardAutocompleteRequest(
            identity=request_identity,
            cache_key=cache_key,
            prefix=prefix,
            limit=limit,
            source_identity=source_identity,
            current_query_identity=current_query_identity,
            refresh_current_query=refresh_current_query,
        )
        request = PromptAsyncRequest(
            identity=request_identity,
            context=PromptAsyncRequestContext(
                operation=_WILDCARD_AUTOCOMPLETE_OPERATION,
                reason="query_refresh",
                safe_fields=(
                    ("prefix_length", len(prefix)),
                    ("query_limit_count", limit),
                    ("cached_query_count", len(self._autocomplete_cache)),
                ),
            ),
            work=lambda _token: self._wildcard_catalog_gateway.search_wildcards(
                prefix,
                limit=limit,
            ),
        )
        handle = self._request_channel.submit_latest(request)
        handle.add_done_callback(
            lambda outcome: self._handle_autocomplete_outcome(
                refresh_request,
                outcome,
            ),
            reason=_WILDCARD_AUTOCOMPLETE_COMPLETION_REASON,
        )
        return True

    def clear_autocomplete_cache(self) -> None:
        """Clear cached wildcard autocomplete rows after catalog invalidation."""

        self._autocomplete_cache.clear()
        self._autocomplete_snapshots.clear()
        self._pending_autocomplete_requests.clear()
        self._request_channel.cancel_pending(reason="wildcard_autocomplete_cleared")
        self._snapshot = self._build_snapshot(stale=False)

    def pending_autocomplete_cache_keys(
        self,
    ) -> tuple[PromptWildcardAutocompleteCacheKey, ...]:
        """Return pending wildcard autocomplete cache keys for tests."""

        return tuple(self._pending_autocomplete_requests)

    def cached_autocomplete_cache_keys(
        self,
    ) -> tuple[PromptWildcardAutocompleteCacheKey, ...]:
        """Return cached wildcard autocomplete keys in LRU order for tests."""

        return tuple(self._autocomplete_cache)

    def complete_autocomplete_refresh_for_tests(
        self,
        *,
        prefix: str,
        limit: int,
        suggestions: tuple[PromptAutocompleteSuggestion, ...],
        source_identity: PromptCommandSourceIdentity | None = None,
        query_identity: Hashable | None = None,
        current_query_identity: (
            PromptWildcardAutocompleteQueryIdentityProvider | None
        ) = None,
        refresh_current_query: PromptWildcardAutocompleteRefreshCallback | None = None,
    ) -> None:
        """Publish wildcard autocomplete rows directly for deterministic tests."""

        request = PromptWildcardAutocompleteRequest(
            identity=self._async_identity(
                request_id=self._request_id + 1,
                source_identity=source_identity,
                query_identity=query_identity,
            ),
            cache_key=self._autocomplete_cache_key(prefix=prefix, limit=limit),
            prefix=prefix,
            limit=limit,
            source_identity=source_identity,
            current_query_identity=current_query_identity,
            refresh_current_query=refresh_current_query,
        )
        self._publish_autocomplete_success(
            request=request,
            suggestions=suggestions,
        )

    def fail_autocomplete_refresh_for_tests(
        self,
        *,
        prefix: str,
        limit: int,
        error: BaseException,
        source_identity: PromptCommandSourceIdentity | None = None,
        query_identity: Hashable | None = None,
    ) -> None:
        """Publish a wildcard autocomplete failure directly for deterministic tests."""

        request = PromptWildcardAutocompleteRequest(
            identity=self._async_identity(
                request_id=self._request_id + 1,
                source_identity=source_identity,
                query_identity=query_identity,
            ),
            cache_key=self._autocomplete_cache_key(prefix=prefix, limit=limit),
            prefix=prefix,
            limit=limit,
            source_identity=source_identity,
            current_query_identity=None,
            refresh_current_query=None,
        )
        self._publish_autocomplete_failure(request=request, error=error)

    def _build_snapshot(
        self,
        *,
        stale: bool,
        wildcard_action_ready: bool = False,
        unavailable_reason: str | None = None,
    ) -> PromptWildcardPresentationSnapshot:
        """Return a source-identified wildcard presentation snapshot."""

        source_revision = self._source_revision()
        identity = PromptFeatureSnapshotIdentity(
            source_revision=source_revision,
            feature_profile_id=self._feature_profile.identity.feature_profile_id,
            stale=stale,
        )
        catalog_identity = self._catalog_identity()
        wildcard_syntax_enabled = self._feature_profile.wildcard_syntax_enabled
        autocomplete_enabled = self._feature_profile.wildcard_autocomplete_enabled
        return PromptWildcardPresentationSnapshot(
            identity=identity,
            catalog_identity=catalog_identity,
            diagnostics=PromptWildcardDiagnosticsState(
                enabled=wildcard_syntax_enabled,
                provider_ready=wildcard_syntax_enabled,
                action_ready=wildcard_action_ready,
                disabled_reason=None
                if wildcard_syntax_enabled
                else "wildcard_syntax_disabled",
            ),
            autocomplete=PromptWildcardAutocompleteState(
                enabled=autocomplete_enabled,
                catalog_identity=catalog_identity,
                cached_query_count=len(self._autocomplete_cache),
                disabled_reason=None
                if autocomplete_enabled
                else "wildcard_autocomplete_disabled",
            ),
            numeric_step=PromptWildcardNumericStepState(
                enabled=wildcard_syntax_enabled,
                mutates_through_commands=True,
                source="syntax_render_plan",
                disabled_reason=None
                if wildcard_syntax_enabled
                else "wildcard_syntax_disabled",
            ),
            unavailable_reason=unavailable_reason,
        )

    def _publish_presentation_snapshot(
        self,
        *,
        query_snapshot: PromptWildcardAutocompleteQuerySnapshot | None = None,
        unavailable_reason: str | None = None,
    ) -> None:
        """Publish wildcard readiness with optional autocomplete query state."""

        self._snapshot = self._build_snapshot(
            stale=query_snapshot is not None
            and query_snapshot.status.readiness is CatalogSnapshotReadiness.STALE,
            unavailable_reason=unavailable_reason,
        )
        if query_snapshot is None:
            return
        autocomplete_state = PromptWildcardAutocompleteState(
            enabled=self._snapshot.autocomplete.enabled,
            catalog_identity=self._snapshot.autocomplete.catalog_identity,
            cached_query_count=self._snapshot.autocomplete.cached_query_count,
            disabled_reason=self._snapshot.autocomplete.disabled_reason,
            status=query_snapshot.status,
            query_identity=query_snapshot.identity.query_identity,
            pending_query_count=len(self._pending_autocomplete_requests),
        )
        self._snapshot = PromptWildcardPresentationSnapshot(
            identity=self._snapshot.identity,
            catalog_identity=self._snapshot.catalog_identity,
            diagnostics=self._snapshot.diagnostics,
            autocomplete=autocomplete_state,
            numeric_step=self._snapshot.numeric_step,
            unavailable_reason=unavailable_reason,
        )

    def _handle_autocomplete_outcome(
        self,
        request: PromptWildcardAutocompleteRequest,
        outcome: PromptAsyncTaskOutcome[tuple[PromptAutocompleteSuggestion, ...]],
    ) -> None:
        """Publish one async wildcard autocomplete outcome if still applicable."""

        self._pending_autocomplete_requests.discard(request.cache_key)
        if outcome.cancelled:
            return
        if outcome.error is not None:
            self._publish_autocomplete_failure(request=request, error=outcome.error)
            return
        if outcome.result is None:
            self._publish_autocomplete_failure(
                request=request,
                error=RuntimeError("Wildcard autocomplete returned no result."),
            )
            return
        self._publish_autocomplete_success(
            request=request,
            suggestions=tuple(outcome.result),
        )

    def _publish_autocomplete_success(
        self,
        *,
        request: PromptWildcardAutocompleteRequest,
        suggestions: tuple[PromptAutocompleteSuggestion, ...],
    ) -> None:
        """Cache successful wildcard autocomplete rows and refresh current query."""

        self._pending_autocomplete_requests.discard(request.cache_key)
        if not self._request_is_current(request):
            self._publish_presentation_snapshot(
                query_snapshot=self._query_snapshot(
                    prefix=request.prefix,
                    limit=request.limit,
                    status=CatalogSnapshotStatus(
                        CatalogSnapshotReadiness.STALE,
                        unavailable_reason="stale_query",
                    ),
                    suggestions=(),
                    cache_key=request.cache_key,
                    query_identity=request.identity.query_identity,
                ),
                unavailable_reason="stale_query",
            )
            return
        self._autocomplete_cache[request.cache_key] = suggestions
        self._autocomplete_cache.move_to_end(request.cache_key)
        self._trim_autocomplete_cache()
        snapshot = self._query_snapshot(
            prefix=request.prefix,
            limit=request.limit,
            status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
            suggestions=suggestions,
            cache_key=request.cache_key,
            query_identity=request.identity.query_identity,
        )
        self._autocomplete_snapshots[request.cache_key] = snapshot
        self._publish_presentation_snapshot(query_snapshot=snapshot)
        if request.refresh_current_query is not None:
            request.refresh_current_query()

    def _publish_autocomplete_failure(
        self,
        *,
        request: PromptWildcardAutocompleteRequest,
        error: BaseException,
    ) -> None:
        """Record a failed wildcard autocomplete query without raising foreground errors."""

        self._pending_autocomplete_requests.discard(request.cache_key)
        stale_snapshot = self._stale_snapshot_for_query(
            prefix=request.prefix,
            limit=request.limit,
            query_identity=request.identity.query_identity,
        )
        snapshot = stale_snapshot or self._query_snapshot(
            prefix=request.prefix,
            limit=request.limit,
            status=CatalogSnapshotStatus(
                CatalogSnapshotReadiness.REFRESH_FAILED,
                unavailable_reason="refresh_failed",
            ),
            suggestions=(),
            cache_key=request.cache_key,
            query_identity=request.identity.query_identity,
        )
        self._autocomplete_snapshots[request.cache_key] = snapshot
        self._publish_presentation_snapshot(
            query_snapshot=snapshot,
            unavailable_reason="refresh_failed",
        )
        log_prompt_async_warning(
            _LOGGER,
            "wildcard_autocomplete.query_refresh.failed",
            error=error,
            request_id=request.identity.request_id,
            prefix_length=len(request.prefix),
            query_limit_count=request.limit,
            cached_query_count=len(self._autocomplete_cache),
        )

    def _query_snapshot(
        self,
        *,
        prefix: str,
        limit: int,
        status: CatalogSnapshotStatus,
        suggestions: tuple[PromptAutocompleteSuggestion, ...],
        cache_key: PromptWildcardAutocompleteCacheKey | None = None,
        query_identity: Hashable | None = None,
        pending: bool = False,
    ) -> PromptWildcardAutocompleteQuerySnapshot:
        """Build one prepared wildcard autocomplete query snapshot."""

        return PromptWildcardAutocompleteQuerySnapshot(
            identity=CatalogSnapshotIdentity(
                source_revision=self._source_revision(),
                feature_profile_id=self._feature_profile.identity.feature_profile_id,
                catalog_revision=self._catalog_revision(),
                query_identity=query_identity
                or ("wildcard", prefix, limit, self._catalog_identity()),
                stale=status.readiness is CatalogSnapshotReadiness.STALE,
                unavailable_reason=status.unavailable_reason,
            ),
            status=status,
            prefix=prefix,
            limit=limit,
            suggestions=suggestions,
            cache_key=cache_key,
            pending=pending,
        )

    def _stale_snapshot_for_query(
        self,
        *,
        prefix: str,
        limit: int,
        query_identity: Hashable | None,
    ) -> PromptWildcardAutocompleteQuerySnapshot | None:
        """Return stale rows for the same query across catalog identity changes."""

        for cache_key, suggestions in reversed(self._autocomplete_cache.items()):
            _catalog_identity, cached_prefix, cached_limit = cache_key
            if cached_prefix != prefix or cached_limit != limit:
                continue
            return self._query_snapshot(
                prefix=prefix,
                limit=limit,
                status=CatalogSnapshotStatus(
                    CatalogSnapshotReadiness.STALE,
                    unavailable_reason="catalog_identity_changed",
                ),
                suggestions=suggestions,
                cache_key=cache_key,
                query_identity=query_identity,
                pending=True,
            )
        return None

    def _request_is_current(
        self,
        request: PromptWildcardAutocompleteRequest,
    ) -> bool:
        """Return whether a completed request still matches current editor state."""

        if request.current_query_identity is not None:
            if request.current_query_identity() != request.identity.query_identity:
                return False
        if request.source_identity is None or self._host is None:
            return True
        current_identity = self._host.prompt_command_source_identity()
        current_revision = getattr(current_identity, "source_revision", None)
        current_length = getattr(current_identity, "source_length", None)
        if not isinstance(current_revision, int):
            return False
        if current_length is not None and not isinstance(current_length, int):
            return False
        return request.source_identity.matches(
            source_revision=current_revision,
            source_length=current_length,
        )

    def _async_identity(
        self,
        *,
        request_id: int,
        source_identity: PromptCommandSourceIdentity | None,
        query_identity: Hashable | None,
    ) -> PromptAsyncResultIdentity:
        """Return prompt-safe async identity for one wildcard autocomplete request."""

        return PromptAsyncResultIdentity(
            request_id=request_id,
            source_revision=None
            if source_identity is None
            else source_identity.source_revision,
            source_length=None
            if source_identity is None
            else source_identity.source_length,
            feature_profile_id=self._feature_profile.identity.feature_profile_id,
            query_identity=query_identity,
        )

    def _autocomplete_cache_key(
        self,
        *,
        prefix: str,
        limit: int,
    ) -> PromptWildcardAutocompleteCacheKey:
        """Return the current catalog-bound wildcard autocomplete cache key."""

        return (self._catalog_identity(), prefix, limit)

    def _trim_autocomplete_cache(self) -> None:
        """Keep wildcard autocomplete rows within the configured LRU limit."""

        while len(self._autocomplete_cache) > _AUTOCOMPLETE_CACHE_LIMIT:
            cache_key, _suggestions = self._autocomplete_cache.popitem(last=False)
            self._autocomplete_snapshots.pop(cache_key, None)

    def _catalog_identity(self) -> Hashable:
        """Return the catalog identity used by wildcard presentation caches."""

        revision = self._catalog_revision()
        return (
            type(self._wildcard_catalog_gateway).__qualname__,
            id(self._wildcard_catalog_gateway),
            revision,
        )

    def _catalog_revision(self) -> Hashable | None:
        """Return the wildcard catalog revision when exposed by the gateway."""

        revision = getattr(self._wildcard_catalog_gateway, "cache_revision", None)
        return revision if isinstance(revision, Hashable) else repr(revision)

    def _source_revision(self) -> int | None:
        """Return the current prompt source revision when supplied by the host."""

        if self._host is None:
            return None
        source_identity = self._host.prompt_command_source_identity()
        return getattr(source_identity, "source_revision", None)


__all__ = [
    "PromptWildcardAutocompleteCacheKey",
    "PromptWildcardAutocompleteQuerySnapshot",
    "PromptWildcardAutocompleteRefreshCallback",
    "PromptWildcardAutocompleteRequest",
    "PromptWildcardAutocompleteState",
    "PromptWildcardContextAction",
    "PromptWildcardDiagnosticsState",
    "PromptWildcardFeatureController",
    "PromptWildcardNumericStepState",
    "PromptWildcardPresentationSnapshot",
    "PromptWildcardSourceHost",
]

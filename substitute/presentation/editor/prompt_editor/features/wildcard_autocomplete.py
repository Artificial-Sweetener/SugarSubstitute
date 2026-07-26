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

"""Own bounded wildcard autocomplete caching and asynchronous query lifecycle."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass

from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardCatalogGateway,
)
from substitute.shared.logging.logger import get_logger

from ..async_work import (
    PromptAsyncRequest,
    PromptAsyncRequestContext,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptEditorRequestChannel,
    log_prompt_async_warning,
)
from ..core.state.revisions import PromptSourceIdentity

from .catalog_snapshots import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
)
from .feature_profile_controller import PromptFeatureProfileController
from .wildcard_autocomplete_cache import PromptWildcardAutocompleteCache
from .wildcard_models import (
    PromptWildcardAutocompleteCacheKey,
    PromptWildcardAutocompleteQueryIdentityProvider,
    PromptWildcardAutocompleteQuerySnapshot,
    PromptWildcardAutocompleteRefreshCallback,
    PromptWildcardAutocompleteRequest,
)

_AUTOCOMPLETE_CACHE_LIMIT = 64
_WILDCARD_AUTOCOMPLETE_OPERATION = "wildcard_autocomplete_query"
_WILDCARD_AUTOCOMPLETE_COMPLETION_REASON = "wildcard_autocomplete_query_completed"
_LOGGER = get_logger("presentation.editor.prompt_editor.features.wildcard_autocomplete")


@dataclass(frozen=True, slots=True)
class PromptWildcardAutocompleteState:
    """Publish prepared autocomplete cache state for diagnostics and tests."""

    enabled: bool
    catalog_identity: Hashable
    cached_query_count: int
    disabled_reason: str | None = None
    status: CatalogSnapshotStatus | None = None
    query_identity: Hashable | None = None
    pending_query_count: int = 0


class PromptWildcardAutocompletePresentation:
    """Own wildcard autocomplete cache, request lifecycle, and query snapshots."""

    def __init__(
        self,
        *,
        feature_profile: PromptFeatureProfileController,
        wildcard_catalog_gateway: PromptWildcardCatalogGateway,
        source_identity_provider: Callable[[], object | None] | None = None,
        request_channel: PromptEditorRequestChannel[
            tuple[PromptAutocompleteSuggestion, ...]
        ]
        | None = None,
    ) -> None:
        """Store wildcard dependencies and publish an initial query-state snapshot."""

        self._feature_profile = feature_profile
        self._wildcard_catalog_gateway = wildcard_catalog_gateway
        self._source_identity_provider = source_identity_provider
        self._autocomplete_cache = PromptWildcardAutocompleteCache(
            limit=_AUTOCOMPLETE_CACHE_LIMIT
        )
        self._pending_autocomplete_requests: set[PromptWildcardAutocompleteCacheKey] = (
            set()
        )
        self._request_id = 0
        if request_channel is None:
            raise TypeError(
                "request_channel is required for prompt wildcard autocomplete."
            )
        self._request_channel = request_channel
        self._snapshot = self._build_state()

    @property
    def snapshot(self) -> PromptWildcardAutocompleteState:
        """Return the last prepared wildcard autocomplete state."""

        return self._snapshot

    def wildcard_autocomplete_enabled(self) -> bool:
        """Return whether wildcard autocomplete may present suggestions."""

        return self._feature_profile.wildcard_autocomplete_enabled

    def wildcard_autocomplete_suggestions(
        self,
        prefix: str,
        *,
        limit: int,
        source_identity: PromptSourceIdentity | None = None,
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
        source_identity: PromptSourceIdentity | None = None,
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
            self._publish_state(query_snapshot=snapshot)
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
            self._publish_state(query_snapshot=snapshot)
            return snapshot

        cache_key = self._autocomplete_cache_key(prefix=prefix, limit=limit)
        cached = self._autocomplete_cache.get(cache_key)
        if cached is not None:
            snapshot = self._query_snapshot(
                prefix=prefix,
                limit=limit,
                status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
                suggestions=cached,
                cache_key=cache_key,
                query_identity=query_identity,
            )
            self._publish_state(query_snapshot=snapshot)
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
        completed_during_submission = self._autocomplete_cache.get(cache_key)
        if completed_during_submission is not None:
            snapshot = self._query_snapshot(
                prefix=prefix,
                limit=limit,
                status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
                suggestions=completed_during_submission,
                cache_key=cache_key,
                query_identity=query_identity,
            )
            self._publish_state(query_snapshot=snapshot)
            return snapshot
        if stale_snapshot is not None:
            self._publish_state(query_snapshot=stale_snapshot)
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
        self._publish_state(query_snapshot=snapshot)
        return snapshot

    def request_wildcard_autocomplete_refresh(
        self,
        *,
        prefix: str,
        limit: int,
        source_identity: PromptSourceIdentity | None = None,
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
                    ("cached_query_count", self._autocomplete_cache.count),
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
        self._pending_autocomplete_requests.clear()
        self._request_channel.cancel_pending(reason="wildcard_autocomplete_cleared")
        self._snapshot = self._build_state()

    def pending_autocomplete_cache_keys(
        self,
    ) -> tuple[PromptWildcardAutocompleteCacheKey, ...]:
        """Return pending wildcard autocomplete cache keys for tests."""

        return tuple(self._pending_autocomplete_requests)

    def cached_autocomplete_cache_keys(
        self,
    ) -> tuple[PromptWildcardAutocompleteCacheKey, ...]:
        """Return cached wildcard autocomplete keys in LRU order for tests."""

        return self._autocomplete_cache.keys()

    def complete_autocomplete_refresh_for_tests(
        self,
        *,
        prefix: str,
        limit: int,
        suggestions: tuple[PromptAutocompleteSuggestion, ...],
        source_identity: PromptSourceIdentity | None = None,
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
        source_identity: PromptSourceIdentity | None = None,
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

    def _build_state(
        self,
        *,
        query_snapshot: PromptWildcardAutocompleteQuerySnapshot | None = None,
    ) -> PromptWildcardAutocompleteState:
        """Return the current autocomplete-only presentation state."""

        catalog_identity = self._catalog_identity()
        autocomplete_enabled = self._feature_profile.wildcard_autocomplete_enabled
        return PromptWildcardAutocompleteState(
            catalog_identity=catalog_identity,
            enabled=autocomplete_enabled,
            cached_query_count=self._autocomplete_cache.count,
            disabled_reason=(
                None if autocomplete_enabled else "wildcard_autocomplete_disabled"
            ),
            status=None if query_snapshot is None else query_snapshot.status,
            query_identity=(
                None
                if query_snapshot is None
                else query_snapshot.identity.query_identity
            ),
            pending_query_count=len(self._pending_autocomplete_requests),
        )

    def _publish_state(
        self,
        *,
        query_snapshot: PromptWildcardAutocompleteQuerySnapshot | None = None,
    ) -> None:
        """Publish current autocomplete cache state after one query transition."""

        self._snapshot = self._build_state(query_snapshot=query_snapshot)

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
            self._publish_state(
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
            )
            return
        self._autocomplete_cache.store(request.cache_key, suggestions)
        snapshot = self._query_snapshot(
            prefix=request.prefix,
            limit=request.limit,
            status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
            suggestions=suggestions,
            cache_key=request.cache_key,
            query_identity=request.identity.query_identity,
        )
        self._publish_state(query_snapshot=snapshot)
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
        self._publish_state(query_snapshot=snapshot)
        log_prompt_async_warning(
            _LOGGER,
            "wildcard_autocomplete.query_refresh.failed",
            error=error,
            request_id=request.identity.request_id,
            prefix_length=len(request.prefix),
            query_limit_count=request.limit,
            cached_query_count=self._autocomplete_cache.count,
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

        stale_rows = self._autocomplete_cache.stale_rows(
            prefix=prefix,
            limit=limit,
        )
        if stale_rows is None:
            return None
        cache_key, suggestions = stale_rows
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

    def _request_is_current(
        self,
        request: PromptWildcardAutocompleteRequest,
    ) -> bool:
        """Return whether a completed request still matches current editor state."""

        if request.current_query_identity is not None:
            if request.current_query_identity() != request.identity.query_identity:
                return False
        if request.source_identity is None or self._source_identity_provider is None:
            return True
        current_identity = self._source_identity_provider()
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
        source_identity: PromptSourceIdentity | None,
        query_identity: Hashable | None,
    ) -> PromptAsyncResultIdentity:
        """Return prompt-safe async identity for one wildcard autocomplete request."""

        return PromptAsyncResultIdentity(
            request_id=request_id,
            source_identity=source_identity,
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

        if self._source_identity_provider is None:
            return None
        source_identity = self._source_identity_provider()
        return getattr(source_identity, "source_revision", None)


__all__ = [
    "PromptWildcardAutocompleteCacheKey",
    "PromptWildcardAutocompleteQuerySnapshot",
    "PromptWildcardAutocompleteRefreshCallback",
    "PromptWildcardAutocompleteRequest",
    "PromptWildcardAutocompleteState",
    "PromptWildcardAutocompletePresentation",
]

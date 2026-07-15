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

"""Resolve shared scheduled-LoRA context through the async boundary."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol, cast

from substitute.application.prompt_editor import (
    PromptScheduledLora,
    PromptTriggerWordIndex,
    PromptTriggerWordSuggestion,
)
from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.shared.logging.logger import get_logger

from ..commands import PromptCommandSourceIdentity
from .cancellation import PromptEditorCancellationController
from .execution import (
    PromptAsyncRequest,
    PromptAsyncRequestContext,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptEditorExecutor,
    PromptEditorTaskHandle,
)
from .main_thread_dispatcher import (
    PromptEditorMainThreadDispatcher,
    QtPromptEditorMainThreadDispatcher,
)
from .observability import (
    log_prompt_async_debug,
    log_prompt_async_warning,
    prompt_async_freshness_log_fields,
    prompt_async_outcome_log_fields,
)
from .stale_result_guard import PromptFreshnessField, PromptStaleResultGuard
from .task_executor import PromptEditorTaskExecutor

_LOGGER = get_logger(
    "presentation.editor.prompt_editor.async_work.scheduled_lora_context"
)

_SCHEDULED_LORA_CONTEXT_CACHE_LIMIT = 64
_SCHEDULED_LORA_OPERATION = "scheduled_lora_context"
_TASK_COMPLETION_REASON = "scheduled_lora_context_completed"

PromptScheduledLoraContextCacheKey = tuple[Hashable, str]
PromptScheduledLoraContextToken = tuple[Hashable, int, int]
PromptScheduledLoraResolver = Callable[[str], tuple[PromptScheduledLora, ...]]
PromptScheduledLoraSignature = tuple[
    tuple[str, str, str, tuple[str, ...], str],
    ...,
]


@dataclass(frozen=True, slots=True)
class PromptAutocompleteTriggerWordResult:
    """Carry prepared trigger-word rows and their scheduled-LoRA signature."""

    suggestions: tuple[PromptAutocompleteSuggestion, ...]
    scheduled_lora_signature: PromptScheduledLoraSignature


@dataclass(frozen=True, slots=True)
class PromptScheduledLoraContext:
    """Store resolved scheduled-LoRA context for autocomplete and menus."""

    scheduled_loras: tuple[PromptScheduledLora, ...]
    signature: PromptScheduledLoraSignature
    trigger_word_index: PromptTriggerWordIndex


@dataclass(frozen=True, slots=True)
class PromptScheduledLoraCachedContextSnapshot:
    """Publish a cached scheduled-LoRA context with prompt-safe identity."""

    cache_key: PromptScheduledLoraContextCacheKey
    prompt_context_token: PromptScheduledLoraContextToken
    scheduled_loras: tuple[PromptScheduledLora, ...]
    signature: PromptScheduledLoraSignature


@dataclass(frozen=True, slots=True)
class PromptScheduledLoraContextRequest:
    """Carry one scheduled-LoRA context request without prompt text in logs."""

    identity: PromptAsyncResultIdentity
    cache_key: PromptScheduledLoraContextCacheKey
    prompt_text: str
    source_text: str | None
    queued_at: float


class PromptScheduledLoraContextProvider(Protocol):
    """Return cached scheduled-LoRA context and schedule async refreshes."""

    def prewarm(self, prompt_text: str) -> bool:
        """Schedule scheduled-LoRA context warmup for one prompt snapshot."""

    def cached_scheduled_loras(
        self,
        prompt_text: str,
    ) -> tuple[PromptScheduledLora, ...] | None:
        """Return cached scheduled LoRAs for one prompt snapshot."""

    def cached_context_snapshot(
        self,
        prompt_text: str,
    ) -> PromptScheduledLoraCachedContextSnapshot | None:
        """Return cached scheduled-LoRA context identity for one prompt snapshot."""

    def trigger_word_result(
        self,
        *,
        prefix: str,
        prompt_text: str,
        source_text: str,
        source_identity: PromptCommandSourceIdentity | None,
        query_identity: Hashable | None,
        current_source_text: Callable[[], str] | None,
        current_query_identity: Callable[[], Hashable | None],
        refresh_current_query: Callable[[], None],
        current_source_identity: Callable[[], PromptCommandSourceIdentity | None]
        | None = None,
    ) -> PromptAutocompleteTriggerWordResult:
        """Return cached trigger words and queue a stale-safe refresh when cold."""


class PromptScheduledLoraContextCoordinator:
    """Own shared scheduled-LoRA cache, task dispatch, and publication."""

    def __init__(
        self,
        *,
        resolver: PromptScheduledLoraResolver | None,
        enabled: bool,
        parent: object | None = None,
        executor: PromptEditorExecutor | None = None,
        dispatcher: PromptEditorMainThreadDispatcher | None = None,
        stale_result_guard: PromptStaleResultGuard | None = None,
        cache_limit: int = _SCHEDULED_LORA_CONTEXT_CACHE_LIMIT,
    ) -> None:
        """Create an async owner for shared scheduled-LoRA context."""

        self._resolver = resolver
        self._enabled = enabled and resolver is not None
        self._dispatcher = dispatcher or QtPromptEditorMainThreadDispatcher(
            cast(Any, parent)
        )
        if executor is None:
            raise TypeError("executor is required for scheduled LoRA context.")
        self._executor = executor
        self._owns_executor = isinstance(self._executor, PromptEditorTaskExecutor)
        self._stale_result_guard = stale_result_guard or PromptStaleResultGuard()
        self._cancellation_controller = PromptEditorCancellationController()
        self._cache_limit = cache_limit
        self._request_id = 0
        self._context_cache: OrderedDict[
            PromptScheduledLoraContextCacheKey,
            PromptScheduledLoraContext,
        ] = OrderedDict()
        self._pending_requests: dict[
            PromptScheduledLoraContextCacheKey,
            PromptEditorTaskHandle[tuple[PromptScheduledLora, ...]],
        ] = {}
        self._requests_by_identity: dict[
            PromptAsyncResultIdentity,
            PromptScheduledLoraContextRequest,
        ] = {}
        self._trigger_word_index_signature: PromptScheduledLoraSignature | None = None
        self._trigger_word_index = PromptTriggerWordIndex.build(())

    @property
    def enabled(self) -> bool:
        """Return whether async scheduled-LoRA trigger context is available."""

        return self._enabled

    @property
    def cache_limit(self) -> int:
        """Return the bounded scheduled-LoRA context cache limit."""

        return self._cache_limit

    def prewarm(self, prompt_text: str) -> bool:
        """Schedule scheduled-LoRA context warmup for one prompt snapshot."""

        return self._schedule_context_refresh(
            prompt_text=prompt_text,
            source_text=None,
            source_identity=None,
            query_identity=None,
            current_source_text=None,
            current_query_identity=None,
            refresh_current_query=None,
        )

    def cached_scheduled_loras(
        self,
        prompt_text: str,
    ) -> tuple[PromptScheduledLora, ...] | None:
        """Return cached scheduled LoRAs for one prompt snapshot."""

        snapshot = self.cached_context_snapshot(prompt_text)
        if snapshot is None:
            return None
        return snapshot.scheduled_loras

    def cached_context_snapshot(
        self,
        prompt_text: str,
    ) -> PromptScheduledLoraCachedContextSnapshot | None:
        """Return cached scheduled-LoRA context identity for one prompt snapshot."""

        cache_key = self.cache_key_for_prompt(prompt_text)
        cached = self._cached_context(cache_key)
        if cached is None:
            return None
        return PromptScheduledLoraCachedContextSnapshot(
            cache_key=cache_key,
            prompt_context_token=self._prompt_context_token(cache_key),
            scheduled_loras=cached.scheduled_loras,
            signature=cached.signature,
        )

    def trigger_word_result(
        self,
        *,
        prefix: str,
        prompt_text: str,
        source_text: str,
        source_identity: PromptCommandSourceIdentity | None,
        query_identity: Hashable | None,
        current_source_text: Callable[[], str] | None,
        current_query_identity: Callable[[], Hashable | None],
        refresh_current_query: Callable[[], None],
        current_source_identity: Callable[[], PromptCommandSourceIdentity | None]
        | None = None,
    ) -> PromptAutocompleteTriggerWordResult:
        """Return cached trigger words and schedule a refresh when stale."""

        cache_key = self.cache_key_for_prompt(prompt_text)
        cached = self._cached_context(cache_key)
        if cached is not None:
            return PromptAutocompleteTriggerWordResult(
                suggestions=self._suggestions_for_prefix(cached, prefix),
                scheduled_lora_signature=cached.signature,
            )
        _ = self._schedule_context_refresh(
            prompt_text=prompt_text,
            source_text=source_text,
            source_identity=source_identity,
            query_identity=query_identity,
            current_source_text=current_source_text,
            current_source_identity=current_source_identity,
            current_query_identity=current_query_identity,
            refresh_current_query=refresh_current_query,
        )
        return PromptAutocompleteTriggerWordResult(
            suggestions=(),
            scheduled_lora_signature=(),
        )

    def cache_key_for_prompt(
        self,
        prompt_text: str,
    ) -> PromptScheduledLoraContextCacheKey:
        """Return the bounded-cache key for one prompt text snapshot."""

        resolver = self._resolver
        context_token = getattr(
            resolver,
            "scheduled_lora_context_token",
            id(resolver),
        )
        if isinstance(context_token, Hashable):
            return (context_token, prompt_text)
        return (id(resolver), prompt_text)

    def prompt_context_token_for_prompt(
        self,
        prompt_text: str,
    ) -> PromptScheduledLoraContextToken:
        """Return the prompt-safe scheduled-LoRA context token for one prompt."""

        return self._prompt_context_token(self.cache_key_for_prompt(prompt_text))

    def pending_cache_keys(self) -> tuple[PromptScheduledLoraContextCacheKey, ...]:
        """Return currently pending cache keys for tests and guardrails."""

        return tuple(self._pending_requests)

    def cached_cache_keys(self) -> tuple[PromptScheduledLoraContextCacheKey, ...]:
        """Return cached keys in LRU order for tests and guardrails."""

        return tuple(self._context_cache)

    def complete_for_tests(
        self,
        *,
        cache_key: PromptScheduledLoraContextCacheKey,
        prompt_text: str,
        scheduled_loras: tuple[PromptScheduledLora, ...],
        source_text: str | None = None,
        source_identity: PromptCommandSourceIdentity | None = None,
        query_identity: Hashable | None = None,
        current_source_text: Callable[[], str] | None = None,
        current_source_identity: Callable[[], PromptCommandSourceIdentity | None]
        | None = None,
        current_query_identity: Callable[[], Hashable | None] | None = None,
        refresh_current_query: Callable[[], None] | None = None,
    ) -> None:
        """Publish a resolved context directly for deterministic tests."""

        request = self._build_request(
            cache_key=cache_key,
            prompt_text=prompt_text,
            source_text=source_text,
            source_identity=source_identity,
            query_identity=query_identity,
        )
        self._handle_completed_context(
            request=request,
            scheduled_loras=scheduled_loras,
            current_source_text=current_source_text,
            current_source_identity=current_source_identity,
            current_query_identity=current_query_identity,
            refresh_current_query=refresh_current_query,
        )

    def fail_for_tests(
        self,
        *,
        cache_key: PromptScheduledLoraContextCacheKey,
        prompt_text: str,
        error: BaseException,
        source_text: str | None = None,
        source_identity: PromptCommandSourceIdentity | None = None,
        query_identity: Hashable | None = None,
    ) -> None:
        """Publish a failed context refresh directly for deterministic tests."""

        request = self._build_request(
            cache_key=cache_key,
            prompt_text=prompt_text,
            source_text=source_text,
            source_identity=source_identity,
            query_identity=query_identity,
        )
        self._pending_requests.pop(cache_key, None)
        log_prompt_async_warning(
            _LOGGER,
            "scheduled_lora_context.refresh.failed",
            error=error,
            operation=_SCHEDULED_LORA_OPERATION,
            reason="test_failure",
            request_id=request.identity.request_id,
            source_length=len(prompt_text),
            source_revision=request.identity.source_revision,
            query_identity=query_identity,
        )

    def shutdown(self) -> None:
        """Cancel pending scheduled-LoRA context work and release execution."""

        for handle in tuple(self._pending_requests.values()):
            handle.cancel(reason="scheduled_lora_context_shutdown")
        self._pending_requests.clear()
        self._requests_by_identity.clear()
        if self._owns_executor:
            cast(PromptEditorTaskExecutor, self._executor).shutdown(
                wait=False,
                cancel_futures=True,
            )

    def _schedule_context_refresh(
        self,
        *,
        prompt_text: str,
        source_text: str | None,
        source_identity: PromptCommandSourceIdentity | None,
        query_identity: Hashable | None,
        current_source_text: Callable[[], str] | None,
        current_query_identity: Callable[[], Hashable | None] | None,
        refresh_current_query: Callable[[], None] | None,
        current_source_identity: Callable[[], PromptCommandSourceIdentity | None]
        | None = None,
    ) -> bool:
        """Schedule one background scheduled-LoRA context refresh."""

        if not self._enabled or self._resolver is None:
            return False
        cache_key = self.cache_key_for_prompt(prompt_text)
        if self._cached_context(cache_key) is not None:
            return False
        if cache_key in self._pending_requests:
            return False
        request = self._build_request(
            cache_key=cache_key,
            prompt_text=prompt_text,
            source_text=source_text,
            source_identity=source_identity,
            query_identity=query_identity,
        )
        async_request = PromptAsyncRequest[tuple[PromptScheduledLora, ...]](
            identity=request.identity,
            context=PromptAsyncRequestContext(
                operation=_SCHEDULED_LORA_OPERATION,
                reason=(
                    "trigger_word_context"
                    if source_text is not None
                    else "context_prewarm"
                ),
                safe_fields=(
                    ("source_length", len(prompt_text)),
                    ("query_identity", query_identity),
                    ("cache_size", len(self._context_cache)),
                ),
            ),
            work=lambda _token: self._resolve_prompt(prompt_text),
        )
        cancellation = self._cancellation_controller.next_source()
        handle = self._executor.submit(async_request, cancellation=cancellation)
        self._pending_requests[cache_key] = handle
        self._requests_by_identity[handle.identity] = request
        handle.add_done_callback(
            lambda outcome: self._handle_async_outcome(
                outcome,
                current_source_text=current_source_text,
                current_source_identity=current_source_identity,
                current_query_identity=current_query_identity,
                refresh_current_query=refresh_current_query,
            ),
            reason=_TASK_COMPLETION_REASON,
        )
        return True

    def _build_request(
        self,
        *,
        cache_key: PromptScheduledLoraContextCacheKey,
        prompt_text: str,
        source_text: str | None,
        source_identity: PromptCommandSourceIdentity | None,
        query_identity: Hashable | None,
    ) -> PromptScheduledLoraContextRequest:
        """Build one request identity for shared scheduled-LoRA work."""

        self._request_id += 1
        identity = PromptAsyncResultIdentity(
            request_id=self._request_id,
            source_revision=(
                None if source_identity is None else source_identity.source_revision
            ),
            source_length=(
                len(prompt_text)
                if source_identity is None or source_identity.source_length is None
                else source_identity.source_length
            ),
            query_identity=query_identity,
        )
        return PromptScheduledLoraContextRequest(
            identity=identity,
            cache_key=cache_key,
            prompt_text=prompt_text,
            source_text=source_text,
            queued_at=perf_counter(),
        )

    def _resolve_prompt(self, prompt_text: str) -> tuple[PromptScheduledLora, ...]:
        """Resolve scheduled LoRAs away from the GUI thread."""

        resolver = self._resolver
        if resolver is None:
            return ()
        return resolver(prompt_text)

    def _handle_async_outcome(
        self,
        outcome: PromptAsyncTaskOutcome[tuple[PromptScheduledLora, ...]],
        *,
        current_source_text: Callable[[], str] | None,
        current_source_identity: Callable[[], PromptCommandSourceIdentity | None]
        | None,
        current_query_identity: Callable[[], Hashable | None] | None,
        refresh_current_query: Callable[[], None] | None,
    ) -> None:
        """Publish one task outcome through cache and stale-safe refresh hooks."""

        request = self._requests_by_identity.pop(outcome.identity, None)
        if request is None:
            request = self._request_for_pending_identity(outcome.identity)
        if request is not None:
            self._pending_requests.pop(request.cache_key, None)
        if outcome.cancelled:
            return
        if outcome.error is not None:
            log_prompt_async_warning(
                _LOGGER,
                "scheduled_lora_context.refresh.failed",
                error=outcome.error,
                **prompt_async_outcome_log_fields(outcome),
            )
            return
        if request is None or outcome.result is None:
            return
        self._handle_completed_context(
            request=request,
            scheduled_loras=outcome.result,
            current_source_text=current_source_text,
            current_source_identity=current_source_identity,
            current_query_identity=current_query_identity,
            refresh_current_query=refresh_current_query,
        )

    def _request_for_pending_identity(
        self,
        identity: PromptAsyncResultIdentity,
    ) -> PromptScheduledLoraContextRequest | None:
        """Return a request whose handle identity matches a completed outcome."""

        for cache_key, handle in tuple(self._pending_requests.items()):
            if handle.identity == identity:
                return PromptScheduledLoraContextRequest(
                    identity=identity,
                    cache_key=cache_key,
                    prompt_text=cache_key[1],
                    source_text=None,
                    queued_at=perf_counter(),
                )
        return None

    def _handle_completed_context(
        self,
        *,
        request: PromptScheduledLoraContextRequest,
        scheduled_loras: tuple[PromptScheduledLora, ...],
        current_source_text: Callable[[], str] | None,
        current_source_identity: Callable[[], PromptCommandSourceIdentity | None]
        | None,
        current_query_identity: Callable[[], Hashable | None] | None,
        refresh_current_query: Callable[[], None] | None,
    ) -> None:
        """Cache one resolved context and refresh visible tag rows when fresh."""

        context = self._context_for_scheduled_loras(scheduled_loras)
        self._cache_context(request.cache_key, context)
        if not context.signature:
            return
        if (
            current_source_text is None
            and current_source_identity is None
            or current_query_identity is None
            or refresh_current_query is None
        ):
            return
        if not self._visible_publication_is_fresh(
            request=request,
            current_source_text=current_source_text,
            current_source_identity=current_source_identity,
            current_query_identity=current_query_identity,
        ):
            return
        refresh_current_query()

    def _visible_publication_is_fresh(
        self,
        *,
        request: PromptScheduledLoraContextRequest,
        current_source_text: Callable[[], str] | None,
        current_source_identity: Callable[[], PromptCommandSourceIdentity | None]
        | None,
        current_query_identity: Callable[[], Hashable | None],
    ) -> bool:
        """Return whether a task result still matches the active tag query."""

        live_source_identity = (
            None if current_source_identity is None else current_source_identity()
        )
        if live_source_identity is not None:
            current_source_length = (
                request.identity.source_length
                if live_source_identity.source_length is None
                else live_source_identity.source_length
            )
            if (
                request.identity.source_revision is not None
                and live_source_identity.source_revision
                != request.identity.source_revision
            ):
                return False
        elif current_source_text is not None:
            current_text = current_source_text()
            if request.source_text is not None and current_text != request.source_text:
                return False
            if request.source_text is None and current_text != request.prompt_text:
                return False
            current_source_length = len(current_text)
        else:
            return False
        current_identity = PromptAsyncResultIdentity(
            request_id=request.identity.request_id,
            source_revision=request.identity.source_revision,
            source_length=current_source_length,
            query_identity=current_query_identity(),
            cancellation_generation=request.identity.cancellation_generation,
        )
        required_fields: list[PromptFreshnessField] = ["query_identity"]
        if request.identity.source_revision is not None:
            required_fields.append("source_revision")
        decision = self._stale_result_guard.validate(
            result_identity=request.identity,
            current_identity=current_identity,
            required_fields=required_fields,
        )
        if not decision.is_fresh:
            log_prompt_async_debug(
                _LOGGER,
                "scheduled_lora_context.refresh.dropped",
                **prompt_async_freshness_log_fields(decision),
                source_length=current_source_length,
                query_identity=request.identity.query_identity,
            )
        return decision.is_fresh

    def _cached_context(
        self,
        cache_key: PromptScheduledLoraContextCacheKey,
    ) -> PromptScheduledLoraContext | None:
        """Return a cached scheduled-LoRA trigger-word context."""

        cached = self._context_cache.get(cache_key)
        if cached is not None:
            self._context_cache.move_to_end(cache_key)
        return cached

    def _cache_context(
        self,
        cache_key: PromptScheduledLoraContextCacheKey,
        value: PromptScheduledLoraContext,
    ) -> None:
        """Store one bounded scheduled-LoRA trigger-word context."""

        self._context_cache[cache_key] = value
        self._context_cache.move_to_end(cache_key)
        while len(self._context_cache) > self._cache_limit:
            self._context_cache.popitem(last=False)

    @staticmethod
    def _prompt_context_token(
        cache_key: PromptScheduledLoraContextCacheKey,
    ) -> PromptScheduledLoraContextToken:
        """Return a prompt-safe identity for a scheduled-LoRA cache key."""

        context_token, prompt_text = cache_key
        return (context_token, len(prompt_text), hash(prompt_text))

    def _context_for_scheduled_loras(
        self,
        scheduled_loras: tuple[PromptScheduledLora, ...],
    ) -> PromptScheduledLoraContext:
        """Build a cached trigger-word context for resolved scheduled LoRAs."""

        signature = scheduled_lora_signature(scheduled_loras)
        trigger_word_index = self._trigger_word_index_for(signature, scheduled_loras)
        return PromptScheduledLoraContext(
            scheduled_loras=scheduled_loras,
            signature=signature,
            trigger_word_index=trigger_word_index,
        )

    def _trigger_word_index_for(
        self,
        signature: PromptScheduledLoraSignature,
        scheduled_loras: tuple[PromptScheduledLora, ...],
    ) -> PromptTriggerWordIndex:
        """Return a cached trigger-word index for one scheduled-LoRA signature."""

        if self._trigger_word_index_signature == signature:
            return self._trigger_word_index
        self._trigger_word_index_signature = signature
        self._trigger_word_index = PromptTriggerWordIndex.build(scheduled_loras)
        return self._trigger_word_index

    @staticmethod
    def _suggestions_for_prefix(
        context: PromptScheduledLoraContext,
        prefix: str,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return autocomplete suggestions for trigger words matching one prefix."""

        return tuple(
            autocomplete_suggestion_from_trigger_word(trigger_word)
            for trigger_word in context.trigger_word_index.search(prefix)
        )


def build_prompt_scheduled_lora_context_coordinator(
    *,
    resolver: PromptScheduledLoraResolver | None,
    enabled: bool,
    parent: object | None,
    executor: PromptEditorExecutor,
) -> PromptScheduledLoraContextCoordinator:
    """Build the production shared scheduled-LoRA context coordinator."""

    return PromptScheduledLoraContextCoordinator(
        resolver=resolver,
        enabled=enabled,
        parent=parent,
        executor=executor,
    )


def autocomplete_suggestion_from_trigger_word(
    trigger_word: PromptTriggerWordSuggestion,
) -> PromptAutocompleteSuggestion:
    """Adapt one LoRA trigger-word object into an autocomplete suggestion row."""

    return PromptAutocompleteSuggestion(
        tag=trigger_word.trigger_word,
        popularity=None,
        source_label=trigger_word.lora_display_name,
        source_kind="lora_trigger",
    )


def scheduled_lora_signature(
    scheduled_loras: tuple[PromptScheduledLora, ...],
) -> PromptScheduledLoraSignature:
    """Return the trigger-word output signature for scheduled LoRAs."""

    return tuple(
        (
            scheduled_lora.prompt_name,
            scheduled_lora.backend_value,
            scheduled_lora.display_name,
            scheduled_lora.trained_words,
            scheduled_lora.source,
        )
        for scheduled_lora in scheduled_loras
    )


__all__ = [
    "PromptScheduledLoraSignature",
    "PromptAutocompleteTriggerWordResult",
    "PromptScheduledLoraCachedContextSnapshot",
    "PromptScheduledLoraContextCacheKey",
    "PromptScheduledLoraContext",
    "PromptScheduledLoraContextCoordinator",
    "PromptScheduledLoraContextProvider",
    "PromptScheduledLoraContextRequest",
    "PromptScheduledLoraContextToken",
    "PromptScheduledLoraResolver",
    "autocomplete_suggestion_from_trigger_word",
    "build_prompt_scheduled_lora_context_coordinator",
    "scheduled_lora_signature",
]

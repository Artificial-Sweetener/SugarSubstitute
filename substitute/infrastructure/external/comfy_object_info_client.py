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

"""Fetch and cache live Comfy node definitions for editor option lookups."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from threading import RLock
from time import perf_counter
from typing import Any

from substitute.application.ports import (
    NodeDefinitionHydrationResult,
    NodeDefinitionRefreshEvent,
    NodeDefinitionRefreshObserver,
)
from substitute.domain.common import JsonObject
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external.http_transport import (
    default_http_get,
    is_request_exception,
)
from substitute.shared.logging.logger import get_logger, log_timing, log_warning

_LOGGER = get_logger("infrastructure.external.comfy_object_info_client")

HttpGet = Callable[..., Any]
BackgroundScheduler = Callable[[Callable[[], None]], object]


class ComfyObjectInfoClient:
    """Query Comfy `/object_info` and memoize live node-definition payloads."""

    def __init__(
        self,
        *,
        endpoint: ComfyEndpoint | None = None,
        host: str | None = None,
        port: int | None = None,
        http_get: HttpGet | None = None,
        background_scheduler: BackgroundScheduler | None = None,
        shutdown_background_scheduler: Callable[[], None] | None = None,
    ) -> None:
        """Initialize object-info client with configurable endpoint and HTTP transport."""

        resolved_host = host if host is not None else "127.0.0.1"
        resolved_port = port if port is not None else 8188
        self._endpoint = endpoint or ComfyEndpoint(
            host=resolved_host,
            port=resolved_port,
        )
        self._http_get = http_get or default_http_get
        self._cache: dict[str, JsonObject] = {}
        self._inflight: set[str] = set()
        self._refresh_observers: list[NodeDefinitionRefreshObserver] = []
        self._lock = RLock()
        self._background_request_id = 0
        self._background_scheduler = (
            background_scheduler or _missing_background_scheduler
        )
        self._shutdown_background_scheduler = shutdown_background_scheduler

    def add_refresh_observer(
        self,
        observer: NodeDefinitionRefreshObserver,
    ) -> Callable[[], None]:
        """Register an observer for completed cache refreshes."""

        with self._lock:
            self._refresh_observers.append(observer)

        def unsubscribe() -> None:
            """Remove the registered refresh observer when still present."""

            with self._lock:
                try:
                    self._refresh_observers.remove(observer)
                except ValueError:
                    return

        return unsubscribe

    def clear_cache(self) -> None:
        """Clear cached object-info definitions after target runtime mutation."""

        with self._lock:
            self._cache.clear()
            self._inflight.clear()

    def shutdown(self) -> None:
        """Release object-info client resources."""

        if self._shutdown_background_scheduler is not None:
            self._shutdown_background_scheduler()
            self._shutdown_background_scheduler = None

    def get_node_definition(self, node_class: str) -> JsonObject:
        """Return cached node definition and queue a background refresh on cache miss."""

        lookup_started_at = perf_counter()
        with self._lock:
            if node_class in self._cache:
                cached_definition = self._cache[node_class]
                log_timing(
                    _LOGGER,
                    "Returned cached live node definition",
                    started_at=lookup_started_at,
                    level="debug",
                    node_class=node_class,
                    cache_hit=True,
                    inflight=node_class in self._inflight,
                )
                return cached_definition
        scheduled = self.refresh_node_class_async(node_class)
        log_timing(
            _LOGGER,
            "Returned empty live node definition pending refresh",
            started_at=lookup_started_at,
            level="debug",
            node_class=node_class,
            cache_hit=False,
            refresh_scheduled=scheduled,
        )
        return {}

    def get_required_node_definition(self, node_class: str) -> JsonObject:
        """Synchronously fetch required node metadata when the cache is incomplete."""

        normalized_class = node_class.strip()
        if not normalized_class:
            return {}
        cached_payload = self._cached_node_definition(normalized_class)
        if _payload_contains_node_class(cached_payload, normalized_class):
            return cached_payload if cached_payload is not None else {}
        payload = self.refresh_node_definition(normalized_class)
        with self._lock:
            self._inflight.discard(normalized_class)
        return payload

    def prewarm_node_classes(self, node_classes: Iterable[str]) -> int:
        """Queue background refreshes for uncached node classes."""

        scheduled_count = 0
        for node_class in sorted(
            {node_class for node_class in node_classes if node_class}
        ):
            if self.refresh_node_class_async(node_class):
                scheduled_count += 1
        return scheduled_count

    def ensure_node_definitions(
        self,
        node_classes: Iterable[str],
    ) -> NodeDefinitionHydrationResult:
        """Synchronously fetch missing node definitions for active projection."""

        hydration_started_at = perf_counter()
        requested = _normalized_node_classes(node_classes)
        available: list[str] = []
        unavailable: list[str] = []
        for node_class in requested:
            payload = self._cached_node_definition(node_class)
            if not _payload_contains_node_class(payload, node_class):
                payload = self.refresh_node_definition(node_class)
                with self._lock:
                    self._inflight.discard(node_class)
            if _payload_contains_node_class(payload, node_class):
                available.append(node_class)
            else:
                unavailable.append(node_class)
        result = NodeDefinitionHydrationResult(
            requested=requested,
            available=tuple(available),
            unavailable=tuple(unavailable),
        )
        log_timing(
            _LOGGER,
            "Completed foreground node definition hydration",
            started_at=hydration_started_at,
            requested_count=len(result.requested),
            available_count=len(result.available),
            unavailable_count=len(result.unavailable),
            unavailable_node_classes=",".join(result.unavailable),
        )
        return result

    def _cached_node_definition(self, node_class: str) -> JsonObject | None:
        """Return cached payload for one node class when present."""

        with self._lock:
            if node_class in self._cache:
                return self._cache[node_class]
        return None

    def refresh_node_class_async(self, node_class: str) -> bool:
        """Queue one background refresh when the class is uncached and not in flight."""

        normalized_class = node_class.strip()
        if not normalized_class:
            return False
        with self._lock:
            if normalized_class in self._cache or normalized_class in self._inflight:
                return False
            self._inflight.add(normalized_class)
        try:
            self._background_scheduler(
                lambda: self._refresh_node_class_in_background(normalized_class)
            )
        except Exception as error:
            with self._lock:
                self._inflight.discard(normalized_class)
            log_timing(
                _LOGGER,
                "Failed to schedule live node definition refresh",
                started_at=perf_counter(),
                level="warning",
                node_class=normalized_class,
                error=repr(error),
            )
            return False
        return True

    def refresh_node_definition(self, node_class: str) -> JsonObject:
        """Fetch one live node definition synchronously and update the cache."""

        lookup_started_at = perf_counter()
        try:
            response = self._http_get(
                self._endpoint.object_info_url(node_class),
                timeout=5,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise TypeError("object_info payload must be a JSON object")
            with self._lock:
                self._cache[node_class] = payload
            self._notify_refresh_observers(
                NodeDefinitionRefreshEvent(
                    node_class=node_class,
                    available=bool(payload),
                )
            )
            log_timing(
                _LOGGER,
                "Fetched live node definition",
                started_at=lookup_started_at,
                node_class=node_class,
                cache_hit=False,
            )
            return payload
        except Exception as error:
            if not _is_expected_http_error(error):
                raise
            log_timing(
                _LOGGER,
                "Failed to fetch live node definition",
                started_at=lookup_started_at,
                level="warning",
                node_class=node_class,
                cache_hit=False,
                error=repr(error),
            )
            with self._lock:
                self._cache[node_class] = {}
            self._notify_refresh_observers(
                NodeDefinitionRefreshEvent(
                    node_class=node_class,
                    available=False,
                )
            )
            return {}

    def refresh_node_definitions(self, node_classes: Iterable[str]) -> tuple[str, ...]:
        """Force-refresh selected node definitions and return available classes."""

        refreshed: list[str] = []
        for node_class in _normalized_node_classes(node_classes):
            payload = self.refresh_node_definition(node_class)
            with self._lock:
                self._inflight.discard(node_class)
            if _payload_contains_node_class(payload, node_class):
                refreshed.append(node_class)
        return tuple(refreshed)

    def _notify_refresh_observers(self, event: NodeDefinitionRefreshEvent) -> None:
        """Notify registered observers after the cache has been updated."""

        with self._lock:
            observers = tuple(self._refresh_observers)
        for observer in observers:
            try:
                observer(event)
            except Exception as error:
                log_warning(
                    _LOGGER,
                    "Node definition refresh observer failed",
                    node_class=event.node_class,
                    available=event.available,
                    error=repr(error),
                )

    def _refresh_node_class_in_background(self, node_class: str) -> None:
        """Refresh one node class and clear the in-flight marker after completion."""

        try:
            self.refresh_node_definition(node_class)
        finally:
            with self._lock:
                self._inflight.discard(node_class)


def _normalized_node_classes(node_classes: Iterable[str]) -> tuple[str, ...]:
    """Return stable non-empty node class names for foreground hydration."""

    return tuple(
        sorted(
            {node_class.strip() for node_class in node_classes if node_class.strip()}
        )
    )


def _missing_background_scheduler(_callback: Callable[[], None]) -> object:
    """Reject async object-info refresh without an injected scheduler."""

    raise RuntimeError("background_scheduler is required for async node definitions.")


def _is_expected_http_error(error: BaseException) -> bool:
    """Return whether an object-info request failure should cache an empty payload."""

    return isinstance(error, TypeError | ValueError) or is_request_exception(error)


def _payload_contains_node_class(payload: object, node_class: str) -> bool:
    """Return whether a payload contains an authoritative definition key."""

    return isinstance(payload, Mapping) and bool(payload) and node_class in payload


__all__ = ["ComfyObjectInfoClient"]

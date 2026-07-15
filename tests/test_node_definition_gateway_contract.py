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

"""Contract tests for live node-definition gateway behavior."""

from __future__ import annotations

from typing import Any, cast
from urllib.parse import unquote

import requests

from substitute.application.ports import (
    NodeDefinitionRefreshEvent,
    NodeDefinitionRefreshObserver,
)
from substitute.infrastructure.external import ComfyObjectInfoClient
from substitute.application.node_behavior import NodeBehaviorService
from tests.node_behavior_test_helpers import cube_state


class _Response:
    """Minimal requests-like response stub for object-info client tests."""

    def __init__(self, payload: dict[str, object]) -> None:
        """Store payload returned by `.json()`."""

        self._payload = payload

    def raise_for_status(self) -> None:
        """Simulate a successful HTTP response."""

    def json(self) -> dict[str, object]:
        """Return the configured JSON payload."""

        return self._payload


def test_comfy_object_info_client_returns_empty_on_miss_and_queues_refresh() -> None:
    """Render-path lookups should not block on object-info HTTP cache misses."""

    calls: list[tuple[str, int]] = []
    scheduled: list[Any] = []

    def _fake_get(url: str, *, timeout: int) -> _Response:
        calls.append((url, timeout))
        return _Response(
            {
                "KSampler": {
                    "input": {"required": {"sampler_name": [["C:\\folder\\file"]]}}
                }
            }
        )

    client = ComfyObjectInfoClient(
        host="127.0.0.1",
        port=8188,
        http_get=_fake_get,
        background_scheduler=lambda callback: scheduled.append(callback),
    )

    first = client.get_node_definition("KSampler")

    assert first == {}
    assert calls == []
    assert len(scheduled) == 1

    scheduled.pop()()

    second = client.get_node_definition("KSampler")
    assert calls == [("http://127.0.0.1:8188/object_info/KSampler", 5)]
    assert len(scheduled) == 0
    sampler_definition = cast(dict[str, Any], second["KSampler"])
    assert sampler_definition["input"]["required"]["sampler_name"][0][0] == (
        "C:\\folder\\file"
    )


def test_comfy_object_info_client_notifies_after_async_refresh() -> None:
    """Observers should run once after an async refresh writes the cache."""

    scheduled: list[Any] = []
    events: list[NodeDefinitionRefreshEvent] = []

    def _fake_get(_url: str, *, timeout: int) -> _Response:
        _ = timeout
        return _Response({"KSampler": {"input": {}}})

    client = ComfyObjectInfoClient(
        http_get=_fake_get,
        background_scheduler=lambda callback: scheduled.append(callback),
    )
    client.add_refresh_observer(cast("NodeDefinitionRefreshObserver", events.append))

    assert client.get_node_definition("KSampler") == {}
    assert events == []

    scheduled.pop()()

    assert events == [NodeDefinitionRefreshEvent("KSampler", available=True)]
    assert client.get_node_definition("KSampler") == {"KSampler": {"input": {}}}
    assert events == [NodeDefinitionRefreshEvent("KSampler", available=True)]


def test_comfy_object_info_client_force_refreshes_deduplicated_node_batch() -> None:
    """Batch refresh should force selected definitions and return available classes."""

    calls: list[str] = []
    events: list[NodeDefinitionRefreshEvent] = []

    def _fake_get(url: str, *, timeout: int) -> _Response:
        _ = timeout
        node_class = url.rsplit("/", 1)[-1]
        calls.append(node_class)
        if node_class == "MissingNode":
            return _Response({})
        return _Response({node_class: {"input": {}}})

    client = ComfyObjectInfoClient(http_get=_fake_get)
    client.add_refresh_observer(cast("NodeDefinitionRefreshObserver", events.append))

    refreshed = client.refresh_node_definitions(("KSampler", "KSampler", "MissingNode"))

    assert refreshed == ("KSampler",)
    assert calls == ["KSampler", "MissingNode"]
    assert events == [
        NodeDefinitionRefreshEvent("KSampler", available=True),
        NodeDefinitionRefreshEvent("MissingNode", available=False),
    ]


def test_comfy_object_info_client_caches_empty_fallback_on_refresh_failure() -> None:
    """Failed object-info refreshes should cache and return an empty mapping."""

    calls = 0
    scheduled: list[Any] = []

    def _boom(_url: str, *, timeout: int) -> _Response:
        nonlocal calls
        calls += 1
        raise requests.RequestException(f"offline after {timeout}s")

    client = ComfyObjectInfoClient(
        http_get=_boom,
        background_scheduler=lambda callback: scheduled.append(callback),
    )

    first = client.get_node_definition("OfflineNode")
    assert first == {}
    assert calls == 0
    assert len(scheduled) == 1

    scheduled.pop()()
    second = client.get_node_definition("OfflineNode")

    assert first == {}
    assert second == {}
    assert calls == 1


def test_comfy_object_info_client_notifies_unavailable_on_refresh_failure() -> None:
    """Failed refreshes should publish unavailable events after caching fallback."""

    scheduled: list[Any] = []
    events: list[NodeDefinitionRefreshEvent] = []

    def _boom(_url: str, *, timeout: int) -> _Response:
        raise requests.RequestException(f"offline after {timeout}s")

    client = ComfyObjectInfoClient(
        http_get=_boom,
        background_scheduler=lambda callback: scheduled.append(callback),
    )
    client.add_refresh_observer(cast("NodeDefinitionRefreshObserver", events.append))

    assert client.get_node_definition("OfflineNode") == {}
    scheduled.pop()()

    assert client.get_node_definition("OfflineNode") == {}
    assert events == [NodeDefinitionRefreshEvent("OfflineNode", available=False)]


def test_comfy_object_info_client_can_refresh_synchronously_for_prewarm() -> None:
    """Explicit prewarm refresh should fetch and cache live definitions."""

    calls: list[str] = []

    def _fake_get(url: str, *, timeout: int) -> _Response:
        calls.append(f"{url}|{timeout}")
        return _Response({"VAELoader": {"input": {}}})

    client = ComfyObjectInfoClient(http_get=_fake_get)

    refreshed = client.refresh_node_definition("VAELoader")
    cached = client.get_node_definition("VAELoader")

    assert refreshed == {"VAELoader": {"input": {}}}
    assert cached is refreshed
    assert calls == ["http://127.0.0.1:8188/object_info/VAELoader|5"]


def test_comfy_object_info_client_required_lookup_fetches_synchronously() -> None:
    """Required lookups should fetch on cache miss instead of scheduling later work."""

    calls: list[str] = []
    scheduled: list[Any] = []

    def _fake_get(url: str, *, timeout: int) -> _Response:
        calls.append(f"{url}|{timeout}")
        return _Response({"UpscaleModelLoader": {"input": {}}})

    client = ComfyObjectInfoClient(
        http_get=_fake_get,
        background_scheduler=lambda callback: scheduled.append(callback),
    )

    payload = client.get_required_node_definition("UpscaleModelLoader")

    assert payload == {"UpscaleModelLoader": {"input": {}}}
    assert calls == ["http://127.0.0.1:8188/object_info/UpscaleModelLoader|5"]
    assert scheduled == []
    assert client.get_node_definition("UpscaleModelLoader") is payload


def test_comfy_object_info_client_required_lookup_retries_cached_empty_payload() -> (
    None
):
    """Required lookups should not treat an old cached empty miss as authoritative."""

    calls: list[str] = []

    def _fake_get(url: str, *, timeout: int) -> _Response:
        calls.append(f"{url}|{timeout}")
        return _Response({"UpscaleModelLoader": {"input": {}}})

    client = ComfyObjectInfoClient(http_get=_fake_get)
    client._cache["UpscaleModelLoader"] = {}

    payload = client.get_required_node_definition("UpscaleModelLoader")

    assert payload == {"UpscaleModelLoader": {"input": {}}}
    assert calls == ["http://127.0.0.1:8188/object_info/UpscaleModelLoader|5"]


def test_comfy_object_info_client_encodes_object_info_class_path_segment() -> None:
    """Object-info requests should encode class names as one URL path segment."""

    calls: list[str] = []

    def _fake_get(url: str, *, timeout: int) -> _Response:
        calls.append(f"{url}|{timeout}")
        encoded_class = url.rsplit("/", maxsplit=1)[-1]
        node_class = unquote(encoded_class)
        return _Response({node_class: {"input": {}}})

    client = ComfyObjectInfoClient(http_get=_fake_get)

    payload = client.get_required_node_definition("MathExpression|pysssss")

    assert payload == {"MathExpression|pysssss": {"input": {}}}
    assert calls == ["http://127.0.0.1:8188/object_info/MathExpression%7Cpysssss|5"]


def test_comfy_object_info_client_refresh_observer_can_unsubscribe() -> None:
    """Unsubscribed observers should not receive later refresh notifications."""

    events: list[NodeDefinitionRefreshEvent] = []

    def _fake_get(url: str, *, timeout: int) -> _Response:
        _ = timeout
        node_class = url.rsplit("/", maxsplit=1)[-1]
        return _Response({node_class: {"input": {}}})

    client = ComfyObjectInfoClient(http_get=_fake_get)
    unsubscribe = client.add_refresh_observer(
        cast("NodeDefinitionRefreshObserver", events.append)
    )

    client.refresh_node_definition("VAELoader")
    unsubscribe()
    client.refresh_node_definition("KSampler")

    assert events == [NodeDefinitionRefreshEvent("VAELoader", available=True)]


def test_comfy_object_info_client_prewarm_skips_cached_and_inflight_classes() -> None:
    """Prewarm should queue only uncached node classes once."""

    scheduled: list[Any] = []
    client = ComfyObjectInfoClient(
        background_scheduler=lambda callback: scheduled.append(callback),
    )
    client._cache["Cached"] = {}

    scheduled_count = client.prewarm_node_classes(["Cached", "KSampler", "KSampler"])

    assert scheduled_count == 1
    assert len(scheduled) == 1
    assert client.prewarm_node_classes(["KSampler"]) == 0


def test_comfy_object_info_client_foreground_hydration_uses_cached_definition() -> None:
    """Foreground hydration should report cached classes without HTTP work."""

    calls: list[str] = []

    def _fake_get(url: str, *, timeout: int) -> _Response:
        calls.append(f"{url}|{timeout}")
        return _Response({})

    client = ComfyObjectInfoClient(http_get=_fake_get)
    client._cache["KSampler"] = {"KSampler": {"input": {}}}

    result = client.ensure_node_definitions(["KSampler"])

    assert result.requested == ("KSampler",)
    assert result.available == ("KSampler",)
    assert result.unavailable == ()
    assert calls == []


def test_comfy_object_info_client_clear_cache_forces_later_refetch() -> None:
    """Post-restart cache clear should make later object-info lookups refetch."""

    calls: list[str] = []

    def _fake_get(url: str, timeout: int) -> object:
        calls.append(f"{url}|{timeout}")
        return _Response({"VAELoader": {"input": {}}})

    client = ComfyObjectInfoClient(http_get=_fake_get)

    assert client.get_required_node_definition("VAELoader") == {
        "VAELoader": {"input": {}}
    }
    client.clear_cache()
    assert client.get_required_node_definition("VAELoader") == {
        "VAELoader": {"input": {}}
    }

    assert calls == [
        "http://127.0.0.1:8188/object_info/VAELoader|5",
        "http://127.0.0.1:8188/object_info/VAELoader|5",
    ]


def test_comfy_object_info_client_foreground_hydration_fetches_missing_class() -> None:
    """Foreground hydration should synchronously fetch missing definitions."""

    calls: list[str] = []

    def _fake_get(url: str, *, timeout: int) -> _Response:
        calls.append(f"{url}|{timeout}")
        return _Response({"VAELoader": {"input": {}}})

    client = ComfyObjectInfoClient(http_get=_fake_get)

    result = client.ensure_node_definitions([" VAELoader "])

    assert result.requested == ("VAELoader",)
    assert result.available == ("VAELoader",)
    assert result.unavailable == ()
    assert calls == ["http://127.0.0.1:8188/object_info/VAELoader|5"]
    assert client.get_node_definition("VAELoader") == {"VAELoader": {"input": {}}}


def test_comfy_object_info_client_foreground_hydration_retries_cached_empty_payload() -> (
    None
):
    """Foreground hydration should retry a cached empty payload before failing."""

    calls: list[str] = []

    def _fake_get(url: str, *, timeout: int) -> _Response:
        calls.append(f"{url}|{timeout}")
        return _Response({"VAELoader": {"input": {}}})

    client = ComfyObjectInfoClient(http_get=_fake_get)
    client._cache["VAELoader"] = {}

    result = client.ensure_node_definitions(["VAELoader"])

    assert result.requested == ("VAELoader",)
    assert result.available == ("VAELoader",)
    assert result.unavailable == ()
    assert calls == ["http://127.0.0.1:8188/object_info/VAELoader|5"]


def test_comfy_object_info_client_foreground_hydration_reports_unavailable() -> None:
    """Foreground hydration should classify failed fetches as unavailable."""

    def _boom(_url: str, *, timeout: int) -> _Response:
        raise requests.RequestException(f"offline after {timeout}s")

    client = ComfyObjectInfoClient(http_get=_boom)

    result = client.ensure_node_definitions(["OfflineNode"])

    assert result.requested == ("OfflineNode",)
    assert result.available == ()
    assert result.unavailable == ("OfflineNode",)


def test_comfy_object_info_client_foreground_hydration_deduplicates_input() -> None:
    """Foreground hydration should fetch each normalized class at most once."""

    calls: list[str] = []

    def _fake_get(url: str, *, timeout: int) -> _Response:
        calls.append(f"{url}|{timeout}")
        node_class = url.rsplit("/", maxsplit=1)[-1]
        return _Response({node_class: {"input": {}}})

    client = ComfyObjectInfoClient(http_get=_fake_get)

    result = client.ensure_node_definitions(["KSampler", "KSampler", " VAELoader "])

    assert result.requested == ("KSampler", "VAELoader")
    assert result.available == ("KSampler", "VAELoader")
    assert result.unavailable == ()
    assert calls == [
        "http://127.0.0.1:8188/object_info/KSampler|5",
        "http://127.0.0.1:8188/object_info/VAELoader|5",
    ]


def test_comfy_object_info_client_foreground_hydration_fetches_inflight_class() -> None:
    """Foreground hydration should not wait on existing async in-flight markers."""

    calls: list[str] = []

    def _fake_get(url: str, *, timeout: int) -> _Response:
        calls.append(f"{url}|{timeout}")
        return _Response({"KSampler": {"input": {}}})

    client = ComfyObjectInfoClient(http_get=_fake_get)
    client._inflight.add("KSampler")

    result = client.ensure_node_definitions(["KSampler"])

    assert result.available == ("KSampler",)
    assert calls == ["http://127.0.0.1:8188/object_info/KSampler|5"]
    assert "KSampler" not in client._inflight


def test_node_behavior_snapshot_does_not_block_on_object_info_cache_miss() -> None:
    """Editor behavior snapshots should queue cache refreshes instead of doing HTTP."""

    calls: list[str] = []
    scheduled: list[Any] = []

    def _fake_get(url: str, *, timeout: int) -> _Response:
        calls.append(f"{url}|{timeout}")
        return _Response({"KSampler": {"input": {}}})

    gateway = ComfyObjectInfoClient(
        http_get=_fake_get,
        background_scheduler=lambda callback: scheduled.append(callback),
    )
    service = NodeBehaviorService(node_definition_gateway=gateway)
    cube = cube_state(
        nodes={
            "sampler": {
                "class_type": "KSampler",
                "inputs": {"seed": 7},
            }
        },
        definitions={
            "KSampler": {
                "input": {"required": {"seed": ["INT", {"min": 0, "max": 10}]}}
            }
        },
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    assert "sampler" in snapshot.resolved_nodes_by_alias["A"]
    assert calls == []
    assert len(scheduled) == 1

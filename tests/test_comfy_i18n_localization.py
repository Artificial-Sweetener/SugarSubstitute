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

"""Tests for bounded Comfy server node localization loading and layering."""

from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from typing import Any

from substitute.application.localization import (
    ActiveComfyNodeCatalogStore,
    NodeTextCatalogResolver,
)
from substitute.domain.localization import (
    NodeCatalogText,
    NodeTextCatalog,
    NodeTextSource,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.localization.comfy_i18n_client import (
    ComfyI18nCatalogClient,
    ComfyI18nLanguageSelection,
)
from substitute.infrastructure.localization.comfy_frontend_i18n_client import (
    ComfyFrontendI18nClient,
)


class FakeStreamingResponse:
    """Expose the bounded requests response surface consumed by the client."""

    def __init__(self, payload: object, *, content_length: str | None = None) -> None:
        """Serialize one response payload into a streaming byte buffer."""

        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.raw = BytesIO(encoded)
        self.headers = {
            "Content-Length": content_length or str(len(encoded)),
        }
        self.closed = False

    def raise_for_status(self) -> None:
        """Represent a successful HTTP response."""

    def close(self) -> None:
        """Record deterministic response cleanup."""

        self.closed = True


class FakeAssetResponse:
    """Expose the bounded response surface used for frontend locale assets."""

    def __init__(self, payload: str) -> None:
        """Encode one UTF-8 frontend response."""

        self.content = payload.encode("utf-8")
        self.headers = {"Content-Length": str(len(self.content))}
        self.closed = False

    def raise_for_status(self) -> None:
        """Represent a successful HTTP response."""

    def close(self) -> None:
        """Record deterministic response cleanup."""

        self.closed = True


def _selection() -> ComfyI18nLanguageSelection:
    """Return the Simplified Chinese branch selection used by tests."""

    return ComfyI18nLanguageSelection(
        effective_language_identifier="zh-Hans",
        comfy_aliases=("zh", "zh-CN"),
    )


def _node(display_name: str, *, input_name: str | None = None) -> dict[str, object]:
    """Build one frontend-shaped custom node translation entry."""

    inputs: dict[str, object] = {}
    if input_name is not None:
        inputs["prompt"] = {"name": input_name, "tooltip": f"{input_name} tip"}
    return {
        "display_name": display_name,
        "description": f"{display_name} description",
        "inputs": inputs,
    }


def test_streaming_client_retains_only_active_and_english_branches(
    tmp_path: Path,
) -> None:
    """Discard unrelated locales while custom layers override bundled core."""

    payload = {
        "zh": {"nodeDefs": {"CustomNode": _node("自定义节点", input_name="提示词")}},
        "en": {"nodeDefs": {"EnglishOnly": _node("English fallback")}},
        "ja": {"nodeDefs": {"Discarded": _node("破棄")}},
        "fr": {"nodeDefs": {"DiscardedFrench": _node("Ignoré")}},
    }
    response = FakeStreamingResponse(payload)
    calls: list[tuple[str, dict[str, object]]] = []
    store = ActiveComfyNodeCatalogStore()
    published: list[bool] = []

    def http_get(url: str, **kwargs: object) -> FakeStreamingResponse:
        """Capture URL and bounded streaming request options."""

        calls.append((url, dict(kwargs)))
        return response

    client = ComfyI18nCatalogClient(
        endpoint=ComfyEndpoint("127.0.0.1", 8188),
        cache_root=tmp_path,
        language_selection=_selection,
        store=store,
        background_scheduler=lambda callback: callback(),
        catalog_published=lambda: published.append(True),
        http_get=http_get,
    )

    assert client.refresh() is True

    selection = store.selection()
    assert selection is not None
    assert selection.active_catalog is not None
    assert selection.english_catalog is not None
    assert set(selection.active_catalog.node_definitions) == {"CustomNode"}
    assert set(selection.english_catalog.node_definitions) == {"EnglishOnly"}
    assert "Discarded" not in selection.active_catalog.node_definitions
    resolved = NodeTextCatalogResolver(store.snapshot("zh-Hans"))
    display_name = resolved.node_text("CustomNode").display_name
    assert display_name is not None
    assert display_name.text == "自定义节点"
    assert display_name.source is NodeTextSource.ACTIVE_COMFY
    assert calls == [
        (
            "http://127.0.0.1:8188/i18n",
            {"timeout": 5, "stream": True},
        )
    ]
    assert response.closed is True
    assert published == [True]
    cache_document = json.loads(
        next((tmp_path / "comfy_i18n").glob("*.json")).read_text(encoding="utf-8")
    )
    assert "ja" not in json.dumps(cache_document, ensure_ascii=False)
    assert set(cache_document) == {
        "schema_version",
        "active_alias",
        "active_node_defs",
        "english_node_defs",
    }


def test_frontend_client_loads_only_requested_official_core_locales() -> None:
    """Resolve hashed nodeDefs source maps from the attached Comfy frontend."""

    index = '<link rel="modulepreload" href="./assets/i18n-release.js">'
    module = (
        '"./en/nodeDefs.json":()=>import(`./nodeDefs-en.js`),'
        '"./zh/nodeDefs.json":()=>import(`./nodeDefs-zh.js`),'
        '"./ja/nodeDefs.json":()=>import(`./nodeDefs-ja.js`)'
    )
    payloads = {
        "http://127.0.0.1:8188/": index,
        "http://127.0.0.1:8188/assets/i18n-release.js": module,
        "http://127.0.0.1:8188/assets/nodeDefs-en.js.map": _source_map(
            "en", {"KSampler": _node("KSampler")}
        ),
        "http://127.0.0.1:8188/assets/nodeDefs-zh.js.map": _source_map(
            "zh", {"KSampler": _node("K 采样器", input_name="提示词")}
        ),
    }
    calls: list[str] = []

    def http_get(url: str, **_kwargs: object) -> FakeAssetResponse:
        """Return one same-origin frontend fixture."""

        calls.append(url)
        return FakeAssetResponse(payloads[url])

    client = ComfyFrontendI18nClient(
        ComfyEndpoint("127.0.0.1", 8188),
        http_get=http_get,
    )

    branches = client.load_node_definitions(("zh", "en"))

    assert branches["zh"]["KSampler"] == _node("K 采样器", input_name="提示词")
    assert branches["en"]["KSampler"] == _node("KSampler")
    assert all("nodeDefs-ja" not in url for url in calls)
    assert calls == [
        "http://127.0.0.1:8188/",
        "http://127.0.0.1:8188/assets/i18n-release.js",
        "http://127.0.0.1:8188/assets/nodeDefs-zh.js.map",
        "http://127.0.0.1:8188/assets/nodeDefs-en.js.map",
    ]


def test_frontend_client_loads_official_korean_node_definitions() -> None:
    """Request Korean node text from Comfy without loading unrelated locales."""

    index = '<link rel="modulepreload" href="./assets/i18n-release.js">'
    module = (
        '"./en/nodeDefs.json":()=>import(`./nodeDefs-en.js`),'
        '"./ko/nodeDefs.json":()=>import(`./nodeDefs-ko.js`),'
        '"./ja/nodeDefs.json":()=>import(`./nodeDefs-ja.js`)'
    )
    payloads = {
        "http://127.0.0.1:8188/": index,
        "http://127.0.0.1:8188/assets/i18n-release.js": module,
        "http://127.0.0.1:8188/assets/nodeDefs-ko.js.map": _source_map(
            "ko", {"KSampler": _node("K샘플러", input_name="시드")}
        ),
        "http://127.0.0.1:8188/assets/nodeDefs-en.js.map": _source_map(
            "en", {"KSampler": _node("KSampler")}
        ),
    }
    calls: list[str] = []

    def http_get(url: str, **_kwargs: object) -> FakeAssetResponse:
        """Return one attached-server asset and record selective requests."""

        calls.append(url)
        return FakeAssetResponse(payloads[url])

    client = ComfyFrontendI18nClient(
        ComfyEndpoint("127.0.0.1", 8188),
        http_get=http_get,
    )

    branches = client.load_node_definitions(("ko", "en"))

    assert branches["ko"]["KSampler"] == _node("K샘플러", input_name="시드")
    assert branches["en"]["KSampler"] == _node("KSampler")
    assert all("nodeDefs-ja" not in url for url in calls)
    assert calls == [
        "http://127.0.0.1:8188/",
        "http://127.0.0.1:8188/assets/i18n-release.js",
        "http://127.0.0.1:8188/assets/nodeDefs-ko.js.map",
        "http://127.0.0.1:8188/assets/nodeDefs-en.js.map",
    ]


def test_frontend_client_skips_one_unavailable_locale_source_map() -> None:
    """Keep translated core branches when English uses raw object-info fallback."""

    index = '<script src="./assets/i18n-release.js"></script>'
    module = (
        '"./en/nodeDefs.json":()=>import(`./nodeDefs-en.js`),'
        '"./zh/nodeDefs.json":()=>import(`./nodeDefs-zh.js`)'
    )
    payloads = {
        "http://127.0.0.1:8188/": index,
        "http://127.0.0.1:8188/assets/i18n-release.js": module,
        "http://127.0.0.1:8188/assets/nodeDefs-zh.js.map": _source_map(
            "zh", {"KSampler": _node("K 采样器")}
        ),
    }

    def http_get(url: str, **_kwargs: object) -> FakeAssetResponse:
        """Raise for the deliberately absent English source map."""

        if url not in payloads:
            raise OSError("source map absent")
        return FakeAssetResponse(payloads[url])

    client = ComfyFrontendI18nClient(
        ComfyEndpoint("127.0.0.1", 8188),
        http_get=http_get,
    )

    branches = client.load_node_definitions(("zh", "en"))

    assert set(branches) == {"zh"}
    assert branches["zh"]["KSampler"] == _node("K 采样器")


def test_custom_node_locales_recursively_override_official_core_locales(
    tmp_path: Path,
) -> None:
    """Compose core and custom branches like Comfy without retaining other locales."""

    core: dict[str, dict[str, object]] = {
        "zh": {
            "KSampler": {
                "display_name": "K 采样器",
                "description": "核心说明",
                "inputs": {
                    "seed": {"name": "种子", "tooltip": "核心提示"},
                },
            }
        },
        "en": {"KSampler": _node("KSampler")},
    }
    custom = FakeStreamingResponse(
        {
            "zh-CN": {
                "nodeDefs": {
                    "CustomNode": _node("自定义节点"),
                }
            },
            "zh": {
                "nodeDefs": {"KSampler": {"inputs": {"seed": {"tooltip": "扩展提示"}}}}
            },
        }
    )
    store = ActiveComfyNodeCatalogStore()
    client = ComfyI18nCatalogClient(
        endpoint=ComfyEndpoint("127.0.0.1", 8188),
        cache_root=tmp_path,
        language_selection=_selection,
        store=store,
        background_scheduler=lambda callback: callback(),
        http_get=lambda *_args, **_kwargs: custom,
        frontend_node_definitions_loader=lambda _aliases: core,
    )

    assert client.refresh() is True

    selection = store.selection()
    assert selection is not None
    assert selection.active_catalog is not None
    ksampler = selection.active_catalog.node_definitions["KSampler"]
    assert ksampler.display_name == "K 采样器"
    assert ksampler.description == "核心说明"
    assert ksampler.inputs["seed"].name == "种子"
    assert ksampler.inputs["seed"].tooltip == "扩展提示"
    assert "CustomNode" in selection.active_catalog.node_definitions


def test_frontend_core_locales_publish_when_custom_i18n_is_unavailable(
    tmp_path: Path,
) -> None:
    """Keep official core localization usable without the custom-node endpoint."""

    store = ActiveComfyNodeCatalogStore()

    def unavailable_custom(*_args: object, **_kwargs: object) -> None:
        """Represent a Comfy installation without a working `/i18n` route."""

        raise OSError("custom localization unavailable")

    client = ComfyI18nCatalogClient(
        endpoint=ComfyEndpoint("127.0.0.1", 8188),
        cache_root=tmp_path,
        language_selection=_selection,
        store=store,
        background_scheduler=lambda callback: callback(),
        http_get=unavailable_custom,
        frontend_node_definitions_loader=lambda _aliases: {
            "zh": {"KSampler": _node("K 采样器")},
            "en": {"KSampler": _node("KSampler")},
        },
    )

    assert client.refresh() is True
    selection = store.selection()
    assert selection is not None
    assert selection.active_catalog is not None
    assert selection.active_catalog.node_definitions["KSampler"].display_name == (
        "K 采样器"
    )


def test_custom_locales_publish_when_frontend_assets_are_unavailable(
    tmp_path: Path,
) -> None:
    """Keep custom localization usable with an older or incomplete frontend."""

    store = ActiveComfyNodeCatalogStore()

    def unavailable_frontend(
        _aliases: tuple[str, ...],
    ) -> dict[str, dict[str, object]]:
        """Represent a frontend package without resolvable source maps."""

        raise OSError("frontend localization unavailable")

    client = ComfyI18nCatalogClient(
        endpoint=ComfyEndpoint("127.0.0.1", 8188),
        cache_root=tmp_path,
        language_selection=_selection,
        store=store,
        background_scheduler=lambda callback: callback(),
        http_get=lambda *_args, **_kwargs: FakeStreamingResponse(
            {"zh": {"nodeDefs": {"CustomNode": _node("自定义节点")}}}
        ),
        frontend_node_definitions_loader=unavailable_frontend,
    )

    assert client.refresh() is True
    selection = store.selection()
    assert selection is not None
    assert selection.active_catalog is not None
    assert selection.active_catalog.node_definitions["CustomNode"].display_name == (
        "自定义节点"
    )


def test_cached_generation_requires_matching_active_alias(tmp_path: Path) -> None:
    """Do not apply an old locale generation after the effective language changes."""

    store = ActiveComfyNodeCatalogStore()
    response = FakeStreamingResponse(
        {"zh": {"nodeDefs": {"CustomNode": _node("缓存节点")}}}
    )
    client = ComfyI18nCatalogClient(
        endpoint=ComfyEndpoint("localhost", 8188),
        cache_root=tmp_path,
        language_selection=_selection,
        store=store,
        background_scheduler=lambda callback: callback(),
        http_get=lambda *_args, **_kwargs: response,
    )
    assert client.refresh() is True

    japanese_store = ActiveComfyNodeCatalogStore()
    japanese_client = ComfyI18nCatalogClient(
        endpoint=ComfyEndpoint("localhost", 8188),
        cache_root=tmp_path,
        language_selection=lambda: ComfyI18nLanguageSelection("ja", ("ja",)),
        store=japanese_store,
        background_scheduler=lambda callback: callback(),
        http_get=lambda *_args, **_kwargs: FakeStreamingResponse({}),
    )

    assert japanese_client.load_cached_selection() is False
    japanese_selection = japanese_store.selection()
    assert japanese_selection is not None
    assert japanese_selection.active_catalog is None


def test_oversized_response_fails_closed_without_replacing_valid_store(
    tmp_path: Path,
) -> None:
    """Preserve the current fallback generation when the server exceeds bounds."""

    store = ActiveComfyNodeCatalogStore()
    existing = NodeTextCatalog.create(
        language_identifier="zh-Hans",
        source=NodeTextSource.ACTIVE_COMFY,
        node_definitions={
            "Existing": NodeCatalogText("现有", None, {}, {}),
        },
    )
    store.publish(
        effective_language_identifier="zh-Hans",
        active_catalog=existing,
        english_catalog=None,
    )
    oversized = FakeStreamingResponse({}, content_length=str(33 * 1024 * 1024))
    client = ComfyI18nCatalogClient(
        endpoint=ComfyEndpoint("localhost", 8188),
        cache_root=tmp_path,
        language_selection=_selection,
        store=store,
        background_scheduler=lambda callback: callback(),
        http_get=lambda *_args, **_kwargs: oversized,
    )

    assert client.refresh() is False
    selection = store.selection()
    assert selection is not None
    assert selection.active_catalog is existing
    assert oversized.closed is True


def test_async_refresh_coalesces_inflight_work(tmp_path: Path) -> None:
    """Schedule at most one custom catalog refresh for one active generation."""

    scheduled: list[Any] = []
    client = ComfyI18nCatalogClient(
        endpoint=ComfyEndpoint("localhost", 8188),
        cache_root=tmp_path,
        language_selection=_selection,
        store=ActiveComfyNodeCatalogStore(),
        background_scheduler=lambda callback: scheduled.append(callback),
        http_get=lambda *_args, **_kwargs: FakeStreamingResponse({}),
    )

    assert client.refresh_async() is True
    assert client.refresh_async() is False
    assert len(scheduled) == 1


def test_language_change_during_inflight_refresh_schedules_new_generation(
    tmp_path: Path,
) -> None:
    """Do not lose a locale refresh when the previous branch is still loading."""

    current = [_selection()]
    scheduled: list[Any] = []
    client = ComfyI18nCatalogClient(
        endpoint=ComfyEndpoint("localhost", 8188),
        cache_root=tmp_path,
        language_selection=lambda: current[0],
        store=ActiveComfyNodeCatalogStore(),
        background_scheduler=lambda callback: scheduled.append(callback),
        http_get=lambda *_args, **_kwargs: FakeStreamingResponse({}),
    )
    assert client.refresh_async() is True
    current[0] = ComfyI18nLanguageSelection("ja", ("ja",))
    assert client.refresh_async() is False

    scheduled.pop(0)()

    assert len(scheduled) == 1


def _source_map(alias: str, node_definitions: dict[str, object]) -> str:
    """Return one frontend source-map document containing locale JSON."""

    return json.dumps(
        {
            "version": 3,
            "sources": [f"../../src/locales/{alias}/nodeDefs.json"],
            "sourcesContent": [json.dumps(node_definitions, ensure_ascii=False)],
            "mappings": "",
        },
        ensure_ascii=False,
    )

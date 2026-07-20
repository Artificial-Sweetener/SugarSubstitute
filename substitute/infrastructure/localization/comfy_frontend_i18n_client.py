#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Load official core node translations from the running Comfy frontend."""

from __future__ import annotations

from collections.abc import Mapping
import json
import re
from typing import Any, cast

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external.http_transport import (
    default_http_get,
    is_request_exception,
)
from substitute.shared.logging.logger import get_logger

_LOGGER = get_logger("infrastructure.localization.comfy_frontend_i18n_client")

_MAX_INDEX_BYTES = 512 * 1024
_MAX_I18N_MODULE_BYTES = 512 * 1024
_MAX_SOURCE_MAP_BYTES = 4 * 1024 * 1024
_ASSET_NAME_PATTERN = r"[A-Za-z0-9_.-]+\.js"
_I18N_ASSET_PATTERN = re.compile(
    r'(?:href|src)=["\'](?:\./)?assets/'
    r'(?P<asset>i18n-[A-Za-z0-9_.-]+\.js)["\']'
)


class ComfyFrontendI18nClient:
    """Resolve active-only core nodeDefs through Comfy's served locale assets."""

    def __init__(
        self,
        endpoint: ComfyEndpoint,
        *,
        http_get: Any | None = None,
    ) -> None:
        """Store the same-origin endpoint and bounded HTTP transport."""

        self._endpoint = endpoint
        self._http_get = http_get or default_http_get

    def load_node_definitions(
        self,
        aliases: tuple[str, ...],
    ) -> dict[str, dict[str, object]]:
        """Return official core nodeDefs for only the requested locale aliases."""

        index_text = self._get_text("/", limit=_MAX_INDEX_BYTES)
        i18n_asset = _find_i18n_asset(index_text)
        i18n_module = self._get_text(
            f"/assets/{i18n_asset}",
            limit=_MAX_I18N_MODULE_BYTES,
        )
        node_assets = _find_node_definition_assets(i18n_module, aliases)
        loaded: dict[str, dict[str, object]] = {}
        for alias in aliases:
            asset = node_assets.get(alias)
            if asset is None:
                continue
            try:
                source_map = self._get_json(
                    f"/assets/{asset}.map",
                    limit=_MAX_SOURCE_MAP_BYTES,
                )
                loaded[alias] = _node_definitions_from_source_map(source_map, alias)
            except Exception as error:
                if not _is_expected_asset_error(error):
                    raise
                _LOGGER.warning(
                    "Comfy frontend node locale asset unavailable",
                    extra={"alias": alias, "error": repr(error)},
                )
        return loaded

    def _get_text(self, path: str, *, limit: int) -> str:
        """Fetch one same-origin UTF-8 asset within its declared size bound."""

        response: Any | None = None
        try:
            response = self._http_get(
                _endpoint_url(self._endpoint, path),
                timeout=5,
            )
            response.raise_for_status()
            payload = _bounded_response_bytes(response, limit=limit)
            return payload.decode("utf-8", errors="strict")
        finally:
            if response is not None:
                response.close()

    def _get_json(self, path: str, *, limit: int) -> Mapping[str, object]:
        """Fetch and validate one same-origin JSON asset."""

        decoded = json.loads(self._get_text(path, limit=limit))
        if not isinstance(decoded, Mapping):
            raise TypeError("Comfy frontend source map must be a JSON object.")
        return cast(Mapping[str, object], decoded)


def _find_i18n_asset(index_text: str) -> str:
    """Return the hashed frontend i18n module referenced by Comfy's index."""

    match = _I18N_ASSET_PATTERN.search(index_text)
    if match is None:
        raise ValueError("Comfy frontend index does not reference an i18n module.")
    return match.group("asset")


def _find_node_definition_assets(
    i18n_module: str,
    aliases: tuple[str, ...],
) -> dict[str, str]:
    """Return hashed nodeDefs modules for the requested official locales."""

    assets: dict[str, str] = {}
    for alias in aliases:
        escaped_alias = re.escape(alias)
        pattern = re.compile(
            rf'["\']\./{escaped_alias}/nodeDefs\.json["\']\s*:\s*\(\)\s*=>.*?'
            rf"import\(`\./(?P<asset>{_ASSET_NAME_PATTERN})`\)",
        )
        match = pattern.search(i18n_module)
        if match is not None:
            assets[alias] = match.group("asset")
    return assets


def _node_definitions_from_source_map(
    source_map: Mapping[str, object],
    alias: str,
) -> dict[str, object]:
    """Extract the exact locale JSON embedded in one official source map."""

    sources = source_map.get("sources")
    contents = source_map.get("sourcesContent")
    if not isinstance(sources, list) or not isinstance(contents, list):
        raise TypeError("Comfy nodeDefs source map is missing source content.")
    expected_suffix = f"/locales/{alias}/nodeDefs.json"
    for index, source in enumerate(sources):
        if not isinstance(source, str) or not source.replace("\\", "/").endswith(
            expected_suffix
        ):
            continue
        if index >= len(contents) or not isinstance(contents[index], str):
            break
        decoded = json.loads(contents[index])
        if not isinstance(decoded, dict):
            raise TypeError("Comfy frontend nodeDefs locale must be a JSON object.")
        return cast(dict[str, object], decoded)
    raise ValueError(f"Comfy frontend source map has no nodeDefs locale for {alias!r}.")


def _bounded_response_bytes(response: Any, *, limit: int) -> bytes:
    """Return response bytes after enforcing advertised and actual size limits."""

    raw_length = response.headers.get("Content-Length")
    if raw_length is not None:
        try:
            content_length = int(raw_length)
        except (TypeError, ValueError) as error:
            raise ValueError("Invalid Comfy frontend content length.") from error
        if content_length <= 0 or content_length > limit:
            raise ValueError("Comfy frontend response size is out of bounds.")
    payload = bytes(response.content)
    if not payload or len(payload) > limit:
        raise ValueError("Comfy frontend response size is out of bounds.")
    return payload


def _endpoint_url(endpoint: ComfyEndpoint, path: str) -> str:
    """Build one same-origin Comfy URL from a validated absolute path."""

    if not path.startswith("/") or ".." in path or "://" in path:
        raise ValueError(
            "Comfy frontend asset path must remain on the configured host."
        )
    return f"http://{endpoint.host}:{endpoint.port}{path}"


def _is_expected_asset_error(error: BaseException) -> bool:
    """Return whether one absent or invalid locale asset can be skipped safely."""

    return isinstance(error, OSError | UnicodeError | TypeError | ValueError) or (
        is_request_exception(error)
    )


__all__ = ["ComfyFrontendI18nClient"]

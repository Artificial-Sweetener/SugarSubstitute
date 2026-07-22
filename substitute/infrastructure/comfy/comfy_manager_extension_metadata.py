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

"""Resolve extension metadata through runtime-correct Manager endpoints."""

from __future__ import annotations

from collections.abc import Mapping
import json

import requests

from substitute.application.ports.comfy_extension_metadata_provider import (
    ComfyExtensionMetadata,
)
from substitute.domain.comfy_manager import ComfyManagerKind
from substitute.infrastructure.comfy.comfy_registry_metadata import (
    ComfyRegistryMetadataClient,
    ComfyRegistryMetadataEnricher,
)
from substitute.infrastructure.comfy.manager_api_routes import ComfyManagerApiRoutes
from substitute.infrastructure.comfy.manager_metadata_parser import (
    ComfyManagerMetadataParser,
    needs_catalog,
)
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("infrastructure.comfy.manager_extension_metadata")


class ComfyManagerExtensionMetadataProvider:
    """Fetch installed extension metadata from the selected Manager server."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        manager_kind: ComfyManagerKind | None = None,
        timeout_seconds: float = 2.0,
        registry_client: ComfyRegistryMetadataEnricher | None = None,
    ) -> None:
        """Store Manager endpoint configuration and runtime route ownership."""

        self._base_url = f"http://{host}:{port}"
        self._routes = (
            ComfyManagerApiRoutes.for_kind(manager_kind)
            if manager_kind is not None
            else None
        )
        self._timeout_seconds = timeout_seconds
        self._parser = ComfyManagerMetadataParser()
        self._registry = registry_client or ComfyRegistryMetadataClient(
            timeout_seconds=timeout_seconds
        )

    def installed_extensions(self) -> Mapping[str, ComfyExtensionMetadata]:
        """Return installed metadata with optional legacy catalog enrichment."""

        routes, installed_payload = self._installed_payload()
        installed = self._parser.installed(installed_payload)
        if not installed:
            return {}
        if routes.catalog is not None and needs_catalog(installed):
            catalog = self._fetch_json(f"{self._base_url}{routes.catalog}")
            installed = self._parser.merge_catalog(installed, catalog)
        return self._registry.enrich(installed)

    def _installed_payload(self) -> tuple[ComfyManagerApiRoutes, object]:
        """Fetch installed metadata from known or server-discovered routes."""

        if self._routes is not None:
            return self._routes, self._fetch_json(
                f"{self._base_url}{self._routes.installed}"
            )
        integrated = ComfyManagerApiRoutes.for_kind(ComfyManagerKind.INTEGRATED)
        payload = self._fetch_json(f"{self._base_url}{integrated.installed}")
        if payload is not None:
            self._routes = integrated
            return integrated, payload
        legacy = ComfyManagerApiRoutes.for_kind(ComfyManagerKind.LEGACY_CUSTOM_NODE)
        self._routes = legacy
        return legacy, self._fetch_json(f"{self._base_url}{legacy.installed}")

    def _fetch_json(self, url: str) -> object:
        """Fetch one optional Manager endpoint and decode nested JSON strings."""

        try:
            response = requests.get(url, timeout=self._timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            log_info(
                _LOGGER,
                "Failed to fetch ComfyUI-Manager extension metadata",
                url=url,
                error=repr(error),
            )
            return None
        if isinstance(payload, str):
            try:
                return json.loads(payload)
            except json.JSONDecodeError as error:
                log_warning(
                    _LOGGER,
                    "ComfyUI-Manager returned invalid JSON string",
                    url=url,
                    error=repr(error),
                )
                return None
        return payload


__all__ = ["ComfyManagerExtensionMetadataProvider"]

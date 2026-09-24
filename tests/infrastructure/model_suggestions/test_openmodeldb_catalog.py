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

"""Verify OpenModelDB parsing, persistent reuse, and failure recovery."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests

from substitute.infrastructure.model_suggestions.openmodeldb_catalog import (
    OpenModelDbCatalogClient,
    parse_openmodeldb_catalog,
)


class _Response:
    """Expose the bounded requests response surface used by the adapter."""

    status_code = 200

    def __init__(self, payload: dict[str, object]) -> None:
        """Store deterministic JSON and revalidation headers."""

        self._payload = payload
        self.content = json.dumps(payload).encode("utf-8")
        self.headers = {
            "Content-Length": str(len(self.content)),
            "ETag": '"catalog-v1"',
            "Last-Modified": "Tue, 22 Sep 2026 12:00:00 GMT",
        }

    def raise_for_status(self) -> None:
        """Represent one successful response."""

    def json(self) -> dict[str, object]:
        """Return the stored catalog payload."""

        return self._payload


def _payload() -> dict[str, object]:
    """Return a minimal catalog with multiple supported artifact formats."""

    return {
        "1x-DeJPG-realplksr-otf": {
            "name": "DeJPG",
            "author": "Phhofm",
            "license": "MIT",
            "architecture": "realplksr",
            "scale": 1,
            "tags": ["jpeg", "restoration"],
            "description": "JPEG restoration",
            "resources": [
                {
                    "platform": "pytorch",
                    "type": "pth",
                    "size": 10,
                    "sha256": "a" * 64,
                    "urls": [
                        "https://github.com/example/models/releases/download/v1/model.pth"
                    ],
                },
                {
                    "platform": "pytorch",
                    "type": "safetensors",
                    "size": 9,
                    "sha256": "b" * 64,
                    "urls": [
                        "https://github.com/example/models/releases/download/v1/model.safetensors"
                    ],
                },
            ],
            "thumbnail": {"type": "standalone", "url": "/thumbs/dejpg.jpg"},
        },
        "invalid": {"name": "Missing resources", "resources": []},
    }


def test_parser_preserves_exact_resources_and_prefers_safetensors() -> None:
    """Catalog parsing should retain hashes while preferring safer artifacts."""

    catalog = parse_openmodeldb_catalog(_payload())

    assert len(catalog.models) == 1
    model = catalog.models[0]
    assert model.model_id == "1x-DeJPG-realplksr-otf"
    assert model.thumbnail_url == "https://openmodeldb.info/thumbs/dejpg.jpg"
    resource = model.preferred_resource()
    assert resource is not None
    assert resource.resource_type == "safetensors"
    assert resource.sha256 == "b" * 64
    assert catalog.resource_for_sha256("B" * 64) == (model, resource)


def test_client_reuses_fresh_cache_and_falls_back_when_refresh_fails(
    tmp_path: Path,
) -> None:
    """A valid stale snapshot should keep discovery available during an outage."""

    requests_seen: list[dict[str, Any]] = []

    def fetch(_url: str, **kwargs: Any) -> _Response:
        """Record one successful remote catalog request."""

        requests_seen.append(kwargs)
        return _Response(_payload())

    clock = [1000.0]
    client = OpenModelDbCatalogClient(
        tmp_path,
        http_get=fetch,
        freshness_seconds=60.0,
        clock=lambda: clock[0],
    )

    first = client.load()
    second = client.load()

    assert second == first
    assert len(requests_seen) == 1
    assert (tmp_path / "catalog-v1.json").is_file()

    clock[0] = 2000.0

    def unavailable(_url: str, **_kwargs: Any) -> object:
        """Represent a recoverable provider outage."""

        raise requests.ConnectionError("offline")

    stale_client = OpenModelDbCatalogClient(
        tmp_path,
        http_get=unavailable,
        freshness_seconds=60.0,
        clock=lambda: clock[0],
    )

    assert stale_client.load() == first

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

"""Verify CivitAI monthly discovery request and strict candidate safety."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

from sugarsubstitute_shared.model_discovery import (
    CivitaiDiscoveryClient,
    ModelCategory,
)


def _safe_model(
    *, model_id: int = 1, file_overrides: dict[str, object] | None = None
) -> dict[str, Any]:
    """Build one eligible public model response item."""

    file: dict[str, object] = {
        "name": f"model-{model_id}.safetensors",
        "sizeKB": 1024.5,
        "downloadUrl": f"https://civitai.com/api/download/models/{model_id * 10}",
        "primary": True,
        "pickleScanResult": "Success",
        "virusScanResult": "Success",
        "hashes": {"SHA256": f"{model_id:064x}"},
        "metadata": {"format": "SafeTensor"},
    }
    file.update(file_overrides or {})
    return {
        "id": model_id,
        "name": f"Model {model_id}",
        "type": "Checkpoint",
        "nsfw": False,
        "mode": None,
        "creator": {"username": "Creator"},
        "modelVersions": [
            {
                "id": model_id * 10,
                "name": "Version",
                "baseModel": "SDXL 1.0",
                "availability": "Public",
                "files": [file],
                "images": [
                    {
                        "url": "https://image.civitai.com/preview.jpeg",
                        "nsfw": False,
                    }
                ],
            }
        ],
    }


def test_client_requests_monthly_popularity_and_parses_safe_primary_file() -> None:
    """Discovery should use the documented monthly order without client reranking."""

    calls: list[tuple[str, dict[str, str], float]] = []

    def fetch(
        url: str,
        *,
        headers: dict[str, str],
        timeout: float,
    ) -> object:
        """Capture the request and return two eligible items."""

        calls.append((url, headers, timeout))
        return {"items": [_safe_model(model_id=4), _safe_model(model_id=9)]}

    models = CivitaiDiscoveryClient(
        fetch_json=fetch,
        api_key_provider=lambda: "secret-key",
    ).discover_monthly_popular(ModelCategory.CHECKPOINTS, limit=30)

    query = parse_qs(urlparse(calls[0][0]).query)
    assert query == {
        "limit": ["30"],
        "types": ["Checkpoint"],
        "sort": ["Most Downloaded"],
        "period": ["Month"],
        "nsfw": ["false"],
        "earlyAccess": ["false"],
        "primaryFileOnly": ["true"],
    }
    assert calls[0][1]["Authorization"] == "Bearer secret-key"
    assert [model.model_id for model in models] == [4, 9]
    assert [model.provider_rank for model in models] == [1, 2]
    assert models[0].size_bytes == 1_049_088
    assert models[0].thumbnail_url == "https://image.civitai.com/preview.jpeg"


def test_client_filters_archived_nsfw_bad_scan_hash_format_and_host() -> None:
    """No unsafe or unverifiable provider record may become a download card."""

    archived = _safe_model(model_id=1)
    archived["mode"] = "Archived"
    nsfw = _safe_model(model_id=2)
    nsfw["nsfw"] = True
    pickle_failed = _safe_model(
        model_id=3, file_overrides={"pickleScanResult": "Danger"}
    )
    virus_failed = _safe_model(model_id=4, file_overrides={"virusScanResult": "Danger"})
    missing_hash = _safe_model(model_id=5, file_overrides={"hashes": {}})
    checkpoint = _safe_model(
        model_id=6,
        file_overrides={
            "name": "unsafe.ckpt",
            "metadata": {"format": "PickleTensor"},
        },
    )
    hostile_host = _safe_model(
        model_id=7,
        file_overrides={
            "downloadUrl": "https://attacker.invalid/api/download/models/70"
        },
    )
    safe = _safe_model(model_id=8)
    client = CivitaiDiscoveryClient(
        fetch_json=lambda *_args, **_kwargs: {
            "items": [
                archived,
                nsfw,
                pickle_failed,
                virus_failed,
                missing_hash,
                checkpoint,
                hostile_host,
                safe,
            ]
        }
    )

    models = client.discover_monthly_popular(ModelCategory.CHECKPOINTS, limit=30)

    assert [model.model_id for model in models] == [8]
    assert models[0].provider_rank == 8


def test_client_omits_thumbnail_unless_image_is_explicitly_safe() -> None:
    """Cards may still be useful without leaking a mature or untrusted preview."""

    model = _safe_model()
    version = model["modelVersions"][0]
    version["images"] = [
        {"url": "https://image.civitai.com/mature.jpeg", "nsfw": True},
        {"url": "https://attacker.invalid/sfw.jpeg", "nsfw": False},
    ]
    client = CivitaiDiscoveryClient(
        fetch_json=lambda *_args, **_kwargs: {"items": [model]}
    )

    candidates = client.discover_monthly_popular(ModelCategory.CHECKPOINTS, limit=1)

    assert candidates[0].thumbnail_url is None

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

"""Verify exact CivitAI upscaler link safety and mixed-provider routing."""

from __future__ import annotations

from typing import cast

import pytest

from substitute.domain.model_recommendations import ModelFamilyId
from substitute.infrastructure.model_recommendations.civitai_gateway import (
    CivitaiFamilyRecommendationGateway,
)
from substitute.infrastructure.model_recommendations.civitai_upscaler_parser import (
    parse_civitai_upscaler,
)
from substitute.infrastructure.model_recommendations.provider_gateway import (
    ProviderRecommendationGateway,
)
from substitute.infrastructure.model_suggestions.openmodeldb_catalog import (
    OpenModelDbCatalogClient,
)


def _model_payload() -> dict[str, object]:
    """Return one fully specified public CivitAI upscaler response."""

    return {
        "id": 116225,
        "name": "4x-Ultrasharp",
        "type": "Upscaler",
        "nsfw": False,
        "mode": None,
        "creator": {"username": "modelmaker"},
        "modelVersions": [
            {
                "id": 125843,
                "name": "v1",
                "availability": "Public",
                "files": [
                    {
                        "name": "4xUltrasharp_v10.pt",
                        "sizeKB": 64.0,
                        "downloadUrl": "https://civitai.com/api/download/models/125843?fileId=90900",
                        "metadata": {"format": "PickleTensor"},
                        "hashes": {"SHA256": "a" * 64},
                        "pickleScanResult": "Success",
                        "virusScanResult": "Success",
                    }
                ],
            }
        ],
    }


def test_civitai_upscaler_link_resolves_exact_verified_file() -> None:
    """Allow a CivitAI-only upscaler through the installer provider gateway."""

    requested: list[str] = []

    def fetch_json(url: str, *, headers: dict[str, str], timeout: float) -> object:
        """Record the fixed API lookup and return its model payload."""

        requested.append(url)
        return _model_payload()

    gateway = ProviderRecommendationGateway(
        civitai=CivitaiFamilyRecommendationGateway(fetch_json=fetch_json),
        openmodeldb=cast(OpenModelDbCatalogClient, object()),
    )

    recommendation = gateway.resolve_model_page(
        ModelFamilyId.UPSCALERS,
        "https://civitai.com/models/116225?modelVersionId=125843",
    )

    assert recommendation is not None
    assert recommendation.provider_id == "civitai"
    assert recommendation.file_name == "4xUltrasharp_v10.pt"
    assert recommendation.sha256 == "a" * 64
    assert recommendation.thumbnail_url is None
    assert requested == ["https://civitai.com/api/v1/models/116225"]


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("model", "type", "Checkpoint"),
        ("model", "nsfw", True),
        ("version", "availability", "EarlyAccess"),
        ("file", "virusScanResult", "Danger"),
        ("file", "hashes", {}),
    ],
)
def test_civitai_upscaler_rejects_incompatible_or_unsafe_payload(
    section: str,
    field: str,
    value: object,
) -> None:
    """Reject other families, restricted files, failed scans, and missing hashes."""

    payload = _model_payload()
    version = cast(dict[str, object], cast(list[object], payload["modelVersions"])[0])
    file = cast(dict[str, object], cast(list[object], version["files"])[0])
    record = {"model": payload, "version": version, "file": file}[section]
    record[field] = value
    assert parse_civitai_upscaler(payload, target_version_id=None) is None


def test_civitai_upscaler_requires_selected_version_and_safe_page() -> None:
    """Never silently substitute a different version or accept forged URLs."""

    assert parse_civitai_upscaler(_model_payload(), target_version_id=999) is None
    gateway = ProviderRecommendationGateway(
        civitai=CivitaiFamilyRecommendationGateway(fetch_json=lambda **_kw: {}),
        openmodeldb=cast(OpenModelDbCatalogClient, object()),
    )
    with pytest.raises(ValueError):
        gateway.resolve_model_page(
            ModelFamilyId.UPSCALERS, "https://user@civitai.com/models/116225"
        )

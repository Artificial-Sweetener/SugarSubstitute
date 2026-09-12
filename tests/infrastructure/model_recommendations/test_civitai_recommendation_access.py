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

"""Verify unauthenticated access policy for automatic CivitAI recommendations."""

from __future__ import annotations

from urllib.parse import urlparse

import pytest

from substitute.domain.model_recommendations import (
    ModelFamilyId,
    ModelRecommendationAccess,
    ModelRecommendationAccessPolicy,
    ModelRecommendationQuery,
)
from substitute.infrastructure.model_recommendations import (
    CivitaiFamilyRecommendationGateway,
    CivitaiRecommendationError,
)


def _model(model_id: int) -> dict[str, object]:
    """Build one family-compatible recommendation candidate."""

    version_id = model_id * 10
    return {
        "id": model_id,
        "name": f"Model {model_id}",
        "type": "Checkpoint",
        "nsfw": False,
        "creator": {"username": "creator"},
        "modelVersions": [
            {
                "id": version_id,
                "name": f"Version {model_id}",
                "baseModel": "Illustrious",
                "availability": "Public",
                "images": [
                    {
                        "id": model_id * 100,
                        "url": f"https://image.civitai.com/model-{model_id}.jpeg",
                        "nsfw": False,
                        "nsfwLevel": 1,
                        "type": "image",
                        "width": 832,
                        "height": 1216,
                    }
                ],
                "files": [
                    {
                        "name": f"model-{model_id}.safetensors",
                        "downloadUrl": (
                            f"https://civitai.com/api/download/models/{version_id}"
                        ),
                        "sizeKB": 1024,
                        "primary": True,
                        "metadata": {"format": "SafeTensor"},
                        "hashes": {"SHA256": f"{model_id:064x}"},
                        "pickleScanResult": "Success",
                        "virusScanResult": "Success",
                    }
                ],
            }
        ],
    }


class _AccessProvider:
    """Serve model candidates and exact per-version access declarations."""

    def __init__(self, access_by_version: dict[int, object]) -> None:
        """Store access payloads and observable request state."""

        self.access_by_version = access_by_version
        self.urls: list[str] = []
        self.access_headers: list[dict[str, str]] = []

    def __call__(self, url: str, **kwargs: object) -> object:
        """Return the provider response owned by the requested route."""

        self.urls.append(url)
        path = urlparse(url).path
        if path.endswith("/enums"):
            return {"BaseModel": ["Illustrious"]}
        if "/model-versions/mini/" in path:
            headers = kwargs.get("headers")
            assert isinstance(headers, dict)
            self.access_headers.append(headers)
            version_id = int(path.rsplit("/", maxsplit=1)[-1])
            return self.access_by_version[version_id]
        if path == "/api/v1/models/1":
            return _model(1)
        return {"items": [_model(1), _model(2)]}


def _access(*, requires_authentication: bool) -> dict[str, object]:
    """Return one current CivitAI minimal-version access declaration."""

    return {
        "availability": "Public",
        "requireAuth": requires_authentication,
        "checkPermission": False,
    }


def test_automatic_recommendations_exclude_api_key_downloads() -> None:
    """Never suggest a model that first-run setup cannot download anonymously."""

    provider = _AccessProvider(
        {
            10: _access(requires_authentication=True),
            20: _access(requires_authentication=False),
        }
    )

    cards = CivitaiFamilyRecommendationGateway(
        fetch_json=provider,
        api_key_provider=lambda: "configured-secret",
    ).discover(
        ModelRecommendationQuery(ModelFamilyId.SDXL),
        limit=2,
    )

    assert [card.model_id for card in cards] == [2]
    assert provider.access_headers
    assert all("Authorization" not in headers for headers in provider.access_headers)


def test_explicit_picker_suggestions_include_and_label_api_key_downloads() -> None:
    """A user-opened picker may offer protected models without authenticating yet."""

    provider = _AccessProvider(
        {
            10: _access(requires_authentication=True),
            20: _access(requires_authentication=False),
        }
    )

    cards = CivitaiFamilyRecommendationGateway(fetch_json=provider).discover(
        ModelRecommendationQuery(
            ModelFamilyId.SDXL,
            access_policy=ModelRecommendationAccessPolicy.INCLUDE_AUTHENTICATED,
        ),
        limit=2,
    )

    assert [card.model_id for card in cards] == [1, 2]
    assert [card.access for card in cards] == [
        ModelRecommendationAccess.API_KEY_REQUIRED,
        ModelRecommendationAccess.PUBLIC,
    ]
    assert all("Authorization" not in headers for headers in provider.access_headers)


def test_explicit_model_links_remain_available_for_api_key_downloads() -> None:
    """Keep auth-capable user-selected downloads outside recommendation policy."""

    provider = _AccessProvider({10: _access(requires_authentication=True)})

    card = CivitaiFamilyRecommendationGateway(fetch_json=provider).resolve_model_page(
        ModelFamilyId.SDXL,
        "https://civitai.com/models/1?modelVersionId=10",
    )

    assert card is not None
    assert card.version_id == 10
    assert not provider.access_headers


def test_automatic_recommendations_fail_closed_on_unknown_access() -> None:
    """Do not surface a candidate when the provider omits its auth contract."""

    provider = _AccessProvider({10: {}, 20: _access(requires_authentication=False)})

    with pytest.raises(CivitaiRecommendationError):
        CivitaiFamilyRecommendationGateway(fetch_json=provider).discover(
            ModelRecommendationQuery(ModelFamilyId.SDXL),
            limit=2,
        )

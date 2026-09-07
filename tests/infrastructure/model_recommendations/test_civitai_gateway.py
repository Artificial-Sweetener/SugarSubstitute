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

"""Verify exact-family, safe, ordered CivitAI onboarding recommendations."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from substitute.domain.civitai import CivitaiThumbnailSafetyPolicy
from substitute.domain.model_metadata import CivitaiThumbnailPolicy
from substitute.domain.model_recommendations import (
    ModelFamilyId,
    ModelRecommendationQuery,
)
from substitute.infrastructure.model_recommendations import (
    CivitaiFamilyRecommendationGateway,
    CivitaiRecommendationError,
)

_HASH = "a" * 64
_SDXL_LINK_BASE_MODELS = (
    "Illustrious",
    "NoobAI",
    "Playground v2",
    "Pony",
    "SDXL 0.9",
    "SDXL 1.0",
    "SDXL 1.0 LCM",
    "SDXL Distilled",
    "SDXL Hyper",
    "SDXL Lightning",
    "SDXL Turbo",
)


def _model(
    model_id: int,
    *,
    base_model: str,
    thumbnail: bool = True,
    model_type: str = "Checkpoint",
    sha256: str | None = None,
) -> dict[str, object]:
    """Build one provider model fixture with a single primary SafeTensor."""

    version_id = model_id * 10
    return {
        "id": model_id,
        "name": f"Model {model_id}",
        "type": model_type,
        "nsfw": False,
        "creator": {"username": f"creator-{model_id}"},
        "modelVersions": [
            {
                "id": version_id,
                "name": f"Version {model_id}",
                "baseModel": base_model,
                "availability": "Public",
                "images": (
                    [
                        {
                            "id": model_id * 100,
                            "url": f"https://image.civitai.com/model-{model_id}.jpeg",
                            "nsfw": False,
                            "nsfwLevel": 1,
                            "type": "image",
                            "width": 832,
                            "height": 1216,
                        }
                    ]
                    if thumbnail
                    else []
                ),
                "files": [
                    {
                        "name": f"model-{model_id}.safetensors",
                        "downloadUrl": f"https://civitai.com/api/download/models/{version_id}",
                        "sizeKB": 1024,
                        "primary": True,
                        "metadata": {"format": "SafeTensor"},
                        "hashes": {"SHA256": sha256 or f"{model_id:064x}"},
                        "pickleScanResult": "Success",
                        "virusScanResult": "Success",
                    }
                ],
            }
        ],
    }


class _RecordedProvider:
    """Return deterministic enum and paged model responses."""

    def __init__(
        self,
        pages: list[dict[str, object]],
        *,
        fallback_images: dict[int, list[dict[str, object]]] | None = None,
        base_models: tuple[str, ...] = ("Illustrious", "Anima"),
    ) -> None:
        """Store pages and expose requested URLs for exact query assertions."""

        self.pages = pages
        self.fallback_images = fallback_images or {}
        self.base_models = base_models
        self.urls: list[str] = []

    def __call__(self, url: str, **_kwargs: object) -> object:
        """Return enums or the next recorded page."""

        self.urls.append(url)
        if url.endswith("/enums"):
            return {"BaseModel": list(self.base_models)}
        if urlparse(url).path.endswith("/images"):
            version_id = int(parse_qs(urlparse(url).query)["modelVersionId"][0])
            return {"items": self.fallback_images.get(version_id, [])}
        if not self.pages:
            raise AssertionError("Unexpected provider page request.")
        return self.pages.pop(0)


@pytest.mark.parametrize(
    ("family_id", "base_model"),
    [(ModelFamilyId.SDXL, "Illustrious"), (ModelFamilyId.ANIMA, "Anima")],
)
def test_exact_family_query_yields_five_unique_thumbnail_complete_cards(
    family_id: ModelFamilyId,
    base_model: str,
) -> None:
    """Each shipped family keeps exact filters, provider order, and five cards."""

    provider = _RecordedProvider(
        [{"items": [_model(index, base_model=base_model) for index in range(1, 7)]}]
    )
    gateway = CivitaiFamilyRecommendationGateway(fetch_json=provider)

    cards = gateway.discover(ModelRecommendationQuery(family_id))

    assert [card.model_id for card in cards] == [1, 2, 3, 4, 5]
    assert [card.popularity_rank for card in cards] == [1, 2, 3, 4, 5]
    assert all(card.family_id is family_id for card in cards)
    assert all(
        card.thumbnail_url.startswith("https://image.civitai.com/") for card in cards
    )
    query = parse_qs(urlparse(provider.urls[1]).query)
    assert query["baseModels"] == [base_model]
    assert query["types"] == ["Checkpoint"]
    assert query["sort"] == ["Most Downloaded"]
    assert query["period"] == ["Month"]


def test_gateway_returns_fewer_than_five_when_provider_has_only_three() -> None:
    """Keep every usable result without fabricating or duplicating a full page."""

    provider = _RecordedProvider(
        [{"items": [_model(index, base_model="Anima") for index in range(1, 4)]}]
    )

    cards = CivitaiFamilyRecommendationGateway(fetch_json=provider).discover(
        ModelRecommendationQuery(ModelFamilyId.ANIMA)
    )

    assert [card.model_id for card in cards] == [1, 2, 3]
    assert [card.popularity_rank for card in cards] == [1, 2, 3]


def test_gateway_filters_wrong_family_unsafe_missing_image_and_local_hash() -> None:
    """Provider content must pass every family, safety, and local-identity gate."""

    unsafe = _model(2, base_model="Illustrious")
    unsafe["nsfw"] = True
    provider = _RecordedProvider(
        [
            {
                "items": [
                    _model(1, base_model="Anima"),
                    unsafe,
                    _model(3, base_model="Illustrious", thumbnail=False),
                    _model(4, base_model="Illustrious", sha256=_HASH),
                    _model(5, base_model="Illustrious"),
                ]
            }
        ]
    )

    cards = CivitaiFamilyRecommendationGateway(fetch_json=provider).discover(
        ModelRecommendationQuery(ModelFamilyId.SDXL),
        excluded_sha256=frozenset({_HASH}),
    )

    assert [card.model_id for card in cards] == [5]
    assert cards[0].popularity_rank == 5


def test_gateway_accepts_current_civitai_sfw_level_when_boolean_is_absent() -> None:
    """Treat numeric NSFW level 1 as safe through the shared thumbnail policy."""

    model = _model(1, base_model="Illustrious")
    versions = model["modelVersions"]
    assert isinstance(versions, list)
    version = versions[0]
    assert isinstance(version, dict)
    image = version["images"][0]
    assert isinstance(image, dict)
    image.pop("nsfw")
    provider = _RecordedProvider([{"items": [model]}])

    cards = CivitaiFamilyRecommendationGateway(fetch_json=provider).discover(
        ModelRecommendationQuery(ModelFamilyId.SDXL),
        limit=1,
    )

    assert len(cards) == 1


def test_gateway_uses_current_thumbnail_content_preference() -> None:
    """Apply the user's saved safety choice to recommendation previews."""

    model = _model(1, base_model="Illustrious")
    versions = model["modelVersions"]
    assert isinstance(versions, list)
    version = versions[0]
    assert isinstance(version, dict)
    images = version["images"]
    assert isinstance(images, list)
    image = images[0]
    assert isinstance(image, dict)
    image["nsfwLevel"] = 2
    default = CivitaiFamilyRecommendationGateway(
        fetch_json=_RecordedProvider([{"items": [model]}])
    ).discover(ModelRecommendationQuery(ModelFamilyId.SDXL), limit=1)
    allowed = CivitaiFamilyRecommendationGateway(
        fetch_json=_RecordedProvider([{"items": [model]}]),
        thumbnail_policy_provider=lambda: CivitaiThumbnailPolicy(
            CivitaiThumbnailSafetyPolicy.ALLOW_SOFT
        ),
    ).discover(ModelRecommendationQuery(ModelFamilyId.SDXL), limit=1)

    assert default == ()
    assert len(allowed) == 1


def test_gateway_fetches_a_large_portrait_when_model_payload_has_no_preview() -> None:
    """Use the version image endpoint so sparse model results still render real cards."""

    provider = _RecordedProvider(
        [{"items": [_model(7, base_model="Illustrious", thumbnail=False)]}],
        fallback_images={
            70: [
                {
                    "id": 700,
                    "url": "https://image.civitai.com/x/original=true/landscape.jpeg",
                    "nsfwLevel": 1,
                    "type": "image",
                    "width": 1216,
                    "height": 832,
                },
                {
                    "id": 701,
                    "url": "https://image.civitai.com/x/original=true/portrait.jpeg",
                    "nsfwLevel": 1,
                    "type": "image",
                    "width": 832,
                    "height": 1216,
                },
            ]
        },
    )

    cards = CivitaiFamilyRecommendationGateway(fetch_json=provider).discover(
        ModelRecommendationQuery(ModelFamilyId.SDXL),
        limit=1,
    )

    assert len(cards) == 1
    assert cards[0].thumbnail_image_id == 701
    assert cards[0].thumbnail_url == (
        "https://image.civitai.com/x/width=512/portrait.jpeg"
    )
    image_query = parse_qs(urlparse(provider.urls[-1]).query)
    assert image_query["modelVersionId"] == ["70"]
    assert image_query["sort"] == ["Most Reactions"]
    assert image_query["nsfw"] == ["None"]


def test_shared_model_page_uses_the_selected_family_versions_own_preview() -> None:
    """Bind each family card to its exact version when one model page spans both."""

    shared_model = _model(42, base_model="Illustrious")
    anima_model = _model(42, base_model="Anima")
    anima_versions = anima_model["modelVersions"]
    assert isinstance(anima_versions, list)
    anima_version = anima_versions[0]
    assert isinstance(anima_version, dict)
    anima_version["id"] = 421
    anima_version["name"] = "Anima edition"
    anima_images = anima_version["images"]
    assert isinstance(anima_images, list)
    anima_image = anima_images[0]
    assert isinstance(anima_image, dict)
    anima_image["id"] = 42100
    anima_image["url"] = "https://image.civitai.com/anima-version.jpeg"
    illustrious_versions = shared_model["modelVersions"]
    assert isinstance(illustrious_versions, list)
    illustrious_version = illustrious_versions[0]
    assert isinstance(illustrious_version, dict)
    illustrious_images = illustrious_version["images"]
    assert isinstance(illustrious_images, list)
    illustrious_image = illustrious_images[0]
    assert isinstance(illustrious_image, dict)
    illustrious_image["id"] = 42000
    illustrious_image["url"] = "https://image.civitai.com/illustrious-version.jpeg"
    shared_model["modelVersions"] = [anima_version, illustrious_version]

    sdxl = CivitaiFamilyRecommendationGateway(
        fetch_json=_RecordedProvider([{"items": [shared_model]}])
    ).discover(ModelRecommendationQuery(ModelFamilyId.SDXL), limit=1)
    anima = CivitaiFamilyRecommendationGateway(
        fetch_json=_RecordedProvider([{"items": [shared_model]}])
    ).discover(ModelRecommendationQuery(ModelFamilyId.ANIMA), limit=1)

    assert sdxl[0].model_id == anima[0].model_id == 42
    assert (sdxl[0].version_id, anima[0].version_id) == (420, 421)
    assert (sdxl[0].thumbnail_image_id, anima[0].thumbnail_image_id) == (
        42000,
        42100,
    )
    assert sdxl[0].thumbnail_url.endswith("illustrious-version.jpeg")
    assert anima[0].thumbnail_url.endswith("anima-version.jpeg")


def test_gateway_rank_tracks_provider_position_across_duplicates_and_pages() -> None:
    """Do not relabel a later eligible card as more popular than provider order."""

    provider = _RecordedProvider(
        [
            {
                "items": [
                    _model(1, base_model="Anima"),
                    _model(1, base_model="Anima"),
                ],
                "metadata": {"nextPage": "https://civitai.com/api/v1/models?page=2"},
            },
            {"items": [_model(2, base_model="Anima")]},
        ]
    )

    cards = CivitaiFamilyRecommendationGateway(fetch_json=provider).discover(
        ModelRecommendationQuery(ModelFamilyId.ANIMA),
        limit=2,
    )

    assert [(card.model_id, card.popularity_rank) for card in cards] == [(1, 1), (2, 3)]


def test_gateway_resolves_model_and_version_links_against_the_requested_family() -> (
    None
):
    """Accept trusted model pages while honoring an explicitly linked version."""

    model = _model(42, base_model="Anima")
    versions = model["modelVersions"]
    assert isinstance(versions, list)
    first = versions[0]
    assert isinstance(first, dict)
    second = dict(first)
    second["id"] = 421
    second["name"] = "Exact linked version"
    versions.insert(0, second)
    alternate_model = _model(934764, base_model="Anima")
    alternate_versions = alternate_model["modelVersions"]
    assert isinstance(alternate_versions, list)
    alternate_version = alternate_versions[0]
    assert isinstance(alternate_version, dict)
    alternate_version["id"] = 1142097
    furrytoonmix = _model(97479, base_model="Illustrious")
    furrytoonmix_versions = furrytoonmix["modelVersions"]
    assert isinstance(furrytoonmix_versions, list)
    furrytoonmix_version = furrytoonmix_versions[0]
    assert isinstance(furrytoonmix_version, dict)
    furrytoonmix_version["id"] = 3209518
    provider = _RecordedProvider([model, model, alternate_model, furrytoonmix])
    gateway = CivitaiFamilyRecommendationGateway(fetch_json=provider)

    default = gateway.resolve_model_page(
        ModelFamilyId.ANIMA,
        "https://civitai.com/models/42/example",
    )
    exact = gateway.resolve_model_page(
        ModelFamilyId.ANIMA,
        "https://www.civitai.com/models/42?modelVersionId=420",
    )
    alternate_host = gateway.resolve_model_page(
        ModelFamilyId.ANIMA,
        "https://civitai.red/models/934764/miaomiao-harem?modelVersionId=1142097",
    )
    versionless_sdxl = gateway.resolve_model_page(
        ModelFamilyId.SDXL,
        "https://civitai.com/models/97479/furrytoonmix",
    )

    assert default is not None and default.version_id == 421
    assert exact is not None and exact.version_id == 420
    assert alternate_host is not None and alternate_host.version_id == 1142097
    assert versionless_sdxl is not None and versionless_sdxl.version_id == 3209518


@pytest.mark.parametrize("base_model", _SDXL_LINK_BASE_MODELS)
def test_gateway_accepts_every_civitai_sdxl_compatible_link_family(
    base_model: str,
) -> None:
    """Accept every researched CivitAI SDXL lineage for pasted checkpoint links."""

    provider = _RecordedProvider(
        [_model(42, base_model=base_model)],
        base_models=(base_model,),
    )

    card = CivitaiFamilyRecommendationGateway(fetch_json=provider).resolve_model_page(
        ModelFamilyId.SDXL,
        "https://civitai.com/models/42/example",
    )

    assert card is not None
    assert card.family_id is ModelFamilyId.SDXL


@pytest.mark.parametrize("base_model", ("Anima", "Flux.1 D", "Pony V7", "SD 1.5"))
def test_gateway_rejects_non_sdxl_link_families(base_model: str) -> None:
    """Keep unrelated and AuraFlow-based checkpoints out of the SDXL flow."""

    provider = _RecordedProvider(
        [_model(42, base_model=base_model)],
        base_models=(base_model, "Illustrious"),
    )

    card = CivitaiFamilyRecommendationGateway(fetch_json=provider).resolve_model_page(
        ModelFamilyId.SDXL,
        "https://civitai.com/models/42/example",
    )

    assert card is None


@pytest.mark.parametrize(
    "url",
    (
        "http://civitai.com/models/1",
        "https://example.com/models/1",
        "https://civitai.com/images/1",
        "https://civitai.com/models/nope",
    ),
)
def test_gateway_rejects_untrusted_or_non_model_links(url: str) -> None:
    """Never send malformed or cross-origin user input to the provider."""

    with pytest.raises(ValueError):
        CivitaiFamilyRecommendationGateway(
            fetch_json=lambda *_a, **_k: {}
        ).resolve_model_page(
            ModelFamilyId.SDXL,
            url,
        )


def test_gateway_uses_bounded_trusted_pagination_and_caches_enum_validation() -> None:
    """Discovery may fill from trusted pages without repeatedly fetching enums."""

    next_page = "https://civitai.com/api/v1/models?page=2"
    provider = _RecordedProvider(
        [
            {
                "items": [_model(1, base_model="Illustrious")],
                "metadata": {"nextPage": next_page},
            },
            {"items": [_model(2, base_model="Illustrious")]},
            {"items": [_model(3, base_model="Anima")]},
        ]
    )
    gateway = CivitaiFamilyRecommendationGateway(fetch_json=provider)

    first = gateway.discover(ModelRecommendationQuery(ModelFamilyId.SDXL), limit=2)
    second = gateway.discover(ModelRecommendationQuery(ModelFamilyId.ANIMA), limit=1)

    assert [card.model_id for card in first] == [1, 2]
    assert [card.model_id for card in second] == [3]
    assert sum(url.endswith("/enums") for url in provider.urls) == 1


@pytest.mark.parametrize(
    "payload",
    [None, [], {}, {"items": "wrong"}],
)
def test_gateway_fails_closed_for_malformed_provider_payload(payload: object) -> None:
    """Malformed discovery responses remain retryable failures, never empty success."""

    calls = 0

    def fetch(url: str, **_kwargs: object) -> object:
        """Return valid enums followed by the parameterized malformed payload."""

        nonlocal calls
        calls += 1
        return {"BaseModel": ["Illustrious"]} if url.endswith("/enums") else payload

    gateway = CivitaiFamilyRecommendationGateway(fetch_json=fetch)

    with pytest.raises(CivitaiRecommendationError):
        gateway.discover(ModelRecommendationQuery(ModelFamilyId.SDXL))
    assert calls == 2


def test_gateway_rejects_changed_enums_and_untrusted_pagination() -> None:
    """Changed mappings and cross-origin pagination must stop discovery safely."""

    def missing_enum(*_args: object, **_kwargs: object) -> object:
        """Return an enum response that omits every configured family."""

        return {"BaseModel": ["Other"]}

    with pytest.raises(CivitaiRecommendationError):
        CivitaiFamilyRecommendationGateway(fetch_json=missing_enum).discover(
            ModelRecommendationQuery(ModelFamilyId.ANIMA)
        )

    provider = _RecordedProvider(
        [
            {
                "items": [],
                "metadata": {"nextPage": "https://attacker.example/api/v1/models"},
            }
        ]
    )
    with pytest.raises(CivitaiRecommendationError):
        CivitaiFamilyRecommendationGateway(fetch_json=provider).discover(
            ModelRecommendationQuery(ModelFamilyId.SDXL)
        )

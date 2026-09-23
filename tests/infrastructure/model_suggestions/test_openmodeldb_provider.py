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

"""Verify curated OpenModelDB suggestion and download-host policy."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from substitute.domain.model_suggestions import (
    ModelSuggestionAccessPolicy,
    ModelSuggestionContext,
)
from substitute.application.model_metadata import CivitaiMetadataGateway
from substitute.application.model_recommendations.onboarding_service import (
    FamilyRecommendationGateway,
    RecommendationThumbnailFetcher,
)
from substitute.application.recipes import RecipeModelDownloadCandidate
from substitute.domain.model_metadata import (
    BackendModelDownloadJob,
    CivitaiDownloadAccess,
    CivitaiFile,
    CivitaiLookupResult,
    CivitaiLookupStatus,
    CivitaiModelVersion,
    CivitaiThumbnailPolicy,
    ModelDownloadStatus,
)
from substitute.domain.model_recommendations import (
    ModelFamilyId,
    ModelRecommendationQuery,
)
from substitute.infrastructure.model_suggestions.openmodeldb_catalog import (
    OpenModelDbCatalog,
    OpenModelDbCatalogClient,
    OpenModelDbModel,
    OpenModelDbResource,
)
from substitute.infrastructure.model_suggestions.openmodeldb_provider import (
    CachedOpenModelDbThumbnailFetcher,
    OpenModelDbSuggestionProvider,
    OpenModelDbThumbnailFetcher,
    require_openmodeldb_download_url,
)
from substitute.infrastructure.model_suggestions.civitai_provider import (
    CivitaiModelSuggestionProvider,
)
from substitute.infrastructure.model_suggestions.openmodeldb_recipe_recovery import (
    OpenModelDbRecipeRecoveryGateway,
)
from substitute.infrastructure.model_suggestions.openmodeldb_recipe_acquisition import (
    OpenModelDbRecipeAcquirer,
)
from substitute.infrastructure.model_recommendations import (
    CivitaiFamilyRecommendationGateway,
    ProviderRecommendationGateway,
)
from sugarsubstitute_shared.model_acquisition import (
    ModelAcquisitionError,
    ModelAcquisitionService,
)
from sugarsubstitute_shared.model_discovery import (
    ModelArtifactDestinationPolicy,
    ModelArtifactKind,
)


class _Stream:
    """Expose deterministic bytes through the acquisition stream contract."""

    def __init__(self, payload: bytes) -> None:
        """Store payload and cursor state."""

        self._payload = payload
        self._offset = 0

    @property
    def content_length(self) -> int:
        """Return the exact response size."""

        return len(self._payload)

    def read(self, size: int) -> bytes:
        """Return the next bounded response chunk."""

        chunk = self._payload[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk

    def close(self) -> None:
        """Release the in-memory stream."""


class _Catalog:
    """Return one deterministic curated catalog."""

    def load(self) -> OpenModelDbCatalog:
        """Return a known RealESRGAN entry."""

        return OpenModelDbCatalog(
            (
                OpenModelDbModel(
                    model_id="4x-realesrgan-x4plus-anime-6b",
                    name="RealESRGAN Anime 6B",
                    author="xinntao",
                    license_name="BSD-3-Clause",
                    architecture="esrgan",
                    scale=4,
                    tags=("anime",),
                    description=None,
                    resources=(
                        OpenModelDbResource(
                            resource_type="pth",
                            size_bytes=20,
                            sha256="a" * 64,
                            urls=(
                                "https://github.com/xinntao/Real-ESRGAN/releases/download/v1/model.pth",
                            ),
                        ),
                    ),
                    thumbnail_url="https://openmodeldb.info/thumbs/model.jpg",
                ),
            )
        )


def test_thumbnail_fetcher_accepts_live_catalog_image_hosts() -> None:
    """Catalog previews may live on OpenModelDB or its reviewed image host."""

    requested: list[str] = []

    def transport(url: str, timeout: float, maximum_bytes: int) -> bytes:
        """Record a bounded approved preview request."""

        assert timeout > 0
        assert maximum_bytes > 0
        requested.append(url)
        return b"image"

    fetcher = OpenModelDbThumbnailFetcher(transport=transport)
    own_url = "https://openmodeldb.info/thumbs/model.jpg"
    external_url = "https://i.slow.pics/k1sDOhPk.webp"

    assert fetcher.fetch(own_url) == b"image"
    assert fetcher.fetch(external_url) == b"image"
    assert requested == [own_url, external_url]

    for invalid in (
        "http://i.slow.pics/model.webp",
        "https://i.slow.pics.evil.example/model.webp",
        "https://user:secret@i.slow.pics/model.webp",
    ):
        with pytest.raises(ValueError, match="reviewed OpenModelDB hosts"):
            fetcher.fetch(invalid)


def test_civitai_offers_scan_clean_pt_for_exact_upscaler_hash() -> None:
    """A scan-clean CivitAI .pt file is a valid alternate acquisition offer."""

    class _Metadata:
        """Return the exact version of the curated test upscaler."""

        def lookup_model_version_by_hash(self, sha256: str) -> CivitaiLookupResult:
            """Return a scan-clean PyTorch upscaler matching the requested hash."""

            return CivitaiLookupResult(
                status=CivitaiLookupStatus.FOUND,
                version=CivitaiModelVersion(
                    model_id=147821,
                    model_version_id=164904,
                    model_name="RealESRGAN Anime 6B",
                    model_type="Upscaler",
                    version_name="v1",
                    base_model=None,
                    trained_words=(),
                    description=None,
                    version_description=None,
                    tags=(),
                    creator_username="xinntao",
                    creator_image=None,
                    nsfw=None,
                    nsfw_level=None,
                    availability=None,
                    files=(
                        CivitaiFile(
                            file_id=124735,
                            name="realesrganX4plusAnime_v1.pt",
                            size_kb=1.0,
                            file_type="Model",
                            download_url="https://civitai.com/api/download/models/164904?fileId=124735",
                            pickle_scan_result="Success",
                            virus_scan_result="Success",
                            primary=True,
                            hashes={"SHA256": sha256.upper()},
                            metadata={},
                        ),
                    ),
                    images=(),
                    stats={},
                    model_page_url="https://civitai.com/models/147821?modelVersionId=164904",
                    source_url="https://civitai.com/api/v1/model-versions/by-hash/"
                    + sha256,
                    fetched_at="2026-09-22T00:00:00Z",
                    raw_provider_payload={},
                ),
            )

        def model_version_download_access(
            self, model_version_id: int
        ) -> CivitaiDownloadAccess:
            """Treat the known model version as public."""

            assert model_version_id == 164904
            return CivitaiDownloadAccess.PUBLIC

    provider = CivitaiModelSuggestionProvider(
        recommendations=cast(CivitaiFamilyRecommendationGateway, object()),
        thumbnails=cast(RecommendationThumbnailFetcher, object()),
        acquisition=cast(ModelAcquisitionService, object()),
        upscaler_catalog=cast(OpenModelDbCatalogClient, _Catalog()),
        metadata=cast(CivitaiMetadataGateway, _Metadata()),
        thumbnail_policy=CivitaiThumbnailPolicy(),
    )

    suggestions = provider.suggest(
        ModelSuggestionContext(ModelArtifactKind.UPSCALE_MODELS),
        access_policy=ModelSuggestionAccessPolicy.PUBLIC_ONLY,
        limit=5,
        excluded_sha256=frozenset(),
    )

    assert len(suggestions) == 1
    assert suggestions[0].primary_offer.file_name == "realesrganX4plusAnime_v1.pt"
    assert suggestions[0].sha256 == "a" * 64


def test_provider_returns_curated_upscaler_with_openmodeldb_identity(
    tmp_path: Path,
) -> None:
    """Upscale discovery should expose OpenModelDB as the primary exact source."""

    provider = OpenModelDbSuggestionProvider(
        catalog=cast(OpenModelDbCatalogClient, _Catalog()),
        thumbnails=cast(CachedOpenModelDbThumbnailFetcher, object()),
        acquisition=ModelAcquisitionService(
            allowed_roots=(tmp_path,),
            download_url_validator=require_openmodeldb_download_url,
            allowed_extensions=(".pth", ".safetensors"),
        ),
    )
    context = ModelSuggestionContext(ModelArtifactKind.UPSCALE_MODELS)

    suggestions = provider.suggest(
        context,
        access_policy=ModelSuggestionAccessPolicy.CURRENT_USER,
        limit=8,
        excluded_sha256=frozenset(),
    )

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion.context == context
    assert suggestion.sha256 == "a" * 64
    assert suggestion.primary_offer.reference.provider_id == "openmodeldb"
    assert suggestion.primary_offer.file_name == "4x-realesrgan-x4plus-anime-6b.pth"


def test_installer_recommendations_use_curated_openmodeldb_upscalers() -> None:
    """The installer should route the upscaler family to its curated provider."""

    gateway = ProviderRecommendationGateway(
        civitai=cast(FamilyRecommendationGateway, object()),
        openmodeldb=cast(OpenModelDbCatalogClient, _Catalog()),
    )

    recommendations = gateway.discover(
        ModelRecommendationQuery(ModelFamilyId.UPSCALERS),
        limit=5,
    )

    assert len(recommendations) == 1
    recommendation = recommendations[0]
    assert recommendation.provider_id == "openmodeldb"
    assert recommendation.file_name == "4x-realesrgan-x4plus-anime-6b.pth"
    assert recommendation.sha256 == "A" * 64


def test_installer_keeps_openmodeldb_model_without_preview() -> None:
    """A missing catalog image must not remove an otherwise usable upscaler."""

    class _NoPreviewCatalog:
        """Expose one real curated identity without an image URL."""

        def load(self) -> OpenModelDbCatalog:
            """Return the Remacri entry with verified file metadata."""

            model = _Catalog().load().models[0]
            return OpenModelDbCatalog(
                (
                    replace(
                        model, model_id="4x-Remacri", name="Remacri", thumbnail_url=None
                    ),
                )
            )

    gateway = ProviderRecommendationGateway(
        civitai=cast(FamilyRecommendationGateway, object()),
        openmodeldb=cast(OpenModelDbCatalogClient, _NoPreviewCatalog()),
    )

    recommendations = gateway.discover(
        ModelRecommendationQuery(ModelFamilyId.UPSCALERS), limit=8
    )
    linked = gateway.resolve_model_page(
        ModelFamilyId.UPSCALERS, "https://openmodeldb.info/models/4x-Remacri"
    )

    assert len(recommendations) == 1
    assert recommendations[0].model_name == "Remacri"
    assert recommendations[0].thumbnail_url is None
    assert linked is not None and linked.sha256 == recommendations[0].sha256


def test_portable_recovery_uses_openmodeldb_for_exact_upscaler_hash() -> None:
    """Portable workflow recovery should prefer an exact OpenModelDB artifact."""

    gateway = OpenModelDbRecipeRecoveryGateway(
        cast(OpenModelDbCatalogClient, _Catalog())
    )

    candidate = gateway.candidate(kind="upscale_models", sha256="A" * 64)

    assert candidate is not None
    assert candidate.provider_id == "openmodeldb"
    assert candidate.name == "4x-realesrgan-x4plus-anime-6b.pth"
    assert candidate.sha256 == "A" * 64
    assert candidate.size_bytes == 20
    assert gateway.candidate(kind="checkpoints", sha256="A" * 64) is None


def test_portable_recovery_acquires_verified_pth_into_upscale_models(
    tmp_path: Path,
) -> None:
    """Direct recovery should verify bytes and return the Comfy-visible value."""

    payload = b"verified OpenModelDB upscaler"
    sha256 = hashlib.sha256(payload).hexdigest().upper()
    acquisition = ModelAcquisitionService(
        allowed_roots=(tmp_path,),
        stream_opener=lambda _url, _headers, _timeout: _Stream(payload),
        download_url_validator=require_openmodeldb_download_url,
        allowed_extensions=(".pth", ".safetensors"),
    )
    candidate = RecipeModelDownloadCandidate(
        kind="upscale_models",
        sha256=sha256,
        name="restoration.pth",
        download_url="https://github.com/example/releases/restoration.pth",
        size_kb=len(payload) / 1024,
        model_id=1,
        model_version_id=1,
        model_name="Restoration",
        version_name="4x",
        base_model=None,
        creator="OpenModelDB community",
        file_id=None,
        file_type="Model",
        metadata_format="PickleTensor",
        pickle_scan_result=None,
        virus_scan_result=None,
        model_page_url="https://openmodeldb.info/models/restoration",
        provider_id="openmodeldb",
        provider_name="OpenModelDB",
        size_bytes=len(payload),
    )
    progress: list[BackendModelDownloadJob] = []

    value = OpenModelDbRecipeAcquirer(
        acquisition=acquisition,
        destinations=ModelArtifactDestinationPolicy(tmp_path),
    ).acquire(candidate, progress_callback=progress.append, should_cancel=None)

    assert value == "restoration.pth"
    assert (tmp_path / "upscale_models" / value).read_bytes() == payload
    assert progress[-1].status is ModelDownloadStatus.COMPLETE
    assert progress[-1].sha256.upper() == sha256


@pytest.mark.parametrize(
    "url",
    (
        "http://github.com/example/model.pth",
        "https://example.com/model.pth",
        "https://user:secret@github.com/example/model.pth",
    ),
)
def test_download_policy_rejects_unreviewed_origins(url: str) -> None:
    """Provider acquisition must not accept arbitrary catalog URLs."""

    with pytest.raises(ModelAcquisitionError):
        require_openmodeldb_download_url(url)

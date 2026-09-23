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

"""Define provider-neutral exact-hash enrichment for installed model catalogs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from substitute.domain.model_metadata import (
    ModelMetadataCacheRecord,
    ThumbnailStoreResult,
)

if TYPE_CHECKING:
    from substitute.application.model_metadata.model_catalog_models import (
        ModelThumbnailVariant,
    )


@dataclass(frozen=True, slots=True)
class ModelProviderLink:
    """Describe one provider page associated with an exact model artifact."""

    provider_id: str
    provider_name: str
    model_id: str
    version_id: str
    model_page_url: str


@dataclass(frozen=True, slots=True)
class ModelCatalogProviderMatch:
    """Carry provider metadata proven by one installed artifact hash."""

    link: ModelProviderLink
    model_name: str
    version_name: str | None
    tags: tuple[str, ...]
    thumbnail: ThumbnailStoreResult | None


class ModelCatalogProvider(Protocol):
    """Resolve provider metadata from an installed artifact's exact identity."""

    def match(
        self,
        *,
        kind: str,
        sha256: str,
    ) -> ModelCatalogProviderMatch | None:
        """Return provider metadata only for an exact supported hash match."""


def exact_provider_matches(
    providers: tuple[ModelCatalogProvider, ...],
    *,
    kind: str,
    sha256: str | None,
) -> tuple[ModelCatalogProviderMatch, ...]:
    """Return ordered provider matches for one exact installed-model identity."""

    if sha256 is None:
        return ()
    return tuple(
        match
        for provider in providers
        for match in (provider.match(kind=kind, sha256=sha256),)
        if match is not None
    )


def provider_links_for_record(
    record: ModelMetadataCacheRecord | None,
    matches: tuple[ModelCatalogProviderMatch, ...],
) -> tuple[ModelProviderLink, ...]:
    """Merge ordered exact-hash links while preserving provider precedence."""

    links = [match.link for match in matches]
    if record is not None and record.provider is not None:
        links.append(
            ModelProviderLink(
                provider_id="civitai",
                provider_name="CivitAI",
                model_id=str(record.provider.model_id),
                version_id=str(record.provider.model_version_id),
                model_page_url=record.provider.model_page_url,
            )
        )
    unique: dict[str, ModelProviderLink] = {}
    for link in links:
        unique.setdefault(link.provider_id.casefold(), link)
    return tuple(unique.values())


def thumbnail_variants_for_match(
    match: ModelCatalogProviderMatch | None,
    *,
    fallback: ModelMetadataCacheRecord | None,
) -> tuple[ModelThumbnailVariant, ...]:
    """Prefer exact-provider thumbnails over legacy cached metadata."""

    from substitute.application.model_metadata.model_catalog_models import (
        ModelThumbnailVariant,
    )

    thumbnail = match.thumbnail if match is not None else None
    if thumbnail is None and fallback is not None:
        thumbnail = fallback.thumbnail
    if thumbnail is None:
        return ()
    return tuple(
        sorted(
            (
                ModelThumbnailVariant(
                    size=variant.size,
                    storage_key=variant.storage_key,
                    width=variant.width,
                    height=variant.height,
                    content_format=variant.content_format,
                    byte_size=variant.byte_size,
                    role=variant.role,
                )
                for variant in thumbnail.variants
            ),
            key=lambda variant: (variant.role, variant.size),
        )
    )


__all__ = [
    "ModelCatalogProvider",
    "ModelCatalogProviderMatch",
    "ModelProviderLink",
    "exact_provider_matches",
    "provider_links_for_record",
    "thumbnail_variants_for_match",
]

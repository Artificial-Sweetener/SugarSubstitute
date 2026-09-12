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

"""Derive immutable presentation values used by model-choice snapshots."""

from __future__ import annotations

from substitute.application.display_labels import beautify_label
from substitute.application.model_metadata import RichChoiceResolution
from substitute.domain.model_recommendations import SUPPORTED_MODEL_FAMILIES
from substitute.domain.model_suggestions import ModelSuggestionContext
from substitute.presentation.widgets.media_wall import (
    MediaThumbnailReadiness,
    MediaThumbnailReadinessStatus,
    unavailable_thumbnail_readiness,
)
from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.model_discovery import ModelArtifactKind


def thumbnail_readiness_for_resolution(
    resolution: RichChoiceResolution,
    *,
    repository_available: bool,
) -> MediaThumbnailReadiness:
    """Return metadata-only thumbnail readiness for prepared model choices."""

    storage_key = first_resolution_thumbnail_storage_key(resolution)
    if storage_key is None:
        return unavailable_thumbnail_readiness("thumbnail_variant_unavailable")
    if not repository_available:
        return unavailable_thumbnail_readiness("thumbnail_repository_unavailable")
    return MediaThumbnailReadiness(
        status=MediaThumbnailReadinessStatus.PENDING,
        storage_key=storage_key,
    )


def first_resolution_thumbnail_storage_key(
    resolution: RichChoiceResolution,
) -> str | None:
    """Return the first prepared thumbnail storage key without reading assets."""

    for item in resolution.items:
        for variant in item.thumbnail_variants:
            if variant.storage_key:
                return variant.storage_key
    return None


def rich_choice_search_placeholder(
    matched_kinds: tuple[str, ...],
) -> ApplicationText:
    """Return a concise search placeholder for one rich choice resolution."""

    if len(matched_kinds) == 1:
        return app_text("Search %1", beautify_label(matched_kinds[0]))
    return app_text("Search models")


def suggestion_context(
    *,
    model_kind: str,
    target_model: str,
) -> ModelSuggestionContext | None:
    """Resolve an explicit cube target into safe picker suggestion compatibility."""

    try:
        artifact_kind = ModelArtifactKind(model_kind)
    except ValueError:
        return None
    family = SUPPORTED_MODEL_FAMILIES.for_target_model(target_model)
    if family is None or family.primary_artifact_kind is not artifact_kind:
        return None
    return ModelSuggestionContext(artifact_kind, family.family_id)


__all__ = [
    "first_resolution_thumbnail_storage_key",
    "rich_choice_search_placeholder",
    "suggestion_context",
    "thumbnail_readiness_for_resolution",
]

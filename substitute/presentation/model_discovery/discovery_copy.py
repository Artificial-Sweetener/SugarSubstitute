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

"""Name model-discovery offers and explain their purpose in plain language."""

from __future__ import annotations

from substitute.domain.model_suggestions import ModelSuggestionContext
from sugarsubstitute_shared.localization import ApplicationMessage, app_text
from sugarsubstitute_shared.model_discovery import ModelArtifactKind


def discovery_copy(
    context: ModelSuggestionContext | None,
) -> tuple[ApplicationMessage, ApplicationMessage]:
    """Return the offer heading and one purpose statement for its model role."""

    if (
        context is not None
        and context.artifact_kind is ModelArtifactKind.UPSCALE_MODELS
    ):
        return (
            app_text("Download an upscaler model?"),
            app_text("Upscalers enlarge existing images and refine details."),
        )
    if context is not None and context.artifact_kind in {
        ModelArtifactKind.CHECKPOINTS,
        ModelArtifactKind.DIFFUSION_MODELS,
    }:
        return (
            app_text("Download an image model?"),
            app_text("Image models create new images from your prompts."),
        )
    return (
        app_text("Download a model?"),
        app_text("Models add new ways to create and edit images."),
    )


__all__ = ["discovery_copy"]

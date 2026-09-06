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

"""Own localized product copy for supported model families."""

from __future__ import annotations

from dataclasses import dataclass

from sugarsubstitute_shared.localization import ApplicationText, app_text

from substitute.domain.model_recommendations import ModelFamilyId


@dataclass(frozen=True, slots=True)
class ModelFamilyPresentation:
    """Describe localized family copy without using text as identity."""

    name: ApplicationText
    recommendation_name: ApplicationText
    description: ApplicationText


_PRESENTATIONS = {
    ModelFamilyId.SDXL: ModelFamilyPresentation(
        name=app_text("SDXL"),
        recommendation_name=app_text("Illustrious SDXL"),
        description=app_text(
            "A widely supported family with versatile realistic and illustrative fine-tunes."
        ),
    ),
    ModelFamilyId.ANIMA: ModelFamilyPresentation(
        name=app_text("Anima"),
        recommendation_name=app_text("Anima"),
        description=app_text(
            "A newer image model family with strong illustration and character-focused fine-tunes."
        ),
    ),
    ModelFamilyId.FLUX_2: ModelFamilyPresentation(
        name=app_text("FLUX.2"),
        recommendation_name=app_text("FLUX.2"),
        description=app_text(
            "A high-quality image model family suited to detailed prompt following."
        ),
    ),
}


def model_family_presentation(
    family_id: ModelFamilyId,
) -> ModelFamilyPresentation:
    """Return localized copy for one selectable supported family."""

    try:
        return _PRESENTATIONS[family_id]
    except KeyError as error:
        raise ValueError(
            f"No selectable presentation for model family: {family_id.value}"
        ) from error


__all__ = ["ModelFamilyPresentation", "model_family_presentation"]

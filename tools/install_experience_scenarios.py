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

"""Define the deterministic ComfyUI-setup qualification matrix."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from substitute.domain.model_recommendations import ModelFamilyId


@dataclass(frozen=True, slots=True)
class InstallExperienceScenario:
    """Describe one side-effect-free production onboarding journey."""

    slug: str
    target: Literal["managed", "attached", "remote"]
    existing_models: bool = False
    detected_families: tuple[ModelFamilyId, ...] = ()
    selected_families: tuple[ModelFamilyId, ...] = ()
    recommendation_failure: bool = False
    thumbnail_failure: bool = False
    background_finishes_after_choices: bool = False
    provisioning_failures: int = 0
    scan_failure: bool = False
    scan_unknown_count: int = 0


INSTALL_EXPERIENCE_SCENARIOS: tuple[InstallExperienceScenario, ...] = (
    InstallExperienceScenario(
        "managed-existing-sdxl",
        "managed",
        existing_models=True,
        detected_families=(ModelFamilyId.SDXL,),
        selected_families=(ModelFamilyId.ANIMA,),
    ),
    InstallExperienceScenario(
        "managed-existing-anima",
        "managed",
        existing_models=True,
        detected_families=(ModelFamilyId.ANIMA,),
        selected_families=(ModelFamilyId.SDXL,),
    ),
    InstallExperienceScenario(
        "managed-existing-mixed",
        "managed",
        existing_models=True,
        detected_families=(ModelFamilyId.SDXL, ModelFamilyId.ANIMA),
    ),
    InstallExperienceScenario(
        "managed-existing-unsupported",
        "managed",
        existing_models=True,
        scan_unknown_count=1,
        selected_families=(ModelFamilyId.SDXL, ModelFamilyId.ANIMA),
    ),
    InstallExperienceScenario(
        "managed-scan-unavailable",
        "managed",
        existing_models=True,
        scan_failure=True,
    ),
    InstallExperienceScenario("managed-decline-model", "managed"),
    InstallExperienceScenario(
        "managed-sdxl",
        "managed",
        selected_families=(ModelFamilyId.SDXL,),
    ),
    InstallExperienceScenario(
        "managed-anima",
        "managed",
        selected_families=(ModelFamilyId.ANIMA,),
    ),
    InstallExperienceScenario(
        "managed-sdxl-and-anima",
        "managed",
        selected_families=(ModelFamilyId.SDXL, ModelFamilyId.ANIMA),
        background_finishes_after_choices=True,
    ),
    InstallExperienceScenario(
        "managed-model-download-retry",
        "managed",
        selected_families=(ModelFamilyId.SDXL,),
        provisioning_failures=1,
    ),
    InstallExperienceScenario(
        "managed-civitai-unavailable",
        "managed",
        selected_families=(ModelFamilyId.SDXL,),
        recommendation_failure=True,
    ),
    InstallExperienceScenario(
        "managed-thumbnail-unavailable",
        "managed",
        selected_families=(ModelFamilyId.ANIMA,),
        thumbnail_failure=True,
    ),
    InstallExperienceScenario("attached-decline-model", "attached"),
    InstallExperienceScenario("remote-no-local-models", "remote"),
)


__all__ = ["INSTALL_EXPERIENCE_SCENARIOS", "InstallExperienceScenario"]

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

"""Expose model recommendation application services."""

from substitute.application.model_recommendations.family_scanner import (
    ExistingModelFamilyScanner,
    ModelScanCancellation,
)
from substitute.application.model_recommendations.family_presentation import (
    ModelFamilyPresentation,
    model_family_presentation,
)
from substitute.application.model_recommendations.onboarding_service import (
    FamilyRecommendationPage,
    ModelOnboardingApplicationService,
    RecommendationCardAsset,
    RecommendationLinkResult,
    RecommendationLinkStatus,
)
from substitute.application.model_recommendations.install_service import (
    ModelInstallRecipePlanner,
    ModelInstallService,
)

__all__ = [
    "ExistingModelFamilyScanner",
    "FamilyRecommendationPage",
    "ModelFamilyPresentation",
    "ModelScanCancellation",
    "ModelOnboardingApplicationService",
    "ModelInstallRecipePlanner",
    "ModelInstallService",
    "RecommendationCardAsset",
    "RecommendationLinkResult",
    "RecommendationLinkStatus",
    "model_family_presentation",
]

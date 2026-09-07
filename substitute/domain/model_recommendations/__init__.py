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

"""Expose model-family recommendation domain values."""

from substitute.domain.model_recommendations.catalog import (
    SUPPORTED_MODEL_FAMILIES,
    SupportedModelFamilyCatalog,
)
from substitute.domain.model_recommendations.install_models import (
    ModelInstallFile,
    ModelInstallPlan,
    ModelInstallProgress,
)
from substitute.domain.model_recommendations.models import (
    CivitaiFamilyMapping,
    FamilyDetectionPolicy,
    ModelFamilyDefinition,
    ModelFamilyId,
    ModelRecommendation,
    ModelRecommendationQuery,
    ModelStylePreference,
    TensorShapeSignature,
)
from substitute.domain.model_recommendations.scan_models import (
    DetectedModelFamily,
    ModelFamilyConfidence,
    ModelFamilyEvidenceKind,
    ModelFamilyScanResult,
    ModelFamilyScanStatus,
)

__all__ = [
    "CivitaiFamilyMapping",
    "DetectedModelFamily",
    "FamilyDetectionPolicy",
    "ModelFamilyConfidence",
    "ModelFamilyDefinition",
    "ModelFamilyEvidenceKind",
    "ModelFamilyId",
    "ModelFamilyScanResult",
    "ModelFamilyScanStatus",
    "ModelInstallFile",
    "ModelInstallPlan",
    "ModelInstallProgress",
    "ModelRecommendation",
    "ModelRecommendationQuery",
    "ModelStylePreference",
    "TensorShapeSignature",
    "SUPPORTED_MODEL_FAMILIES",
    "SupportedModelFamilyCatalog",
]

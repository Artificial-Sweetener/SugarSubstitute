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

"""Define safe local model-family scan evidence and outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from substitute.domain.model_recommendations.models import ModelFamilyId


class ModelFamilyEvidenceKind(str, Enum):
    """Identify the trusted source of one family classification."""

    SAFETENSOR_METADATA = "safetensor_metadata"
    TENSOR_SIGNATURE = "tensor_signature"


class ModelFamilyConfidence(str, Enum):
    """Describe whether local evidence is strong enough to affect onboarding."""

    CONFIDENT = "confident"
    UNKNOWN = "unknown"


class ModelFamilyScanStatus(str, Enum):
    """Describe whether a bounded local scan reached a reliable conclusion."""

    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class DetectedModelFamily:
    """Record one confidently identified local model family and its evidence."""

    family_id: ModelFamilyId
    path: Path
    evidence_kind: ModelFamilyEvidenceKind
    confidence: ModelFamilyConfidence = ModelFamilyConfidence.CONFIDENT


@dataclass(frozen=True, slots=True)
class ModelFamilyScanResult:
    """Summarize a read-only bounded scan without exposing file contents."""

    root: Path
    status: ModelFamilyScanStatus
    detected: tuple[DetectedModelFamily, ...]
    inspected_count: int
    unreadable_count: int
    unknown_count: int
    diagnostic: str | None = None

    @property
    def detected_families(self) -> frozenset[ModelFamilyId]:
        """Return unique confidently detected family identities."""

        return frozenset(item.family_id for item in self.detected)

    @property
    def confidently_empty(self) -> bool:
        """Return whether a complete scan found no supported family."""

        return (
            self.status is ModelFamilyScanStatus.COMPLETED
            and not self.detected_families
        )


__all__ = [
    "DetectedModelFamily",
    "ModelFamilyConfidence",
    "ModelFamilyEvidenceKind",
    "ModelFamilyScanResult",
    "ModelFamilyScanStatus",
]

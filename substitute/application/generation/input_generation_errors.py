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

"""Define application errors raised while capturing Input generation content."""

from __future__ import annotations

from enum import StrEnum


class InputGenerationPreparationFailureKind(StrEnum):
    """Identify the generation-preparation boundary that failed."""

    REGIONAL_MASK_ASSOCIATION = "regional_mask_association"
    CANVAS_SURFACE_AUTHORITY = "canvas_surface_authority"
    WORKFLOW_IDENTITY = "workflow_identity"
    DOCUMENT_CAPTURE = "document_capture"
    IMAGE_MATERIALIZATION = "image_materialization"
    MASK_MATERIALIZATION = "mask_materialization"


class InputGenerationPreparationError(RuntimeError):
    """Report a typed Input generation-preparation failure to shell preflight."""

    def __init__(self, kind: InputGenerationPreparationFailureKind) -> None:
        """Store the failed preparation boundary for diagnostics and chaining."""

        super().__init__(kind.value)
        self.kind = kind


__all__ = [
    "InputGenerationPreparationError",
    "InputGenerationPreparationFailureKind",
]

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

"""Expose direct Comfy workflow application services."""

from .execution_projection import (
    DirectWorkflowExecutionProjection,
    DirectWorkflowExecutionProjector,
    RecoveryOutputIdentity,
)
from .generation_plan_service import DirectWorkflowGenerationPlanService
from .prompt_field_overlay import DirectWorkflowPromptFieldOverlayService
from .prompt_scene_projection import (
    DirectWorkflowPromptProjector,
    DirectWorkflowPromptView,
)
from .scene_preparation_service import (
    DirectScenePreparationResult,
    DirectWorkflowScenePreparationService,
)
from .load_service import DirectWorkflowLoadService, DirectWorkflowRepository

__all__ = [
    "DirectWorkflowExecutionProjection",
    "DirectWorkflowExecutionProjector",
    "DirectWorkflowGenerationPlanService",
    "DirectWorkflowPromptFieldOverlayService",
    "DirectWorkflowPromptProjector",
    "DirectWorkflowPromptView",
    "DirectScenePreparationResult",
    "DirectWorkflowScenePreparationService",
    "DirectWorkflowLoadService",
    "DirectWorkflowRepository",
    "RecoveryOutputIdentity",
]

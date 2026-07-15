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

"""Track deterministic Comfy workflow progress from node events."""

from __future__ import annotations

from substitute.application.generation.progress_estimation.node_classifier import (
    NodeCategory,
    classify_node,
)
from substitute.application.generation.progress_estimation.workflow_progress_tracker import (
    ComfyWorkflowProgressTracker,
)
from substitute.application.generation.progress_estimation.progress_state_application import (
    ProgressStateEntry,
    ProgressStateName,
    apply_progress_states_to_tracker,
)

__all__ = [
    "ComfyWorkflowProgressTracker",
    "NodeCategory",
    "ProgressStateEntry",
    "ProgressStateName",
    "apply_progress_states_to_tracker",
    "classify_node",
]

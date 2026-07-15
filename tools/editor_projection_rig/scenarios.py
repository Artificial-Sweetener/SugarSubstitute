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

"""Define required workflow scenarios for editor projection capture and replay."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkflowScenario:
    """Describe one required workflow fixture scenario."""

    workflow_id: str
    requested_cube_labels: tuple[str, ...]


WORKFLOW_SDXL_BASELINE = WorkflowScenario(
    workflow_id="workflow_sdxl_baseline",
    requested_cube_labels=(
        "sdxl/text to image",
        "sdxl/diffusion upscale",
        "sdxl/automask detailer",
    ),
)
WORKFLOW_ANIMA_BASELINE = WorkflowScenario(
    workflow_id="workflow_anima_baseline",
    requested_cube_labels=(
        "anima/text to image",
        "anima/diffusion upscale",
        "anima/promptmask detailer",
    ),
)
SCENARIOS: dict[str, WorkflowScenario] = {
    WORKFLOW_SDXL_BASELINE.workflow_id: WORKFLOW_SDXL_BASELINE,
    WORKFLOW_ANIMA_BASELINE.workflow_id: WORKFLOW_ANIMA_BASELINE,
}


def resolve_scenarios(name: str) -> tuple[WorkflowScenario, ...]:
    """Return scenarios selected by a command-line scenario name."""

    normalized = name.casefold()
    if normalized == "both":
        return (WORKFLOW_SDXL_BASELINE, WORKFLOW_ANIMA_BASELINE)
    if normalized in {"sdxl", WORKFLOW_SDXL_BASELINE.workflow_id.casefold()}:
        return (WORKFLOW_SDXL_BASELINE,)
    if normalized in {"anima", WORKFLOW_ANIMA_BASELINE.workflow_id.casefold()}:
        return (WORKFLOW_ANIMA_BASELINE,)
    if normalized == "alternating":
        return (WORKFLOW_SDXL_BASELINE, WORKFLOW_ANIMA_BASELINE)
    message = f"Unknown scenario {name!r}."
    raise ValueError(message)

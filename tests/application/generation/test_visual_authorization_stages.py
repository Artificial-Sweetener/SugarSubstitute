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

"""Verify visual authorization across sequential prompts in one user run."""

from substitute.application.generation.visual_authorization import (
    VisualAuthorizationService,
)
from substitute.application.ports.comfy_gateway import GenerationVisualIdentity


def _identity(prompt_id: str, *, client_id: str = "client") -> GenerationVisualIdentity:
    """Describe a visual from one prompt in the staged run."""

    return GenerationVisualIdentity(
        workflow_id="workflow",
        generation_run_id="run",
        prompt_id=prompt_id,
        client_id=client_id,
        source_key="source",
        source_label="Output",
    )


def test_previous_stage_final_remains_authorized_after_next_stage_starts() -> None:
    """Keep earlier final outputs while limiting previews to the active prompt."""

    authorization = VisualAuthorizationService()
    authorization.register_run(
        workflow_id="workflow",
        generation_run_id="run",
        prompt_id="image",
        client_id="client",
    )
    authorization.register_run(
        workflow_id="workflow",
        generation_run_id="run",
        prompt_id="video",
        client_id="client",
    )

    assert authorization.authorize_final_output(_identity("image"))
    assert authorization.authorize_final_output(_identity("video"))
    assert not authorization.authorize_preview(_identity("image"))
    assert authorization.authorize_preview(_identity("video"))
    assert not authorization.authorize_final_output(_identity("unknown"))
    assert not authorization.authorize_final_output(
        _identity("image", client_id="other")
    )


def test_completed_staged_run_retains_both_final_prompts() -> None:
    """Final output callbacks can arrive after the last prompt completes."""

    authorization = VisualAuthorizationService()
    for prompt_id in ("image", "video"):
        authorization.register_run(
            workflow_id="workflow",
            generation_run_id="run",
            prompt_id=prompt_id,
            client_id="client",
        )
    authorization.complete_run(
        workflow_id="workflow", generation_run_id="run", prompt_id="video"
    )

    assert authorization.authorize_final_output(_identity("image"))
    assert authorization.authorize_final_output(_identity("video"))
    assert not authorization.authorize_preview(_identity("video"))
    authorization.fail_run(workflow_id="workflow", generation_run_id="run")
    assert not authorization.authorize_final_output(_identity("image"))
    assert not authorization.authorize_final_output(_identity("video"))

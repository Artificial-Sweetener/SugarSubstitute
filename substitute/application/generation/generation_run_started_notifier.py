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

"""Publish prompt-bound generation identity before visual events can arrive."""

from __future__ import annotations

from collections.abc import Callable

from substitute.application.generation.generation_models import GenerationRunStarted
from substitute.application.ports.comfy_gateway import QueueVisualRunContext
from substitute.domain.common import WorkflowId


def notify_generation_run_started(
    callback: Callable[[GenerationRunStarted], None] | None,
    *,
    workflow_id: WorkflowId,
    generation_run_id: str,
    output_session_id: str,
    prompt_id: str,
    client_id: str,
    visual_context: QueueVisualRunContext,
) -> None:
    """Publish the run and its complete set of authorized preview placeholders."""

    if callback is None:
        return
    callback(
        GenerationRunStarted(
            workflow_id=workflow_id,
            generation_run_id=generation_run_id,
            output_session_id=output_session_id,
            prompt_id=prompt_id,
            client_id=client_id,
            preview_source_keys=frozenset(
                source_key
                for source in visual_context.sources.values()
                if (source_key := source.get("sourceKey"))
            ),
        )
    )


__all__ = ["notify_generation_run_started"]

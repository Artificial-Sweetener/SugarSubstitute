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

"""Route Substitute model-load progress events without listener side effects."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from substitute.application.ports.comfy_gateway import ModelLoadProgressUpdate
from substitute.domain.common import WorkflowId
from substitute.infrastructure.comfy.comfy_progress_event_parser import (
    ModelLoadSourceMetadataResolver,
    parse_model_load_progress,
)


@dataclass(frozen=True)
class ModelLoadProgressRouteResult:
    """Describe the listener action selected for one model-load event."""

    handled: bool
    emitted: bool = False


def route_model_load_progress_event(
    message_type: object,
    data: Mapping[str, object],
    *,
    workflow_id: WorkflowId,
    active_prompt_id: str,
    all_node_ids: set[str],
    source_metadata_resolver: ModelLoadSourceMetadataResolver,
    on_model_load_progress: Callable[[ModelLoadProgressUpdate], None],
) -> ModelLoadProgressRouteResult:
    """Parse and dispatch model-load progress for matching event payloads."""

    if message_type != "substitute_model_load_progress":
        return ModelLoadProgressRouteResult(handled=False)

    model_load_progress = parse_model_load_progress(
        data=data,
        workflow_id=workflow_id,
        active_prompt_id=active_prompt_id,
        all_node_ids=all_node_ids,
        source_metadata_resolver=source_metadata_resolver,
    )
    if model_load_progress is None:
        return ModelLoadProgressRouteResult(handled=True)

    on_model_load_progress(model_load_progress)
    return ModelLoadProgressRouteResult(handled=True, emitted=True)


__all__ = [
    "ModelLoadProgressRouteResult",
    "route_model_load_progress_event",
]

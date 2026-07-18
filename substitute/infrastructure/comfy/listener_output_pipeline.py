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

"""Build listener-scoped final-output routing and persistence collaborators."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from substitute.application.ports.comfy_gateway import (
    ListenerCallbacks,
    ListenerStartRequest,
    OutputSavePlan,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.artifact_fetcher import ComfyArtifactFetcher
from substitute.infrastructure.comfy.cube_output_event import SubstituteVisualIdentity
from substitute.infrastructure.comfy.cube_output_event_handler import (
    CubeOutputEventHandler,
)
from substitute.infrastructure.comfy.cube_output_event_router import (
    CubeOutputDiagnostic,
    CubeOutputRouteContext,
)
from substitute.infrastructure.comfy.listener_output_source_resolver import (
    ListenerOutputSourceResolver,
)
from substitute.infrastructure.comfy.listener_visual_event_guard import (
    ListenerVisualEventGuard,
)
from substitute.infrastructure.comfy.output_source_identity_resolver import (
    OutputSourceDiagnostic,
    collect_cube_output_node_ids,
    output_cube_numbers_by_alias,
)
from substitute.infrastructure.comfy.output_image_persistence import (
    OutputImagePersistence,
)
from substitute.infrastructure.comfy.final_image_event import FinalImageScene
from substitute.infrastructure.comfy.final_image_event_handler import (
    FinalImageEventHandler,
)
from substitute.infrastructure.comfy.standard_executed_image_handler import (
    StandardExecutedImageContext,
    StandardExecutedImageHandler,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.comfy.listener_output_pipeline")


@dataclass(frozen=True)
class ListenerOutputPipeline:
    """Carry final-output collaborators for one listener run."""

    cube_output_node_ids: set[str]
    output_source_resolver: ListenerOutputSourceResolver
    cube_output_handler: CubeOutputEventHandler
    standard_output_handler: StandardExecutedImageHandler


def build_listener_output_pipeline(
    *,
    request: ListenerStartRequest,
    endpoint: ComfyEndpoint,
    callbacks: ListenerCallbacks,
    visual_event_guard: ListenerVisualEventGuard,
    on_output_source_diagnostic: Callable[[OutputSourceDiagnostic], None],
    on_cube_output_diagnostic: Callable[[CubeOutputDiagnostic], None],
    job_started_at: Callable[[], datetime] | None = None,
) -> ListenerOutputPipeline:
    """Build listener final-output source, fetch, persistence, and callback owners."""

    cube_output_node_ids = collect_cube_output_node_ids(request.workflow_payload)
    if not cube_output_node_ids:
        log_warning(
            _LOGGER,
            "No SugarCubes.CubeOutput nodes found in queued workflow payload",
            workflow_id=request.workflow_id,
            generation_run_id=request.generation_run_id,
            prompt_id=request.prompt_id,
        )
    output_source_resolver = ListenerOutputSourceResolver(
        workflow_id=request.workflow_id,
        prompt_id=request.prompt_id,
        workflow_payload=request.workflow_payload,
        cube_output_node_ids=cube_output_node_ids,
        on_diagnostic=on_output_source_diagnostic,
    )
    artifact_fetcher = ComfyArtifactFetcher(endpoint=endpoint)
    output_save_plan = _output_save_plan(
        request=request,
        job_started_at=job_started_at,
    )
    cube_numbers_by_alias = output_cube_numbers_by_alias(request.workflow_payload)
    cube_numbers_by_alias.update(output_save_plan.cube_numbers_by_alias)
    output_persistence = OutputImagePersistence(
        output_save_plan=output_save_plan,
        workflow_payload=request.workflow_payload,
        sugar_script=request.sugar_script,
        cube_numbers_by_alias=cube_numbers_by_alias,
    )
    final_image_handler = FinalImageEventHandler(
        artifact_fetcher=artifact_fetcher,
        output_persistence=output_persistence,
        on_output_image=callbacks.on_output_image,
    )
    cube_output_handler = CubeOutputEventHandler(
        context=CubeOutputRouteContext(
            workflow_id=request.workflow_id,
            generation_run_id=request.generation_run_id,
            prompt_id=request.prompt_id,
        ),
        workflow_payload=request.workflow_payload,
        final_image_handler=final_image_handler,
        identity_acceptor=lambda identity, prompt_id, node_id: _accept_final_output(
            visual_event_guard=visual_event_guard,
            identity=identity,
            prompt_id=prompt_id,
            node_id=node_id,
        ),
        on_diagnostic=on_cube_output_diagnostic,
    )
    standard_output_handler = StandardExecutedImageHandler(
        context=StandardExecutedImageContext(
            workflow_id=request.workflow_id,
            generation_run_id=request.generation_run_id,
            prompt_id=request.prompt_id,
            client_id=request.client_id,
            workflow_payload=request.workflow_payload,
            scene=FinalImageScene(
                run_id=request.scene_run_id,
                key=request.scene_key,
                title=request.scene_title,
                order=request.scene_order,
                count=request.scene_count,
            ),
        ),
        sources_by_node={
            source.node_id: source for source in request.standard_output_sources
        },
        final_image_handler=final_image_handler,
    )
    return ListenerOutputPipeline(
        cube_output_node_ids=cube_output_node_ids,
        output_source_resolver=output_source_resolver,
        cube_output_handler=cube_output_handler,
        standard_output_handler=standard_output_handler,
    )


def _output_save_plan(
    *,
    request: ListenerStartRequest,
    job_started_at: Callable[[], datetime] | None,
) -> OutputSavePlan:
    """Return the explicit or listener-default output save plan."""

    if request.output_save_plan is not None:
        return request.output_save_plan
    started_at = job_started_at() if job_started_at is not None else datetime.now()
    return OutputSavePlan(
        output_root=request.output_dir,
        path_pattern="{date}\\{run}_{cube#}_{workflow}_{source}",
        workflow_name=request.workflow_name,
        output_run_number=request.output_run_number,
        job_started_at=started_at.astimezone(),
    )


def _accept_final_output(
    *,
    visual_event_guard: ListenerVisualEventGuard,
    identity: SubstituteVisualIdentity | None,
    prompt_id: str | None,
    node_id: str | None,
) -> bool:
    """Return whether one final-output visual identity belongs to this listener."""

    return visual_event_guard.accepts(
        identity,
        prompt_id=prompt_id,
        event_type="final_output",
        node_id=node_id,
    )


__all__ = [
    "ListenerOutputPipeline",
    "build_listener_output_pipeline",
]

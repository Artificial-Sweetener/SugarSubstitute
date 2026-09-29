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

"""Defer Comfy transport construction until the first gateway operation."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from substitute.domain.onboarding import ComfyEndpoint

if TYPE_CHECKING:
    from substitute.application.ports.comfy_gateway import (
        ComfyGateway,
        ComfyQueueMutationResult,
        ComfyQueueSnapshot,
        InterruptResult,
        ListenerCallbacks,
        ListenerSessionHandle,
        ListenerSessionConnectRequest,
        ListenerSessionConnectResult,
        ListenerStartRequest,
        ListenerStartResult,
        QueuePromptResult,
        QueueVisualRunContext,
    )


class LazyComfyGateway:
    """Construct the concrete transport gateway only when generation uses it."""

    def __init__(
        self,
        endpoint: ComfyEndpoint,
        *,
        listener_task_factory: Callable[..., object] | None = None,
        listener_preview_image_decoder: Callable[[bytes], object] | None = None,
    ) -> None:
        """Store transport dependencies without importing the concrete adapter."""

        self._endpoint = endpoint
        self._listener_task_factory = listener_task_factory
        self._listener_preview_image_decoder = listener_preview_image_decoder
        self._gateway: ComfyGateway | None = None

    def connect_listener_session(
        self, request: ListenerSessionConnectRequest
    ) -> ListenerSessionConnectResult:
        """Open a listener session through the concrete gateway on first use."""

        return self._resolve().connect_listener_session(request)

    def queue_prompt(
        self,
        workflow_payload: dict[str, object],
        *,
        client_id: str,
        execution_targets: tuple[str, ...] | None = None,
        preview_method: str | None = None,
        sugar_script: str | None = None,
        visual_context: QueueVisualRunContext | None = None,
    ) -> QueuePromptResult:
        """Queue one ordinary workflow through the concrete gateway."""

        return self._resolve().queue_prompt(
            workflow_payload,
            client_id=client_id,
            execution_targets=execution_targets,
            preview_method=preview_method,
            sugar_script=sugar_script,
            visual_context=visual_context,
        )

    def queue_cube_workflow(
        self,
        workflow: dict[str, object],
        *,
        client_id: str,
        preview_method: str | None = None,
        visual_context: QueueVisualRunContext,
        persistence_sugar_script: str | None = None,
        execution_targets: tuple[str, ...] | None = None,
    ) -> QueuePromptResult:
        """Queue a canonical Cube stage through SugarCubes on first use."""

        return self._resolve().queue_cube_workflow(
            workflow,
            client_id=client_id,
            preview_method=preview_method,
            visual_context=visual_context,
            persistence_sugar_script=persistence_sugar_script,
            execution_targets=execution_targets,
        )

    def start_listener(
        self, request: ListenerStartRequest, callbacks: ListenerCallbacks
    ) -> ListenerStartResult:
        """Start a generation listener through the concrete gateway."""

        return self._resolve().start_listener(request, callbacks)

    def interrupt(self) -> InterruptResult:
        """Interrupt active generation through the concrete gateway."""

        return self._resolve().interrupt()

    def get_queue(self) -> ComfyQueueSnapshot:
        """Load the Comfy queue snapshot through the concrete gateway."""

        return self._resolve().get_queue()

    def delete_pending_prompt(self, prompt_id: str) -> ComfyQueueMutationResult:
        """Delete one queued prompt through the concrete gateway."""

        return self._resolve().delete_pending_prompt(prompt_id)

    def close_listener_session(self, handle: ListenerSessionHandle) -> None:
        """Close a preconnected listener session through the concrete gateway."""

        self._resolve().close_listener_session(handle)

    def _resolve(self) -> ComfyGateway:
        """Build and cache the concrete Comfy gateway implementation."""

        if self._gateway is None:
            from substitute.infrastructure.comfy.gateway_adapter import (
                InfrastructureComfyGatewayAdapter,
            )
            from substitute.infrastructure.comfy.native_cube_execution_client import (
                NativeCubeExecutionClient,
            )
            from substitute.infrastructure.comfy.prompt_gateway import (
                ComfyPromptGateway,
            )

            self._gateway = InfrastructureComfyGatewayAdapter(
                gateway=ComfyPromptGateway(
                    endpoint=self._endpoint,
                    listener_task_factory=self._listener_task_factory,
                    listener_preview_image_decoder=self._listener_preview_image_decoder,
                ),
                native_cube_client=NativeCubeExecutionClient(endpoint=self._endpoint),
            )
        return self._gateway


__all__ = ["LazyComfyGateway"]

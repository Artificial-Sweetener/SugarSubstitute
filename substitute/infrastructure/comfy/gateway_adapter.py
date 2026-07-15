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

"""Map infrastructure Comfy transport DTOs to application port contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from substitute.application.ports.comfy_gateway import (
    ComfyGateway,
    ComfyQueueMutationResult,
    ComfyQueueSnapshot,
    InterruptResult,
    ListenerCallbacks,
    ListenerHandle,
    ListenerSessionConnectRequest,
    ListenerSessionConnectResult,
    ListenerSessionHandle,
    ListenerStartRequest,
    ListenerStartResult,
    QueueVisualRunContext,
    QueuePromptResult,
)
from substitute.infrastructure.comfy.prompt_gateway import (
    ComfyQueueMutationResult as InfraComfyQueueMutationResult,
    ComfyQueueSnapshot as InfraComfyQueueSnapshot,
    InterruptResult as InfraInterruptResult,
    ListenerSessionConnectRequest as InfraListenerSessionConnectRequest,
    ListenerSessionConnectResult as InfraListenerSessionConnectResult,
    ListenerStartResult as InfraListenerStartResult,
    QueuePromptResult as InfraQueuePromptResult,
)


class InfrastructureGateway(Protocol):
    """Define infrastructure gateway methods consumed by the transport adapter."""

    def queue_prompt(
        self,
        workflow_payload: dict[str, object],
        *,
        client_id: str,
        preview_method: str | None = None,
        sugar_script: str | None = None,
        visual_context: QueueVisualRunContext | None = None,
    ) -> InfraQueuePromptResult:
        """Queue prompt payload through infrastructure transport."""

    def connect_listener_session(
        self,
        request: InfraListenerSessionConnectRequest,
    ) -> InfraListenerSessionConnectResult:
        """Open a pre-queue infrastructure listener websocket session."""

    def start_listener(
        self,
        request: ListenerStartRequest,
        callbacks: ListenerCallbacks,
    ) -> InfraListenerStartResult:
        """Start infrastructure websocket listener with infrastructure DTOs."""

    def interrupt(self) -> InfraInterruptResult:
        """Interrupt infrastructure transport execution."""

    def get_queue(self) -> InfraComfyQueueSnapshot:
        """Return infrastructure Comfy queue snapshot."""

    def delete_pending_prompt(self, prompt_id: str) -> InfraComfyQueueMutationResult:
        """Delete one pending Comfy prompt through infrastructure transport."""

    def close_listener_session(self, handle: ListenerSessionHandle) -> None:
        """Close an infrastructure listener websocket session."""


@dataclass
class InfrastructureComfyGatewayAdapter(ComfyGateway):
    """Bridge infrastructure transport payloads to application-facing DTOs."""

    gateway: InfrastructureGateway

    def queue_prompt(
        self,
        workflow_payload: dict[str, object],
        *,
        client_id: str,
        preview_method: str | None = None,
        sugar_script: str | None = None,
        visual_context: QueueVisualRunContext | None = None,
    ) -> QueuePromptResult:
        """Queue workflow payload through infrastructure and normalize result DTO."""

        result: InfraQueuePromptResult = self.gateway.queue_prompt(
            workflow_payload,
            client_id=client_id,
            preview_method=preview_method,
            sugar_script=sugar_script,
            visual_context=visual_context,
        )
        return QueuePromptResult(
            status=result.status,
            prompt_id=result.prompt_id,
            payload=result.payload,
            error=result.error,
            error_report=result.error_report,
        )

    def connect_listener_session(
        self,
        request: ListenerSessionConnectRequest,
    ) -> ListenerSessionConnectResult:
        """Open a pre-queue listener session through infrastructure transport."""

        infra_result = self.gateway.connect_listener_session(
            request=InfraListenerSessionConnectRequest(
                workflow_id=request.workflow_id,
                generation_run_id=request.generation_run_id,
                client_id=request.client_id,
            )
        )
        handle = getattr(infra_result, "handle", None)
        if not bool(getattr(infra_result, "connected", False)) or handle is None:
            return ListenerSessionConnectResult(
                connected=False,
                handle=None,
                error=getattr(infra_result, "error", None),
            )
        return ListenerSessionConnectResult(
            connected=True,
            handle=handle,
            error=None,
        )

    def start_listener(
        self,
        request: ListenerStartRequest,
        callbacks: ListenerCallbacks,
    ) -> ListenerStartResult:
        """Start infrastructure websocket listener and map callback payload DTOs."""

        infra_callbacks = ListenerCallbacks(
            on_progress=callbacks.on_progress,
            on_model_load_progress=callbacks.on_model_load_progress,
            on_preview=callbacks.on_preview,
            on_output_image=callbacks.on_output_image,
            on_timing=callbacks.on_timing,
            on_failed=callbacks.on_failed,
            on_completed=callbacks.on_completed,
        )
        infra_result: InfraListenerStartResult = self.gateway.start_listener(
            request=request,
            callbacks=infra_callbacks,
        )
        if not infra_result.started or infra_result.handle is None:
            return ListenerStartResult(
                started=False,
                handle=None,
                error=infra_result.error,
            )
        return ListenerStartResult(
            started=True,
            handle=ListenerHandle(
                prompt_id=infra_result.handle.prompt_id,
                generation_run_id=infra_result.handle.generation_run_id,
                client_id=infra_result.handle.client_id,
                workflow_id=infra_result.handle.workflow_id,
                task=infra_result.handle.task,
            ),
            error=None,
        )

    def interrupt(self) -> InterruptResult:
        """Interrupt generation through infrastructure transport and map DTO."""

        result: InfraInterruptResult = self.gateway.interrupt()
        return InterruptResult(
            status=result.status,
            status_code=result.status_code,
            error=result.error,
        )

    def get_queue(self) -> ComfyQueueSnapshot:
        """Read Comfy queue state through infrastructure transport."""

        result: InfraComfyQueueSnapshot = self.gateway.get_queue()
        return ComfyQueueSnapshot(
            running_prompt_ids=result.running_prompt_ids,
            pending_prompt_ids=result.pending_prompt_ids,
        )

    def delete_pending_prompt(self, prompt_id: str) -> ComfyQueueMutationResult:
        """Delete one pending prompt through infrastructure transport."""

        result: InfraComfyQueueMutationResult = self.gateway.delete_pending_prompt(
            prompt_id
        )
        return ComfyQueueMutationResult(
            status=result.status,
            status_code=result.status_code,
            error=result.error,
        )

    def close_listener_session(self, handle: ListenerSessionHandle) -> None:
        """Close an unstarted infrastructure listener session."""

        self.gateway.close_listener_session(handle)


__all__ = ["InfrastructureComfyGatewayAdapter"]

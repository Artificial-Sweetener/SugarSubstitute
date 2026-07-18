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

"""Provide Comfy queue/listener/interrupt transport adapter implementations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from itertools import count
from typing import Any, Literal, cast

import requests

from substitute.application.execution import ExecutionContext, TaskIdentity
from substitute.application.errors import (
    ErrorReport,
    build_prompt_validation_error_report,
)
from substitute.application.ports.comfy_gateway import (
    ListenerCallbacks,
    ListenerSessionHandle,
    ListenerStartRequest,
    QueueVisualRunContext,
)
from substitute.infrastructure.comfy.websocket_transport import (
    PreconnectedComfyWebsocketSession,
)
from substitute.infrastructure.comfy.queue_payload import extract_prompt_ids
from substitute.infrastructure.comfy.websocket_listener import ComfyWebsocketListener
from substitute.infrastructure.execution.long_lived_task import LongLivedWork
from substitute.infrastructure.comfy.runtime_report_context import (
    fetch_runtime_report_context,
)
from substitute.domain.common import WorkflowId
from substitute.domain.onboarding import ComfyEndpoint
from substitute.shared.logging.logger import get_logger, log_exception, log_warning

_LOGGER = get_logger("infrastructure.comfy.prompt_gateway")
_LISTENER_REQUEST_IDS = count(1)

QueuePromptStatus = Literal["queued", "missing_prompt_id", "error"]
InterruptStatus = Literal["sent", "failed"]
ComfyQueueMutationStatus = Literal["deleted", "failed"]
ListenerTaskFactory = Callable[
    [TaskIdentity, ExecutionContext, LongLivedWork[None], str],
    object,
]


@dataclass(frozen=True)
class QueuePromptResult:
    """Capture raw queue prompt transport outcome."""

    status: QueuePromptStatus
    prompt_id: str | None
    payload: object | None
    error: str | None
    error_report: ErrorReport | None = None


@dataclass(frozen=True)
class InterruptResult:
    """Capture interrupt transport outcome."""

    status: InterruptStatus
    status_code: int | None
    error: str | None


@dataclass(frozen=True)
class ComfyQueueSnapshot:
    """Capture raw Comfy queue prompt identifiers."""

    running_prompt_ids: tuple[str, ...]
    pending_prompt_ids: tuple[str, ...]


@dataclass(frozen=True)
class ComfyQueueMutationResult:
    """Capture a Comfy queue mutation transport outcome."""

    status: ComfyQueueMutationStatus
    status_code: int | None
    error: str | None


@dataclass(frozen=True)
class ListenerHandle:
    """Describe listener task handle tracked by infrastructure gateway."""

    prompt_id: str
    generation_run_id: str
    client_id: str
    workflow_id: WorkflowId
    task: object


@dataclass(frozen=True)
class ListenerStartResult:
    """Capture listener startup outcome."""

    started: bool
    handle: ListenerHandle | None
    error: str | None


@dataclass(frozen=True)
class ListenerSessionConnectRequest:
    """Describe a run websocket that must be live before queueing."""

    workflow_id: WorkflowId
    generation_run_id: str
    client_id: str


@dataclass(frozen=True)
class ListenerSessionConnectResult:
    """Capture run websocket connection and feature negotiation outcome."""

    connected: bool
    handle: ListenerSessionHandle | None
    error: str | None


class ComfyPromptQueueError(RuntimeError):
    """Carry structured Comfy `/prompt` error responses through queue handling."""

    def __init__(
        self,
        message: str,
        *,
        payload: object | None,
        error_report: ErrorReport | None,
    ) -> None:
        """Store queue failure message, raw payload, and optional error report."""

        super().__init__(message)
        self.payload = payload
        self.error_report = error_report


@dataclass(frozen=True)
class ComfyPromptGateway:
    """Bridge generation services to Comfy transport endpoints."""

    endpoint: ComfyEndpoint = ComfyEndpoint(host="127.0.0.1", port=8188)
    listener_connect_timeout_seconds: float = 10.0
    listener_receive_timeout_seconds: float = 60.0
    interrupt_timeout_seconds: float = 10.0
    queue_timeout_seconds: float = 10.0
    listener_task_factory: ListenerTaskFactory | None = None
    listener_preview_image_decoder: Callable[[bytes], object] | None = None

    def connect_listener_session(
        self,
        request: ListenerSessionConnectRequest,
    ) -> ListenerSessionConnectResult:
        """Open and feature-negotiate a run websocket before queueing."""

        websocket_url = self.endpoint.websocket_url(request.client_id)
        try:
            session = PreconnectedComfyWebsocketSession.connect(
                client_id=request.client_id,
                websocket_url=websocket_url,
                connect_timeout_seconds=self.listener_connect_timeout_seconds,
            )
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to connect Comfy listener websocket",
                workflow_id=request.workflow_id,
                generation_run_id=request.generation_run_id,
                client_id=request.client_id,
                websocket_url=websocket_url,
                error=error,
            )
            return ListenerSessionConnectResult(
                connected=False,
                handle=None,
                error=str(error),
            )
        return ListenerSessionConnectResult(
            connected=True,
            handle=ListenerSessionHandle(
                workflow_id=request.workflow_id,
                generation_run_id=request.generation_run_id,
                client_id=request.client_id,
                session=session,
            ),
            error=None,
        )

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
        """Queue workflow payload in Comfy and normalize response shape."""
        try:
            payload = queue_prompt(
                workflow_payload,
                client_id=client_id,
                execution_targets=execution_targets,
                preview_method=preview_method,
                sugar_script=sugar_script,
                visual_context=visual_context,
                endpoint=self.endpoint,
                timeout_seconds=self.listener_connect_timeout_seconds,
            )
        except ComfyPromptQueueError as error:
            log_exception(
                _LOGGER,
                "Comfy rejected prompt",
                client_id=client_id,
                endpoint=self.endpoint.substitute_prompt_queue_url(),
                error=error,
            )
            return QueuePromptResult(
                status="error",
                prompt_id=None,
                payload=error.payload,
                error=str(error),
                error_report=error.error_report,
            )
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to queue prompt",
                client_id=client_id,
                endpoint=self.endpoint.substitute_prompt_queue_url(),
                error=error,
            )
            return QueuePromptResult(
                status="error",
                prompt_id=None,
                payload=None,
                error=str(error),
            )

        if isinstance(payload, dict):
            prompt_id = payload.get("prompt_id")
            if isinstance(prompt_id, str):
                return QueuePromptResult(
                    status="queued",
                    prompt_id=prompt_id,
                    payload=payload,
                    error=None,
                )

        if payload is not None:
            log_warning(
                _LOGGER,
                "Queue prompt returned payload without prompt_id",
                client_id=client_id,
                payload=payload,
            )
        return QueuePromptResult(
            status="missing_prompt_id",
            prompt_id=None,
            payload=payload,
            error=None,
        )

    def start_listener(
        self,
        request: ListenerStartRequest,
        callbacks: ListenerCallbacks,
    ) -> ListenerStartResult:
        """Start websocket listener work on the configured long-lived task runtime."""

        if self.listener_task_factory is None:
            return ListenerStartResult(
                started=False,
                handle=None,
                error="Listener execution runtime is not configured.",
            )
        try:
            listener = ComfyWebsocketListener(
                request=request,
                callbacks=callbacks,
                websocket_url=self.endpoint.websocket_url(request.client_id),
                endpoint=self.endpoint,
                preconnected_session=cast(
                    PreconnectedComfyWebsocketSession,
                    request.listener_session.session,
                ),
                connect_timeout_seconds=self.listener_connect_timeout_seconds,
                receive_timeout_seconds=self.listener_receive_timeout_seconds,
                preview_image_decoder=self.listener_preview_image_decoder,
            )
            task = self.listener_task_factory(
                TaskIdentity(
                    request_id=next(_LISTENER_REQUEST_IDS),
                    domain="generation_listener",
                    parts=(("workflow_id", request.workflow_id),),
                ),
                ExecutionContext(
                    operation="generation_listener",
                    reason="generation_run",
                    lane="generation_listener",
                    safe_fields=(
                        ("workflow_id", request.workflow_id),
                        ("client_id", request.client_id),
                    ),
                ),
                lambda _cancellation: _run_listener(listener),
                f"substitute-generation-listener-{request.client_id}",
            )
            return ListenerStartResult(
                started=True,
                handle=ListenerHandle(
                    prompt_id=request.prompt_id,
                    generation_run_id=request.generation_run_id,
                    client_id=request.client_id,
                    workflow_id=request.workflow_id,
                    task=task,
                ),
                error=None,
            )
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to start websocket listener",
                workflow_id=request.workflow_id,
                prompt_id=request.prompt_id,
                error=error,
            )
            return ListenerStartResult(
                started=False,
                handle=None,
                error=str(error),
            )

    def close_listener_session(self, handle: ListenerSessionHandle) -> None:
        """Close a connected listener session that cannot be consumed by a runnable."""

        session = handle.session
        close = getattr(session, "close", None)
        if callable(close):
            close()

    def interrupt(self) -> InterruptResult:
        """Send interrupt request to Comfy and return transport outcome."""
        try:
            response = requests.post(
                self.endpoint.interrupt_url(),
                timeout=self.interrupt_timeout_seconds,
            )
            if response.status_code == 200:
                return InterruptResult(
                    status="sent",
                    status_code=response.status_code,
                    error=None,
                )
            log_warning(
                _LOGGER,
                "Interrupt request returned non-success status",
                status_code=response.status_code,
            )
            return InterruptResult(
                status="failed",
                status_code=response.status_code,
                error=f"HTTP {response.status_code}",
            )
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to interrupt Comfy generation",
                error=error,
            )
            return InterruptResult(
                status="failed",
                status_code=None,
                error=str(error),
            )

    def get_queue(self) -> ComfyQueueSnapshot:
        """Read Comfy's running and pending queue prompt ids."""

        try:
            response = requests.get(
                self.endpoint.queue_url(),
                timeout=self.queue_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to read Comfy queue",
                endpoint=self.endpoint.queue_url(),
                error=error,
            )
            return ComfyQueueSnapshot(
                running_prompt_ids=(),
                pending_prompt_ids=(),
            )

        if not isinstance(payload, dict):
            log_warning(_LOGGER, "Comfy queue response was not an object")
            return ComfyQueueSnapshot(
                running_prompt_ids=(),
                pending_prompt_ids=(),
            )
        return ComfyQueueSnapshot(
            running_prompt_ids=extract_prompt_ids(payload.get("queue_running")),
            pending_prompt_ids=extract_prompt_ids(payload.get("queue_pending")),
        )

    def delete_pending_prompt(self, prompt_id: str) -> ComfyQueueMutationResult:
        """Delete one pending prompt from Comfy's queue."""

        try:
            response = requests.post(
                self.endpoint.queue_url(),
                json={"delete": [prompt_id]},
                timeout=self.queue_timeout_seconds,
            )
            if response.status_code == 200:
                return ComfyQueueMutationResult(
                    status="deleted",
                    status_code=response.status_code,
                    error=None,
                )
            log_warning(
                _LOGGER,
                "Comfy pending prompt delete returned non-success status",
                prompt_id=prompt_id,
                status_code=response.status_code,
            )
            return ComfyQueueMutationResult(
                status="failed",
                status_code=response.status_code,
                error=f"HTTP {response.status_code}",
            )
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to delete Comfy pending prompt",
                prompt_id=prompt_id,
                error=error,
            )
            return ComfyQueueMutationResult(
                status="failed",
                status_code=None,
                error=str(error),
            )


def _run_listener(listener: ComfyWebsocketListener) -> None:
    """Run one listener delegate as long-lived execution work."""

    listener.run()


def queue_prompt(
    workflow_payload: dict[str, object],
    *,
    client_id: str,
    execution_targets: tuple[str, ...] | None = None,
    preview_method: str | None = None,
    sugar_script: str | None = None,
    visual_context: QueueVisualRunContext | None = None,
    endpoint: ComfyEndpoint = ComfyEndpoint(host="127.0.0.1", port=8188),
    timeout_seconds: float = 10.0,
) -> object:
    """Queue one workflow payload against the supplied Comfy endpoint."""

    actual_prompt = workflow_payload.get("prompt")
    if not isinstance(actual_prompt, dict):
        actual_prompt = workflow_payload
    body: dict[str, object] = {
        "prompt": actual_prompt,
        "client_id": client_id,
    }
    if execution_targets is not None:
        body["partial_execution_targets"] = list(execution_targets)
    extra_data = _queue_extra_data(
        workflow_payload,
        preview_method=preview_method,
        sugar_script=sugar_script,
        visual_context=visual_context,
    )
    if extra_data:
        body["extra_data"] = extra_data
    _require_prompt_queue_facade(endpoint, timeout_seconds=min(timeout_seconds, 3.0))
    response = requests.post(
        endpoint.substitute_prompt_queue_url(),
        json=cast(Any, body),
        timeout=timeout_seconds,
    )
    status_code = getattr(response, "status_code", 200)
    if isinstance(status_code, int) and status_code >= 400:
        payload, raw_text = _response_error_payload(response)
        report = build_prompt_validation_error_report(
            payload,
            runtime=fetch_runtime_report_context(
                endpoint,
                timeout_seconds=min(timeout_seconds, 3.0),
            ),
            status_code=status_code,
            raw_response_text=raw_text,
            prompt_nodes=actual_prompt,
        )
        raise ComfyPromptQueueError(
            _prompt_queue_error_message(payload, status_code),
            payload=payload,
            error_report=report,
        )
    response.raise_for_status()
    return response.json()


def _require_prompt_queue_facade(
    endpoint: ComfyEndpoint,
    *,
    timeout_seconds: float,
) -> None:
    """Fail before queueing when Substitute BackEnd is missing the queue facade."""

    payload: object | None = None
    try:
        response = requests.get(
            endpoint.substitute_capabilities_url(),
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as error:
        raise ComfyPromptQueueError(
            "Substitute BackEnd prompt queue facade is unavailable.",
            payload=payload,
            error_report=None,
        ) from error
    if not _supports_prompt_queue_facade(payload):
        raise ComfyPromptQueueError(
            "Substitute BackEnd prompt queue facade is incompatible.",
            payload=payload,
            error_report=None,
        )


def _supports_prompt_queue_facade(payload: object) -> bool:
    """Return whether a capability payload supports the prompt queue contract."""

    if not isinstance(payload, dict):
        return False
    features = payload.get("features")
    if not isinstance(features, list) or "prompt-queue-facade" not in features:
        return False
    prompt_queue = payload.get("promptQueue")
    if not isinstance(prompt_queue, dict):
        return False
    visual_routing = payload.get("visualRouting")
    if not isinstance(visual_routing, dict):
        return False
    return (
        prompt_queue.get("schemaVersion") == 1
        and prompt_queue.get("queueRoute") == "/substitute/v1/prompt/queue"
        and visual_routing.get("schemaVersion") == 1
        and visual_routing.get("finalOutputIdentityRequired") is True
        and visual_routing.get("previewMetadataIdentitySupported") is True
        and visual_routing.get("previewMetadataKey") == "substitute"
    )


def _queue_extra_data(
    workflow_payload: dict[str, object],
    *,
    preview_method: str | None,
    sugar_script: str | None,
    visual_context: QueueVisualRunContext | None = None,
) -> dict[str, object]:
    """Build Comfy queue metadata without changing the executable prompt."""

    extra_data: dict[str, object] = {}
    if preview_method is not None:
        extra_data["preview_method"] = preview_method
    extra_pnginfo: dict[str, object] = {}
    workflow = workflow_payload.get("workflow")
    if isinstance(workflow, dict):
        extra_pnginfo["workflow"] = workflow
    if sugar_script is not None:
        extra_pnginfo["sugar_script"] = sugar_script
    if extra_pnginfo:
        extra_data["extra_pnginfo"] = extra_pnginfo
    if visual_context is not None:
        extra_data["substitute"] = visual_context.to_payload()
    return extra_data


def _response_error_payload(response: object) -> tuple[object | None, str | None]:
    """Return parsed JSON and raw text for a failed Comfy queue response."""

    raw_text = getattr(response, "text", None)
    if not isinstance(raw_text, str):
        raw_text = None
    response_json = getattr(response, "json", None)
    if not callable(response_json):
        return None, raw_text
    try:
        payload = response_json()
    except Exception:
        return None, raw_text
    return payload, raw_text


def _prompt_queue_error_message(payload: object | None, status_code: int) -> str:
    """Return a concise user-facing message for a failed prompt queue response."""

    if status_code == 404:
        return "Substitute BackEnd prompt queue facade is unavailable."
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, str) and error:
            return error
        if isinstance(error, dict):
            message = error.get("message")
            details = error.get("details")
            if isinstance(message, str) and isinstance(details, str) and details:
                return f"{message}: {details}"
            if isinstance(message, str) and message:
                return message
    return f"Comfy rejected prompt with HTTP {status_code}"


__all__ = [
    "ComfyPromptGateway",
    "ComfyPromptQueueError",
    "ComfyQueueMutationResult",
    "ComfyQueueMutationStatus",
    "ComfyQueueSnapshot",
    "InterruptResult",
    "InterruptStatus",
    "ListenerHandle",
    "ListenerSessionConnectRequest",
    "ListenerSessionConnectResult",
    "ListenerStartResult",
    "QueuePromptResult",
    "QueuePromptStatus",
    "queue_prompt",
]

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

"""Negotiate and dispatch canonical Cube workflows directly to SugarCubes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, cast

import requests

from substitute.application.cubes import cube_alias_body
from substitute.application.ports.comfy_gateway import (
    ListenerOutputSource,
    QueueVisualRunContext,
)
from substitute.domain.common import JsonObject
from substitute.domain.onboarding import ComfyEndpoint
from substitute.shared.logging.logger import get_logger, log_exception

_LOGGER = get_logger("infrastructure.comfy.native_cube_execution_client")


class HttpResponse(Protocol):
    """Describe the bounded requests response surface used by the client."""

    status_code: int

    def raise_for_status(self) -> None:
        """Raise when an HTTP response is unsuccessful."""

    def json(self) -> object:
        """Decode the response body."""


class HttpClient(Protocol):
    """Describe synchronous JSON transport for native execution."""

    def get(self, url: str, *, timeout: float) -> HttpResponse:
        """Read one JSON resource."""

    def post(self, url: str, *, json: object, timeout: float) -> HttpResponse:
        """Post one JSON resource."""


@dataclass(frozen=True)
class NativeCubeQueueResult:
    """Normalize native graph queue acceptance for generation orchestration."""

    prompt_id: str | None
    payload: object | None
    error: str | None
    output_sources: tuple[ListenerOutputSource, ...] = ()
    execution_sources: tuple[ListenerOutputSource, ...] = ()
    execution_prompt: JsonObject | None = None


@dataclass(frozen=True)
class NativeCubeExecutionClient:
    """Own SugarCubes native execution negotiation and HTTP transport."""

    endpoint: ComfyEndpoint
    timeout_seconds: float = 10.0
    http: HttpClient = cast(HttpClient, requests)

    def queue(
        self,
        *,
        workflow: JsonObject,
        client_id: str,
        visual_context: QueueVisualRunContext,
        preview_method: str | None = None,
        persistence_sugar_script: str | None = None,
    ) -> NativeCubeQueueResult:
        """Queue one canonical workflow only after exact capability negotiation."""

        try:
            backend_response = self.http.get(
                self.endpoint.substitute_capabilities_url(),
                timeout=min(self.timeout_seconds, 3.0),
            )
            backend_response.raise_for_status()
            backend_capabilities = backend_response.json()
            if not _supports_backend_context_bridge(backend_capabilities):
                return NativeCubeQueueResult(
                    prompt_id=None,
                    payload=backend_capabilities,
                    error="Substitute BackEnd native queue context bridge is incompatible.",
                )
            capabilities_response = self.http.get(
                self.endpoint.sugarcubes_execution_capabilities_url(),
                timeout=min(self.timeout_seconds, 3.0),
            )
            capabilities_response.raise_for_status()
            capabilities = capabilities_response.json()
            if not _supports_native_execution(capabilities):
                return NativeCubeQueueResult(
                    prompt_id=None,
                    payload=capabilities,
                    error="SugarCubes native execution contract is incompatible.",
                )
            response = self.http.post(
                self.endpoint.sugarcubes_execution_queue_url(),
                json=_queue_body(
                    workflow=workflow,
                    client_id=client_id,
                    visual_context=visual_context,
                    preview_method=preview_method,
                    persistence_sugar_script=persistence_sugar_script,
                ),
                timeout=self.timeout_seconds,
            )
            payload = response.json()
            if response.status_code >= 400:
                return NativeCubeQueueResult(
                    prompt_id=None,
                    payload=payload,
                    error=_error_message(payload, response.status_code),
                )
            response.raise_for_status()
            prompt_id = payload.get("prompt_id") if isinstance(payload, dict) else None
            if not isinstance(prompt_id, str) or not prompt_id:
                return NativeCubeQueueResult(
                    prompt_id=None,
                    payload=payload,
                    error="SugarCubes queue response did not include a prompt id.",
                )
            return NativeCubeQueueResult(
                prompt_id=prompt_id,
                payload=payload,
                error=None,
                output_sources=_output_sources(payload),
                execution_sources=_execution_sources(payload),
                execution_prompt=_execution_prompt(payload),
            )
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to queue native Cube workflow",
                client_id=client_id,
                error=error,
            )
            return NativeCubeQueueResult(prompt_id=None, payload=None, error=str(error))


def _supports_native_execution(value: object) -> bool:
    """Return whether SugarCubes exposes the complete supported execution contract."""

    if not isinstance(value, dict):
        return False
    return (
        value.get("available") is True
        and value.get("schema_version") == 1
        and value.get("workflow_schema_version") == 1
        and value.get("report_schema_version") == 1
        and value.get("queue_observer_api_version") == 1
        and value.get("queue_route") == "/sugarcubes/v2/executions/queue"
        and value.get("execution_owner") == "sugarcubes"
        and value.get("atomic_queueing") is True
        and value.get("cube_scoped_optimization") is True
        and value.get("validated_queue_observers") is True
    )


def _supports_backend_context_bridge(value: object) -> bool:
    """Return whether BackEnd can atomically retain native output context."""

    if not isinstance(value, dict):
        return False
    features = value.get("features")
    bridge = value.get("nativeCubeQueueContext")
    return (
        isinstance(features, list)
        and "native-cube-queue-context" in features
        and isinstance(bridge, dict)
        and bridge.get("schemaVersion") == 1
        and bridge.get("queueObserverApiVersion") == 1
        and bridge.get("requiredObserver") is True
        and bridge.get("preQueuePersistence") is True
        and bridge.get("sourceIdentityFromExecutionReport") is True
    )


def _queue_body(
    *,
    workflow: JsonObject,
    client_id: str,
    visual_context: QueueVisualRunContext,
    preview_method: str | None,
    persistence_sugar_script: str | None,
) -> JsonObject:
    """Build the versioned native request and persistence-only output metadata."""

    substitute_context = visual_context.to_payload()
    if not visual_context.sources:
        substitute_context.pop("sources", None)
    extra_data: JsonObject = {"substitute": substitute_context}
    if preview_method is not None:
        extra_data["preview_method"] = preview_method
    persistence: JsonObject = {"workflow": workflow}
    if persistence_sugar_script is not None:
        persistence["sugar_script"] = persistence_sugar_script
    extra_data["extra_pnginfo"] = persistence
    return {
        "schema_version": 1,
        "workflow": workflow,
        "queue": {"client_id": client_id, "atomic": True},
        "optimization": {"enabled": True},
        "extra_data": extra_data,
    }


def _error_message(payload: object, status_code: int) -> str:
    """Extract a stable native queue error message."""

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, str) and error:
            return error
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message:
                return message
    return f"SugarCubes rejected native execution with HTTP {status_code}."


def _output_sources(payload: object) -> tuple[ListenerOutputSource, ...]:
    """Normalize SugarCubes output identities for cached-output recovery."""

    if not isinstance(payload, dict):
        return ()
    report = payload.get("report")
    if not isinstance(report, dict):
        return ()
    identities = report.get("output_identities")
    if not isinstance(identities, list):
        return ()
    sources: list[ListenerOutputSource] = []
    seen_execution_ids: set[str] = set()
    for identity in identities:
        if not isinstance(identity, dict):
            continue
        execution_id = identity.get("execution_id")
        instance_id = identity.get("instance_id")
        instance_alias = identity.get("instance_alias")
        if (
            not isinstance(execution_id, str)
            or not execution_id
            or execution_id in seen_execution_ids
            or not isinstance(instance_id, str)
            or not instance_id
        ):
            continue
        source_label = cube_alias_body(
            instance_alias.strip()
            if isinstance(instance_alias, str) and instance_alias.strip()
            else instance_id
        )
        seen_execution_ids.add(execution_id)
        sources.append(
            ListenerOutputSource(
                node_id=execution_id,
                source_key=f"cube:{instance_id}",
                source_label=source_label,
            )
        )
    return tuple(sources)


def _execution_sources(payload: object) -> tuple[ListenerOutputSource, ...]:
    """Normalize every lowered Cube node identity for timing attribution."""

    if not isinstance(payload, dict):
        return ()
    report = payload.get("report")
    if not isinstance(report, dict):
        return ()
    identities = report.get("execution_node_identities")
    if not isinstance(identities, list):
        return ()
    sources: list[ListenerOutputSource] = []
    seen_execution_ids: set[str] = set()
    for identity in identities:
        if not isinstance(identity, dict):
            continue
        execution_id = identity.get("execution_id")
        instance_id = identity.get("instance_id")
        instance_alias = identity.get("instance_alias")
        if (
            not isinstance(execution_id, str)
            or not execution_id
            or execution_id in seen_execution_ids
            or not isinstance(instance_id, str)
            or not instance_id
        ):
            continue
        source_label = cube_alias_body(
            instance_alias.strip()
            if isinstance(instance_alias, str) and instance_alias.strip()
            else instance_id
        )
        seen_execution_ids.add(execution_id)
        sources.append(
            ListenerOutputSource(
                node_id=execution_id,
                source_key=f"cube:{instance_id}",
                source_label=source_label,
            )
        )
    return tuple(sources)


def _execution_prompt(payload: object) -> JsonObject | None:
    """Normalize the exact validated prompt returned by SugarCubes."""

    if not isinstance(payload, dict):
        return None
    prompt = payload.get("execution_prompt")
    if not isinstance(prompt, dict):
        return None
    if not all(
        isinstance(node_id, str) and isinstance(node, dict)
        for node_id, node in prompt.items()
    ):
        return None
    return cast(JsonObject, prompt)


__all__ = ["NativeCubeExecutionClient", "NativeCubeQueueResult"]

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

"""HTTP client and workflow compiler adapter for backend-owned Sugar compilation."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from substitute.domain.common import JsonObject
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external.http_transport import (
    default_http_get,
    default_http_post,
    is_request_exception,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.external.substitute_backend_sugar_compile_client")
HttpGet = Callable[..., Any]
HttpPost = Callable[..., Any]


class BackendSugarCompileError(RuntimeError):
    """Carry structured Substitute BackEnd Sugar compile failures."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        backend_code: str | None = None,
        raw_payload: object | None = None,
    ) -> None:
        """Store public and diagnostic error details."""

        super().__init__(message)
        self.status_code = status_code
        self.backend_code = backend_code
        self.raw_payload = raw_payload


class SubstituteBackendSugarCompileClient:
    """Call Substitute BackEnd's Sugar compile route through Comfy HTTP."""

    def __init__(
        self,
        endpoint: ComfyEndpoint,
        *,
        http_get: HttpGet | None = None,
        http_post: HttpPost | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        """Initialize the client with endpoint and injectable transports."""

        self._endpoint = endpoint
        self._http_get = http_get or default_http_get
        self._http_post = http_post or default_http_post
        self._timeout_seconds = timeout_seconds

    def compile_workflow_payload(
        self,
        *,
        sugar_script_text: str,
        output_dir: Path,
    ) -> JsonObject:
        """Return prompt/workflow artifacts compiled by Substitute BackEnd."""

        self._require_sugar_compile_capability()
        endpoint = self._endpoint.substitute_sugar_compile_url()
        body: JsonObject = {
            "schemaVersion": 1,
            "sugarScriptText": sugar_script_text,
            "outputDir": str(output_dir),
        }
        try:
            response = self._http_post(
                endpoint,
                json=body,
                timeout=self._timeout_seconds,
            )
        except Exception as error:
            if not is_request_exception(error):
                raise
            log_warning(
                _LOGGER,
                "Substitute BackEnd Sugar compile request failed",
                endpoint=endpoint,
                output_dir=str(output_dir),
                script_length=len(sugar_script_text),
                error=repr(error),
            )
            raise BackendSugarCompileError(
                "Substitute BackEnd Sugar compile route is unavailable."
            ) from error

        status_code = getattr(response, "status_code", 200)
        if isinstance(status_code, int) and status_code >= 400:
            payload = _safe_json(response)
            message, backend_code = _backend_error_details(payload, status_code)
            log_warning(
                _LOGGER,
                "Substitute BackEnd Sugar compile returned an error",
                endpoint=endpoint,
                status_code=status_code,
                backend_code=backend_code or "",
                output_dir=str(output_dir),
                script_length=len(sugar_script_text),
            )
            raise BackendSugarCompileError(
                message,
                status_code=status_code,
                backend_code=backend_code,
                raw_payload=payload,
            )

        try:
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            if not _is_expected_http_error(error):
                raise
            log_warning(
                _LOGGER,
                "Invalid Substitute BackEnd Sugar compile response",
                endpoint=endpoint,
                status_code=status_code if isinstance(status_code, int) else None,
                error=repr(error),
            )
            raise BackendSugarCompileError(
                "Substitute BackEnd Sugar compile returned an invalid response.",
                status_code=status_code if isinstance(status_code, int) else None,
            ) from error

        return _compiled_payload(payload)

    def _require_sugar_compile_capability(self) -> None:
        """Fail early when the backend reports Sugar compilation unavailable."""

        payload: object | None = None
        try:
            response = self._http_get(
                self._endpoint.substitute_capabilities_url(),
                timeout=min(self._timeout_seconds, 3.0),
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            if not _is_expected_http_error(error):
                raise
            raise BackendSugarCompileError(
                "Substitute BackEnd capabilities are unavailable.",
                raw_payload=payload,
            ) from error

        if not isinstance(payload, dict):
            raise BackendSugarCompileError(
                "Substitute BackEnd capabilities response is invalid.",
                raw_payload=payload,
            )
        sugar_compile = payload.get("sugarCompile")
        if not isinstance(sugar_compile, dict):
            raise BackendSugarCompileError(
                "Substitute BackEnd does not advertise Sugar compilation.",
                raw_payload=payload,
            )
        if sugar_compile.get("available") is not True:
            reason = sugar_compile.get("unavailableReason")
            message = (
                reason
                if isinstance(reason, str) and reason.strip()
                else "Substitute BackEnd Sugar compilation is unavailable."
            )
            raise BackendSugarCompileError(
                message,
                backend_code="sugar-compile-unavailable",
                raw_payload=payload,
            )
        if (
            sugar_compile.get("schemaVersion") != 1
            or sugar_compile.get("compileRoute") != "/substitute/v1/sugar/compile"
        ):
            raise BackendSugarCompileError(
                "Substitute BackEnd Sugar compile capability is incompatible.",
                raw_payload=payload,
            )


class BackendSugarWorkflowPayloadCompiler:
    """Implement the app compiler port by delegating Sugar compile to backend."""

    def __init__(self, *, client: SubstituteBackendSugarCompileClient) -> None:
        """Store the backend compile client."""

        self._client = client

    def compile_workflow_payload(
        self,
        *,
        sugar_script_text: str,
        output_dir: Path,
    ) -> JsonObject:
        """Compile Sugar text through Substitute BackEnd."""

        return self._client.compile_workflow_payload(
            sugar_script_text=sugar_script_text,
            output_dir=output_dir,
        )


def _compiled_payload(payload: object) -> JsonObject:
    """Validate the backend compile response shape."""

    if not isinstance(payload, dict):
        raise BackendSugarCompileError(
            "Substitute BackEnd Sugar compile response is not a JSON object.",
            raw_payload=payload,
        )
    prompt = payload.get("prompt")
    workflow = payload.get("workflow")
    if not isinstance(prompt, dict) or not isinstance(workflow, dict):
        raise BackendSugarCompileError(
            "Substitute BackEnd Sugar compile response is missing prompt/workflow artifacts.",
            raw_payload=payload,
        )
    return {
        "prompt": cast(JsonObject, prompt),
        "workflow": cast(JsonObject, workflow),
    }


def _is_expected_http_error(error: BaseException) -> bool:
    """Return whether an HTTP operation failure should become compile failure."""

    return isinstance(error, TypeError | ValueError) or is_request_exception(error)


def _safe_json(response: object) -> object | None:
    """Return a response JSON payload when possible."""

    json_method = getattr(response, "json", None)
    if not callable(json_method):
        return None
    try:
        payload: object = json_method()
        return payload
    except (TypeError, ValueError):
        return None


def _backend_error_details(
    payload: object | None, status_code: int
) -> tuple[str, str | None]:
    """Read backend error details from a structured response."""

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            code = error.get("code")
            return (
                message
                if isinstance(message, str) and message.strip()
                else f"Sugar compile failed with HTTP {status_code}.",
                code if isinstance(code, str) and code.strip() else None,
            )
    return f"Sugar compile failed with HTTP {status_code}.", None


__all__ = [
    "BackendSugarCompileError",
    "BackendSugarWorkflowPayloadCompiler",
    "SubstituteBackendSugarCompileClient",
]

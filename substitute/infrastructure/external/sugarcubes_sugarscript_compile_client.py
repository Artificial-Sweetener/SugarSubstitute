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

"""Compile persistence SugarScript through SugarCubes' authoring boundary."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, cast

from substitute.domain.common import JsonObject
from substitute.domain.comfy_workflow import CanonicalCubeGraphAnalysis
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external.http_transport import default_http_post
from substitute.infrastructure.external.sugarcubes_workflow_analysis_client import (
    parse_sugarcubes_workflow_analysis,
)

HttpPost = Callable[..., Any]


class SugarCubesSugarScriptCompileError(RuntimeError):
    """Report a rejected or malformed SugarCubes authoring response."""


class SugarCubesSugarScriptWorkflowCompiler:
    """Adapt SugarCubes' persistence-language route to workflow export."""

    def __init__(
        self,
        endpoint: ComfyEndpoint,
        *,
        http_post: HttpPost | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        """Capture the Comfy endpoint and injectable JSON transport."""

        self._endpoint = endpoint
        self._http_post = http_post or default_http_post
        self._timeout_seconds = timeout_seconds

    def compile_workflow_payload(
        self,
        *,
        sugar_script_text: str,
        output_dir: Path,
    ) -> JsonObject:
        """Return the canonical workflow authored by SugarCubes from SugarScript."""

        payload = self._compile(sugar_script_text, output_dir=output_dir)
        workflow = payload.get("workflow")
        if not isinstance(workflow, dict):
            raise SugarCubesSugarScriptCompileError(
                "SugarCubes SugarScript authoring response has no canonical workflow."
            )
        return cast(JsonObject, workflow)

    def compile_cube_graph(
        self,
        *,
        sugar_script_text: str,
        output_dir: Path,
    ) -> CanonicalCubeGraphAnalysis:
        """Compile and analyze one persistence artifact in a single request."""

        payload = self._compile(sugar_script_text, output_dir=output_dir)
        analysis = payload.get("analysis")
        if not isinstance(analysis, Mapping):
            raise SugarCubesSugarScriptCompileError(
                "SugarCubes SugarScript response has no canonical graph analysis."
            )
        try:
            return parse_sugarcubes_workflow_analysis(analysis)
        except RuntimeError as error:
            raise SugarCubesSugarScriptCompileError(str(error)) from error

    def _compile(
        self,
        sugar_script_text: str,
        *,
        output_dir: Path,
    ) -> Mapping[str, object]:
        """Return one validated SugarCubes authoring response object."""

        _ = output_dir
        response = self._http_post(
            self._endpoint.sugarcubes_sugarscript_compile_url(),
            json={"source": sugar_script_text},
            timeout=self._timeout_seconds,
        )
        status_code = getattr(response, "status_code", 200)
        try:
            payload = response.json()
        except (TypeError, ValueError) as error:
            raise SugarCubesSugarScriptCompileError(
                "SugarCubes returned an invalid SugarScript authoring response."
            ) from error
        if isinstance(status_code, int) and status_code >= 400:
            raise SugarCubesSugarScriptCompileError(_diagnostic_message(payload))
        response.raise_for_status()
        if not isinstance(payload, Mapping):
            raise SugarCubesSugarScriptCompileError(
                "SugarCubes returned an invalid SugarScript authoring response."
            )
        return payload


def _diagnostic_message(payload: object) -> str:
    """Return the first located SugarScript diagnostic when available."""

    if isinstance(payload, dict):
        diagnostics = payload.get("diagnostics")
        if isinstance(diagnostics, list) and diagnostics:
            first = diagnostics[0]
            if isinstance(first, dict) and isinstance(first.get("message"), str):
                return cast(str, first["message"])
    return "SugarCubes rejected the SugarScript workflow."


__all__ = [
    "SugarCubesSugarScriptCompileError",
    "SugarCubesSugarScriptWorkflowCompiler",
]

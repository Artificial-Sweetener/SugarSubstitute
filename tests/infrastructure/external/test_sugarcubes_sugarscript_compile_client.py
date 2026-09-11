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

"""Verify persistence SugarScript compilation is owned by SugarCubes."""

from __future__ import annotations

from pathlib import Path

import pytest
import requests

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external.sugarcubes_sugarscript_compile_client import (
    SugarCubesSugarScriptCompileError,
    SugarCubesSugarScriptWorkflowCompiler,
)


class FakeResponse:
    """Represent a configured SugarCubes HTTP response."""

    def __init__(self, payload: object, *, status_code: int = 200) -> None:
        """Store the response payload and status."""
        self._payload = payload
        self.status_code = status_code

    def json(self) -> object:
        """Return the configured response payload."""
        return self._payload

    def raise_for_status(self) -> None:
        """Raise when the response represents an HTTP failure."""
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def test_compiler_posts_source_and_returns_canonical_workflow() -> None:
    """The export adapter should consume SugarCubes' native authoring response."""

    calls: list[tuple[str, object, float]] = []

    def post(url: str, *, json: object, timeout: float) -> FakeResponse:
        calls.append((url, json, timeout))
        return FakeResponse(
            {
                "diagnostics": [],
                "plan": {"instances": []},
                "workflow": {"version": 0.4, "nodes": [], "links": []},
            }
        )

    compiler = SugarCubesSugarScriptWorkflowCompiler(
        ComfyEndpoint("127.0.0.1", 8188),
        http_post=post,
    )

    result = compiler.compile_workflow_payload(
        sugar_script_text='use "cube" as Main',
        output_dir=Path("ignored"),
    )

    assert result == {"version": 0.4, "nodes": [], "links": []}
    assert calls == [
        (
            "http://127.0.0.1:8188/sugarcubes/v2/sugarscript/compile",
            {"source": 'use "cube" as Main'},
            30.0,
        )
    ]


def test_compiler_surfaces_sugarcubes_diagnostic() -> None:
    """Invalid persistence source should report SugarCubes' located diagnostic."""

    compiler = SugarCubesSugarScriptWorkflowCompiler(
        ComfyEndpoint("127.0.0.1", 8188),
        http_post=lambda *_args, **_kwargs: FakeResponse(
            {
                "diagnostics": [{"message": "Unknown Cube alias"}],
                "plan": None,
                "workflow": None,
            },
            status_code=422,
        ),
    )

    with pytest.raises(SugarCubesSugarScriptCompileError, match="Unknown Cube alias"):
        compiler.compile_workflow_payload(
            sugar_script_text="set Missing.value = 1",
            output_dir=Path("ignored"),
        )


def test_compiler_returns_combined_canonical_graph_analysis() -> None:
    """Load persistence source without a second workflow-analysis request."""

    response = {
        "workflow": {"version": 0.4, "nodes": [], "links": []},
        "analysis": {
            "schema_version": 1,
            "workflow_semantic_hash": "semantic",
            "instances": [],
            "edges": [],
            "proximity_connections": [],
            "segments": [],
            "workflow": {"version": 0.4, "nodes": [], "links": []},
        },
    }
    compiler = SugarCubesSugarScriptWorkflowCompiler(
        ComfyEndpoint("127.0.0.1", 8188),
        http_post=lambda *_args, **_kwargs: FakeResponse(response),
    )

    result = compiler.compile_cube_graph(
        sugar_script_text='use "cube" as Main',
        output_dir=Path("ignored"),
    )

    assert result.workflow_semantic_hash == "semantic"
    assert result.instances == ()
    assert result.edges == ()
    assert result.proximity_edges == ()

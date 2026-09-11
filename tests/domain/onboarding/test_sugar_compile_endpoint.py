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

"""Verify endpoint construction for SugarCubes SugarScript authoring."""

from __future__ import annotations

from substitute.domain.onboarding import ComfyEndpoint


def test_endpoint_builds_sugar_compile_url() -> None:
    """Expose the SugarCubes authoring route from a Comfy endpoint."""
    endpoint = ComfyEndpoint(host="10.0.0.2", port=8189)

    assert (
        endpoint.sugarcubes_sugarscript_compile_url()
        == "http://10.0.0.2:8189/sugarcubes/v2/sugarscript/compile"
    )


def test_endpoint_builds_sugarcubes_workflow_analysis_url() -> None:
    """Expose canonical graph analysis from the selected Comfy endpoint."""

    endpoint = ComfyEndpoint(host="10.0.0.2", port=8189)

    assert (
        endpoint.sugarcubes_workflow_analysis_url()
        == "http://10.0.0.2:8189/sugarcubes/v2/workflows/analyze"
    )


def test_endpoint_builds_sugarcubes_cube_graph_creation_url() -> None:
    """Expose one-request legacy stack migration from the selected target."""

    endpoint = ComfyEndpoint(host="10.0.0.2", port=8189)

    assert (
        endpoint.sugarcubes_workflow_cube_create_url()
        == "http://10.0.0.2:8189/sugarcubes/v2/workflows/cubes/create"
    )

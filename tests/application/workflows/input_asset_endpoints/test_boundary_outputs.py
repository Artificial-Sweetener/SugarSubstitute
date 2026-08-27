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

"""Verify input-asset semantics across exported cube output boundaries."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
)
from substitute.domain.workflow import InputAssetEndpointIndex, InputAssetRole


def test_cube_boundary_output_counts_as_used_image_socket() -> None:
    """A boundary-only image source should remain an editable asset endpoint."""

    graph = {
        "nodes": {
            "uploader": {
                "class_type": "LoadImage",
                "inputs": {"image": "example.png"},
            }
        },
        "outputs": {"output.image": "uploader"},
    }

    index = _endpoint_index("Any/Load Image", graph)

    assert [
        (endpoint.node_name, endpoint.field_key, endpoint.output_index, endpoint.role)
        for endpoint in index.endpoints
    ] == [("uploader", "image", 0, InputAssetRole.IMAGE)]


def test_cube_boundary_output_socket_forms_are_normalized() -> None:
    """Portable list and mapping output references should retain their socket roles."""

    definitions = {"DualUpload": _definition(outputs=("IMAGE", "MASK"))}
    list_index = _endpoint_index(
        "list",
        {
            "nodes": {"uploader": {"class_type": "DualUpload", "inputs": {}}},
            "outputs": {"output.mask": ["uploader", 1]},
        },
        node_definitions=definitions,
    )
    mapping_index = _endpoint_index(
        "mapping",
        {
            "nodes": {"uploader": {"class_type": "DualUpload", "inputs": {}}},
            "outputs": {"output.image": {"symbol": "uploader", "slot": 0}},
        },
        node_definitions=definitions,
    )

    assert [
        (endpoint.output_index, endpoint.role) for endpoint in list_index.endpoints
    ] == [(1, InputAssetRole.MASK)]
    assert [
        (endpoint.output_index, endpoint.role) for endpoint in mapping_index.endpoints
    ] == [(0, InputAssetRole.IMAGE)]


def _endpoint_index(
    section_key: str,
    graph: Mapping[str, object],
    *,
    node_definitions: Mapping[str, Mapping[str, object]] | None = None,
) -> InputAssetEndpointIndex:
    """Build boundary endpoint discovery through its production owner."""

    return InputAssetEndpointService().build_index(
        section_key,
        graph,
        node_definitions=node_definitions,
    )


def _definition(*, outputs: tuple[str, ...]) -> dict[str, object]:
    """Build one live upload-node definition."""

    return {
        "input": {
            "required": {
                "image": (["example.png"], {"image_upload": True}),
            }
        },
        "output": list(outputs),
    }

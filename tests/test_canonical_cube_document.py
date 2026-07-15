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

"""Contract tests for canonical SugarCube document validation."""

from __future__ import annotations

import pytest
from typing import cast

from substitute.domain.cubes.canonical_document import (
    CanonicalCubeError,
    validate_canonical_cube_document,
)


def _cube_document() -> dict[str, object]:
    """Return a minimal current-format cube with one surface control."""

    return {
        "cube_id": "demo",
        "version": "1.0",
        "implementation": {
            "nodes": {"sampler": {"class_type": "Sampler", "inputs": {"cfg": 7.0}}},
            "inputs": {},
            "outputs": {},
            "layout": {},
            "definitions": {},
            "subgraphs": [],
        },
        "surface": {
            "default_flavor_id": "default",
            "controls": [
                {
                    "control_id": "sampler.cfg",
                    "symbol": "sampler",
                    "input_name": "cfg",
                    "label": "CFG Scale",
                    "class_type": "Sampler",
                    "value_type": "number",
                }
            ],
        },
        "flavors": {
            "authored": [
                {"id": "default", "name": "Default", "values": {"sampler.cfg": 7.0}}
            ]
        },
    }


def test_validate_canonical_cube_document_requires_surface_control_label() -> None:
    """Current-format surface controls must store explicit visible labels."""

    payload = _cube_document()
    surface = cast(dict[str, object], payload["surface"])
    controls = cast(list[dict[str, object]], surface["controls"])
    del controls[0]["label"]

    with pytest.raises(CanonicalCubeError, match="non-empty 'label'"):
        validate_canonical_cube_document(payload)


def test_validate_canonical_cube_document_rejects_duplicate_control_labels() -> None:
    """Duplicate surface labels in one symbol scope cannot be scripted unambiguously."""

    payload = _cube_document()
    surface = cast(dict[str, object], payload["surface"])
    controls = cast(list[dict[str, object]], surface["controls"])
    controls.append(
        {
            "control_id": "sampler.cfg_copy",
            "symbol": "sampler",
            "input_name": "cfg_copy",
            "label": "CFG Scale",
            "class_type": "Sampler",
            "value_type": "number",
        }
    )

    with pytest.raises(CanonicalCubeError, match="duplicate label 'CFG Scale'"):
        validate_canonical_cube_document(payload)


def test_validate_canonical_cube_document_normalizes_node_labels() -> None:
    """Current-format nodes expose stored labels for script-facing lookup."""

    payload = _cube_document()
    document = validate_canonical_cube_document(payload)

    assert document.implementation["nodes"]["sampler"]["label"] == "sampler"


def test_validate_canonical_cube_document_rejects_duplicate_node_labels() -> None:
    """Duplicate node labels in one cube cannot be scripted unambiguously."""

    payload = _cube_document()
    implementation = cast(dict[str, object], payload["implementation"])
    nodes = cast(dict[str, dict[str, object]], implementation["nodes"])
    nodes["sampler"]["label"] = "Sampler"
    nodes["sampler_copy"] = {
        "class_type": "Sampler",
        "label": "Sampler",
        "inputs": {"cfg": 7.0},
    }

    with pytest.raises(CanonicalCubeError, match="duplicate node label 'Sampler'"):
        validate_canonical_cube_document(payload)

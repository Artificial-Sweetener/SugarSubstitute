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

"""Verify canonical cube input-asset compatibility analysis."""

from __future__ import annotations

import json
from pathlib import Path

from tools.input_asset_governance.cube_contracts import validate_cube


def test_any_load_image_boundary_contract_passes(tmp_path: Path) -> None:
    """A boundary-only built-in image source should satisfy the cube contract."""

    cube_path = _write_cube(
        tmp_path,
        {
            "nodes": {
                "load_image": {"class_type": "LoadImage", "inputs": {}},
            },
            "outputs": {"output.image": "load_image"},
            "definitions": {
                "LoadImage": {
                    "input": {"required": {"image": ["LIST"]}},
                    "output": ["IMAGE", "MASK"],
                }
            },
        },
    )

    assert validate_cube(cube_path) == ()


def test_invalid_boundary_reference_fails_contract(tmp_path: Path) -> None:
    """A boundary output should reference an existing canonical provider socket."""

    cube_path = _write_cube(
        tmp_path,
        {
            "nodes": {
                "load_image": {"class_type": "LoadImage", "inputs": {}},
            },
            "outputs": {"output.image": "missing_node"},
        },
    )

    diagnostics = validate_cube(cube_path)

    assert len(diagnostics) == 1
    assert "canonical endpoints" in diagnostics[0].message


def test_upload_field_without_asset_output_role_fails_contract(tmp_path: Path) -> None:
    """An upload widget should expose an IMAGE or MASK output role."""

    cube_path = _write_cube(
        tmp_path,
        {
            "nodes": {
                "source": {"class_type": "CustomUpload", "inputs": {}},
            },
            "outputs": {},
            "definitions": {
                "CustomUpload": {
                    "input": {
                        "required": {
                            "asset": ["LIST", {"image_upload": True}],
                        }
                    },
                    "output": ["STRING"],
                }
            },
        },
    )

    diagnostics = validate_cube(cube_path)

    assert len(diagnostics) == 1
    assert "no IMAGE or MASK output role" in diagnostics[0].message


def _write_cube(tmp_path: Path, implementation: dict[str, object]) -> Path:
    """Write one deterministic cube artifact for contract validation."""

    path = tmp_path / "fixture.cube"
    path.write_text(
        json.dumps(
            {
                "cube_id": "Fixture.cube",
                "version": "1.0.0",
                "implementation": implementation,
            }
        ),
        encoding="utf-8",
    )
    return path

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

"""Contract tests for authoritative external input-asset field semantics."""

from __future__ import annotations

from substitute.application.workflows.input_asset_field_policy import (
    InputAssetFieldPolicy,
)
from substitute.domain.workflow import InputAssetCardinality, InputAssetRole


def test_live_metadata_owns_custom_ordered_mask_semantics() -> None:
    """Live upload, cardinality, and output metadata should form one contract."""

    fields = InputAssetFieldPolicy().fields_for_node(
        "CustomMaskBatch",
        {
            "input": {
                "required": {
                    "files": [
                        "LIST",
                        {"image_upload": True, "allow_batch": True},
                    ]
                }
            },
            "output": ["MASK"],
        },
    )

    assert len(fields) == 1
    assert fields[0].field_key == "files"
    assert fields[0].preferred_role is InputAssetRole.MASK
    assert fields[0].cardinality is InputAssetCardinality.ORDERED


def test_output_folder_picker_is_not_an_input_asset() -> None:
    """Output-folder selectors should remain outside input transport ownership."""

    fields = InputAssetFieldPolicy().fields_for_node(
        "OutputBrowser",
        {
            "input": {
                "required": {
                    "image": [
                        "LIST",
                        {"image_upload": True, "image_folder": "output"},
                    ]
                }
            },
            "output": ["IMAGE"],
        },
    )

    assert fields == ()


def test_legacy_contracts_recover_roles_before_live_metadata_arrives() -> None:
    """Built-in image and mask fields should remain typed during restore."""

    policy = InputAssetFieldPolicy()

    image_field = policy.fields_for_node("LoadImage", {})[0]
    mask_field = policy.fields_for_node("LoadImageMask", {})[0]
    ordered_field = policy.fields_for_node("SimpleSyrup.LoadMaskBatch", {})[0]

    assert image_field.preferred_role is InputAssetRole.IMAGE
    assert mask_field.preferred_role is InputAssetRole.MASK
    assert ordered_field.preferred_role is InputAssetRole.MASK
    assert ordered_field.cardinality is InputAssetCardinality.ORDERED

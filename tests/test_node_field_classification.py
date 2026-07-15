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

"""Contract tests for application-owned node field classification."""

from __future__ import annotations

from substitute.application.node_behavior import NodeFieldKind, classify_node_field


def test_classify_load_image_fields_as_asset_fields() -> None:
    """Load image node image inputs are Substitute-owned asset fields."""

    assert (
        classify_node_field(
            class_type="LoadImage",
            field_key="image",
            node_data={"inputs": {"image": "E:/images/input.png"}},
            field_type="LIST",
        )
        is NodeFieldKind.ASSET_FIELD
    )
    assert (
        classify_node_field(
            class_type="LoadImageMask",
            field_key="image",
            node_data={"inputs": {"image": "mask.png"}},
            field_type="LIST",
        )
        is NodeFieldKind.ASSET_FIELD
    )


def test_classify_regular_live_lists_as_comfy_enum_fields() -> None:
    """Non-asset live list fields remain Comfy-owned enum fields."""

    assert (
        classify_node_field(
            class_type="CheckpointLoaderSimple",
            field_key="ckpt_name",
            node_data={"inputs": {"ckpt_name": "model-a.safetensors"}},
            field_type="LIST",
        )
        is NodeFieldKind.COMFY_ENUM_FIELD
    )


def test_classify_combo_fields_as_comfy_enum_fields() -> None:
    """COMBO fields are finite Comfy-owned choice fields like LIST inputs."""

    assert (
        classify_node_field(
            class_type="UpscaleModelLoader",
            field_key="model_name",
            node_data={"inputs": {"model_name": "R-ESRGAN 4x+ Anime6B.pth"}},
            field_type="COMBO",
        )
        is NodeFieldKind.COMFY_ENUM_FIELD
    )


def test_classify_active_sampler_links_as_linked_fields() -> None:
    """Explicit list links outrank enum canonicalization."""

    assert (
        classify_node_field(
            class_type="KSampler",
            field_key="sampler_name",
            node_data={
                "inputs": {"sampler_name": "euler"},
                "sampler_link": {"from": "workflow"},
            },
            field_type="LIST",
        )
        is NodeFieldKind.LINKED_FIELD
    )


def test_classify_non_list_fields_as_plain_fields() -> None:
    """Non-list fields do not enter live-list canonicalization."""

    assert (
        classify_node_field(
            class_type="KSampler",
            field_key="seed",
            node_data={"inputs": {"seed": 1}},
            field_type="INT",
        )
        is NodeFieldKind.PLAIN_FIELD
    )

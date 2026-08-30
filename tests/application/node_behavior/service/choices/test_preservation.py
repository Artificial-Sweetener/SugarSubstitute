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

"""Choice-value preservation contracts."""

from __future__ import annotations


from substitute.application.node_behavior import (
    FieldPresentation,
)
from tests.support.node_behavior import (
    build_behavior_snapshot,
    cube_state,
)


def test_build_snapshot_preserves_asset_fields_outside_comfy_live_options() -> None:
    """Asset fields are Substitute-owned and must not canonicalize to Comfy options."""

    selected_image = "E:/images/selected.png"
    selected_mask = "E:/projects/Recipe/masks/selected_mask.png"
    cube = cube_state(
        nodes={
            "load_image": {
                "class_type": "LoadImage",
                "inputs": {"image": selected_image},
            },
            "load_image_as_mask": {
                "class_type": "LoadImageMask",
                "inputs": {"image": selected_mask},
            },
        },
    )
    snapshot = build_behavior_snapshot(
        cube_states={"Inpaint": cube},
        stack_order=["Inpaint"],
        definitions_by_class={
            "LoadImage": {
                "input": {
                    "required": {
                        "image": [
                            ["00282-3430329909-ad-before.png"],
                            {},
                        ]
                    }
                }
            },
            "LoadImageMask": {
                "input": {
                    "required": {
                        "image": [
                            ["00282-3430329909-ad-before.png"],
                            {},
                        ]
                    }
                }
            },
        },
    )

    image_spec = snapshot.field_specs_by_alias["Inpaint"]["load_image"]["image"]
    mask_spec = snapshot.field_specs_by_alias["Inpaint"]["load_image_as_mask"]["image"]

    assert image_spec.value == selected_image
    assert mask_spec.value == selected_mask
    assert cube.buffer["nodes"]["load_image"]["inputs"]["image"] == selected_image
    assert (
        cube.buffer["nodes"]["load_image_as_mask"]["inputs"]["image"] == selected_mask
    )
    assert cube.dirty is False


def test_checkpoint_field_no_longer_uses_node_specific_model_picker_patch() -> None:
    """Checkpoint fields should stay standard until value enrichment selects a picker."""

    cube = cube_state(
        nodes={
            "checkpoint": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model-a.safetensors"},
            },
            "ultralytics": {
                "class_type": "UltralyticsDetectorProvider",
                "inputs": {"model_name": "bbox/yolo.pt"},
            },
        }
    )
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "CheckpointLoaderSimple": {
                "input": {
                    "required": {
                        "ckpt_name": [
                            ["model-a.safetensors", "model-b.safetensors"],
                            {"default": "model-a.safetensors"},
                        ]
                    }
                }
            },
            "UltralyticsDetectorProvider": {
                "input": {
                    "required": {
                        "model_name": [
                            ["bbox/yolo.pt", "segm/yolo-seg.pt"],
                            {"default": "bbox/yolo.pt"},
                        ]
                    }
                }
            },
        },
    )

    checkpoint_behavior = snapshot.field_specs_by_alias["A"]["checkpoint"][
        "ckpt_name"
    ].field_behavior
    ultralytics_behavior = snapshot.field_specs_by_alias["A"]["ultralytics"][
        "model_name"
    ].field_behavior

    assert checkpoint_behavior.presentation == FieldPresentation.STANDARD
    assert checkpoint_behavior.style == {}
    assert ultralytics_behavior.presentation == FieldPresentation.STANDARD

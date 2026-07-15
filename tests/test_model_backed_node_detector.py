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

"""Tests for cache-neutral model node detection."""

from __future__ import annotations

from substitute.application.node_behavior import ModelBackedNodeDetector


def test_known_checkpoint_choice_field_is_model_backed() -> None:
    """Known model loader fields should qualify without catalog reads."""

    detector = ModelBackedNodeDetector()

    assert detector.node_uses_configured_model(
        node_data={"class_type": "CheckpointLoaderSimple", "inputs": {}},
        live_definition={
            "input": {
                "required": {
                    "ckpt_name": [
                        ["Anime\\preview.safetensors", "Realism\\base.safetensors"],
                        {},
                    ]
                }
            }
        },
    )


def test_upscale_model_name_combo_is_model_backed() -> None:
    """Non-rich upscale model combos should still qualify for the title icon."""

    detector = ModelBackedNodeDetector()

    assert detector.node_uses_configured_model(
        node_data={"class_type": "UpscaleModelLoader", "inputs": {}},
        live_definition={
            "input": {
                "required": {
                    "model_name": [
                        "COMBO",
                        {"options": ["ESRGAN_4x.pth", "R-ESRGAN 4x+ Anime6B.pth"]},
                    ]
                }
            }
        },
    )


def test_modelish_field_name_is_model_backed_for_choice_fields() -> None:
    """Model-like finite choice fields should qualify across custom nodes."""

    detector = ModelBackedNodeDetector()

    assert detector.node_uses_configured_model(
        node_data={"class_type": "CustomCheckpointNode", "inputs": {}},
        live_definition={
            "input": {
                "required": {"checkpoint": [["a.safetensors", "b.safetensors"], {}]}
            }
        },
    )


def test_model_name_requires_modelish_class_context() -> None:
    """Generic model_name fields should not qualify on unrelated node classes."""

    detector = ModelBackedNodeDetector()

    assert not detector.node_uses_configured_model(
        node_data={"class_type": "DisplayModeSelector", "inputs": {}},
        live_definition={
            "input": {
                "required": {
                    "model_name": ["COMBO", {"options": ["compact", "expanded"]}]
                }
            }
        },
    )


def test_non_choice_fields_do_not_qualify() -> None:
    """String fields without finite options should not qualify structurally."""

    detector = ModelBackedNodeDetector()

    assert not detector.node_uses_configured_model(
        node_data={"class_type": "CheckpointLoaderSimple", "inputs": {}},
        live_definition={"input": {"required": {"ckpt_name": ["STRING", {}]}}},
    )


def test_non_model_list_values_do_not_qualify() -> None:
    """Ordinary finite choices should not receive model-backed classification."""

    detector = ModelBackedNodeDetector()

    assert not detector.node_uses_configured_model(
        node_data={"class_type": "ModeSelector", "inputs": {"mode": "fast"}},
        live_definition={"input": {"required": {"mode": [["fast", "accurate"], {}]}}},
    )

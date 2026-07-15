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

"""Behavior snapshot tests for sampler denoise visibility."""

from __future__ import annotations

from tests.node_behavior_test_helpers import build_behavior_snapshot, cube_state


def test_empty_latent_sampler_keeps_denoise_visible_for_custom_sampler_class() -> None:
    """Sampler-like nodes fed by EmptyLatentImage should keep denoise visible."""

    snapshot = build_behavior_snapshot(
        cube_states={
            "A": cube_state(
                nodes={
                    "latent": {"class_type": "EmptyLatentImage", "inputs": {}},
                    "sampler": {
                        "class_type": "CustomSamplerLike",
                        "inputs": {
                            "latent_image": ["latent", 0],
                            "denoise": 0.35,
                        },
                    },
                },
            )
        },
        stack_order=["A"],
    )

    assert ("A", "sampler", "denoise") not in snapshot.hidden_field_keys_by_alias["A"]


def test_encoded_latent_sampler_keeps_denoise_visible() -> None:
    """Sampler-like nodes fed by encoded latents should keep denoise visible."""

    snapshot = build_behavior_snapshot(
        cube_states={
            "A": cube_state(
                nodes={
                    "encode": {"class_type": "VAEEncode", "inputs": {}},
                    "sampler": {
                        "class_type": "KSampler",
                        "inputs": {
                            "latent_image": ["encode", 0],
                            "denoise": 0.5,
                        },
                    },
                },
            )
        },
        stack_order=["A"],
    )

    assert ("A", "sampler", "denoise") not in snapshot.hidden_field_keys_by_alias["A"]

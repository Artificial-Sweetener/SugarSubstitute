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

"""Verify built-in VAE option row grouping."""

from __future__ import annotations

import pytest

from substitute.domain.node_behavior.defaults import host_node_behavior_patch


@pytest.mark.parametrize(
    "class_type",
    ["SimpleSyrup.VAEDecodeOptions", "SimpleSyrup.VAEEncodeOptions"],
)
def test_vae_option_defaults_group_spatial_and_temporal_controls(
    class_type: str,
) -> None:
    """VAE option cards should keep paired advanced dimensions compact."""

    patch = host_node_behavior_patch("vae_options", class_type)

    assert patch.field_groups == (
        ("tile_size", "overlap"),
        ("temporal_size", "temporal_overlap"),
    )

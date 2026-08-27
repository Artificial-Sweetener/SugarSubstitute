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

"""Verify override and field-presentation policy."""

from __future__ import annotations

from substitute.domain.node_behavior import (
    FieldPresentation,
    OverridePinPolicy,
    resolve_node_behavior,
)
from tests.domain.node_behavior.resolver.support import context


def test_resolver_marks_steps_and_cfg_as_optional_override_candidates() -> None:
    """Host field defaults should expose steps and cfg without default pinning them."""

    resolved = resolve_node_behavior(
        node_name="ksampler",
        class_type="KSampler",
        input_keys=("seed", "sampler_name", "scheduler", "steps", "cfg"),
        context=context(node_name="ksampler", class_type="KSampler"),
    )

    expected_policies = {
        "seed": OverridePinPolicy.DEFAULT_PINNED,
        "sampler_name": OverridePinPolicy.DEFAULT_PINNED,
        "scheduler": OverridePinPolicy.DEFAULT_PINNED,
        "steps": OverridePinPolicy.OPTIONAL,
        "cfg": OverridePinPolicy.OPTIONAL,
    }

    for field_key, expected_policy in expected_policies.items():
        override_behavior = resolved.fields[field_key].override_behavior
        assert override_behavior.override_key == field_key
        assert override_behavior.pin_policy == expected_policy


def test_resolver_owns_seedbox_presentation_for_both_comfy_aliases() -> None:
    """Seed aliases should resolve one presentation contract before Qt rendering."""

    resolved = resolve_node_behavior(
        node_name="sampler",
        class_type="SamplerCustom",
        input_keys=("seed", "noise_seed", "ordinary_int"),
        context=context(node_name="sampler", class_type="SamplerCustom"),
    )

    assert resolved.fields["seed"].presentation is FieldPresentation.SEED_BOX
    assert resolved.fields["noise_seed"].presentation is FieldPresentation.SEED_BOX
    assert resolved.fields["ordinary_int"].presentation is FieldPresentation.STANDARD

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

"""Focused tests for node-behavior model defaults and enums."""

from __future__ import annotations

from substitute.domain.node_behavior import (
    ActivationSwitchRole,
    ActivationSwitchSource,
    CardBehavior,
    CardMode,
    CollapseMode,
    FieldBehavior,
    FieldPresentation,
    ResolvedNodeBehavior,
)


def test_model_defaults_are_stable() -> None:
    """Default models should encode standard card and field behavior."""

    field = FieldBehavior(field_key="seed")
    card = CardBehavior()

    assert field.presentation == FieldPresentation.STANDARD
    assert card.card_mode == CardMode.STANDARD
    assert card.collapse_mode == CollapseMode.AUTO
    assert card.enabled_switch_source == ActivationSwitchSource.DEFAULT
    assert card.activation_switch_role == ActivationSwitchRole.NONE
    assert card.activation_signal_types == frozenset()


def test_resolved_node_behavior_preserves_field_groups() -> None:
    """Resolved node behavior should carry grouped-field layout metadata."""

    resolved = ResolvedNodeBehavior(
        node_name="ksampler",
        class_type="KSampler",
        card=CardBehavior(),
        fields={"seed": FieldBehavior(field_key="seed")},
        field_groups=(("sampler_name", "scheduler"),),
    )

    assert resolved.field_groups == (("sampler_name", "scheduler"),)

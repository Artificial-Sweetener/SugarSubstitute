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

"""Verify override participation and serialization scope."""

from __future__ import annotations


from substitute.application.node_behavior import OverridePinPolicy
from substitute.application.overrides import PinnedOverrideService
from tests.application.overrides.support import _field_spec, _snapshot


def test_participation_snapshot_uses_first_choice_field_as_authority() -> None:
    """Choice overrides should include exact and value-compatible participants only."""

    snapshot = _snapshot(
        {
            "A": {
                "sampler": {
                    "sampler_name": _field_spec(
                        cube_alias="A",
                        node_name="sampler",
                        class_type="KSampler",
                        field_key="sampler_name",
                        value="euler",
                        override_key="sampler_name",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        field_type="LIST",
                        field_info=[["euler", "heun"], {"default": "euler"}],
                    )
                }
            },
            "B": {
                "sampler": {
                    "sampler_name": _field_spec(
                        cube_alias="B",
                        node_name="sampler",
                        class_type="CustomSampler",
                        field_key="sampler_name",
                        value="heun",
                        override_key="sampler_name",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        field_type="LIST",
                        field_info=[["euler", "heun", "dpmpp"], {"default": "euler"}],
                    )
                }
            },
            "C": {
                "sampler": {
                    "sampler_name": _field_spec(
                        cube_alias="C",
                        node_name="sampler",
                        class_type="TinySampler",
                        field_key="sampler_name",
                        value="ddim",
                        override_key="sampler_name",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        field_type="LIST",
                        field_info=[["ddim"], {"default": "ddim"}],
                    )
                }
            },
        }
    )

    participation = PinnedOverrideService().build_participation_snapshot(
        overrides={"sampler_name": {"value": "heun", "mode": "global"}},
        behavior_snapshot=snapshot,
        stack_order=["A", "B", "C"],
    )

    assert participation.participant_fields() == frozenset(
        {
            ("A", "sampler", "sampler_name"),
            ("B", "sampler", "sampler_name"),
        }
    )
    assert participation.eligible_fields_by_key["sampler_name"] == (
        ("A", "sampler", "sampler_name"),
        ("B", "sampler", "sampler_name"),
        ("C", "sampler", "sampler_name"),
    )


def test_serialization_scope_is_partial_when_not_all_choice_fields_participate() -> (
    None
):
    """Partial choice participation should serialize without a wildcard override."""

    snapshot = _snapshot(
        {
            "A": {
                "sampler": {
                    "sampler_name": _field_spec(
                        cube_alias="A",
                        node_name="sampler",
                        class_type="KSampler",
                        field_key="sampler_name",
                        value="euler",
                        override_key="sampler_name",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        field_type="LIST",
                        field_info=[["euler", "heun"], {"default": "euler"}],
                    )
                }
            },
            "B": {
                "sampler": {
                    "sampler_name": _field_spec(
                        cube_alias="B",
                        node_name="sampler",
                        class_type="TinySampler",
                        field_key="sampler_name",
                        value="ddim",
                        override_key="sampler_name",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        field_type="LIST",
                        field_info=[["ddim"], {"default": "ddim"}],
                    )
                }
            },
        }
    )

    scope = PinnedOverrideService().build_serialization_scopes(
        overrides={"sampler_name": {"value": "heun", "mode": "global"}},
        behavior_snapshot=snapshot,
        stack_order=["A", "B"],
    )["sampler_name"]

    assert scope.full_participation is False
    assert scope.participant_fields == frozenset({("A", "sampler", "sampler_name")})


def test_choice_override_value_must_be_supported_by_authority() -> None:
    """Stale persisted choice values should not be applied to any participant."""

    snapshot = _snapshot(
        {
            "A": {
                "sampler": {
                    "sampler_name": _field_spec(
                        cube_alias="A",
                        node_name="sampler",
                        class_type="KSampler",
                        field_key="sampler_name",
                        value="euler",
                        override_key="sampler_name",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        field_type="LIST",
                        field_info=[["euler", "heun"], {"default": "euler"}],
                    )
                }
            }
        }
    )

    scope = PinnedOverrideService().build_serialization_scopes(
        overrides={"sampler_name": {"value": "ddim", "mode": "global"}},
        behavior_snapshot=snapshot,
        stack_order=["A"],
    )["sampler_name"]

    assert scope.full_participation is False
    assert scope.participant_fields == frozenset()


def test_encode_style_scope_uses_wildcard_despite_hidden_same_key_link() -> None:
    """Hidden infrastructure inputs should not force encode style into partial scope."""

    encode_options: list[object] = [["A1111", "Comfy"], {"default": "A1111"}]
    snapshot = _snapshot(
        {
            "A": {
                "prompt_encode_style": {
                    "encode_style": _field_spec(
                        cube_alias="A",
                        node_name="prompt_encode_style",
                        class_type="SimpleSyrup.PromptEncodeStyle",
                        field_key="encode_style",
                        value="A1111",
                        override_key="encode_style",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        field_type="LIST",
                        field_info=encode_options,
                    )
                },
                "schedule_encode_prompts": {
                    "encode_style": _field_spec(
                        cube_alias="A",
                        node_name="schedule_encode_prompts",
                        class_type=(
                            "SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl"
                        ),
                        field_key="encode_style",
                        value=["prompt_encode_style", 0],
                        override_key=None,
                        pin_policy=OverridePinPolicy.NEVER,
                        field_type="LIST",
                        field_info=encode_options,
                    )
                },
            }
        }
    )
    service = PinnedOverrideService()

    participation = service.build_participation_snapshot(
        overrides={"encode_style": {"value": "Comfy", "mode": "global"}},
        behavior_snapshot=snapshot,
        stack_order=["A"],
    )
    scope = service.build_serialization_scopes(
        overrides={"encode_style": {"value": "Comfy", "mode": "global"}},
        behavior_snapshot=snapshot,
        stack_order=["A"],
    )["encode_style"]

    assert participation.participant_fields() == frozenset(
        {("A", "prompt_encode_style", "encode_style")}
    )
    assert participation.eligible_fields_by_key["encode_style"] == (
        ("A", "prompt_encode_style", "encode_style"),
    )
    assert scope.full_participation is True
    assert scope.participant_fields == frozenset(
        {("A", "prompt_encode_style", "encode_style")}
    )

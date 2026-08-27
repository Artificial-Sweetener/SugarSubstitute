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

"""Verify default materialization and explicit pin mutations."""

from __future__ import annotations


from substitute.application.node_behavior import OverridePinPolicy
from substitute.application.overrides import PinnedOverrideService
from tests.application.overrides.support import _field_spec, _snapshot


def test_materialize_default_overrides_uses_first_representative_values() -> None:
    """Default-pinned controls should materialize from the first stack representative."""

    snapshot = _snapshot(
        {
            "A": {
                "ksampler": {
                    "seed": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="seed",
                        value=111,
                        override_key="seed",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        toolbar_order=10,
                    )
                }
            },
            "B": {
                "ksampler": {
                    "seed": _field_spec(
                        cube_alias="B",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="seed",
                        value=222,
                        override_key="seed",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        toolbar_order=10,
                    )
                }
            },
        }
    )
    service = PinnedOverrideService()
    overrides: dict[str, dict[str, object]] = {}

    changed = service.materialize_default_overrides(
        overrides=overrides,
        behavior_snapshot=snapshot,
        stack_order=["A", "B"],
    )

    assert changed is True
    assert overrides == {"seed": {"value": 111, "mode": "global"}}


def test_default_pinned_false_selection_prevents_materialization() -> None:
    """Explicitly unchecked default-pinned controls should stay inactive."""

    snapshot = _snapshot(
        {
            "A": {
                "ksampler": {
                    "seed": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="seed",
                        value=111,
                        override_key="seed",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        toolbar_order=10,
                    )
                }
            }
        }
    )
    service = PinnedOverrideService()
    overrides: dict[str, dict[str, object]] = {}

    changed = service.materialize_default_overrides(
        overrides=overrides,
        selections={"seed": False},
        behavior_snapshot=snapshot,
        stack_order=["A"],
    )

    assert changed is False
    assert overrides == {}


def test_materialize_default_overrides_skips_optional_steps_and_cfg() -> None:
    """Optional sampler controls should remain inactive during default materialization."""

    snapshot = _snapshot(
        {
            "A": {
                "ksampler": {
                    "seed": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="seed",
                        value=111,
                        override_key="seed",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        toolbar_order=10,
                    ),
                    "sampler_name": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="sampler_name",
                        value="euler",
                        override_key="sampler_name",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        toolbar_order=20,
                    ),
                    "scheduler": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="scheduler",
                        value="karras",
                        override_key="scheduler",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        toolbar_order=30,
                    ),
                    "steps": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="steps",
                        value=20,
                        override_key="steps",
                        pin_policy=OverridePinPolicy.OPTIONAL,
                        toolbar_order=40,
                    ),
                    "cfg": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="cfg",
                        value=7.0,
                        override_key="cfg",
                        pin_policy=OverridePinPolicy.OPTIONAL,
                        toolbar_order=50,
                    ),
                }
            }
        }
    )
    service = PinnedOverrideService()
    overrides: dict[str, dict[str, object]] = {}

    changed = service.materialize_default_overrides(
        overrides=overrides,
        behavior_snapshot=snapshot,
        stack_order=["A"],
    )

    assert changed is True
    assert overrides == {
        "seed": {"value": 111, "mode": "global"},
        "sampler_name": {"value": "euler", "mode": "global"},
        "scheduler": {"value": "karras", "mode": "global"},
    }


def test_pin_override_activates_optional_cfg_candidate() -> None:
    """Optional candidates should activate explicitly without special-case handling."""

    snapshot = _snapshot(
        {
            "A": {
                "ksampler": {
                    "cfg": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="cfg",
                        value=7.0,
                        override_key="cfg",
                        pin_policy=OverridePinPolicy.OPTIONAL,
                        toolbar_order=50,
                    )
                }
            }
        }
    )
    service = PinnedOverrideService()
    overrides: dict[str, dict[str, object]] = {}

    changed = service.pin_override(
        overrides=overrides,
        behavior_snapshot=snapshot,
        stack_order=["A"],
        override_key="cfg",
    )

    assert changed is True
    assert overrides == {"cfg": {"value": 7.0, "mode": "global"}}

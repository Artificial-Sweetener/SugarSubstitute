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

"""Tests for class-agnostic node-behavior field group inference."""

from __future__ import annotations

from substitute.domain.node_behavior.common_field_groups import (
    infer_common_field_groups,
)


def test_infer_common_field_groups_returns_steps_cfg_pair() -> None:
    """Co-occurring steps and cfg fields should resolve one common group."""

    groups = infer_common_field_groups(("seed", "steps", "cfg"))

    assert groups == (("steps", "cfg"),)


def test_infer_common_field_groups_preserves_common_group_order() -> None:
    """Common groups should follow policy order rather than input discovery order."""

    groups = infer_common_field_groups(("cfg", "steps", "scheduler", "sampler_name"))

    assert groups == (("sampler_name", "scheduler"), ("steps", "cfg"))


def test_infer_common_field_groups_skips_occupied_fields() -> None:
    """Fields already owned by explicit groups should not be reused."""

    groups = infer_common_field_groups(
        ("sampler_name", "scheduler", "steps", "cfg"),
        occupied_fields=frozenset({"cfg"}),
    )

    assert groups == (("sampler_name", "scheduler"),)


def test_infer_common_field_groups_requires_complete_group() -> None:
    """Partial common groups should not produce grouped rows."""

    groups = infer_common_field_groups(("sampler_name", "steps"))

    assert groups == ()

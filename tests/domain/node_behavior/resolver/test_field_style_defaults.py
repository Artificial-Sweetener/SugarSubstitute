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

"""Verify default resolver field styles."""

from __future__ import annotations

from substitute.domain.node_behavior import resolve_node_behavior
from tests.domain.node_behavior.resolver.support import context


def test_field_style_falls_back_to_class_rule_field_tail() -> None:
    """Apply class-level field styles without external overrides."""

    resolved = resolve_node_behavior(
        node_name="Node",
        class_type="VectorscopeCC",
        input_keys=("r",),
        context=context(node_name="Node", class_type="VectorscopeCC"),
    )

    field = resolved.fields["r"]
    assert field.control_name == "color_slider"
    assert field.label_override == "Red"

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

"""Test application-icon mappings owned by node-card construction."""

from __future__ import annotations

from substitute.presentation.editor.panel.node_card_builder import NodeCardBuilder
from substitute.presentation.resources.app_icon import AppIcon


def test_node_card_model_icon_uses_brain_circuit_app_icon() -> None:
    """Resolve model-backed node cards to the held Brain Circuit icon."""

    icon_map = getattr(NodeCardBuilder, "_ICON_MAP")

    assert icon_map["model"] is AppIcon.BRAIN_CIRCUIT_20_REGULAR


def test_node_card_eraser_icon_uses_regular_eraser_app_icon() -> None:
    """Resolve negative-prompt cards to the held regular Eraser icon."""

    icon_map = getattr(NodeCardBuilder, "_ICON_MAP")

    assert icon_map["eraser"] is AppIcon.ERASER_20_REGULAR

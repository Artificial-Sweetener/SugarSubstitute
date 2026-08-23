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

"""Verify authoritative empty choice fields still produce node cards."""

from __future__ import annotations

import pytest

from substitute.presentation.widgets import ComboBox
from tests.presentation.editor.node_card.visibility.support import (
    create_visibility_scenario,
)


@pytest.mark.parametrize(
    ("section_name", "field_info"),
    (
        ("required", [[], {}]),
        ("required", ["COMBO", {"options": []}]),
        ("optional", [[], {}]),
        ("optional", ["COMBO", {"options": []}]),
    ),
    ids=(
        "required-classic-list",
        "required-combo-options",
        "optional-classic-list",
        "optional-combo-options",
    ),
)
def test_authoritative_empty_choice_always_draws_card(
    monkeypatch: pytest.MonkeyPatch,
    section_name: str,
    field_info: list[object],
) -> None:
    """Render an empty picker instead of dropping or failing the card."""

    node_name = "upscale_model"
    node_type = "UpscaleModelLoader"
    scenario = create_visibility_scenario(
        monkeypatch,
        node_name=node_name,
        node_type=node_type,
        inputs={"model_name": "missing-upscaler.pth"},
        definitions={
            node_type: {
                "input": {
                    section_name: {
                        "model_name": field_info,
                    }
                }
            }
        },
        use_minimal_field_widget=False,
    )
    wrapper = scenario.build()
    try:
        assert wrapper is not None
        assert wrapper.property("base_card_visible") is True
        choice = scenario.panel.input_widgets_by_field_key[
            ("A", node_name, "model_name")
        ]
        assert isinstance(choice, ComboBox)
        assert choice.count() == 0
        assert choice.currentText() == ""
        assert choice.placeholderText() == "No options available"
        assert scenario.cube_state.dirty is False
    finally:
        scenario.destroy(wrapper)

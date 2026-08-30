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

"""Verify when node-card construction produces a visible card."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QWidget

from tests.presentation.editor.node_card.visibility.support import (
    create_visibility_scenario,
)


def test_empty_card_without_title_controls_is_not_constructed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Omit a card that has neither fields nor title controls."""

    scenario = create_visibility_scenario(
        monkeypatch,
        node_name="empty_node",
        node_type="SomeUnknownClass",
        inputs={},
    )
    wrapper = scenario.build()
    try:
        assert wrapper is None
    finally:
        scenario.destroy(wrapper)


def test_empty_card_with_activation_switch_is_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retain an empty card when its activation control is meaningful."""

    scenario = create_visibility_scenario(
        monkeypatch,
        node_name="vae_override",
        node_type="VAELoader",
        inputs={},
    )
    wrapper = scenario.build()
    try:
        assert isinstance(wrapper, QWidget)
        assert wrapper.property("has_title_controls") is True
        assert wrapper.property("base_card_visible") is True
    finally:
        scenario.destroy(wrapper)


def test_bypass_authored_vae_loader_retains_activation_card_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Construct activation UI while behavior remains hidden and disabled."""

    scenario = create_visibility_scenario(
        monkeypatch,
        node_name="vae_override",
        node_type="VAELoader",
        inputs={},
        node_metadata={"mode": 4},
    )
    decision = scenario.snapshot.card_decisions_by_alias["A"]["vae_override"]
    wrapper = scenario.build()
    try:
        assert isinstance(wrapper, QWidget)
        assert decision.visible is False
        assert decision.enabled is False
        assert wrapper.property("has_title_controls") is True
    finally:
        scenario.destroy(wrapper)


def test_hard_hidden_infrastructure_node_is_not_constructed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Omit hard-hidden infrastructure nodes before publishing field rows."""

    node_type = "SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl"
    inputs: dict[str, object] = {
        "positive_prompt": "quality",
        "negative_prompt": "blurry",
        "encode_style": "style",
    }
    scenario = create_visibility_scenario(
        monkeypatch,
        node_name="schedule",
        node_type=node_type,
        inputs=inputs,
        definitions={
            node_type: {
                "input": {
                    "required": {
                        "positive_prompt": ["STRING", {}],
                        "negative_prompt": ["STRING", {}],
                        "encode_style": ["STRING", {}],
                    }
                }
            }
        },
    )
    decision = scenario.snapshot.card_decisions_by_alias["A"]["schedule"]
    assert decision.enabled is True
    assert decision.visible is False
    wrapper = scenario.build()
    try:
        assert wrapper is None
        assert scenario.panel.row_widgets == {}
    finally:
        scenario.destroy(wrapper)


def test_combo_only_node_builds_dropdown_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Render a dropdown row when COMBO is the node's only field."""

    node_type = "UpscaleModelLoader"
    definitions = {
        node_type: {
            "input": {
                "required": {
                    "model_name": [
                        "COMBO",
                        {
                            "options": [
                                "ESRGAN_4x.pth",
                                "R-ESRGAN 4x+ Anime6B.pth",
                            ]
                        },
                    ]
                }
            }
        }
    }
    scenario = create_visibility_scenario(
        monkeypatch,
        node_name="load_upscale_model",
        node_type=node_type,
        inputs={"model_name": "R-ESRGAN 4x+ Anime6B.pth"},
        definitions=definitions,
        use_minimal_field_widget=False,
    )
    wrapper = scenario.build()
    try:
        assert isinstance(wrapper, QWidget)
        assert wrapper.property("has_title_controls") is False
        assert wrapper.property("base_card_visible") is True
        assert ("A", "load_upscale_model", "model_name") in scenario.panel.row_widgets
    finally:
        scenario.destroy(wrapper)

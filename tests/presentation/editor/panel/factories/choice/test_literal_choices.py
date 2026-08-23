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

"""Verify literal and linked choice field factory behavior."""

from __future__ import annotations

from __future__ import annotations
import pytest
import substitute.presentation.editor.panel.factories.choice_factory as choice_factory

from .characterization_support import (
    _FakeChoiceParent,
    _FakeComboBox,
    _FakeNodeDefinitionGateway,
    as_choice_parent,
)


def test_widget_factory_list_str_caps_generic_editor_combo_width(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generic editor combo boxes should receive the standard max hint width."""

    monkeypatch.setattr(choice_factory, "EditorChoiceComboBox", _FakeComboBox)

    combo = choice_factory.widget_factory_list_str(
        parent=as_choice_parent(_FakeChoiceParent()),
        node_name="node",
        key="mode",
        value="Short",
        field_meta={},
        field_type="LIST",
        node_type="CustomNode",
        node_definition_gateway=_FakeNodeDefinitionGateway({}),
        field_info=[
            [
                "Short",
                "An exceptionally long option label that should not widen rows",
            ],
            {},
        ],
    )

    assert isinstance(combo, _FakeComboBox)
    assert combo.max_hint_width == choice_factory._EDITOR_COMBO_MAX_HINT_WIDTH


def test_widget_factory_list_str_sampler_switches_between_link_and_literal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sampler list combobox should prepare link data without mutating node data."""
    monkeypatch.setattr(choice_factory, "EditorChoiceComboBox", _FakeComboBox)
    node_definition_gateway = _FakeNodeDefinitionGateway(
        {
            "KSampler": {
                "KSampler": {
                    "input": {"required": {"sampler_name": [["euler", "heun"]]}}
                }
            }
        },
    )

    parent = _FakeChoiceParent()
    node_data = {
        "inputs": {},
        "sampler_links": [
            {"from_cube": "A", "from_node": "ksampler", "label": "link:A"}
        ],
        "sampler_link": {"from_cube": "A", "from_node": "ksampler"},
        "cube_alias": "B",
    }
    field_meta: dict[str, object] = {"cube_alias": "B", "node_data": node_data}

    combo = choice_factory.widget_factory_list_str(
        parent=as_choice_parent(parent),
        node_name="ksampler",
        key="sampler_name",
        value="euler",
        field_meta=field_meta,
        field_type="LIST",
        node_type="KSampler",
        node_definition_gateway=node_definition_gateway,
    )

    assert isinstance(combo, _FakeComboBox)
    assert combo.current_text == "link:A"
    assert parent.sampler_link_widgets[("B", "ksampler")] is combo
    assert getattr(combo, "_editor_choice_values_by_label")["heun"] == "heun"
    assert getattr(combo, "_editor_choice_values_by_label")["link:A"] == {
        "from_cube": "A",
        "from_node": "ksampler",
    }

    combo.currentTextChanged.emit("heun")
    assert node_data["inputs"] == {}
    assert node_data["sampler_link"] == {"from_cube": "A", "from_node": "ksampler"}

    combo.currentTextChanged.emit("link:A")
    assert node_data["sampler_link"] == {"from_cube": "A", "from_node": "ksampler"}
    assert node_data["inputs"] == {}


def test_widget_factory_list_str_falls_back_to_cube_field_info(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LIST factories should use cube field info when live options are unavailable."""
    monkeypatch.setattr(choice_factory, "EditorChoiceComboBox", _FakeComboBox)
    node_definition_gateway = _FakeNodeDefinitionGateway({})

    combo = choice_factory.widget_factory_list_str(
        parent=as_choice_parent(_FakeChoiceParent()),
        node_name="ksampler",
        key="sampler_name",
        value="heun",
        field_meta={},
        field_type="LIST",
        node_type="KSampler",
        node_definition_gateway=node_definition_gateway,
        field_info=[["euler", "heun"], {"default": "euler"}],
    )

    assert isinstance(combo, _FakeComboBox)
    assert combo.items == ["euler", "heun"]
    assert combo.current_text == "heun"
    assert combo.add_item_calls == 0
    assert combo.add_items_calls == 1


def test_widget_factory_list_str_renders_combo_field_info(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """COMBO fields should render as the same generic dropdown control as LIST fields."""

    monkeypatch.setattr(choice_factory, "EditorChoiceComboBox", _FakeComboBox)
    node_definition_gateway = _FakeNodeDefinitionGateway({})

    combo = choice_factory.widget_factory_list_str(
        parent=as_choice_parent(_FakeChoiceParent()),
        node_name="load_upscale_model",
        key="model_name",
        value="R-ESRGAN 4x+ Anime6B.pth",
        field_meta={},
        field_type="COMBO",
        field_info=[
            "COMBO",
            {
                "options": [
                    "ESRGAN_4x.pth",
                    "R-ESRGAN 4x+ Anime6B.pth",
                ]
            },
        ],
        node_type="UpscaleModelLoader",
        node_definition_gateway=node_definition_gateway,
    )

    assert isinstance(combo, _FakeComboBox)
    assert combo.items == ["ESRGAN_4x.pth", "R-ESRGAN 4x+ Anime6B.pth"]
    assert combo.current_text == "R-ESRGAN 4x+ Anime6B.pth"


def test_widget_factory_list_str_renders_empty_when_no_option_source_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unavailable LIST metadata should render empty without fabricating a choice."""
    monkeypatch.setattr(choice_factory, "EditorChoiceComboBox", _FakeComboBox)
    node_definition_gateway = _FakeNodeDefinitionGateway({})

    combo = choice_factory.widget_factory_list_str(
        parent=as_choice_parent(_FakeChoiceParent()),
        node_name="ksampler",
        key="sampler_name",
        value="euler",
        field_meta={},
        field_type="LIST",
        node_type="KSampler",
        node_definition_gateway=node_definition_gateway,
        field_info=None,
    )

    assert isinstance(combo, _FakeComboBox)
    assert combo.items == []
    assert combo.current_text == ""


def test_widget_factory_list_str_renders_empty_value_without_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LIST factories should admit an empty control when metadata is unavailable."""
    monkeypatch.setattr(choice_factory, "EditorChoiceComboBox", _FakeComboBox)

    combo = choice_factory.widget_factory_list_str(
        parent=as_choice_parent(_FakeChoiceParent()),
        node_name="ksampler",
        key="sampler_name",
        value="",
        field_meta={},
        field_type="LIST",
        node_type="KSampler",
        node_definition_gateway=_FakeNodeDefinitionGateway({}),
        field_info=None,
    )

    assert isinstance(combo, _FakeComboBox)
    assert combo.items == []
    assert combo.current_text == ""


def test_widget_factory_list_str_non_link_fields_use_application_resolved_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-link list widgets should render the effective value chosen upstream."""
    monkeypatch.setattr(choice_factory, "EditorChoiceComboBox", _FakeComboBox)
    node_definition_gateway = _FakeNodeDefinitionGateway(
        {
            "CheckpointLoaderSimple": {
                "CheckpointLoaderSimple": {
                    "input": {
                        "required": {
                            "ckpt_name": [
                                [
                                    "Illustrious\\tNoobnai3_v9.safetensors",
                                    "OtherModel.safetensors",
                                ]
                            ]
                        }
                    }
                }
            }
        }
    )

    combo = choice_factory.widget_factory_list_str(
        parent=as_choice_parent(_FakeChoiceParent()),
        node_name="checkpoint",
        key="ckpt_name",
        value="OtherModel.safetensors",
        field_meta={},
        field_type="LIST",
        node_type="CheckpointLoaderSimple",
        node_definition_gateway=node_definition_gateway,
    )

    assert isinstance(combo, _FakeComboBox)
    assert combo.current_text == "OtherModel.safetensors"


def test_widget_factory_list_str_ultralytics_like_fields_remain_plain_combo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Model-like LIST fields must not receive the picker upgrade by type alone."""

    monkeypatch.setattr(choice_factory, "EditorChoiceComboBox", _FakeComboBox)
    node_definition_gateway = _FakeNodeDefinitionGateway(
        {
            "UltralyticsDetectorProvider": {
                "UltralyticsDetectorProvider": {
                    "input": {
                        "required": {
                            "model_name": [
                                ["bbox/yolo.pt", "segm/yolo-seg.pt"],
                            ]
                        }
                    }
                }
            }
        }
    )

    combo = choice_factory.widget_factory_list_str(
        parent=as_choice_parent(_FakeChoiceParent()),
        node_name="ultralytics",
        key="model_name",
        value="bbox/yolo.pt",
        field_meta={},
        field_type="LIST",
        node_type="UltralyticsDetectorProvider",
        node_definition_gateway=node_definition_gateway,
    )

    assert isinstance(combo, _FakeComboBox)
    assert combo.current_text == "bbox/yolo.pt"


def test_widget_factory_list_str_uses_live_options_for_compact_dynamic_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compact dynamic LIST fields should get their choices from live definitions."""

    monkeypatch.setattr(choice_factory, "EditorChoiceComboBox", _FakeComboBox)
    node_definition_gateway = _FakeNodeDefinitionGateway(
        {
            "KSampler": {
                "KSampler": {
                    "input": {
                        "required": {
                            "sampler_name": [
                                ["euler", "heun"],
                                {"default": "euler"},
                            ]
                        }
                    }
                }
            }
        }
    )

    combo = choice_factory.widget_factory_list_str(
        parent=as_choice_parent(_FakeChoiceParent()),
        node_name="ksampler",
        key="sampler_name",
        value="heun",
        field_meta={"node_data": {"inputs": {"sampler_name": "heun"}}},
        field_type="LIST",
        field_info=["LIST", {"dynamic": True}],
        node_type="KSampler",
        node_definition_gateway=node_definition_gateway,
    )

    assert isinstance(combo, _FakeComboBox)
    assert combo.items == ["euler", "heun"]
    assert combo.current_text == "heun"


def test_widget_factory_list_str_renders_empty_dynamic_marker_without_live_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unavailable dynamic LIST fields must render empty without fake options."""

    monkeypatch.setattr(choice_factory, "EditorChoiceComboBox", _FakeComboBox)

    combo = choice_factory.widget_factory_list_str(
        parent=as_choice_parent(_FakeChoiceParent()),
        node_name="ksampler",
        key="sampler_name",
        value="heun",
        field_meta={
            "options_resolved": False,
            "options_unavailable_reason": "missing_list_options",
        },
        field_type="LIST",
        field_info=["LIST", {"dynamic": True}],
        node_type="KSampler",
        node_definition_gateway=_FakeNodeDefinitionGateway({}),
    )

    assert isinstance(combo, _FakeComboBox)
    assert combo.items == []
    assert combo.current_text == ""

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

"""Verify authored node titles across live locale changes."""

from __future__ import annotations

from typing import cast

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QLineEdit, QWidget
from sugarsubstitute_shared.localization import render_source_application_text

from substitute.application.localization import NodePresentationService
from substitute.domain.localization import (
    NodeCatalogText,
    NodeFieldCatalogText,
    NodeTextCatalog,
    NodeTextCatalogSnapshot,
    NodeTextSource,
)
from substitute.domain.workflow import CubeState
from tests.presentation.editor.node_card.builder_support import build_node_card_builder
from tests.presentation.editor.node_card.support import (
    DefinitionGateway,
    WidgetPanel,
    card_title_text,
    ensure_qapp,
)
from tests.support.node_behavior import build_behavior_snapshot
from tests.support.qt.lifecycle import destroy_qt_object


def test_cube_authored_card_titles_survive_all_live_locale_switches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep SugarCube node identities ahead of localized Comfy control types."""

    ensure_qapp()
    node_type = "PrimitiveStringMultiline"
    nodes = {
        "positive_prompt": {
            "class_type": node_type,
            "inputs": {"value": "初期の正のプロンプト"},
        },
        "negative_prompt": {
            "class_type": node_type,
            "inputs": {"value": "初始负面提示词"},
        },
    }
    buffer = {
        "nodes": nodes,
        "definitions": {},
        "layout": {
            "nodes": {
                "positive_prompt": {"title": "positive prompt"},
                "negative_prompt": {"title": "negative prompt"},
            }
        },
    }
    definitions = {
        node_type: {
            "display_name": "Input Text",
            "description": "Enter text on multiple lines.",
            "input": {
                "required": {
                    "value": [
                        "STRING",
                        {
                            "multiline": True,
                            "tooltip": "Text passed to the workflow.",
                        },
                    ]
                }
            },
        }
    }
    cube_state = CubeState(
        cube_id="SDXL/Text to Image",
        version="1.1.0",
        alias="A",
        original_cube=buffer,
        buffer=buffer,
        ui={},
    )
    panel = WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    behavior_snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
        definitions_by_class=definitions,
    )
    english_catalog = NodeTextCatalog.create(
        language_identifier="en",
        source=NodeTextSource.ENGLISH_COMFY,
        node_definitions={
            node_type: NodeCatalogText(
                display_name="Input Text",
                description="Enter text on multiple lines.",
                inputs={
                    "value": NodeFieldCatalogText(
                        name="Text",
                        tooltip="Text passed to the workflow.",
                    )
                },
                outputs={},
            )
        },
    )
    chinese_catalog = NodeTextCatalog.create(
        language_identifier="zh-Hans",
        source=NodeTextSource.ACTIVE_COMFY,
        node_definitions={
            node_type: NodeCatalogText(
                display_name="字符串（多行）",
                description="输入多行文本。",
                inputs={
                    "value": NodeFieldCatalogText(
                        name="文本",
                        tooltip="传递给工作流的文本。",
                    )
                },
                outputs={},
            )
        },
    )
    japanese_catalog = NodeTextCatalog.create(
        language_identifier="ja",
        source=NodeTextSource.ACTIVE_COMFY,
        node_definitions={
            node_type: NodeCatalogText(
                display_name="文字列（複数行）",
                description="複数行のテキストを入力します。",
                inputs={
                    "value": NodeFieldCatalogText(
                        name="テキスト",
                        tooltip="ワークフローに渡すテキストです。",
                    )
                },
                outputs={},
            )
        },
    )
    active_snapshot = {
        "value": NodeTextCatalogSnapshot(
            effective_language_identifier="en",
            revision=1,
            active_layers=(),
            english_layers=(english_catalog,),
        )
    }
    builder = build_node_card_builder(
        panel,
        DefinitionGateway(definitions),
        node_presentation_service=NodePresentationService(
            lambda: active_snapshot["value"],
            application_text_renderer=render_source_application_text,
        ),
    )
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        lambda **_kwargs: QLineEdit(panel),
    )
    wrappers: dict[str, QWidget] = {}

    try:
        for node_name, node_data in nodes.items():
            node_inputs = cast(dict[str, object], node_data["inputs"])
            wrapper = builder.build_node_card(
                node_name=node_name,
                inputs=node_inputs,
                node_type=node_type,
                field_specs=behavior_snapshot.field_specs_by_alias["A"][node_name],
                cube_state=cube_state,
                resolved_behavior=behavior_snapshot.resolved_nodes_by_alias["A"][
                    node_name
                ],
                display_decision=behavior_snapshot.card_decisions_by_alias["A"][
                    node_name
                ],
                alias="A",
            )
            assert wrapper is not None
            wrappers[node_name] = wrapper

        expected_titles = {
            "positive_prompt": "Positive Prompt",
            "negative_prompt": "Negative Prompt",
        }
        input_widgets = {
            node_name: panel.input_widgets_by_field_key[("A", node_name, "value")]
            for node_name in nodes
        }
        for node_name, wrapper in wrappers.items():
            assert card_title_text(wrapper) == expected_titles[node_name]
            assert wrapper.property("node_title_source") == "authored"
            assert expected_titles[node_name] in wrapper.property("node_search_aliases")

        positive_input = input_widgets["positive_prompt"]
        negative_input = input_widgets["negative_prompt"]
        assert isinstance(positive_input, QLineEdit)
        assert isinstance(negative_input, QLineEdit)
        positive_input.setText("正面提示词とpositive prompt")
        negative_input.setText("負のプロンプト与negative prompt")

        for revision, language, catalog in (
            (2, "zh-Hans", chinese_catalog),
            (3, "ja", japanese_catalog),
            (4, "en", None),
        ):
            active_snapshot["value"] = NodeTextCatalogSnapshot(
                effective_language_identifier=language,
                revision=revision,
                active_layers=() if catalog is None else (catalog,),
                english_layers=(english_catalog,),
            )
            for node_name, wrapper in wrappers.items():
                QCoreApplication.sendEvent(
                    wrapper,
                    QEvent(QEvent.Type.LanguageChange),
                )
                assert card_title_text(wrapper) == expected_titles[node_name]
                assert wrapper.property("node_title_source") == "authored"
                assert (
                    input_widgets[node_name]
                    is panel.input_widgets_by_field_key[("A", node_name, "value")]
                )
            assert positive_input.text() == "正面提示词とpositive prompt"
            assert negative_input.text() == "負のプロンプト与negative prompt"
    finally:
        for wrapper in wrappers.values():
            destroy_qt_object(wrapper)
        destroy_qt_object(panel)

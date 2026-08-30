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

"""Verify live node-card text rebinding without input replacement."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QLineEdit, QWidget
from qfluentwidgets import CaptionLabel  # type: ignore[import-untyped]
from sugarsubstitute_shared.localization import render_source_application_text

from substitute.application.localization import NodePresentationService
from substitute.domain.comfy_workflow.models import DirectWorkflowState
from substitute.domain.localization import (
    NodeCatalogText,
    NodeFieldCatalogText,
    NodeTextCatalog,
    NodeTextCatalogSnapshot,
    NodeTextSource,
)
from tests.presentation.editor.node_card.builder_support import build_node_card_builder
from tests.presentation.editor.node_card.support import (
    DefinitionGateway,
    WidgetPanel,
    ensure_qapp,
    title_row_for,
)
from tests.support.node_behavior import build_behavior_snapshot
from tests.support.qt.lifecycle import destroy_qt_object


def test_node_card_live_locale_switch_rebinds_text_without_rebuilding_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Localize an untitled direct-workflow node without rebuilding its inputs."""

    ensure_qapp()
    node_name = "ksampler"
    node_type = "KSampler"
    definitions = {
        node_type: {
            "display_name": "KSampler",
            "description": "English raw definition",
            "input": {
                "required": {
                    "seed": ["INT", {"tooltip": "English seed tooltip"}],
                    "steps": ["INT", {"tooltip": "English steps tooltip"}],
                }
            },
        }
    }
    nodes = {
        node_name: {
            "class_type": node_type,
            "inputs": {"seed": 1, "steps": 20},
        }
    }
    cube_state = DirectWorkflowState(
        source_path=Path("untitled-workflow.json"),
        source_workflow={"nodes": nodes},
        buffer={"nodes": nodes, "definitions": {}},
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
            "KSampler": NodeCatalogText(
                display_name="KSampler",
                description="English description",
                inputs={
                    "seed": NodeFieldCatalogText(
                        name="seed",
                        tooltip="English seed tooltip",
                    ),
                    "steps": NodeFieldCatalogText(name="steps"),
                },
                outputs={},
            )
        },
    )
    japanese_catalog = NodeTextCatalog.create(
        language_identifier="ja",
        source=NodeTextSource.ACTIVE_COMFY,
        node_definitions={
            "KSampler": NodeCatalogText(
                display_name="Kサンプラー",
                description="提供されたモデルで潜在画像のノイズを除去します。",
                inputs={
                    "seed": NodeFieldCatalogText(
                        name="シード",
                        tooltip="ノイズ生成に使用するランダムシードです。",
                    ),
                    "steps": NodeFieldCatalogText(name="ステップ"),
                },
                outputs={},
            )
        },
    )
    catalog_snapshot = NodeTextCatalogSnapshot(
        effective_language_identifier="ja",
        revision=1,
        active_layers=(japanese_catalog,),
        english_layers=(english_catalog,),
    )
    active_snapshot = {"value": catalog_snapshot}
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

    wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=cast(dict[str, object], nodes[node_name]["inputs"]),
        node_type=node_type,
        field_specs=behavior_snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=behavior_snapshot.resolved_nodes_by_alias["A"][node_name],
        display_decision=behavior_snapshot.card_decisions_by_alias["A"][node_name],
        alias="A",
    )

    try:
        assert wrapper is not None
        labels = {label.text() for label in wrapper.findChildren(CaptionLabel)}
        assert {"Kサンプラー", "シード", "ステップ"} <= labels
        title_row = title_row_for(wrapper)
        assert title_row.toolTip().startswith("提供されたモデル")
        seed_row = panel.row_widgets[("A", node_name, "seed")][1]
        assert isinstance(seed_row, QWidget)
        assert seed_row.toolTip() == "ノイズ生成に使用するランダムシードです。"
        assert wrapper.property("node_title_source") == "active_comfy"
        assert "KSampler" in wrapper.property("node_search_aliases")

        seed_widget = panel.input_widgets_by_field_key[("A", node_name, "seed")]
        assert isinstance(seed_widget, QLineEdit)
        seed_widget.setText("用户入力と日本語")
        chinese_catalog = NodeTextCatalog.create(
            language_identifier="zh-Hans",
            source=NodeTextSource.ACTIVE_COMFY,
            node_definitions={
                "KSampler": NodeCatalogText(
                    display_name="K采样器",
                    description="使用所提供的模型对潜空间图像进行去噪。",
                    inputs={
                        "seed": NodeFieldCatalogText(
                            name="种子",
                            tooltip="用于生成噪声的随机种子。",
                        ),
                        "steps": NodeFieldCatalogText(name="步数"),
                    },
                    outputs={},
                )
            },
        )
        active_snapshot["value"] = NodeTextCatalogSnapshot(
            effective_language_identifier="zh-Hans",
            revision=2,
            active_layers=(chinese_catalog,),
            english_layers=catalog_snapshot.english_layers,
        )

        QCoreApplication.sendEvent(wrapper, QEvent(QEvent.Type.LanguageChange))

        switched_labels = {label.text() for label in wrapper.findChildren(CaptionLabel)}
        assert {"K采样器", "种子", "步数"} <= switched_labels
        assert seed_widget is panel.input_widgets_by_field_key[("A", node_name, "seed")]
        assert seed_widget.text() == "用户入力と日本語"
        assert seed_row.toolTip() == "用于生成噪声的随机种子。"

        active_snapshot["value"] = NodeTextCatalogSnapshot(
            effective_language_identifier="ko",
            revision=3,
            active_layers=(),
            english_layers=catalog_snapshot.english_layers,
        )
        QCoreApplication.sendEvent(wrapper, QEvent(QEvent.Type.LanguageChange))

        fallback_labels = {label.text() for label in wrapper.findChildren(CaptionLabel)}
        assert {"KSampler", "seed", "steps"} <= fallback_labels
        assert wrapper.property("node_title_source") == "english_comfy"
        assert seed_widget is panel.input_widgets_by_field_key[("A", node_name, "seed")]
        assert seed_widget.text() == "用户入力と日本語"
    finally:
        if wrapper is not None:
            destroy_qt_object(wrapper)
        destroy_qt_object(panel)

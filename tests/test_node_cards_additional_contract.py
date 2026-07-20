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

"""Additional characterization tests for node card grouping and switch decisions."""

from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, IconWidget
from sugarsubstitute_shared.localization import render_source_application_text

import substitute.presentation.editor.panel.widgets.node_card as node_card_view
import substitute.presentation.shell.chrome_style as chrome_style
from substitute.application.node_behavior import (
    CardBehavior,
    FieldBehavior,
    FieldPresentation,
    NodeDisplayDecision,
    ResolvedFieldSpec,
    TitleControl,
)
from substitute.application.localization import NodePresentationService
from substitute.domain.comfy_workflow.models import DirectWorkflowState
from substitute.domain.localization import (
    NodeCatalogText,
    NodeFieldCatalogText,
    NodeTextCatalog,
    NodeTextCatalogSnapshot,
    NodeTextSource,
)
from substitute.domain.workflow import CubeState
from substitute.application.prompt_editor import (
    PromptEditorFeatureProfile,
    PromptSyntaxProfile,
)
from substitute.application.display_labels import beautify_label
from substitute.presentation.editor.panel.node_card.accordion_motion import (
    AccordionChevronWidget,
    AccordionContentClip,
)
from substitute.presentation.editor.panel.widgets.field_row import (
    EDITOR_FIELD_ROW_HEIGHT,
    EDITOR_ROW_BODY_SPACING,
    EDITOR_ROW_HEIGHT,
)
from substitute.presentation.editor.panel.field_sync_controller import (
    EditorPanelFieldSyncController,
)
from substitute.presentation.editor.panel.prompt_profile_policy import (
    PanelPromptFieldProfileDecision,
)
from substitute.presentation.editor.panel.node_card_builder import (
    NodeCardPromptFieldInputs,
)
from sugarsubstitute_shared.presentation.fluent_tooltips import FluentToolTipFilter
from tests.node_card_builder_test_helpers import build_node_card_builder
from tests.node_behavior_test_helpers import build_behavior_snapshot
from tests.localization_testing import technical_node_presentation


class _ActivationService:
    """Record node activation commands issued by title-row switch interactions."""

    def __init__(self) -> None:
        """Initialize an empty activation command log."""

        self.calls: list[tuple[object, str, bool | None]] = []

    def set_node_activation_override(
        self,
        cube_state: object,
        node_name: str,
        explicit_enabled: bool | None,
    ) -> None:
        """Record one explicit activation override command."""

        self.calls.append((cube_state, node_name, explicit_enabled))


class _Gateway:
    """Return empty node definitions for deterministic builder tests."""

    @staticmethod
    def get_node_definition(_node_class: str) -> dict[str, object]:
        """Return no live definition payload."""

        return _Gateway.get_required_node_definition(_node_class)

    @staticmethod
    def get_required_node_definition(_node_class: str) -> dict[str, object]:
        """Return no required live definition payload."""

        return {}


class _DefinitionGateway:
    """Return configured live node definitions without external I/O."""

    def __init__(self, definitions: Mapping[str, object]) -> None:
        """Retain the definitions used by behavior and presentation tests."""

        self._definitions = dict(definitions)

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return a Comfy-shaped cached payload for one class type."""

        definition = self._definitions.get(node_class)
        return {node_class: definition} if isinstance(definition, dict) else {}

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return the same deterministic payload for required lookup paths."""

        return self.get_node_definition(node_class)


class _Panel:
    """Minimal panel double required by NodeCardBuilder helpers."""

    def __init__(self) -> None:
        self.cube_id = "Base"
        self._stack_order = []
        self._cube_states = {}
        self.row_widgets = {}
        self.col_widgets = {}

    @staticmethod
    def is_connection(_value) -> bool:
        """Return whether a test value should be treated as a connection."""

        return False


class _WidgetPanel(QWidget):
    """Minimal QWidget-backed panel for full node-card construction tests."""

    def __init__(self) -> None:
        """Initialize panel state consumed by NodeCardBuilder."""

        super().__init__()
        self.cube_id = "Base"
        self._stack_order: list[str] = []
        self._cube_states: dict[str, object] = {}
        self.row_widgets: dict[object, object] = {}
        self.col_widgets: dict[object, object] = {}
        self.input_widgets_by_field_key: dict[tuple[str, str, str], QWidget] = {}
        self.node_behavior_service = _ActivationService()
        self.refresh_reasons: list[str] = []

    @staticmethod
    def is_connection(_value: object) -> bool:
        """Return whether a test value should be treated as a connection."""

        return False

    @staticmethod
    def current_behavior_snapshot() -> None:
        """Return no active behavior snapshot for title-control tests."""

        return None

    def refresh_node_behavior_state(self, *, reason: str) -> None:
        """Record behavior refresh requests issued by title controls."""

        self.refresh_reasons.append(reason)


class _PromptDependencyPanel(_WidgetPanel):
    """Record prompt-only dependency requests made while fields are built."""

    def __init__(self) -> None:
        """Initialize an empty prompt dependency call log."""

        super().__init__()
        self.scheduled_lora_calls: list[tuple[str | None, str, str]] = []
        self.prompt_feature_profile_calls: list[
            tuple[str | None, str, str, dict[str, object]]
        ] = []

    def scheduled_lora_resolver_for_prompt(
        self,
        alias: str | None,
        node_name: str,
        field_key: str,
    ) -> object:
        """Record one scheduled-LoRA resolver request."""

        self.scheduled_lora_calls.append((alias, node_name, field_key))
        return object()

    def prompt_feature_profile_for_prompt(
        self,
        alias: str | None,
        node_name: str,
        field_key: str,
        field_style: Mapping[str, object],
    ) -> object:
        """Record one prompt feature profile request."""

        self.prompt_feature_profile_calls.append(
            (alias, node_name, field_key, dict(field_style))
        )
        return object()


def _ensure_qapp() -> QApplication:
    """Return the shared QApplication used by node-card widget tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _content_layout_for(viewport: QWidget) -> QVBoxLayout:
    """Return the row layout hosted on the moving accordion content surface."""

    assert isinstance(viewport, AccordionContentClip)
    content_layout = viewport.content_widget().layout()
    assert isinstance(content_layout, QVBoxLayout)
    return content_layout


def _accordion_content_attached(widget: QWidget) -> bool:
    """Return the test-visible split-surface attachment state."""

    attached = getattr(widget, "accordion_content_attached", None)
    assert callable(attached)
    return bool(attached())


def _node_card_for(wrapper: QWidget) -> QWidget:
    """Return the node-card surface hosted by one builder wrapper."""

    layout = wrapper.layout()
    assert layout is not None
    node_card = layout.itemAt(0).widget()
    assert node_card is not None
    return node_card


def _title_row_for(wrapper: QWidget) -> QWidget:
    """Return the title row hosted by one builder wrapper."""

    node_card = _node_card_for(wrapper)
    card_layout = node_card.layout()
    assert card_layout is not None
    title_row = card_layout.itemAt(0).widget()
    assert title_row is not None
    return title_row


def _card_title_text(wrapper: QWidget) -> str:
    """Return the sole visible node-card title."""

    title_labels = _title_row_for(wrapper).findChildren(CaptionLabel)
    assert len(title_labels) == 1
    return title_labels[0].text()


def _title_body_divider_for(wrapper: QWidget) -> QWidget:
    """Return the divider between the title row and first body row."""

    content_layout = _content_layout_for(_content_body_for(wrapper))
    divider = content_layout.itemAt(0).widget()
    assert divider is not None
    return divider


def _content_body_for(wrapper: QWidget) -> AccordionContentClip:
    """Return the accordion content clip hosted by a node-card wrapper."""

    node_card = _node_card_for(wrapper)
    card_layout = node_card.layout()
    assert card_layout is not None
    content_body = card_layout.itemAt(1).widget()
    assert isinstance(content_body, AccordionContentClip)
    return content_body


def _row_activation_enabled(title_row: QWidget) -> bool:
    """Return whether a title row exposes row-level activation."""

    enabled = getattr(title_row, "row_activation_enabled", None)
    assert callable(enabled)
    return bool(enabled())


def _release_title_row(title_row: QWidget) -> None:
    """Deliver a deterministic row-release event to a title-row widget."""

    event = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(4, 4),
        QPointF(4, 4),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    title_row.mouseReleaseEvent(event)


def _has_ancestor(widget: QWidget, expected_ancestor: QWidget) -> bool:
    """Return whether one widget is parented below the expected ancestor."""

    parent = widget.parentWidget()
    while parent is not None:
        if parent is expected_ancestor:
            return True
        parent = parent.parentWidget()
    return False


def _title_switch(title_row: QWidget) -> QWidget:
    """Return the enabled switch widget attached to a title row."""

    switch = getattr(title_row, "_enabled_switch_widget", None)
    assert isinstance(switch, QWidget)
    return switch


def _editor_tooltip_filter(widget: QWidget) -> FluentToolTipFilter | None:
    """Return the editor-owned QFluent tooltip filter attached to a widget."""

    tooltip_filter = getattr(widget, "_editor_tooltip_filter", None)
    if tooltip_filter is None:
        return None
    assert isinstance(tooltip_filter, FluentToolTipFilter)
    return tooltip_filter


def _resolved_field_spec(
    *,
    presentation: FieldPresentation,
    value: object = 1,
) -> ResolvedFieldSpec:
    """Return a minimal resolved field spec for field factory tests."""

    return ResolvedFieldSpec(
        cube_alias="A",
        node_name="node",
        class_type="TestNode",
        field_key="text" if presentation == FieldPresentation.PROMPT_BOX else "steps",
        field_type="STRING" if presentation == FieldPresentation.PROMPT_BOX else "INT",
        constraints={},
        meta_info={},
        field_info=None,
        value=value,
        field_behavior=FieldBehavior(
            field_key="text"
            if presentation == FieldPresentation.PROMPT_BOX
            else "steps",
            presentation=presentation,
            style={"prompt_syntaxes": ["wildcard"]}
            if presentation == FieldPresentation.PROMPT_BOX
            else {},
        ),
    )


def test_normal_node_title_rules_preserve_capitalization_without_display_name() -> None:
    """Normal node-card titles should keep project capitalization rules."""

    assert beautify_label("mahiro CFG") == "Mahiro CFG"
    assert beautify_label("vectorscopeCC") == "VectorscopeCC"


def test_node_card_applies_comfy_description_tooltip(monkeypatch) -> None:
    """Node cards should expose the resolved Comfy node description on hover."""

    _ensure_qapp()
    node_name = "ksampler"
    node_type = "KSampler"
    node_tooltip = "Samples an image from latent noise."
    nodes = {
        node_name: {
            "class_type": node_type,
            "inputs": {"steps": 20},
        }
    }
    definitions = {
        node_type: {
            "description": node_tooltip,
            "input": {"required": {"steps": ["INT", {}]}},
        }
    }
    cube_state = SimpleNamespace(buffer={"nodes": nodes, "definitions": {}}, ui={})
    panel = _WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
        definitions_by_class=definitions,
    )
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        lambda **_kwargs: QWidget(panel),
    )

    wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=nodes[node_name]["inputs"],
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=snapshot.resolved_nodes_by_alias["A"][node_name],
        display_decision=snapshot.card_decisions_by_alias["A"][node_name],
        alias="A",
    )

    try:
        assert wrapper is not None
        title_row = _title_row_for(wrapper)
        title_labels = title_row.findChildren(CaptionLabel)
        title_filter = _editor_tooltip_filter(title_row)
        assert title_row.toolTip() == node_tooltip
        assert title_filter is not None
        assert title_filter.eventFilter(
            title_row,
            QEvent(QEvent.Type.ToolTip),
        )
        assert len(title_labels) == 1
        assert title_labels[0].toolTip() == ""
        assert title_filter.eventFilter(
            title_labels[0],
            QEvent(QEvent.Type.ToolTip),
        )
    finally:
        if wrapper is not None:
            wrapper.deleteLater()
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_cube_authored_card_titles_survive_all_live_locale_switches(
    monkeypatch,
) -> None:
    """Keep SugarCube node identities ahead of localized Comfy control types."""

    _ensure_qapp()
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
    panel = _WidgetPanel()
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
        _DefinitionGateway(definitions),
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
            wrapper = builder.build_node_card(
                node_name=node_name,
                inputs=node_data["inputs"],
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
            assert _card_title_text(wrapper) == expected_titles[node_name]
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
                assert _card_title_text(wrapper) == expected_titles[node_name]
                assert wrapper.property("node_title_source") == "authored"
                assert (
                    input_widgets[node_name]
                    is panel.input_widgets_by_field_key[("A", node_name, "value")]
                )
            assert positive_input.text() == "正面提示词とpositive prompt"
            assert negative_input.text() == "負のプロンプト与negative prompt"
    finally:
        for wrapper in wrappers.values():
            wrapper.deleteLater()
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_node_card_live_locale_switch_rebinds_text_without_rebuilding_inputs(
    monkeypatch,
) -> None:
    """Localize an untitled direct-workflow node without rebuilding its inputs."""

    _ensure_qapp()
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
    panel = _WidgetPanel()
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
        _DefinitionGateway(definitions),
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
        inputs=nodes[node_name]["inputs"],
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
        title_row = _title_row_for(wrapper)
        assert title_row.toolTip().startswith("提供されたモデル")
        seed_row = panel.row_widgets[("A", node_name, "seed")][1]
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
            wrapper.deleteLater()
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_node_card_title_widgets_are_born_inside_card_subtree(monkeypatch) -> None:
    """Card-owned title widgets should not be direct editor-panel children."""

    _ensure_qapp()
    node_name = "ksampler"
    node_type = "KSampler"
    nodes = {
        node_name: {
            "class_type": node_type,
            "inputs": {"steps": 20},
        }
    }
    definitions = {
        node_type: {
            "input": {"required": {"steps": ["INT", {}]}},
        }
    }
    cube_state = SimpleNamespace(buffer={"nodes": nodes, "definitions": {}}, ui={})
    panel = _WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
        definitions_by_class=definitions,
    )
    resolved_behavior = snapshot.resolved_nodes_by_alias["A"][node_name]
    resolved_behavior = type(resolved_behavior)(
        node_name=resolved_behavior.node_name,
        class_type=resolved_behavior.class_type,
        card=CardBehavior(
            icon_name="edit",
            title_controls=(TitleControl.ENABLED_SWITCH,),
        ),
        fields=resolved_behavior.fields,
        display_name=resolved_behavior.display_name,
        field_groups=resolved_behavior.field_groups,
    )
    display_decision = NodeDisplayDecision(
        visible=True,
        enabled=True,
        reason="test",
        show_enabled_switch=True,
    )
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        lambda **_kwargs: QWidget(panel),
    )

    wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=nodes[node_name]["inputs"],
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=resolved_behavior,
        display_decision=display_decision,
        alias="A",
    )

    try:
        assert wrapper is not None
        node_card = _node_card_for(wrapper)
        title_row = _title_row_for(wrapper)
        title_icon_slot = title_row.findChild(QWidget, "NodeCardTitleIconSlot")
        chevrons = title_row.findChildren(AccordionChevronWidget)
        enabled_switch_wrapper = getattr(title_row, "_enabled_switch_wrapper", None)

        assert title_row.parentWidget() is node_card
        assert title_icon_slot is not None
        assert title_icon_slot.parentWidget() is title_row
        assert chevrons
        assert chevrons[0].parentWidget() is title_row
        assert isinstance(enabled_switch_wrapper, QWidget)
        assert enabled_switch_wrapper.parentWidget() is title_row
        for card_owned_widget in (
            title_row,
            title_icon_slot,
            chevrons[0],
            enabled_switch_wrapper,
        ):
            assert card_owned_widget.parentWidget() is not panel
            assert _has_ancestor(card_owned_widget, wrapper)
    finally:
        if wrapper is not None:
            wrapper.deleteLater()
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_field_row_applies_comfy_input_tooltip(monkeypatch) -> None:
    """Field rows should expose Comfy input tooltips on row, label, and widget."""

    _ensure_qapp()
    node_name = "ksampler"
    node_type = "KSampler"
    field_tooltip = "Number of denoise steps."
    nodes = {
        node_name: {
            "class_type": node_type,
            "inputs": {"steps": 20},
        }
    }
    definitions = {
        node_type: {
            "input": {
                "required": {
                    "steps": ["INT", {"tooltip": field_tooltip}],
                }
            }
        }
    }
    cube_state = SimpleNamespace(buffer={"nodes": nodes, "definitions": {}}, ui={})
    panel = _WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
        definitions_by_class=definitions,
    )
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        lambda **_kwargs: QWidget(panel),
    )

    wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=nodes[node_name]["inputs"],
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=snapshot.resolved_nodes_by_alias["A"][node_name],
        display_decision=snapshot.card_decisions_by_alias["A"][node_name],
        alias="A",
    )

    try:
        assert wrapper is not None
        field_widget = panel.input_widgets_by_field_key[("A", node_name, "steps")]
        content_layout = _content_layout_for(_content_body_for(wrapper))
        field_row = content_layout.itemAt(1).widget()
        assert field_row is not None
        labels = field_row.findChildren(CaptionLabel)
        row_filter = _editor_tooltip_filter(field_row)
        assert row_filter is not None
        assert field_row.toolTip() == field_tooltip
        assert field_widget.toolTip() == ""
        assert row_filter.eventFilter(field_widget, QEvent(QEvent.Type.ToolTip))
        assert len(labels) == 1
        assert labels[0].toolTip() == ""
        assert row_filter.eventFilter(labels[0], QEvent(QEvent.Type.ToolTip))
    finally:
        if wrapper is not None:
            wrapper.deleteLater()
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_grouped_field_row_keeps_comfy_tooltips_column_specific(monkeypatch) -> None:
    """Grouped field rows should not apply one field tooltip across all columns."""

    _ensure_qapp()
    node_name = "ksampler"
    node_type = "KSampler"
    steps_tooltip = "Number of denoise steps."
    cfg_tooltip = "Classifier-free guidance scale."
    nodes = {
        node_name: {
            "class_type": node_type,
            "inputs": {"steps": 20, "cfg": 7.0},
        }
    }
    definitions = {
        node_type: {
            "input": {
                "required": {
                    "steps": ["INT", {"tooltip": steps_tooltip}],
                    "cfg": ["FLOAT", {"tooltip": cfg_tooltip}],
                }
            }
        }
    }
    cube_state = SimpleNamespace(buffer={"nodes": nodes, "definitions": {}}, ui={})
    panel = _WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
        definitions_by_class=definitions,
    )
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        lambda **_kwargs: QWidget(panel),
    )

    wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=nodes[node_name]["inputs"],
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=snapshot.resolved_nodes_by_alias["A"][node_name],
        display_decision=snapshot.card_decisions_by_alias["A"][node_name],
        alias="A",
    )

    try:
        assert wrapper is not None
        steps_row, steps_col, steps_widget = panel.col_widgets[
            ("A", node_name, "steps")
        ]
        cfg_row, cfg_col, cfg_widget = panel.col_widgets[("A", node_name, "cfg")]
        steps_filter = _editor_tooltip_filter(steps_col)
        cfg_filter = _editor_tooltip_filter(cfg_col)
        assert steps_row is cfg_row
        assert steps_filter is not None
        assert cfg_filter is not None
        assert steps_widget.toolTip() == ""
        assert steps_col.toolTip() == steps_tooltip
        assert steps_filter.eventFilter(steps_widget, QEvent(QEvent.Type.ToolTip))
        assert cfg_widget.toolTip() == ""
        assert cfg_col.toolTip() == cfg_tooltip
        assert cfg_filter.eventFilter(cfg_widget, QEvent(QEvent.Type.ToolTip))
        assert steps_row.toolTip() == ""
        assert _editor_tooltip_filter(steps_row) is None
    finally:
        if wrapper is not None:
            wrapper.deleteLater()
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_non_prompt_field_skips_prompt_only_dependency_requests(monkeypatch) -> None:
    """Scalar field construction should not request prompt-only services."""

    _ensure_qapp()
    panel = _PromptDependencyPanel()
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )
    captured: dict[str, object] = {}

    def fake_factory(**kwargs: object) -> QWidget:
        """Capture prompt dependency arguments passed to the field factory."""

        captured.update(kwargs)
        return QWidget(panel)

    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        fake_factory,
    )
    monkeypatch.setattr(builder, "_wire_widget", lambda *_args: None)

    result: QWidget | None = None
    try:
        result = builder._create_field_for_key(
            node_name="node",
            field_spec=_resolved_field_spec(presentation=FieldPresentation.STANDARD),
            content_body=None,
            content_layout=None,
            allow_unbounded_content_height=False,
            cube_state=SimpleNamespace(buffer={"nodes": {"node": {"inputs": {}}}}),
            alias="A",
            field_presentation=technical_node_presentation(
                node_name="node",
                class_type="TestNode",
                field_keys=("steps",),
            ).fields["steps"],
        )

        assert isinstance(result, QWidget)
        assert panel.scheduled_lora_calls == []
        assert panel.prompt_feature_profile_calls == []
        assert captured["scheduled_lora_resolver"] is None
        assert captured["prompt_feature_profile"] is None
        assert captured["prompt_syntax_profile"] is None
    finally:
        if result is not None:
            result.deleteLater()
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_prompt_field_receives_prompt_only_dependencies(monkeypatch) -> None:
    """Prompt field construction should consume prepared prompt dependencies."""

    _ensure_qapp()
    panel = _PromptDependencyPanel()
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )
    captured: dict[str, object] = {}

    def fake_factory(**kwargs: object) -> QWidget:
        """Capture prompt dependency arguments passed to the field factory."""

        captured.update(kwargs)
        return QWidget(panel)

    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        fake_factory,
    )
    monkeypatch.setattr(builder, "_wire_widget", lambda *_args: None)
    prompt_feature_profile = PromptEditorFeatureProfile.enabled_profile(())
    prompt_syntax_profile = PromptSyntaxProfile(enabled_syntaxes=())
    prompt_field_profile = PanelPromptFieldProfileDecision(
        feature_profile=prompt_feature_profile,
        syntax_profile=prompt_syntax_profile,
    )

    def scheduled_lora_resolver(_text: str) -> tuple[object, ...]:
        """Return no scheduled LoRAs for the prepared resolver sentinel."""

        return ()

    result: QWidget | None = None
    try:
        result = builder._create_field_for_key(
            node_name="node",
            field_spec=_resolved_field_spec(
                presentation=FieldPresentation.PROMPT_BOX,
                value="prompt text",
            ),
            content_body=None,
            content_layout=None,
            allow_unbounded_content_height=False,
            cube_state=SimpleNamespace(buffer={"nodes": {"node": {"inputs": {}}}}),
            alias="A",
            field_presentation=technical_node_presentation(
                node_name="node",
                class_type="TestNode",
                field_keys=("text",),
            ).fields["text"],
            prompt_field_inputs={
                "text": NodeCardPromptFieldInputs(
                    scheduled_lora_resolver=scheduled_lora_resolver,
                    prompt_field_profile=prompt_field_profile,
                )
            },
        )

        assert isinstance(result, QWidget)
        assert panel.scheduled_lora_calls == []
        assert panel.prompt_feature_profile_calls == []
        assert captured["scheduled_lora_resolver"] is scheduled_lora_resolver
        assert captured["prompt_feature_profile"] is prompt_feature_profile
        assert captured["prompt_syntax_profile"] is prompt_syntax_profile
    finally:
        if result is not None:
            result.deleteLater()
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_node_card_background_color_uses_requested_light_surface(
    monkeypatch,
) -> None:
    """Light-theme node cards should use the WinUI card fill token."""

    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: False)

    assert node_card_view._node_card_background_color() == QColor(255, 255, 255, 179)


def test_node_card_background_color_uses_stronger_acrylic_surface(
    monkeypatch,
) -> None:
    """Acrylic node cards should raise the shared card-fill opacity."""

    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: False)
    acrylic_parent = SimpleNamespace(
        window=lambda: SimpleNamespace(_backdrop_mode="acrylic")
    )

    assert node_card_view._node_card_background_color(acrylic_parent) == QColor(
        255,
        255,
        255,
        224,
    )


def test_node_card_border_color_uses_requested_light_surface(
    monkeypatch,
) -> None:
    """Light-theme node cards should use the WinUI card stroke token."""

    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: False)

    assert node_card_view._node_card_border_color() == QColor(0, 0, 0, 15)


def test_attached_content_surface_does_not_repaint_shared_top_stroke(
    monkeypatch,
) -> None:
    """Attached content surfaces should not double-paint the title/body edge."""

    _ensure_qapp()
    fill = QColor(10, 20, 30, 255)
    stroke = QColor(240, 230, 220, 255)
    monkeypatch.setattr(
        node_card_view,
        "_node_card_background_color",
        lambda _widget=None: fill,
    )
    monkeypatch.setattr(node_card_view, "_node_card_border_color", lambda: stroke)

    surface = node_card_view._NodeCardContentSurface()
    surface.set_accordion_content_attached(True)
    surface.resize(24, 24)
    image = QImage(24, 24, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    try:
        surface.render(painter, QPoint(0, 0))
    finally:
        painter.end()
        surface.deleteLater()
        _ensure_qapp().processEvents()

    assert image.pixelColor(12, 0) == fill
    assert image.pixelColor(23, 12) != fill


def test_attached_header_surface_does_not_paint_body_seam_stroke(
    monkeypatch,
) -> None:
    """Attached header surfaces should leave the body seam to the divider widget."""

    _ensure_qapp()
    fill = QColor(10, 20, 30, 255)
    stroke = QColor(240, 230, 220, 255)
    monkeypatch.setattr(
        node_card_view,
        "_node_card_background_color",
        lambda _widget=None: fill,
    )
    monkeypatch.setattr(node_card_view, "_node_card_border_color", lambda: stroke)

    surface = node_card_view._NodeCardHeaderSurface()
    surface.set_accordion_content_attached(True)
    surface.resize(24, 24)
    image = QImage(24, 24, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    try:
        surface.render(painter, QPoint(0, 0))
    finally:
        painter.end()
        surface.deleteLater()
        _ensure_qapp().processEvents()

    assert image.pixelColor(12, 23) == fill
    assert image.pixelColor(12, 0) != fill


def test_gather_visible_keys_prefers_override_groups_in_discovery_order() -> None:
    """Resolved field groups should be emitted in input discovery order."""
    builder = build_node_card_builder(
        _Panel(),
        _Gateway(),
    )
    input_keys = ["steps", "foo", "scheduler", "sampler_name", "cfg"]
    groups = builder._gather_visible_keys(
        input_keys=input_keys,
        skip_keys=set(),
        resolved_behavior=SimpleNamespace(
            field_groups=(("sampler_name", "scheduler"), ("steps", "cfg"))
        ),
    )

    assert groups == [["steps", "cfg"], ["foo"], ["sampler_name", "scheduler"]]


def test_gather_visible_keys_uses_inferred_common_groups_without_overrides() -> None:
    """Common grouping should remain for KSampler with no custom groups."""
    builder = build_node_card_builder(
        _Panel(),
        _Gateway(),
    )
    input_keys = ["steps", "cfg", "sampler_name", "scheduler", "seed"]
    cube = SimpleNamespace(
        buffer={
            "nodes": {
                "ksampler": {
                    "class_type": "KSampler",
                    "inputs": {
                        "steps": 20,
                        "cfg": 7.0,
                        "sampler_name": "euler",
                        "scheduler": "normal",
                    },
                }
            },
            "definitions": {},
        },
        ui={},
    )
    resolved_behavior = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
    ).resolved_nodes_by_alias["A"]["ksampler"]

    groups = builder._gather_visible_keys(
        input_keys=input_keys,
        skip_keys=set(),
        resolved_behavior=resolved_behavior,
    )

    assert groups == [["steps", "cfg"], ["sampler_name", "scheduler"], ["seed"]]


def test_gather_visible_keys_groups_inferred_dimension_pair() -> None:
    """Resolved dimension groups should become one multi-column card row."""

    builder = build_node_card_builder(
        _Panel(),
        _Gateway(),
    )
    cube = SimpleNamespace(
        buffer={
            "nodes": {
                "resize": {
                    "class_type": "CustomResize",
                    "inputs": {
                        "mode": "fit",
                        "source_width": 512,
                        "source_height": 768,
                    },
                }
            },
            "definitions": {},
        },
        ui={},
    )
    resolved_behavior = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
    ).resolved_nodes_by_alias["A"]["resize"]

    groups = builder._gather_visible_keys(
        input_keys=["mode", "source_width", "source_height"],
        skip_keys=set(),
        resolved_behavior=resolved_behavior,
    )

    assert groups == [["mode"], ["source_width", "source_height"]]


def test_detailer_steps_cfg_build_as_grouped_card_row(monkeypatch) -> None:
    """DetailerForEach steps and cfg should render through the grouped-row path."""

    _ensure_qapp()
    node_name = "detailer_segs"
    node_type = "DetailerForEach"
    definitions = {
        node_type: {
            "input": {
                "required": {
                    "steps": ["INT"],
                    "cfg": ["FLOAT"],
                }
            }
        }
    }
    nodes = {
        node_name: {
            "class_type": node_type,
            "inputs": {
                "steps": 8,
                "cfg": 7.0,
            },
        }
    }
    cube_state = SimpleNamespace(
        buffer={"nodes": nodes, "definitions": definitions},
        ui={},
    )
    panel = _WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
        definitions_by_class=definitions,
    )
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )

    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        lambda **_kwargs: QWidget(panel),
    )

    wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=nodes[node_name]["inputs"],
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=snapshot.resolved_nodes_by_alias["A"][node_name],
        display_decision=snapshot.card_decisions_by_alias["A"][node_name],
        alias="A",
    )

    try:
        assert wrapper is not None
        assert snapshot.resolved_nodes_by_alias["A"][node_name].field_groups == (
            ("steps", "cfg"),
        )
        steps_key = ("A", node_name, "steps")
        cfg_key = ("A", node_name, "cfg")
        assert steps_key in panel.col_widgets
        assert cfg_key in panel.col_widgets
        assert panel.col_widgets[steps_key][0] is panel.col_widgets[cfg_key][0]

        content_layout = _content_layout_for(_content_body_for(wrapper))
        assert content_layout.count() == 2
    finally:
        if wrapper is not None:
            wrapper.deleteLater()
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_gather_visible_keys_keeps_unmatched_dimensions_as_single_rows() -> None:
    """Mixed dimension stems should not become grouped card rows."""

    builder = build_node_card_builder(
        _Panel(),
        _Gateway(),
    )
    cube = SimpleNamespace(
        buffer={
            "nodes": {
                "resize": {
                    "class_type": "CustomResize",
                    "inputs": {
                        "source_width": 512,
                        "target_height": 768,
                    },
                }
            },
            "definitions": {},
        },
        ui={},
    )
    resolved_behavior = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
    ).resolved_nodes_by_alias["A"]["resize"]

    groups = builder._gather_visible_keys(
        input_keys=["source_width", "target_height"],
        skip_keys=set(),
        resolved_behavior=resolved_behavior,
    )

    assert groups == [["source_width"], ["target_height"]]


def test_should_add_enabled_switch_defaults_off_when_resolver_undecided() -> None:
    """Resolved behavior should omit enabled-switch controls for non-policy nodes."""
    cube_state = SimpleNamespace(
        buffer={
            "nodes": {},
            "definitions": {"CustomPatch": {"input": {}, "output": []}},
        },
        ui={},
    )
    cube_state.buffer["nodes"]["patch"] = {"class_type": "CustomPatch", "inputs": {}}
    resolved = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
        definitions_by_class={
            "CustomPatch": cube_state.buffer["definitions"]["CustomPatch"]
        },
    ).resolved_nodes_by_alias["A"]["patch"]

    assert TitleControl.ENABLED_SWITCH not in resolved.card.title_controls


def test_checkpoint_behavior_switch_policy_uses_authored_bypass() -> None:
    """Checkpoint switch visibility should come from authored bypass decisions."""
    panel = _Panel()
    cube_a = SimpleNamespace(
        buffer={
            "nodes": {"ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {}}},
            "definitions": {},
        },
        ui={},
    )
    cube_b = SimpleNamespace(
        buffer={
            "nodes": {
                "ckpt": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {},
                    "mode": 4,
                }
            },
            "definitions": {},
        },
        ui={},
    )
    panel._stack_order = ["A", "B"]
    panel._cube_states = {"A": cube_a, "B": cube_b}
    snapshot = build_behavior_snapshot(
        cube_states=panel._cube_states,
        stack_order=["A", "B"],
    )

    assert (
        TitleControl.ENABLED_SWITCH
        not in snapshot.resolved_nodes_by_alias["A"]["ckpt"].card.title_controls
    )
    assert (
        TitleControl.ENABLED_SWITCH
        not in snapshot.resolved_nodes_by_alias["B"]["ckpt"].card.title_controls
    )
    assert snapshot.card_decisions_by_alias["A"]["ckpt"].show_enabled_switch is False
    assert snapshot.card_decisions_by_alias["B"]["ckpt"].show_enabled_switch is True


def test_node_card_build_failure_does_not_leave_panel_child_surfaces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failed card builds should not leave partial surfaces at panel origin."""

    _ensure_qapp()
    node_name = "loader"
    node_type = "ModelLoader"
    nodes = {
        node_name: {
            "class_type": node_type,
            "inputs": {"steps": 12},
        }
    }
    cube_state = SimpleNamespace(
        buffer={"nodes": nodes, "definitions": {}},
        ui={},
    )
    panel = _WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
        definitions_by_class={
            node_type: {
                "input": {
                    "required": {
                        "steps": ["INT", {"default": 20}],
                    }
                }
            }
        },
    )
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )

    def fail_widget_build(**_kwargs: object) -> QWidget:
        """Raise after node-card surfaces have been allocated."""

        raise RuntimeError("forced field build failure")

    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        fail_widget_build,
    )

    with pytest.raises(RuntimeError, match="forced field build failure"):
        builder.build_node_card(
            node_name=node_name,
            inputs=nodes[node_name]["inputs"],
            node_type=node_type,
            field_specs=snapshot.field_specs_by_alias["A"][node_name],
            cube_state=cube_state,
            resolved_behavior=snapshot.resolved_nodes_by_alias["A"][node_name],
            display_decision=snapshot.card_decisions_by_alias["A"][node_name],
            alias="A",
        )

    direct_children = [
        child for child in panel.findChildren(QWidget) if child.parentWidget() is panel
    ]
    assert direct_children == []
    panel.deleteLater()
    _ensure_qapp().processEvents()


def test_node_card_title_row_uses_shared_editor_row_geometry(monkeypatch) -> None:
    """Node-card titles should share fixed editor-row sizing with scalar rows."""

    _ensure_qapp()
    node_name = "ksampler"
    node_type = "KSampler"
    nodes = {
        node_name: {
            "class_type": node_type,
            "inputs": {"steps": 12},
        }
    }
    cube_state = SimpleNamespace(
        buffer={"nodes": nodes, "definitions": {}},
        ui={},
    )
    panel = _WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
    )
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )

    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        lambda **_kwargs: QWidget(panel),
    )

    wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=nodes[node_name]["inputs"],
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=snapshot.resolved_nodes_by_alias["A"][node_name],
        display_decision=snapshot.card_decisions_by_alias["A"][node_name],
        alias="A",
    )

    assert wrapper is not None
    host = QWidget()
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(wrapper)
    host.resize(400, wrapper.sizeHint().height())
    host.show()
    _ensure_qapp().processEvents()
    try:
        node_card = wrapper.layout().itemAt(0).widget()
        assert node_card is not None
        card_layout = node_card.layout()
        assert card_layout.spacing() == 0
        title_row = card_layout.itemAt(0).widget()
        assert title_row is not None
        assert title_row.objectName() == "NodeCardHeaderSurface"
        title_layout = title_row.layout()
        assert title_layout is not None
        title_body_divider = _title_body_divider_for(wrapper)
        content_body = _content_body_for(wrapper)
        assert content_body.objectName() == "NodeCardContentClip"
        assert content_body.content_widget().objectName() == "NodeCardContentSurface"
        content_layout = _content_layout_for(content_body)
        scalar_row = content_layout.itemAt(1).widget()
        assert scalar_row is not None

        title_icon_slot = title_layout.itemAt(0).widget()
        assert title_icon_slot is not None
        title_icon = title_icon_slot.findChild(IconWidget, "NodeCardTitleIcon")
        assert title_icon is not None
        title_labels = title_row.findChildren(CaptionLabel)
        chevrons = title_row.findChildren(AccordionChevronWidget)

        assert title_row.minimumHeight() == node_card_view.NODE_CARD_TITLE_HEIGHT
        assert title_row.maximumHeight() == node_card_view.NODE_CARD_TITLE_HEIGHT
        assert title_row.height() == node_card_view.NODE_CARD_TITLE_HEIGHT
        assert title_layout.contentsMargins().top() == EDITOR_ROW_BODY_SPACING
        assert title_layout.contentsMargins().bottom() == EDITOR_ROW_BODY_SPACING
        assert title_icon_slot.width() == node_card_view.NODE_CARD_TITLE_ICON_SLOT_SIZE
        assert title_icon_slot.height() == node_card_view.NODE_CARD_TITLE_ICON_SLOT_SIZE
        assert title_icon.width() == node_card_view.NODE_CARD_TITLE_ICON_SIZE
        assert title_icon.height() == node_card_view.NODE_CARD_TITLE_ICON_SIZE
        assert len(title_labels) == 1
        assert title_labels[0].font().pixelSize() == 14
        assert len(chevrons) == 1
        assert title_row.cursor().shape() == Qt.CursorShape.PointingHandCursor
        assert _accordion_content_attached(title_row) is True
        assert _accordion_content_attached(content_body.content_widget()) is True
        assert title_body_divider.objectName() == "NodeCardTitleBodyDivider"
        assert title_body_divider.property("title_body_divider") is True
        assert title_body_divider.height() == 1
        assert content_body.content_overlap_y() == 0
        assert node_card_view.NODE_CARD_BODY_TOP_PADDING == 0
        assert (
            content_layout.contentsMargins().top()
            == node_card_view.NODE_CARD_BODY_TOP_PADDING
        )
        assert (
            content_layout.contentsMargins().bottom()
            == node_card_view.NODE_CARD_BODY_BOTTOM_PADDING
        )
        assert content_layout.spacing() == node_card_view.NODE_CARD_BODY_ROW_SPACING
        assert scalar_row.y() == node_card_view.NODE_CARD_BODY_TOP_PADDING + 1
        assert scalar_row.height() == EDITOR_FIELD_ROW_HEIGHT
    finally:
        host.close()
        host.deleteLater()
        panel.deleteLater()
        _ensure_qapp().processEvents()


@pytest.mark.skipif(
    bool(os.environ.get("PYTEST_XDIST_WORKER")),
    reason="real Qt mouse delivery is verified in serial outside xdist",
)
def test_collapsible_node_card_title_row_exposes_row_activation(
    monkeypatch,
) -> None:
    """Collapsible title rows should expose feedback and preserve accordion toggling."""

    app = _ensure_qapp()
    node_name = "ksampler"
    node_type = "KSampler"
    nodes = {
        node_name: {
            "class_type": node_type,
            "inputs": {"steps": 12},
        }
    }
    cube_state = SimpleNamespace(
        buffer={"nodes": nodes, "definitions": {}},
        ui={},
    )
    panel = _WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
    )
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        lambda **_kwargs: QWidget(panel),
    )

    wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=nodes[node_name]["inputs"],
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=snapshot.resolved_nodes_by_alias["A"][node_name],
        display_decision=snapshot.card_decisions_by_alias["A"][node_name],
        alias="A",
    )

    assert wrapper is not None
    host = QWidget()
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(wrapper)
    host.show()
    app.processEvents()
    try:
        title_row = _title_row_for(wrapper)
        content_body = _content_body_for(wrapper)
        assert _row_activation_enabled(title_row) is True
        assert title_row.cursor().shape() == Qt.CursorShape.PointingHandCursor
        assert content_body.maximumHeight() > 0

        QTest.mouseClick(title_row, Qt.MouseButton.LeftButton, pos=QPoint(4, 4))
        QTest.qWait(260)
        app.processEvents()

        assert content_body.maximumHeight() == 0
    finally:
        host.close()
        host.deleteLater()
        panel.deleteLater()
        app.processEvents()


def test_title_only_enabled_switch_row_exposes_row_activation() -> None:
    """Title-only activation-switch cards should light up and toggle from row clicks."""

    app = _ensure_qapp()
    node_name = "vae_override"
    node_type = "VAELoader"
    nodes = {node_name: {"class_type": node_type, "inputs": {}, "mode": 4}}
    cube_state = SimpleNamespace(
        buffer={"nodes": nodes, "definitions": {}},
        ui={},
    )
    panel = _WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
    )
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )

    wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=nodes[node_name]["inputs"],
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=snapshot.resolved_nodes_by_alias["A"][node_name],
        display_decision=snapshot.card_decisions_by_alias["A"][node_name],
        alias="A",
    )

    assert wrapper is not None
    host = QWidget()
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(wrapper)
    host.show()
    app.processEvents()
    try:
        node_card = _node_card_for(wrapper)
        title_row = _title_row_for(wrapper)
        switch = _title_switch(title_row)

        assert node_card.layout().count() == 1
        assert title_row.findChildren(AccordionChevronWidget) == []
        assert _row_activation_enabled(title_row) is True
        assert title_row.cursor().shape() == Qt.CursorShape.PointingHandCursor

        _release_title_row(title_row)
        app.processEvents()

        is_checked = getattr(switch, "isChecked", None)
        assert callable(is_checked)
        assert bool(is_checked()) is True
        assert panel.node_behavior_service.calls == [(cube_state, node_name, True)]
        assert panel.refresh_reasons == ["node_activation_changed"]
    finally:
        host.close()
        host.deleteLater()
        panel.deleteLater()
        app.processEvents()


@pytest.mark.skipif(
    bool(os.environ.get("PYTEST_XDIST_WORKER")),
    reason="real Qt mouse delivery is verified in serial outside xdist",
)
def test_row_click_prefers_accordion_when_title_row_also_has_switch(
    monkeypatch,
) -> None:
    """Accordion title-row clicks should not toggle a visible switch on the same row."""

    app = _ensure_qapp()
    node_name = "vectorscopecc"
    node_type = "VectorscopeCC"
    nodes = {
        node_name: {
            "class_type": node_type,
            "inputs": {"brightness": 0.25, "contrast": 0.0},
        }
    }
    cube_a = SimpleNamespace(buffer={"nodes": nodes, "definitions": {}}, ui={})
    cube_b = SimpleNamespace(buffer={"nodes": nodes, "definitions": {}}, ui={})
    panel = _WidgetPanel()
    panel._stack_order = ["A", "B"]
    panel._cube_states = {"A": cube_a, "B": cube_b}
    snapshot = build_behavior_snapshot(
        cube_states=panel._cube_states,
        stack_order=["A", "B"],
    )
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        lambda **_kwargs: QWidget(panel),
    )

    wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=nodes[node_name]["inputs"],
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["B"][node_name],
        cube_state=cube_b,
        resolved_behavior=snapshot.resolved_nodes_by_alias["B"][node_name],
        display_decision=snapshot.card_decisions_by_alias["B"][node_name],
        alias="B",
    )

    assert wrapper is not None
    host = QWidget()
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(wrapper)
    host.show()
    app.processEvents()
    try:
        title_row = _title_row_for(wrapper)
        content_body = _content_body_for(wrapper)
        switch = _title_switch(title_row)
        is_checked = getattr(switch, "isChecked", None)
        assert callable(is_checked)
        assert bool(is_checked()) is True

        QTest.mouseClick(title_row, Qt.MouseButton.LeftButton, pos=QPoint(4, 4))
        QTest.qWait(260)
        app.processEvents()

        assert content_body.maximumHeight() == 0
        assert bool(is_checked()) is True
        assert panel.node_behavior_service.calls == []

        switch_target = getattr(switch, "indicator", switch)
        assert isinstance(switch_target, QWidget)
        QTest.mouseClick(switch_target, Qt.MouseButton.LeftButton)
        app.processEvents()

        assert bool(is_checked()) is False
        assert panel.node_behavior_service.calls == [(cube_b, node_name, False)]
    finally:
        host.close()
        host.deleteLater()
        panel.deleteLater()
        app.processEvents()


def test_grouped_node_card_rows_use_shared_body_spacing(monkeypatch) -> None:
    """Grouped node-card rows should use the tightened body rhythm contract."""

    _ensure_qapp()
    node_name = "ksampler"
    node_type = "KSampler"
    nodes = {
        node_name: {
            "class_type": node_type,
            "inputs": {"steps": 12, "cfg": 6.5},
        }
    }
    cube_state = SimpleNamespace(
        buffer={"nodes": nodes, "definitions": {}},
        ui={},
    )
    panel = _WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
    )
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )

    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        lambda **_kwargs: QWidget(panel),
    )

    wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=nodes[node_name]["inputs"],
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=snapshot.resolved_nodes_by_alias["A"][node_name],
        display_decision=snapshot.card_decisions_by_alias["A"][node_name],
        alias="A",
    )

    assert wrapper is not None
    host = QWidget()
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(wrapper)
    host.resize(400, wrapper.sizeHint().height())
    host.show()
    _ensure_qapp().processEvents()
    try:
        node_card = wrapper.layout().itemAt(0).widget()
        assert node_card is not None
        card_layout = node_card.layout()
        assert card_layout.spacing() == 0
        content_body = _content_body_for(wrapper)
        assert content_body.objectName() == "NodeCardContentClip"
        assert content_body.content_widget().objectName() == "NodeCardContentSurface"
        content_layout = _content_layout_for(content_body)
        grouped_row = content_layout.itemAt(1).widget()
        assert grouped_row is not None
        grouped_layout = grouped_row.layout()
        assert grouped_layout is not None
        divider = grouped_layout.itemAt(1).widget()
        assert divider is not None

        assert content_body.content_overlap_y() == 0
        assert node_card_view.NODE_CARD_BODY_TOP_PADDING == 0
        assert (
            content_layout.contentsMargins().top()
            == node_card_view.NODE_CARD_BODY_TOP_PADDING
        )
        assert (
            content_layout.contentsMargins().bottom()
            == node_card_view.NODE_CARD_BODY_BOTTOM_PADDING
        )
        assert content_layout.spacing() == node_card_view.NODE_CARD_BODY_ROW_SPACING
        assert grouped_row.y() == node_card_view.NODE_CARD_BODY_TOP_PADDING + 1
        assert grouped_row.height() == EDITOR_FIELD_ROW_HEIGHT
        assert divider.height() == EDITOR_ROW_HEIGHT
        assert divider.minimumHeight() == EDITOR_ROW_HEIGHT
        assert divider.maximumHeight() == EDITOR_ROW_HEIGHT
    finally:
        host.close()
        host.deleteLater()
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_node_card_body_inserts_dividers_only_between_rows(monkeypatch) -> None:
    """Node-card body composition should separate the title seam from row dividers."""

    _ensure_qapp()
    node_name = "vectorscopecc"
    node_type = "VectorscopeCC"
    nodes = {
        node_name: {
            "class_type": node_type,
            "inputs": {"brightness": 0.05, "contrast": 0.0},
        }
    }
    cube_state = SimpleNamespace(
        buffer={"nodes": nodes, "definitions": {}},
        ui={},
    )
    panel = _WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
    )
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )

    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        lambda **_kwargs: QWidget(panel),
    )

    wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=nodes[node_name]["inputs"],
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=snapshot.resolved_nodes_by_alias["A"][node_name],
        display_decision=snapshot.card_decisions_by_alias["A"][node_name],
        alias="A",
    )

    assert wrapper is not None
    host = QWidget()
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(wrapper)
    host.resize(400, wrapper.sizeHint().height())
    host.show()
    _ensure_qapp().processEvents()
    try:
        content_body = _content_body_for(wrapper)
        content_layout = _content_layout_for(content_body)
        title_body_divider = content_layout.itemAt(0).widget()
        first_row = content_layout.itemAt(1).widget()
        divider = content_layout.itemAt(2).widget()
        second_row = content_layout.itemAt(3).widget()
        assert title_body_divider is not None
        assert first_row is not None
        assert divider is not None
        assert second_row is not None

        assert content_body.content_widget().y() == 0
        assert title_body_divider.objectName() == "NodeCardTitleBodyDivider"
        assert title_body_divider.property("title_body_divider") is True
        assert title_body_divider.height() == 1
        assert content_layout.contentsMargins().top() == (
            node_card_view.NODE_CARD_BODY_TOP_PADDING
        )
        assert first_row.y() == node_card_view.NODE_CARD_BODY_TOP_PADDING + 1
        assert first_row.height() == EDITOR_FIELD_ROW_HEIGHT
        assert first_row.property("divider_for_field") is None
        assert tuple(divider.property("divider_for_field")) == (
            "A",
            node_name,
            "contrast",
        )
        assert divider.height() == 1
        assert second_row.y() == (
            node_card_view.NODE_CARD_BODY_TOP_PADDING
            + 1
            + EDITOR_FIELD_ROW_HEIGHT
            + 1
            + node_card_view.NODE_CARD_BODY_ROW_SPACING
        )
        assert panel.row_widgets[("A", node_name, "brightness")][0] is None
        assert panel.row_widgets[("A", node_name, "contrast")][0] is divider
    finally:
        host.close()
        host.deleteLater()
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_hidden_first_body_row_does_not_leave_visible_leading_divider(
    monkeypatch,
) -> None:
    """Hidden first rows should only leave the authoritative title/body divider."""

    _ensure_qapp()
    node_name = "vectorscopecc"
    node_type = "VectorscopeCC"
    nodes = {
        node_name: {
            "class_type": node_type,
            "inputs": {"brightness": 0.05, "contrast": 0.0},
        }
    }
    cube_state = SimpleNamespace(
        buffer={"nodes": nodes, "definitions": {}},
        ui={},
    )
    panel = _WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
    )
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )

    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        lambda **_kwargs: QWidget(panel),
    )

    wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=nodes[node_name]["inputs"],
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=snapshot.resolved_nodes_by_alias["A"][node_name],
        display_decision=snapshot.card_decisions_by_alias["A"][node_name],
        alias="A",
    )

    assert wrapper is not None
    host = QWidget()
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(wrapper)
    host.resize(400, wrapper.sizeHint().height())
    host.show()
    _ensure_qapp().processEvents()
    try:
        EditorPanelFieldSyncController(panel).apply_hidden_field_keys(
            {("A", node_name, "brightness")}
        )
        _ensure_qapp().processEvents()

        content_body = _content_body_for(wrapper)
        content_layout = _content_layout_for(content_body)
        title_body_divider = content_layout.itemAt(0).widget()
        hidden_first_row = content_layout.itemAt(1).widget()
        leading_divider = content_layout.itemAt(2).widget()
        first_visible_row = content_layout.itemAt(3).widget()
        assert title_body_divider is not None
        assert hidden_first_row is not None
        assert leading_divider is not None
        assert first_visible_row is not None

        assert not title_body_divider.isHidden()
        assert hidden_first_row.isHidden()
        assert leading_divider.isHidden()
        assert not first_visible_row.isHidden()
        assert first_visible_row.y() == 1
    finally:
        host.close()
        host.deleteLater()
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_ksampler_hidden_leading_group_does_not_leave_title_seam_divider(
    monkeypatch,
) -> None:
    """Hidden leading groups should keep only the title/body divider visible."""

    _ensure_qapp()
    node_name = "ksampler"
    node_type = "KSampler"
    definitions = {
        node_type: {
            "input": {
                "required": {
                    "sampler_name": ["STRING"],
                    "scheduler": ["STRING"],
                    "steps": ["INT"],
                    "cfg": ["FLOAT"],
                }
            }
        }
    }
    nodes = {
        node_name: {
            "class_type": node_type,
            "inputs": {
                "sampler_name": "euler",
                "scheduler": "normal",
                "steps": 28,
                "cfg": 5.5,
            },
        }
    }
    cube_state = SimpleNamespace(
        buffer={"nodes": nodes, "definitions": definitions},
        ui={},
    )
    panel = _WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
        definitions_by_class=definitions,
    )
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )

    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        lambda **_kwargs: QWidget(panel),
    )

    wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=nodes[node_name]["inputs"],
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=snapshot.resolved_nodes_by_alias["A"][node_name],
        display_decision=snapshot.card_decisions_by_alias["A"][node_name],
        alias="A",
    )

    assert wrapper is not None
    host = QWidget()
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(wrapper)
    host.resize(400, wrapper.sizeHint().height())
    host.show()
    _ensure_qapp().processEvents()
    try:
        EditorPanelFieldSyncController(panel).apply_hidden_field_keys(
            {
                ("A", node_name, "sampler_name"),
                ("A", node_name, "scheduler"),
            }
        )
        _ensure_qapp().processEvents()

        content_body = _content_body_for(wrapper)
        content_layout = _content_layout_for(content_body)
        title_body_divider = content_layout.itemAt(0).widget()
        first_group = content_layout.itemAt(1).widget()
        divider_before_steps = content_layout.itemAt(2).widget()
        steps_group = content_layout.itemAt(3).widget()
        assert title_body_divider is not None
        assert first_group is not None
        assert divider_before_steps is not None
        assert steps_group is not None

        assert not title_body_divider.isHidden()
        assert first_group.isHidden()
        assert divider_before_steps.isHidden()
        assert not steps_group.isHidden()
        assert tuple(divider_before_steps.property("divider_for_field")) == (
            "A",
            node_name,
            "steps",
        )
        assert steps_group.y() == 1
    finally:
        host.close()
        host.deleteLater()
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_rebuilt_n_column_row_replaces_stale_column_widget_registrations(
    monkeypatch,
) -> None:
    """Rebuilt grouped rows should register current column widgets."""

    _ensure_qapp()
    node_name = "ksampler"
    node_type = "KSampler"
    definitions = {
        node_type: {
            "input": {
                "required": {
                    "sampler_name": ["STRING"],
                    "scheduler": ["STRING"],
                    "steps": ["INT"],
                    "cfg": ["FLOAT"],
                }
            }
        }
    }
    nodes = {
        node_name: {
            "class_type": node_type,
            "inputs": {
                "sampler_name": "euler",
                "scheduler": "normal",
                "steps": 28,
                "cfg": 5.5,
            },
        }
    }
    cube_state = SimpleNamespace(
        buffer={"nodes": nodes, "definitions": definitions},
        ui={},
    )
    panel = _WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
        definitions_by_class=definitions,
    )
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )

    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        lambda **_kwargs: QWidget(panel),
    )

    first_wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=nodes[node_name]["inputs"],
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=snapshot.resolved_nodes_by_alias["A"][node_name],
        display_decision=snapshot.card_decisions_by_alias["A"][node_name],
        alias="A",
    )
    sampler_key = ("A", node_name, "sampler_name")
    scheduler_key = ("A", node_name, "scheduler")
    first_sampler_registration = panel.col_widgets[sampler_key]
    first_scheduler_registration = panel.col_widgets[scheduler_key]

    second_wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=nodes[node_name]["inputs"],
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=snapshot.resolved_nodes_by_alias["A"][node_name],
        display_decision=snapshot.card_decisions_by_alias["A"][node_name],
        alias="A",
    )

    try:
        assert first_wrapper is not None
        assert second_wrapper is not None
        second_sampler_registration = panel.col_widgets[sampler_key]
        second_scheduler_registration = panel.col_widgets[scheduler_key]
        assert second_sampler_registration[0] is second_scheduler_registration[0]
        assert second_sampler_registration[1] is not first_sampler_registration[1]
        assert second_scheduler_registration[1] is not first_scheduler_registration[1]
        assert panel.row_widgets[sampler_key][1] is second_sampler_registration[0]
    finally:
        if first_wrapper is not None:
            first_wrapper.deleteLater()
        if second_wrapper is not None:
            second_wrapper.deleteLater()
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_rebuilt_n_column_row_removes_columns_missing_from_current_card(
    monkeypatch,
) -> None:
    """Node-card rebuilds should remove grouped column entries absent from the card."""

    _ensure_qapp()
    node_name = "ksampler"
    node_type = "KSampler"
    definitions = {
        node_type: {
            "input": {
                "required": {
                    "sampler_name": ["STRING"],
                    "scheduler": ["STRING"],
                    "steps": ["INT"],
                    "cfg": ["FLOAT"],
                }
            }
        }
    }
    rebuilt_definitions = {
        node_type: {
            "input": {
                "required": {
                    "sampler_name": ["STRING"],
                    "steps": ["INT"],
                    "cfg": ["FLOAT"],
                }
            }
        }
    }
    initial_nodes = {
        node_name: {
            "class_type": node_type,
            "inputs": {
                "sampler_name": "euler",
                "scheduler": "normal",
                "steps": 28,
                "cfg": 5.5,
            },
        }
    }
    rebuilt_nodes = {
        node_name: {
            "class_type": node_type,
            "inputs": {
                "sampler_name": "euler",
                "steps": 28,
                "cfg": 5.5,
            },
        }
    }
    cube_state = SimpleNamespace(
        buffer={"nodes": initial_nodes, "definitions": definitions},
        ui={},
    )
    panel = _WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    initial_snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
        definitions_by_class=definitions,
    )
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )

    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        lambda **_kwargs: QWidget(panel),
    )

    initial_wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=initial_nodes[node_name]["inputs"],
        node_type=node_type,
        field_specs=initial_snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=initial_snapshot.resolved_nodes_by_alias["A"][node_name],
        display_decision=initial_snapshot.card_decisions_by_alias["A"][node_name],
        alias="A",
    )
    scheduler_key = ("A", node_name, "scheduler")
    assert scheduler_key in panel.col_widgets

    cube_state.buffer = {"nodes": rebuilt_nodes, "definitions": rebuilt_definitions}
    rebuilt_snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
        definitions_by_class=rebuilt_definitions,
    )
    rebuilt_wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=rebuilt_nodes[node_name]["inputs"],
        node_type=node_type,
        field_specs=rebuilt_snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=rebuilt_snapshot.resolved_nodes_by_alias["A"][node_name],
        display_decision=rebuilt_snapshot.card_decisions_by_alias["A"][node_name],
        alias="A",
    )

    try:
        assert initial_wrapper is not None
        assert rebuilt_wrapper is not None
        assert scheduler_key not in panel.col_widgets
        assert scheduler_key not in panel.row_widgets
        assert scheduler_key not in panel.input_widgets_by_field_key
    finally:
        if initial_wrapper is not None:
            initial_wrapper.deleteLater()
        if rebuilt_wrapper is not None:
            rebuilt_wrapper.deleteLater()
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_rebuilt_n_column_row_applies_partial_global_override_visibility(
    monkeypatch,
) -> None:
    """Current grouped columns should honor left-only and right-only hidden keys."""

    _ensure_qapp()
    node_name = "ksampler"
    node_type = "KSampler"
    definitions = {
        node_type: {
            "input": {
                "required": {
                    "sampler_name": ["STRING"],
                    "scheduler": ["STRING"],
                    "steps": ["INT"],
                    "cfg": ["FLOAT"],
                }
            }
        }
    }
    nodes = {
        node_name: {
            "class_type": node_type,
            "inputs": {
                "sampler_name": "euler",
                "scheduler": "normal",
                "steps": 28,
                "cfg": 5.5,
            },
        }
    }
    cube_state = SimpleNamespace(
        buffer={"nodes": nodes, "definitions": definitions},
        ui={},
    )
    panel = _WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
        definitions_by_class=definitions,
    )
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )

    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        lambda **_kwargs: QWidget(panel),
    )

    stale_wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=nodes[node_name]["inputs"],
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=snapshot.resolved_nodes_by_alias["A"][node_name],
        display_decision=snapshot.card_decisions_by_alias["A"][node_name],
        alias="A",
    )
    wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=nodes[node_name]["inputs"],
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=snapshot.resolved_nodes_by_alias["A"][node_name],
        display_decision=snapshot.card_decisions_by_alias["A"][node_name],
        alias="A",
    )

    assert stale_wrapper is not None
    assert wrapper is not None
    host = QWidget()
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(wrapper)
    host.resize(400, wrapper.sizeHint().height())
    host.show()
    _ensure_qapp().processEvents()
    try:
        sampler_key = ("A", node_name, "sampler_name")
        scheduler_key = ("A", node_name, "scheduler")
        row_container, sampler_column, _sampler_widget = panel.col_widgets[sampler_key]
        scheduler_row, scheduler_column, _scheduler_widget = panel.col_widgets[
            scheduler_key
        ]
        assert row_container is scheduler_row
        assert panel.row_widgets[sampler_key][1] is row_container

        controller = EditorPanelFieldSyncController(panel)
        controller.apply_hidden_field_keys({scheduler_key})
        _ensure_qapp().processEvents()
        assert not row_container.isHidden()
        assert not sampler_column.isHidden()
        assert scheduler_column.isHidden()

        controller.apply_hidden_field_keys({sampler_key})
        _ensure_qapp().processEvents()
        assert not row_container.isHidden()
        assert sampler_column.isHidden()
        assert not scheduler_column.isHidden()

        controller.apply_hidden_field_keys({sampler_key, scheduler_key})
        _ensure_qapp().processEvents()
        assert row_container.isHidden()
        assert sampler_column.isHidden()
        assert scheduler_column.isHidden()

        controller.apply_hidden_field_keys(set())
        _ensure_qapp().processEvents()
        assert not row_container.isHidden()
        assert not sampler_column.isHidden()
        assert not scheduler_column.isHidden()
    finally:
        host.close()
        host.deleteLater()
        stale_wrapper.deleteLater()
        wrapper.deleteLater()
        panel.deleteLater()
        _ensure_qapp().processEvents()


def test_non_collapsible_node_card_with_rows_keeps_surfaces_attached(
    monkeypatch,
) -> None:
    """Expanded non-accordion cards should still square the shared content edge."""

    _ensure_qapp()
    node_name = "positive_prompt"
    node_type = "CLIPTextEncode"
    nodes = {
        node_name: {
            "class_type": node_type,
            "inputs": {"prompt_template": "cinematic portrait"},
        }
    }
    cube_state = SimpleNamespace(
        buffer={"nodes": nodes, "definitions": {}},
        ui={},
    )
    panel = _WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
    )
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )

    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        lambda **_kwargs: QWidget(panel),
    )

    wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=nodes[node_name]["inputs"],
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=snapshot.resolved_nodes_by_alias["A"][node_name],
        display_decision=snapshot.card_decisions_by_alias["A"][node_name],
        alias="A",
    )

    assert wrapper is not None
    host = QWidget()
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(wrapper)
    host.resize(400, wrapper.sizeHint().height())
    host.show()
    _ensure_qapp().processEvents()
    try:
        title_row = _title_row_for(wrapper)
        content_body = _content_body_for(wrapper)

        assert title_row.findChildren(AccordionChevronWidget) == []
        assert title_row.cursor().shape() == Qt.CursorShape.ArrowCursor
        assert _row_activation_enabled(title_row) is False
        assert _accordion_content_attached(title_row) is True
        assert _accordion_content_attached(content_body.content_widget()) is True
    finally:
        host.close()
        host.deleteLater()
        panel.deleteLater()
        _ensure_qapp().processEvents()

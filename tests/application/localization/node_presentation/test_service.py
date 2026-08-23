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

"""Localized node-presentation service contracts."""

from __future__ import annotations

from sugarsubstitute_shared.localization import app_text, render_source_application_text

from substitute.application.localization import (
    NodePresentationService,
)
from substitute.domain.localization import (
    NodeCatalogText,
    NodeFieldCatalogText,
    NodeFieldPresentationRequest,
    NodePresentationRequest,
    NodeTextCatalogSnapshot,
    NodeTextSource,
)
from tests.application.localization.node_presentation.support import _catalog


def test_node_presentation_preserves_authored_text_and_localizes_other_fields() -> None:
    """Keep authored identity literal while localizing catalog-owned presentation."""

    active = _catalog(
        "zh-Hans",
        NodeTextSource.ACTIVE_COMFY,
        {
            "KSampler": NodeCatalogText(
                display_name="K采样器",
                description="采样描述",
                inputs={
                    "seed": NodeFieldCatalogText(
                        name="种子",
                        tooltip="生成噪声所使用的随机种子。",
                    ),
                    "steps": NodeFieldCatalogText(name="步数"),
                },
                outputs={"0": NodeFieldCatalogText(name="潜空间")},
            )
        },
    )
    english = _catalog(
        "en",
        NodeTextSource.ENGLISH_COMFY,
        {
            "KSampler": NodeCatalogText(
                display_name="KSampler",
                description="Sampler description",
                inputs={"seed": NodeFieldCatalogText(name="seed")},
                outputs={"0": NodeFieldCatalogText(name="latent")},
            )
        },
    )
    snapshot = NodeTextCatalogSnapshot(
        effective_language_identifier="zh-Hans",
        revision=2,
        active_layers=(active,),
        english_layers=(english,),
    )
    service = NodePresentationService(
        lambda: snapshot,
        application_text_renderer=render_source_application_text,
    )

    presentation = service.present(
        NodePresentationRequest(
            class_type="KSampler",
            node_name="sampler_node",
            authored_title="  My sampler 采样  ",
            raw_display_name="Raw sampler",
            raw_description="Raw description",
            fields=(
                NodeFieldPresentationRequest(field_key="seed"),
                NodeFieldPresentationRequest(
                    field_key="steps",
                    authored_label="  My Steps  ",
                    raw_tooltip="Raw steps tooltip",
                ),
            ),
            outputs=(NodeFieldPresentationRequest(field_key="0"),),
        )
    )

    assert presentation.title == "  My sampler 采样  "
    assert presentation.title_source is NodeTextSource.AUTHORED
    assert "  My sampler 采样  " in presentation.search_aliases
    assert "my sampler 采样" not in presentation.search_aliases
    assert presentation.fields["seed"].label == "种子"
    assert presentation.fields["seed"].tooltip == "生成噪声所使用的随机种子。"
    assert presentation.fields["steps"].label == "  My Steps  "
    assert presentation.fields["steps"].label_source is NodeTextSource.AUTHORED
    assert "  My Steps  " in presentation.fields["steps"].search_aliases
    assert "my steps" not in presentation.fields["steps"].search_aliases
    assert "KSampler" in presentation.search_aliases
    assert "K采样器" in presentation.search_aliases
    assert "seed" in presentation.fields["seed"].search_aliases
    assert presentation.outputs["0"].label == "潜空间"
    assert presentation.outputs["0"].tooltip is None


def test_application_owned_field_label_renders_from_the_active_app_catalog() -> None:
    """Application labels should rerender without competing with Comfy field text."""

    active_language = {"identifier": "zh-Hans"}
    translations = {"zh-Hans": "红色", "ja": "赤"}
    snapshot = NodeTextCatalogSnapshot(
        effective_language_identifier="zh-Hans",
        revision=1,
        active_layers=(),
        english_layers=(),
    )
    service = NodePresentationService(
        lambda: snapshot,
        application_text_renderer=lambda _message: translations[
            active_language["identifier"]
        ],
    )
    request = NodePresentationRequest(
        class_type="VectorscopeCC",
        node_name="scope",
        fields=(
            NodeFieldPresentationRequest(
                field_key="r",
                application_label=app_text("Red"),
                raw_name="r",
            ),
        ),
    )

    chinese = service.present(request)
    active_language["identifier"] = "ja"
    japanese = service.present(request)

    assert chinese.fields["r"].label == "红色"
    assert japanese.fields["r"].label == "赤"
    assert chinese.fields["r"].label_source is NodeTextSource.APPLICATION
    assert "Red" in chinese.fields["r"].search_aliases


def test_node_presentation_localizes_named_output_and_retains_english_alias() -> None:
    """Project an upstream output name while retaining its English search alias."""

    active = _catalog(
        "zh-Hans",
        NodeTextSource.ACTIVE_COMFY,
        {
            "AddTextPrefix": NodeCatalogText(
                display_name="添加文本前缀",
                description=None,
                inputs={},
                outputs={
                    "0": NodeFieldCatalogText(
                        name="文本",
                        tooltip="处理后的文本",
                    )
                },
            )
        },
    )
    english = _catalog(
        "en",
        NodeTextSource.ENGLISH_COMFY,
        {
            "AddTextPrefix": NodeCatalogText(
                display_name="Add Text Prefix",
                description=None,
                inputs={},
                outputs={"0": NodeFieldCatalogText(name="texts")},
            )
        },
    )
    snapshot = NodeTextCatalogSnapshot(
        effective_language_identifier="zh-Hans",
        revision=3,
        active_layers=(active,),
        english_layers=(english,),
    )

    presentation = NodePresentationService(
        lambda: snapshot,
        application_text_renderer=render_source_application_text,
    ).present(
        NodePresentationRequest(
            class_type="AddTextPrefix",
            node_name="prefix",
            outputs=(NodeFieldPresentationRequest(field_key="0", raw_name="texts"),),
        )
    )

    assert presentation.outputs["0"].label == "文本"
    assert presentation.outputs["0"].tooltip == "处理后的文本"
    assert "texts" in presentation.outputs["0"].search_aliases


def test_node_presentation_falls_back_to_raw_then_technical_identity() -> None:
    """Never expose blanks for unknown custom nodes or fields."""

    snapshot = NodeTextCatalogSnapshot(
        effective_language_identifier="ja",
        revision=1,
        active_layers=(),
        english_layers=(),
    )
    service = NodePresentationService(
        lambda: snapshot,
        application_text_renderer=render_source_application_text,
    )

    raw = service.present(
        NodePresentationRequest(
            class_type="CustomNode",
            node_name="custom_instance",
            raw_display_name="Custom Display",
            fields=(
                NodeFieldPresentationRequest(
                    field_key="raw_key",
                    raw_name="Raw Label",
                ),
            ),
        )
    )
    technical = service.present(
        NodePresentationRequest(
            class_type="UnknownNode",
            node_name="unknown_node",
            fields=(NodeFieldPresentationRequest(field_key="field_key"),),
        )
    )

    assert raw.title == "Custom Display"
    assert raw.title_source is NodeTextSource.RAW_DEFINITION
    assert raw.fields["raw_key"].label == "Raw Label"
    assert technical.title == "Unknown Node"
    assert technical.title_source is NodeTextSource.TECHNICAL_ID
    assert technical.fields["field_key"].label == "Field Key"

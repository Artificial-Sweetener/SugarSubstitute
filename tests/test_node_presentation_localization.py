#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Test authoritative Comfy server node-presentation precedence."""

from __future__ import annotations

from sugarsubstitute_shared.localization import app_text, render_source_application_text

from substitute.application.localization import (
    NodePresentationService,
    NodeTextCatalogResolver,
)
from substitute.application.node_behavior import ResolvedFieldSpec
from substitute.domain.localization import (
    NodeCatalogText,
    NodeFieldCatalogText,
    NodeFieldPresentationRequest,
    NodePresentationRequest,
    NodeTextCatalog,
    NodeTextCatalogSnapshot,
    NodeTextSource,
)
from substitute.domain.node_behavior import (
    CardBehavior,
    FieldBehavior,
    FieldLabelSource,
    ResolvedNodeBehavior,
)
from substitute.presentation.editor.panel.node_presentation_adapter import (
    build_node_presentation_request,
)


def test_catalog_resolver_merges_properties_and_normalizes_dotted_class_types() -> None:
    """Use active text per property and fall through to English missing leaves."""

    active = _catalog(
        "ja",
        NodeTextSource.ACTIVE_COMFY,
        {
            "Vendor_Node": NodeCatalogText(
                display_name="ベンダーノード",
                description=None,
                inputs={"amount": NodeFieldCatalogText(name="量")},
                outputs={"0": NodeFieldCatalogText(name="結果")},
            )
        },
    )
    english = _catalog(
        "en",
        NodeTextSource.ENGLISH_COMFY,
        {
            "Vendor_Node": NodeCatalogText(
                display_name="Vendor Node",
                description="English description",
                inputs={
                    "amount": NodeFieldCatalogText(
                        name="Amount",
                        tooltip="English tooltip",
                    )
                },
                outputs={
                    "0": NodeFieldCatalogText(
                        name="Result",
                        tooltip="English output tooltip",
                    )
                },
            )
        },
    )
    resolver = NodeTextCatalogResolver(
        NodeTextCatalogSnapshot(
            effective_language_identifier="ja",
            revision=4,
            active_layers=(active,),
            english_layers=(english,),
        )
    )

    node = resolver.node_text("Vendor.Node")
    field = resolver.input_text("Vendor.Node", "amount")
    output = resolver.output_text("Vendor.Node", "0")

    assert node.display_name is not None
    assert node.display_name.text == "ベンダーノード"
    assert node.display_name.source is NodeTextSource.ACTIVE_COMFY
    assert node.description is not None
    assert node.description.text == "English description"
    assert field.name is not None
    assert field.name.text == "量"
    assert field.tooltip is not None
    assert field.tooltip.text == "English tooltip"
    assert output.name is not None
    assert output.name.text == "結果"
    assert output.tooltip is not None
    assert output.tooltip.text == "English output tooltip"


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


def test_node_card_adapter_captures_live_outputs_by_stable_slot() -> None:
    """Carry raw output names into later locale projections without changing types."""

    class Gateway:
        """Return one bounded live definition for the public adapter contract."""

        def get_node_definition(self, node_class: str) -> dict[str, object]:
            """Return a definition envelope for the requested class."""

            return {
                node_class: {
                    "output": ["STRING", "IMAGE"],
                    "output_name": ["texts", "images"],
                }
            }

        def get_required_node_definition(self, node_class: str) -> dict[str, object]:
            """Return the same deterministic definition for required lookups."""

            return self.get_node_definition(node_class)

    request = build_node_presentation_request(
        node_definition_gateway=Gateway(),
        node_name="prefix",
        node_type="AddTextPrefix",
        field_specs={},
        resolved_behavior=ResolvedNodeBehavior(
            node_name="prefix",
            class_type="AddTextPrefix",
            card=CardBehavior(),
            fields={},
        ),
    )

    assert tuple(output.field_key for output in request.outputs) == ("0", "1")
    assert tuple(output.raw_name for output in request.outputs) == ("texts", "images")


def test_live_definition_field_label_remains_eligible_for_comfy_localization() -> None:
    """Treat raw definition labels as fallback text rather than authored cube copy."""

    class Gateway:
        """Return one raw KSampler definition without external I/O."""

        def get_node_definition(self, node_class: str) -> dict[str, object]:
            """Return the requested definition envelope."""

            return {node_class: {"display_name": "KSampler"}}

        def get_required_node_definition(self, node_class: str) -> dict[str, object]:
            """Return the same deterministic definition."""

            return self.get_node_definition(node_class)

    field_behavior = FieldBehavior(field_key="sampler_name")
    field_spec = ResolvedFieldSpec(
        cube_alias="A",
        node_name="ksampler",
        class_type="KSampler",
        field_key="sampler_name",
        field_type="COMBO",
        constraints={},
        meta_info={"label": "Sampler Name"},
        field_info=None,
        value="euler",
        field_behavior=field_behavior,
        label_source=FieldLabelSource.COMFY_DEFINITION,
    )
    request = build_node_presentation_request(
        node_definition_gateway=Gateway(),
        node_name="ksampler",
        node_type="KSampler",
        field_specs={"sampler_name": field_spec},
        resolved_behavior=ResolvedNodeBehavior(
            node_name="ksampler",
            class_type="KSampler",
            card=CardBehavior(),
            fields={"sampler_name": field_behavior},
        ),
    )
    catalog = _catalog(
        "ja",
        NodeTextSource.ACTIVE_COMFY,
        {
            "KSampler": NodeCatalogText(
                display_name="Kサンプラー",
                description=None,
                inputs={"sampler_name": NodeFieldCatalogText(name="サンプラー名")},
                outputs={},
            )
        },
    )
    presentation = NodePresentationService(
        lambda: NodeTextCatalogSnapshot(
            effective_language_identifier="ja",
            revision=1,
            active_layers=(catalog,),
            english_layers=(),
        ),
        application_text_renderer=render_source_application_text,
    ).present(request)

    assert request.fields[0].authored_label is None
    assert request.fields[0].raw_name == "Sampler Name"
    assert presentation.fields["sampler_name"].label == "サンプラー名"
    assert (
        presentation.fields["sampler_name"].label_source is NodeTextSource.ACTIVE_COMFY
    )


def test_wrapper_interface_field_label_remains_exact_authored_copy() -> None:
    """Keep a public subgraph label ahead of an identically keyed Comfy field."""

    class Gateway:
        """Return no raw definition metadata for a wrapper fixture."""

        @staticmethod
        def get_node_definition(_node_class: str) -> dict[str, object]:
            """Return no separate live definition."""

            return {}

        @staticmethod
        def get_required_node_definition(_node_class: str) -> dict[str, object]:
            """Return no separate required definition."""

            return {}

    field_behavior = FieldBehavior(field_key="sampler_name")
    field_spec = ResolvedFieldSpec(
        cube_alias="A",
        node_name="sampler_wrapper",
        class_type="wrapper-uuid",
        field_key="sampler_name",
        field_type="COMBO",
        constraints={},
        meta_info={
            "subgraph_wrapper": True,
            "label": "Sampler Name",
        },
        field_info=None,
        value="euler",
        field_behavior=field_behavior,
        label_source=FieldLabelSource.WRAPPER_AUTHORED,
    )
    request = build_node_presentation_request(
        node_definition_gateway=Gateway(),
        node_name="sampler_wrapper",
        node_type="wrapper-uuid",
        field_specs={"sampler_name": field_spec},
        resolved_behavior=ResolvedNodeBehavior(
            node_name="sampler_wrapper",
            class_type="wrapper-uuid",
            card=CardBehavior(),
            fields={"sampler_name": field_behavior},
        ),
    )

    assert request.fields[0].authored_label == "Sampler Name"


def _catalog(
    language: str,
    source: NodeTextSource,
    entries: dict[str, NodeCatalogText],
) -> NodeTextCatalog:
    """Build one immutable synthetic catalog layer."""

    return NodeTextCatalog.create(
        language_identifier=language,
        source=source,
        node_definitions=entries,
    )

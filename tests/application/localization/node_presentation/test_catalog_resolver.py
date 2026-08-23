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

"""Node-text catalog resolver contracts."""

from __future__ import annotations


from substitute.application.localization import (
    NodeTextCatalogResolver,
)
from substitute.domain.localization import (
    NodeCatalogText,
    NodeFieldCatalogText,
    NodeTextCatalogSnapshot,
    NodeTextSource,
)
from tests.application.localization.node_presentation.support import _catalog


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


def test_catalog_resolver_normalizes_dotted_dynamic_field_keys() -> None:
    """Resolve Comfy's flattened underscore keys for dotted dynamic inputs."""

    active = _catalog(
        "zh-Hans",
        NodeTextSource.ACTIVE_COMFY,
        {
            "ByteDanceNode": NodeCatalogText(
                display_name=None,
                description=None,
                inputs={
                    "model_duration": NodeFieldCatalogText(
                        name="时长",
                        tooltip="输出视频的时长。",
                    )
                },
                outputs={},
            )
        },
    )
    resolver = NodeTextCatalogResolver(
        NodeTextCatalogSnapshot(
            effective_language_identifier="zh-Hans",
            revision=1,
            active_layers=(active,),
            english_layers=(),
        )
    )

    field = resolver.input_text("ByteDanceNode", "model.duration")

    assert field.name is not None
    assert field.name.text == "时长"
    assert field.tooltip is not None
    assert field.tooltip.text == "输出视频的时长。"
    assert resolver.input_search_aliases("ByteDanceNode", "model.duration") == ("时长",)


def test_catalog_resolver_prefers_exact_dynamic_field_keys() -> None:
    """Keep exact custom-node keys ahead of Comfy's underscore compatibility key."""

    active = _catalog(
        "ja",
        NodeTextSource.ACTIVE_COMFY,
        {
            "VendorNode": NodeCatalogText(
                display_name=None,
                description=None,
                inputs={
                    "model.duration": NodeFieldCatalogText(
                        name="正確な期間",
                        tooltip="正確なキー",
                    ),
                    "model_duration": NodeFieldCatalogText(
                        name="互換期間",
                        tooltip="互換キー",
                    ),
                },
                outputs={},
            )
        },
    )
    resolver = NodeTextCatalogResolver(
        NodeTextCatalogSnapshot(
            effective_language_identifier="ja",
            revision=1,
            active_layers=(active,),
            english_layers=(),
        )
    )

    field = resolver.input_text("VendorNode", "model.duration")

    assert field.name is not None
    assert field.name.text == "正確な期間"
    assert field.tooltip is not None
    assert field.tooltip.text == "正確なキー"
    assert resolver.input_search_aliases("VendorNode", "model.duration") == (
        "正確な期間",
    )

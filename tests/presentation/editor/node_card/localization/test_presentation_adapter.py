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

"""Node-card localization adapter contracts."""

from __future__ import annotations

from sugarsubstitute_shared.localization import render_source_application_text

from substitute.application.localization import (
    NodePresentationService,
)
from substitute.application.node_behavior import ResolvedFieldSpec
from substitute.domain.localization import (
    NodeCatalogText,
    NodeFieldCatalogText,
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
from tests.application.localization.node_presentation.support import _catalog


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

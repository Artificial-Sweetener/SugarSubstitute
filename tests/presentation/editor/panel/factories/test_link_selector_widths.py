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

"""Tests for shared node-link selector width label planning."""

from __future__ import annotations

from substitute.domain.links import (
    NodeLinkEndpoint,
    NodeLinkEndpointIndex,
)
from substitute.domain.node_behavior import PromptRole
from substitute.presentation.editor.panel.factories.link_selector_widths import (
    INDEPENDENT_LINK_LABEL,
    link_target_label,
    node_link_width_labels_by_identity,
)


def _prompt_node_link_index() -> NodeLinkEndpointIndex:
    """Return mixed prompt endpoints represented as canonical node links."""

    return NodeLinkEndpointIndex.from_endpoints(
        (
            NodeLinkEndpoint(
                cube_alias="SDXL/Text to Image",
                node_name="positive_prompt",
                class_type="PrimitiveStringMultiline",
                family="prompt:positive",
                editable_value_keys=("prompt_template",),
            ),
            NodeLinkEndpoint(
                cube_alias="SDXL/Text to Image",
                node_name="negative_prompt",
                class_type="PrimitiveStringMultiline",
                family="prompt:negative",
                editable_value_keys=("prompt_template",),
            ),
            NodeLinkEndpoint(
                cube_alias="SDXL/Automask Detailer",
                node_name="positive_prompt",
                class_type="PrimitiveStringMultiline",
                family="prompt:positive",
                editable_value_keys=("prompt_template",),
            ),
            NodeLinkEndpoint(
                cube_alias="SDXL/Automask Detailer",
                node_name="negative_prompt",
                class_type="PrimitiveStringMultiline",
                family="prompt:negative",
                editable_value_keys=("prompt_template",),
            ),
            NodeLinkEndpoint(
                cube_alias="SDXL/Diffusion Upscale With Longer Name",
                node_name="positive_prompt",
                class_type="PrimitiveStringMultiline",
                family="prompt:positive",
                editable_value_keys=("prompt_template",),
            ),
        )
    )


def _node_endpoint(
    cube_alias: str,
    *,
    node_name: str,
    class_type: str,
    family: str,
) -> NodeLinkEndpoint:
    """Return one node-link endpoint for identity grouping tests."""

    return NodeLinkEndpoint(
        cube_alias=cube_alias,
        node_name=node_name,
        class_type=class_type,
        family=family,
        editable_value_keys=("value",),
    )


def test_prompt_node_link_width_labels_include_reachable_targets_by_identity() -> None:
    """Prompt node-link groups should include target labels reachable by identity."""

    endpoint_index = _prompt_node_link_index()
    positive_identity = endpoint_index.prompt_endpoint_for(
        "SDXL/Text to Image",
        PromptRole.POSITIVE,
    )
    assert positive_identity is not None
    labels = node_link_width_labels_by_identity(
        endpoint_index,
        (
            "SDXL/Text to Image",
            "SDXL/Automask Detailer",
            "SDXL/Diffusion Upscale With Longer Name",
        ),
    )[positive_identity.identity]

    assert labels == (
        INDEPENDENT_LINK_LABEL,
        link_target_label("SDXL/Text to Image"),
        link_target_label("SDXL/Automask Detailer"),
    )


def test_prompt_node_link_width_labels_consider_labels_absent_from_one_combo() -> None:
    """Prompt node-link width should not be limited to one combo's options."""

    endpoint_index = _prompt_node_link_index()
    identity = endpoint_index.identities()[0]
    labels = node_link_width_labels_by_identity(
        endpoint_index,
        (
            "SDXL/Text to Image",
            "SDXL/Automask Detailer",
            "SDXL/Diffusion Upscale With Longer Name",
        ),
    )[identity]

    assert link_target_label("SDXL/Automask Detailer") in labels


def test_node_width_labels_group_by_node_link_identity() -> None:
    """Node link width labels should be independent per compatible identity."""

    endpoint_index = NodeLinkEndpointIndex.from_endpoints(
        (
            _node_endpoint(
                "SDXL/Text to Image",
                node_name="vectorscopecc",
                class_type="VectorscopeCC",
                family="vectorscopecc",
            ),
            _node_endpoint(
                "SDXL/Automask Detailer",
                node_name="vectorscopecc",
                class_type="VectorscopeCC",
                family="vectorscopecc",
            ),
            _node_endpoint(
                "SDXL/Text to Image",
                node_name="load_model",
                class_type="UpscaleModelLoader",
                family="upscale_model",
            ),
            _node_endpoint(
                "SDXL/Diffusion Upscale",
                node_name="load_model",
                class_type="UpscaleModelLoader",
                family="upscale_model",
            ),
        )
    )

    labels_by_identity = node_link_width_labels_by_identity(
        endpoint_index,
        (
            "SDXL/Text to Image",
            "SDXL/Automask Detailer",
            "SDXL/Diffusion Upscale",
        ),
    )

    vectorscope_identity = endpoint_index.endpoint_for(
        "SDXL/Text to Image",
        endpoint_index.identities_for_cube("SDXL/Text to Image")[0],
    )
    assert vectorscope_identity is not None
    upscale_identity = endpoint_index.endpoint_for(
        "SDXL/Text to Image",
        endpoint_index.identities_for_cube("SDXL/Text to Image")[1],
    )
    assert upscale_identity is not None
    assert labels_by_identity[vectorscope_identity.identity] == (
        INDEPENDENT_LINK_LABEL,
        link_target_label("SDXL/Text to Image"),
    )
    assert labels_by_identity[upscale_identity.identity] == (
        INDEPENDENT_LINK_LABEL,
        link_target_label("SDXL/Text to Image"),
    )


def test_vectorscope_width_labels_exclude_unrelated_node_identities() -> None:
    """Vectorscope labels should not inherit labels from unrelated node families."""

    endpoint_index = NodeLinkEndpointIndex.from_endpoints(
        (
            _node_endpoint(
                "SDXL/Text to Image",
                node_name="vectorscopecc",
                class_type="VectorscopeCC",
                family="vectorscopecc",
            ),
            _node_endpoint(
                "SDXL/Automask Detailer",
                node_name="vectorscopecc",
                class_type="VectorscopeCC",
                family="vectorscopecc",
            ),
            _node_endpoint(
                "SDXL/Diffusion Upscale With Longer Name",
                node_name="load_model",
                class_type="UpscaleModelLoader",
                family="upscale_model",
            ),
            _node_endpoint(
                "SDXL/Promptmask Detailer",
                node_name="load_model",
                class_type="UpscaleModelLoader",
                family="upscale_model",
            ),
        )
    )

    labels_by_identity = node_link_width_labels_by_identity(
        endpoint_index,
        (
            "SDXL/Text to Image",
            "SDXL/Automask Detailer",
            "SDXL/Diffusion Upscale With Longer Name",
            "SDXL/Promptmask Detailer",
        ),
    )
    vectorscope_identity = endpoint_index.identities_for_cube("SDXL/Text to Image")[0]

    assert (
        link_target_label("SDXL/Diffusion Upscale With Longer Name")
        not in (labels_by_identity[vectorscope_identity])
    )


def test_empty_width_label_inputs_return_deterministic_minimal_groups() -> None:
    """Empty endpoint indexes should not raise during initial or hidden setup."""

    assert node_link_width_labels_by_identity(NodeLinkEndpointIndex(), ()) == {}

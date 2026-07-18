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

"""Contract tests for semantic input image and mask endpoint discovery."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
)
from substitute.application.workflows.input_canvas_plan_service import (
    InputCanvasPlanService,
)
from substitute.application.workflows.workflow_node_definition_service import (
    WorkflowNodeDefinitionService,
)
from substitute.domain.workflow import (
    InputAssetEndpointIndex,
    InputAssetRole,
    InputCanvasPlan,
)


def test_custom_image_upload_is_discovered_from_live_metadata() -> None:
    """A custom upload widget should be identified without a class-name rule."""

    index = _endpoint_index(
        "section",
        _graph(
            uploader=("FancyDiskSource", {}),
            consumer_inputs={"pixels": ["uploader", 0]},
        ),
        node_definitions={
            "FancyDiskSource": _definition(
                field_key="source_file",
                outputs=("IMAGE",),
            ),
            "Consumer": _consumer_definition(pixels="IMAGE"),
        },
    )

    assert len(index.image_endpoints) == 1
    endpoint = index.image_endpoints[0]
    assert endpoint.field_key == "source_file"
    assert endpoint.output_index == 0
    assert endpoint.role is InputAssetRole.IMAGE
    assert bool(index.image_endpoints) is True


def test_mask_only_use_classifies_dual_output_upload_as_mask() -> None:
    """Only the actually consumed mask socket should determine endpoint role."""

    index = _endpoint_index(
        "section",
        _graph(
            uploader=("DualUpload", {}),
            consumer_inputs={"mask": ["uploader", 1]},
        ),
        node_definitions={
            "DualUpload": _definition(outputs=("IMAGE", "MASK")),
            "Consumer": _consumer_definition(mask="MASK"),
        },
    )

    assert index.image_endpoints == ()
    assert [(item.node_name, item.output_index) for item in index.mask_endpoints] == [
        ("uploader", 1)
    ]


def test_dual_used_upload_is_image_only() -> None:
    """A source with both image and mask outputs in use should fail toward image."""

    graph = _graph(
        uploader=("DualUpload", {}),
        consumer_inputs={
            "pixels": ["uploader", 0],
            "mask": ["uploader", 1],
        },
    )
    index = _endpoint_index(
        "section",
        graph,
        node_definitions={
            "DualUpload": _definition(outputs=("IMAGE", "MASK")),
            "Consumer": _consumer_definition(pixels="IMAGE", mask="MASK"),
        },
    )

    assert [(item.node_name, item.output_index) for item in index.image_endpoints] == [
        ("uploader", 0)
    ]
    assert index.mask_endpoints == ()


def test_unused_upload_and_ordinary_image_producer_are_not_endpoints() -> None:
    """Upload capability requires a used socket and explicit upload metadata."""

    graph = {
        "nodes": {
            "unused_upload": {
                "class_type": "Upload",
                "inputs": {"image": "unused.png"},
            },
            "calculation": {"class_type": "ImageMath", "inputs": {}},
            "consumer": {
                "class_type": "Consumer",
                "inputs": {"pixels": ["calculation", 0]},
            },
        }
    }
    index = _endpoint_index(
        "section",
        graph,
        node_definitions={
            "Upload": _definition(outputs=("IMAGE",)),
            "ImageMath": {"input": {"required": {}}, "output": ["IMAGE"]},
            "Consumer": _consumer_definition(pixels="IMAGE"),
        },
    )

    assert index.endpoints == ()


def test_custom_image_and_mask_uploads_bind_through_shared_consumer() -> None:
    """Semantic uploads should form one editable relation through typed use."""

    graph = {
        "nodes": {
            "photo": {
                "class_type": "PhotoPicker",
                "inputs": {"photo_path": "photo.png"},
            },
            "stencil": {
                "class_type": "StencilPicker",
                "inputs": {"stencil_path": "mask.png"},
            },
            "consumer": {
                "class_type": "Consumer",
                "inputs": {
                    "pixels": ["photo", 2],
                    "mask": ["stencil", 1],
                },
            },
        }
    }
    plan = _canvas_plan(
        "workflow",
        graph,
        node_definitions={
            "PhotoPicker": _definition(
                field_key="photo_path",
                outputs=("TEXT", "LATENT", "IMAGE"),
            ),
            "StencilPicker": _definition(
                field_key="stencil_path",
                outputs=("TEXT", "MASK"),
            ),
            "Consumer": _consumer_definition(pixels="IMAGE", mask="MASK"),
        },
    )

    assert len(plan.mask_bindings) == 1
    binding = plan.mask_bindings[0]
    assert binding.section_key == "workflow"
    image_endpoint = binding.surface.image_endpoint
    assert image_endpoint is not None
    assert (image_endpoint.node_name, image_endpoint.field_key) == (
        "photo",
        "photo_path",
    )
    assert image_endpoint.output_index == 2
    assert (binding.mask_node_name, binding.mask_field_key) == (
        "stencil",
        "stencil_path",
    )
    assert binding.mask_endpoint.output_index == 1


def test_multiple_images_on_consumer_do_not_create_mask_binding() -> None:
    """A mask relation should fail closed when its image context is ambiguous."""

    graph = {
        "nodes": {
            "image_a": {"class_type": "LoadImage", "inputs": {}},
            "image_b": {"class_type": "LoadImage", "inputs": {}},
            "mask": {"class_type": "LoadImageMask", "inputs": {}},
            "consumer": {
                "class_type": "Consumer",
                "inputs": {
                    "image_a": ["image_a", 0],
                    "image_b": ["image_b", 0],
                    "mask": ["mask", 0],
                },
            },
        }
    }

    plan = _canvas_plan("cube", graph)

    assert plan.mask_bindings == ()


def test_mask_shared_by_different_image_contexts_is_ambiguous() -> None:
    """One mask attached to distinct images should not expose either relation."""

    graph = {
        "nodes": {
            "image_a": {"class_type": "LoadImage", "inputs": {}},
            "image_b": {"class_type": "LoadImage", "inputs": {}},
            "mask": {"class_type": "LoadImageMask", "inputs": {}},
            "consumer_a": {
                "class_type": "Consumer",
                "inputs": {"pixels": ["image_a", 0], "mask": ["mask", 0]},
            },
            "consumer_b": {
                "class_type": "Consumer",
                "inputs": {"pixels": ["image_b", 0], "mask": ["mask", 0]},
            },
        }
    }

    plan = _canvas_plan("cube", graph)

    assert plan.mask_bindings == ()
    assert plan.rejected_mask_nodes == ("mask",)


def test_multiple_upload_widgets_and_output_folder_upload_fail_closed() -> None:
    """Ambiguous widgets and output-folder selectors must not become canvas inputs."""

    graph = _graph(
        uploader=("OddUpload", {}),
        consumer_inputs={"pixels": ["uploader", 0]},
    )
    ambiguous = {
        "input": {
            "required": {
                "first": (["a.png"], {"image_upload": True}),
                "second": (["b.png"], {"image_upload": True}),
            }
        },
        "output": ["IMAGE"],
    }
    output_folder = _definition(outputs=("IMAGE",), image_folder="output")

    ambiguous_index = _endpoint_index(
        "section", graph, node_definitions={"OddUpload": ambiguous}
    )
    output_index = _endpoint_index(
        "section", graph, node_definitions={"OddUpload": output_folder}
    )

    assert ambiguous_index.endpoints == ()
    assert ambiguous_index.ambiguous_endpoint_nodes == {"uploader"}
    assert output_index.endpoints == ()


def test_builtin_fallback_and_live_consumer_type_validation_are_conservative() -> None:
    """Built-ins remain usable offline while contradictory live typing is rejected."""

    graph = {
        "nodes": {
            "image": {"class_type": "LoadImage", "inputs": {}},
            "mask": {"class_type": "LoadImageMask", "inputs": {}},
            "consumer": {
                "class_type": "Consumer",
                "inputs": {"pixels": ["image", 0], "mask": ["mask", 0]},
            },
        }
    }

    fallback = _canvas_plan("cube", graph)
    contradicted = _canvas_plan(
        "cube",
        graph,
        node_definitions={
            "Consumer": _consumer_definition(pixels="MASK", mask="IMAGE")
        },
    )

    assert len(fallback.image_endpoints) == 1
    assert len(fallback.mask_bindings) == 1
    assert contradicted.mask_bindings == ()


def _endpoint_index(
    section_key: str,
    graph: Mapping[str, object],
    *,
    node_definitions: Mapping[str, Mapping[str, object]] | None = None,
) -> InputAssetEndpointIndex:
    """Build endpoint discovery through its focused production owner."""

    definitions = WorkflowNodeDefinitionService()
    return InputAssetEndpointService(definitions).build_index(
        section_key,
        graph,
        node_definitions=node_definitions,
    )


def _canvas_plan(
    section_key: str,
    graph: Mapping[str, object],
    *,
    node_definitions: Mapping[str, Mapping[str, object]] | None = None,
) -> InputCanvasPlan:
    """Build canvas relationships through the unified production planner."""

    definitions = WorkflowNodeDefinitionService()
    return InputCanvasPlanService(
        node_definition_service=definitions,
        endpoint_service=InputAssetEndpointService(definitions),
    ).build_plan(
        section_key,
        graph,
        node_definitions=node_definitions,
    )


def _graph(
    *,
    uploader: tuple[str, dict[str, object]],
    consumer_inputs: dict[str, object],
) -> dict[str, object]:
    """Build a minimal upload-to-consumer API graph."""

    class_type, inputs = uploader
    return {
        "nodes": {
            "uploader": {"class_type": class_type, "inputs": inputs},
            "consumer": {"class_type": "Consumer", "inputs": consumer_inputs},
        }
    }


def _definition(
    *,
    field_key: str = "image",
    outputs: tuple[str, ...],
    image_folder: str | None = None,
) -> dict[str, object]:
    """Build one live upload-node definition."""

    metadata: dict[str, object] = {"image_upload": True}
    if image_folder is not None:
        metadata["image_folder"] = image_folder
    return {
        "input": {"required": {field_key: (["example.png"], metadata)}},
        "output": list(outputs),
    }


def _consumer_definition(**input_types: str) -> dict[str, object]:
    """Build one typed live consumer definition."""

    return {
        "input": {
            "required": {
                field_key: (input_type,)
                for field_key, input_type in input_types.items()
            }
        },
        "output": [],
    }

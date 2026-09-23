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

"""Verify portable model identity remains bound to canonical Cube fields."""

from __future__ import annotations

from copy import deepcopy
from typing import cast

from substitute.application.workflows.portable_model_manifest import (
    PORTABLE_MODEL_MANIFEST_KEY,
    PortableModelManifestCodec,
)
from substitute.application.workflows.portable_model_projection import (
    PortableModelManifestService,
)
from substitute.domain.common import JsonObject


class _HashLookup:
    """Return deterministic hashes for selected test model values."""

    def hash_for_model_value(self, *, kind: str, value: str) -> str | None:
        """Return one hash only for the fixture's known models."""

        hashes = {
            ("diffusion_models", "folder/original.safetensors"): "A" * 64,
            ("upscale_models", "RealESRGAN_x4plus.pth"): "B" * 64,
            ("diffusion_models", "moved/model.safetensors"): "A" * 64,
        }
        return hashes.get((kind, value))


class _AmbiguousHashLookup(_HashLookup):
    """Return the same literal under two catalog kinds to force safe omission."""

    def hash_for_model_value(self, *, kind: str, value: str) -> str | None:
        """Make the nested generic field's model kind ambiguous."""

        if value == "RealESRGAN_x4plus.pth" and kind in {
            "upscale_models",
            "ultralytics",
        }:
            return "B" * 64
        return super().hash_for_model_value(kind=kind, value=value)


class _RecordingHashLookup:
    """Record portable candidates without resolving any local identity."""

    def __init__(self) -> None:
        """Initialize empty lookup evidence."""

        self.calls: list[tuple[str, str]] = []

    def hash_for_model_value(self, *, kind: str, value: str) -> str | None:
        """Record one candidate and return no installed hash."""

        self.calls.append((kind, value))
        return None


def test_annotation_preserves_comfy_graph_and_writes_stable_model_bindings() -> None:
    """Manifest metadata must not alter executable Comfy topology or Cube values."""

    graph = _graph()
    before_nodes = deepcopy(graph["nodes"])
    before_definitions = deepcopy(graph["definitions"])

    references = PortableModelManifestService(_HashLookup()).annotate(graph)

    assert graph["nodes"] == before_nodes
    assert graph["definitions"] == before_definitions
    assert [(item.kind, item.value, item.sha256) for item in references] == [
        ("diffusion_models", "folder/original.safetensors", "A" * 64),
        ("upscale_models", "RealESRGAN_x4plus.pth", "B" * 64),
    ]
    extra = cast(dict[str, object], graph["extra"])
    manifest = cast(dict[str, object], extra[PORTABLE_MODEL_MANIFEST_KEY])
    assert manifest["schema_version"] == 1


def test_resolution_projection_rewrites_only_backend_resolved_fields() -> None:
    """Backend-returned values should update embedded documents and refreshed metadata."""

    graph = _graph()
    service = PortableModelManifestService(_HashLookup())
    service.annotate(graph)
    projection = service.project_for_resolution(graph)
    assert projection is not None
    parsed = projection.parsed_script
    buffer = cast(dict[str, object], parsed.buffers["Text to Image"])
    nodes = cast(dict[str, object], buffer["nodes"])
    model_node = cast(dict[str, object], nodes["models"])
    inputs = cast(dict[str, object], model_node["inputs"])
    inputs["diffusion_model"] = "moved/model.safetensors"

    service.apply_resolved_script(
        graph,
        projection=projection,
        parsed_script=parsed,
    )

    document = _document(graph)
    implementation = cast(dict[str, object], document["implementation"])
    document_nodes = cast(dict[str, object], implementation["nodes"])
    resolved_node = cast(dict[str, object], document_nodes["models"])
    resolved_inputs = cast(dict[str, object], resolved_node["inputs"])
    assert resolved_inputs["diffusion_model"] == "moved/model.safetensors"
    references = PortableModelManifestCodec().read(graph)
    assert references[0].value == "moved/model.safetensors"
    assert references[0].sha256 == "A" * 64


def test_projection_ignores_stale_and_malformed_external_metadata() -> None:
    """Optional metadata must fail closed when bindings or hashes are untrustworthy."""

    graph = _graph()
    graph["extra"] = {
        PORTABLE_MODEL_MANIFEST_KEY: {
            "schema_version": 1,
            "references": [
                {
                    "instance_id": "instance-1",
                    "node_symbol": "models",
                    "input_name": "diffusion_model",
                    "kind": "diffusion_models",
                    "value": "stale.safetensors",
                    "sha256": "A" * 64,
                },
                {
                    "instance_id": "instance-1",
                    "node_symbol": "upscale",
                    "input_name": "model_name",
                    "kind": "upscale_models",
                    "value": "RealESRGAN_x4plus.pth",
                    "sha256": "not-a-hash",
                },
            ],
        }
    }

    assert (
        PortableModelManifestService(_HashLookup()).project_for_resolution(graph)
        is None
    )


def test_annotation_omits_model_name_when_catalog_kind_is_ambiguous() -> None:
    """A nested generic model field must not guess its destination model kind."""

    references = PortableModelManifestService(_AmbiguousHashLookup()).annotate(_graph())

    assert [(reference.kind, reference.value) for reference in references] == [
        ("diffusion_models", "folder/original.safetensors")
    ]


def test_annotation_excludes_non_model_configuration_fields() -> None:
    """Diffusion modes, dtypes, and device choices must never enter hash lookup."""

    lookup = _RecordingHashLookup()

    PortableModelManifestService(lookup).annotate(_graph())

    assert all(value not in {"default", "multidiffusion"} for _, value in lookup.calls)
    assert ("upscale_models", "RealESRGAN_x4plus.pth") in lookup.calls
    assert ("ultralytics", "RealESRGAN_x4plus.pth") in lookup.calls


def _graph() -> JsonObject:
    """Return one canonical Cube graph containing two model picker fields."""

    return {
        "version": 0.4,
        "nodes": [
            {
                "id": 1,
                "type": "definition-1",
                "inputs": [],
                "outputs": [],
                "properties": {
                    "sugarcubes_cube": {
                        "instance_id": "instance-1",
                        "instance_alias": "Text to Image",
                    }
                },
            }
        ],
        "links": [],
        "definitions": {
            "subgraphs": [
                {
                    "id": "definition-1",
                    "nodes": [],
                    "links": [],
                    "inputs": [],
                    "outputs": [],
                    "extra": {
                        "sugarcubes_document": {
                            "cube_id": "example/text-to-image",
                            "implementation": {
                                "nodes": {
                                    "models": {
                                        "class_type": "SimpleSyrup.SimpleLoadAnima",
                                        "inputs": {
                                            "diffusion_model": "folder/original.safetensors",
                                            "diffusion_weight_dtype": "default",
                                            "text_encoder_device": "default",
                                        },
                                    },
                                    "sampler": {
                                        "class_type": "CustomSampler",
                                        "inputs": {"diffusion_mode": "multidiffusion"},
                                    },
                                    "upscale": {
                                        "class_type": "nested-subgraph-uuid",
                                        "inputs": {
                                            "model_name": "RealESRGAN_x4plus.pth"
                                        },
                                    },
                                },
                                "inputs": {},
                                "outputs": {},
                            },
                        }
                    },
                }
            ]
        },
    }


def _document(graph: JsonObject) -> dict[str, object]:
    """Return the mutable embedded Cube document from the fixture graph."""

    definitions = cast(dict[str, object], graph["definitions"])
    subgraphs = cast(list[object], definitions["subgraphs"])
    definition = cast(dict[str, object], subgraphs[0])
    extra = cast(dict[str, object], definition["extra"])
    return cast(dict[str, object], extra["sugarcubes_document"])

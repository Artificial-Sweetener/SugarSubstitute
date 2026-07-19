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

"""Contract tests for application workflow export service orchestration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

from substitute.application.recipes.workflow_export_service import (
    WorkflowExportService,
    normalize_csv_wildcard_nodes,
)


class _FakeWorkflowRepository:
    """Repository double capturing workflow JSON persistence payloads."""

    def __init__(self) -> None:
        self.saved: list[tuple[Path, dict[str, object]]] = []

    def save_workflow_json(
        self, path: Path, workflow_payload: dict[str, object]
    ) -> None:
        """Capture workflow save calls from service orchestration."""

        self.saved.append((path, workflow_payload))


class _FakeWorkflowPayloadCompiler:
    """Compiler double capturing Sugar text and output directory."""

    def __init__(self, payload: dict[str, object]) -> None:
        """Store the payload returned for compilation."""

        self.payload = payload
        self.calls: list[tuple[str, Path]] = []

    def compile_workflow_payload(
        self,
        *,
        sugar_script_text: str,
        output_dir: Path,
    ) -> dict[str, object]:
        """Return the configured workflow payload."""

        self.calls.append((sugar_script_text, output_dir))
        return self.payload


class _FakeNodeDefinitionGateway:
    """Node-definition gateway double returning configured object-info payloads."""

    def __init__(self, definitions: dict[str, dict[str, object]]) -> None:
        """Store live definitions by class type."""

        self._definitions = definitions

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return non-blocking live definitions for protocol completeness."""

        return self.get_required_node_definition(node_class)

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return a Comfy object-info response shape for one node class."""

        definition = self._definitions.get(node_class)
        return {node_class: definition} if definition is not None else {}


def _service(
    payload: dict[str, object] | None = None,
    *,
    node_definition_gateway: _FakeNodeDefinitionGateway | None = None,
) -> tuple[
    WorkflowExportService, _FakeWorkflowRepository, _FakeWorkflowPayloadCompiler
]:
    """Return an export service with fake repository and compiler collaborators."""

    repository = _FakeWorkflowRepository()
    compiler = _FakeWorkflowPayloadCompiler(payload or {})
    return (
        WorkflowExportService(
            workflow_repository=repository,
            workflow_payload_compiler=compiler,
            node_definition_gateway=node_definition_gateway,
        ),
        repository,
        compiler,
    )


def test_workflow_export_service_compiles_and_persists_json() -> None:
    """Export should compile workflow payload then persist through repository port."""

    expected_payload: dict[str, object] = {
        "1": {"class_type": "KSampler", "inputs": {"steps": 20}}
    }
    service, repository, compiler = _service(expected_payload)

    payload = service.export_workflow_json(
        destination_path=Path("E:/recipes/export.json"),
        sugar_script_text="use Cube as A",
        output_dir=Path("E:/projects"),
    )

    assert compiler.calls == [("use Cube as A", Path("E:/projects"))]
    assert payload == expected_payload
    assert repository.saved == [(Path("E:/recipes/export.json"), expected_payload)]


def test_compile_workflow_payload_preserves_backslashes_in_node_string_literals() -> (
    None
):
    """Workflow compile should preserve literal backslashes in checkpoint names."""

    service, _repository, _compiler = _service(
        {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": r"Flux\flux1-dev-bnb-nf4.safetensors"},
                "_meta": {
                    "title": "txt.checkpoint",
                    "substitute": {
                        "cube_alias": "txt",
                        "node_name": "checkpoint",
                    },
                },
            }
        }
    )

    workflow_payload = service.compile_workflow_payload(
        sugar_script_text="use Cube as txt",
        output_dir=Path("E:/devprojects/SugarSubstitute/projects"),
    )

    checkpoint_nodes = [
        node
        for node in workflow_payload.values()
        if isinstance(node, dict) and node.get("class_type") == "CheckpointLoaderSimple"
    ]
    assert checkpoint_nodes
    assert checkpoint_nodes[0]["inputs"]["ckpt_name"] == (
        r"Flux\flux1-dev-bnb-nf4.safetensors"
    )
    metadata = checkpoint_nodes[0].get("_meta")
    assert isinstance(metadata, dict)
    assert metadata["title"] == "txt.checkpoint"
    assert metadata["substitute"] == {
        "cube_alias": "txt",
        "node_name": "checkpoint",
    }


def test_compile_workflow_payload_preserves_escaped_prompt_parentheses_in_prompt_nodes() -> (
    None
):
    """Workflow compile should preserve escaped literal prompt parentheses in node inputs."""

    service, _repository, _compiler = _service(
        {
            "1": {
                "class_type": "String",
                "inputs": {"prompt_template": r"painting \(medium\)"},
            }
        }
    )

    workflow_payload = service.compile_workflow_payload(
        sugar_script_text="use Cube as txt",
        output_dir=Path("E:/devprojects/SugarSubstitute/projects"),
    )

    prompt_nodes = [
        node
        for node in workflow_payload.values()
        if isinstance(node, dict)
        and isinstance(node.get("inputs"), dict)
        and node["inputs"].get("prompt_template") == r"painting \(medium\)"
    ]
    assert prompt_nodes
    assert prompt_nodes[0]["inputs"]["prompt_template"] == r"painting \(medium\)"


def test_normalize_csv_wildcard_nodes_replaces_backend_node_with_string() -> None:
    """CSVWildcardNode should not be required in queued or exported payloads."""

    workflow_nodes: dict[str, object] = {
        "1": {
            "class_type": "CSVWildcardNode",
            "inputs": {"prompt_template": "A wolf", "seed": 999},
        },
        "2": {"class_type": "KSampler", "inputs": {}},
    }

    normalize_csv_wildcard_nodes(workflow_nodes)

    assert workflow_nodes["1"] == {
        "class_type": "String",
        "inputs": {"value": "A wolf"},
    }
    assert workflow_nodes["2"] == {"class_type": "KSampler", "inputs": {}}


def test_compile_workflow_payload_normalizes_csv_wildcard_nodes() -> None:
    """Compile should normalize CSVWildcardNode payloads before returning."""

    workflow_payload: dict[str, object] = {
        "1": {
            "class_type": "CSVWildcardNode",
            "inputs": {"prompt_template": "A fox", "seed": 1},
        }
    }
    service, _repository, _compiler = _service(workflow_payload)

    payload = service.compile_workflow_payload(
        sugar_script_text="use Cube as A",
        output_dir=Path("E:/projects"),
    )

    assert payload["1"] == {"class_type": "String", "inputs": {"value": "A fox"}}


def test_compile_workflow_payload_fills_missing_classic_picker_default() -> None:
    """Compile should hydrate absent required classic-list pickers from local Comfy."""

    workflow_payload: dict[str, object] = {
        "out": {
            "class_type": "SugarCubes.CubeOutput",
            "inputs": {
                "cube_id": "local/demo.cube",
                "instance_alias": "txt",
                "value": ["1", 0],
            },
        },
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {},
            "_meta": {"substitute": {"cube_alias": "txt", "node_name": "checkpoint"}},
        },
    }
    service, _repository, _compiler = _service(
        workflow_payload,
        node_definition_gateway=_FakeNodeDefinitionGateway(
            {
                "CheckpointLoaderSimple": {
                    "input": {
                        "required": {
                            "ckpt_name": [
                                ["local-a.safetensors", "local-b.safetensors"],
                                {"default": "local-b.safetensors"},
                            ]
                        }
                    }
                }
            }
        ),
    )

    payload = service.compile_workflow_payload(
        sugar_script_text="use Cube as txt",
        output_dir=Path("E:/projects"),
    )

    node = cast(dict[str, Any], payload["1"])
    inputs = cast(dict[str, Any], node["inputs"])
    assert inputs["ckpt_name"] == "local-b.safetensors"


def test_compile_workflow_payload_preserves_runtime_asset_picker_values() -> None:
    """Compile should not replace LoadImage asset references with Comfy defaults."""

    workflow_payload: dict[str, object] = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": r"D:\Downloads\twilight-beach-original (1).png"},
            "_meta": {
                "substitute": {"cube_alias": "SDXL/Inpaint", "node_name": "load_image"}
            },
        },
        "2": {
            "class_type": "LoadImageMask",
            "inputs": {
                "image": "twilight-beach-original_(1)__ae6d5e73__load_image_as_mask.png",
                "channel": "alpha",
            },
            "_meta": {
                "substitute": {
                    "cube_alias": "SDXL/Inpaint",
                    "node_name": "load_image_as_mask",
                }
            },
        },
    }
    service, _repository, _compiler = _service(
        workflow_payload,
        node_definition_gateway=_FakeNodeDefinitionGateway(
            {
                "LoadImage": {
                    "input": {
                        "required": {
                            "image": [
                                ["00282-3430329909-ad-before.png"],
                                {"default": "00282-3430329909-ad-before.png"},
                            ]
                        }
                    }
                },
                "LoadImageMask": {
                    "input": {
                        "required": {
                            "image": [
                                ["00282-3430329909-ad-before.png"],
                                {"default": "00282-3430329909-ad-before.png"},
                            ],
                            "channel": [["alpha", "red"], {"default": "alpha"}],
                        }
                    }
                },
            }
        ),
    )

    payload = service.compile_workflow_payload(
        sugar_script_text='use "inpaint" as "SDXL/Inpaint"',
        output_dir=Path("E:/projects"),
    )

    load_image = cast(dict[str, Any], payload["1"])
    load_image_inputs = cast(dict[str, Any], load_image["inputs"])
    load_mask = cast(dict[str, Any], payload["2"])
    load_mask_inputs = cast(dict[str, Any], load_mask["inputs"])
    assert load_image_inputs["image"] == r"D:\Downloads\twilight-beach-original (1).png"
    assert (
        load_mask_inputs["image"]
        == "twilight-beach-original_(1)__ae6d5e73__load_image_as_mask.png"
    )
    assert load_mask_inputs["channel"] == "alpha"


def test_compile_workflow_payload_selects_sole_picker_option() -> None:
    """Executable prompts select the only available model for a blank picker."""

    workflow_payload: dict[str, object] = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": ""},
            "_meta": {
                "substitute": {
                    "cube_alias": "SDXL/Text to Image",
                    "node_name": "checkpoint",
                }
            },
        },
    }
    service, _repository, _compiler = _service(
        workflow_payload,
        node_definition_gateway=_FakeNodeDefinitionGateway(
            {
                "CheckpointLoaderSimple": {
                    "input": {
                        "required": {
                            "ckpt_name": [
                                [r"Flux\flux1-dev-bnb-nf4.safetensors"],
                                {},
                            ]
                        }
                    }
                }
            }
        ),
    )

    payload = service.compile_workflow_payload(
        sugar_script_text='use "cube" as "SDXL/Text to Image"',
        output_dir=Path("E:/projects"),
    )

    node = cast(dict[str, Any], payload["1"])
    inputs = cast(dict[str, Any], node["inputs"])
    assert inputs["ckpt_name"] == r"Flux\flux1-dev-bnb-nf4.safetensors"


def test_compile_workflow_payload_rejects_blank_picker_without_models() -> None:
    """Executable prompts reject required model fields with no choices."""

    workflow_payload: dict[str, object] = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": ""},
            "_meta": {
                "substitute": {
                    "cube_alias": "SDXL/Text to Image",
                    "node_name": "checkpoint",
                }
            },
        },
    }
    service, _repository, _compiler = _service(
        workflow_payload,
        node_definition_gateway=_FakeNodeDefinitionGateway(
            {"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [[], {}]}}}}
        ),
    )

    try:
        service.compile_workflow_payload(
            sugar_script_text='use "cube" as "SDXL/Text to Image"',
            output_dir=Path("E:/projects"),
        )
    except RuntimeError as error:
        assert "No local Comfy picker default is available" in str(error)
        assert "cube_alias=SDXL/Text to Image" in str(error)
        assert "node_name=checkpoint" in str(error)
    else:  # pragma: no cover - assertion path only
        raise AssertionError("Expected blank picker hydration to fail")


def test_compile_workflow_payload_rejects_blank_upscaler_without_models() -> None:
    """Required empty upscaler choices must remain blocked at execution time."""

    workflow_payload: dict[str, object] = {
        "1": {
            "class_type": "UpscaleModelLoader",
            "inputs": {"model_name": ""},
            "_meta": {
                "substitute": {
                    "cube_alias": "upscale",
                    "node_name": "upscale_model",
                }
            },
        }
    }
    service, _repository, _compiler = _service(
        workflow_payload,
        node_definition_gateway=_FakeNodeDefinitionGateway(
            {
                "UpscaleModelLoader": {
                    "input": {
                        "required": {
                            "model_name": ["COMBO", {"options": []}],
                        }
                    }
                }
            }
        ),
    )

    try:
        service.compile_workflow_payload(
            sugar_script_text="use Upscale as upscale",
            output_dir=Path("E:/projects"),
        )
    except RuntimeError as error:
        message = str(error)
        assert "No local Comfy picker default is available" in message
        assert "cube_alias=upscale" in message
        assert "node_name=upscale_model" in message
        assert "input=model_name" in message
    else:  # pragma: no cover - assertion path only
        raise AssertionError("Expected blank upscaler hydration to fail")


def test_compile_workflow_payload_replaces_unavailable_combo_picker_default(
    caplog: Any,
) -> None:
    """Compile should treat authored picker values as local preferences."""

    workflow_payload: dict[str, object] = {
        "1": {
            "class_type": "SeedVR2LoadDiTModel",
            "inputs": {
                "model": "missing.safetensors",
                "device": "cuda:0",
            },
            "_meta": {"substitute": {"cube_alias": "up", "node_name": "load_dit"}},
        }
    }
    service, _repository, _compiler = _service(
        workflow_payload,
        node_definition_gateway=_FakeNodeDefinitionGateway(
            {
                "SeedVR2LoadDiTModel": {
                    "input": {
                        "required": {
                            "model": [
                                "COMBO",
                                {
                                    "default": "seedvr2_default.safetensors",
                                    "options": ["seedvr2_default.safetensors"],
                                },
                            ],
                            "device": [
                                "COMBO",
                                {"default": "cuda:0", "options": ["cuda:0"]},
                            ],
                        }
                    }
                }
            }
        ),
    )

    with caplog.at_level(
        logging.DEBUG,
        logger="sugarsubstitute.application.recipes.picker_defaults",
    ):
        payload = service.compile_workflow_payload(
            sugar_script_text="use Cube as up",
            output_dir=Path("E:/projects"),
        )

    node = cast(dict[str, Any], payload["1"])
    inputs = cast(dict[str, Any], node["inputs"])
    assert inputs["model"] == "seedvr2_default.safetensors"
    assert inputs["device"] == "cuda:0"
    assert "Replaced unavailable authored picker value" in caplog.text


def test_compile_workflow_payload_accepts_missing_output_directory(
    tmp_path: Path,
) -> None:
    """Workflow compile should not require SugarPackage to create output directories."""

    service, _repository, compiler = _service({"1": {"class_type": "KSampler"}})
    missing_output_dir = tmp_path / "missing-output-dir"

    workflow_payload = service.compile_workflow_payload(
        sugar_script_text="use Cube as txt",
        output_dir=missing_output_dir,
    )

    assert workflow_payload
    assert compiler.calls == [("use Cube as txt", missing_output_dir)]
    assert not missing_output_dir.exists()


def test_compile_workflow_payload_preserves_empty_latent_sampler_denoise() -> None:
    """Compile should preserve empty-latent sampler denoise before returning payload."""

    workflow_payload: dict[str, object] = {
        "latent": {"class_type": "EmptyLatentImage", "inputs": {}},
        "sampler": {
            "class_type": "CustomSamplerLike",
            "inputs": {"latent_image": ["latent", 0], "denoise": 0.25},
        },
    }
    service, _repository, _compiler = _service(workflow_payload)

    payload = service.compile_workflow_payload(
        sugar_script_text="use Cube as A",
        output_dir=Path("E:/projects"),
    )

    sampler = cast(dict[str, Any], payload["sampler"])
    assert sampler["inputs"]["denoise"] == 0.25


def test_compile_workflow_payload_preserves_wrapped_prompt_denoise() -> None:
    """Compile should preserve nested denoise when Sugar returns a wrapper."""

    workflow_payload: dict[str, object] = {
        "prompt": {
            "latent": {"class_type": "EmptyLatentImage", "inputs": {}},
            "sampler": {
                "class_type": "CustomSamplerLike",
                "inputs": {"latent_image": ["latent", 0], "denoise": 0.25},
            },
        },
        "client_id": "substitute",
    }
    service, _repository, _compiler = _service(workflow_payload)

    payload = service.compile_workflow_payload(
        sugar_script_text="use Cube as A",
        output_dir=Path("E:/projects"),
    )

    prompt = cast(dict[str, Any], payload["prompt"])
    sampler = cast(dict[str, Any], prompt["sampler"])
    assert sampler["inputs"]["denoise"] == 0.25


def test_compile_workflow_payload_preserves_encoded_latent_sampler_denoise() -> None:
    """Compile should preserve denoise when sampler latents are not empty latents."""

    workflow_payload: dict[str, object] = {
        "encode": {"class_type": "VAEEncode", "inputs": {}},
        "sampler": {
            "class_type": "CustomSamplerLike",
            "inputs": {"latent_image": ["encode", 0], "denoise": 0.25},
        },
    }
    service, _repository, _compiler = _service(workflow_payload)

    payload = service.compile_workflow_payload(
        sugar_script_text="use Cube as A",
        output_dir=Path("E:/projects"),
    )

    sampler = cast(dict[str, Any], payload["sampler"])
    assert sampler["inputs"]["denoise"] == 0.25


def test_build_default_export_path_uses_project_folder(
    tmp_path: Path,
) -> None:
    """Default export paths should live beside the workflow recipe."""

    service, _repository, _compiler = _service()

    destination = service.build_default_export_path("Recipe Export", tmp_path)

    assert destination == (tmp_path / "Recipe Export" / "Recipe Export.json").resolve()


def test_validate_export_destination_accepts_paths_outside_output_root(
    tmp_path: Path,
) -> None:
    """Export destination validation should allow explicit paths outside output root."""

    service, _repository, _compiler = _service()

    destination = service.validate_export_destination(tmp_path.parent / "external.json")

    assert destination == (tmp_path.parent / "external.json").resolve()


def test_validate_export_destination_rejects_directory_paths(tmp_path: Path) -> None:
    """Export destination validation should reject directories."""

    service, _repository, _compiler = _service()

    try:
        service.validate_export_destination(tmp_path)
    except ValueError as error:
        assert "Workflow export" in str(error)
    else:  # pragma: no cover - assertion path only
        raise AssertionError(
            "Expected export destination validation to reject directory"
        )


def test_validate_export_destination_rejects_non_json_paths(tmp_path: Path) -> None:
    """Export destination validation should reject non-JSON files."""

    service, _repository, _compiler = _service()

    try:
        service.validate_export_destination(tmp_path / "workflow.txt")
    except ValueError as error:
        assert ".json" in str(error)
    else:  # pragma: no cover - assertion path only
        raise AssertionError("Expected export destination validation to reject suffix")

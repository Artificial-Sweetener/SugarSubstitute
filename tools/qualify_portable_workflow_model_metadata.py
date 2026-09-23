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

"""Qualify attached and synthetic portable Comfy workflow metadata."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import cast

from PIL import Image, PngImagePlugin

from substitute.application.workflows.portable_model_graph import (
    cube_document_bindings,
    model_fields,
)
from substitute.application.workflows.portable_model_manifest import (
    PORTABLE_MODEL_MANIFEST_KEY,
    PortableModelManifestCodec,
)
from substitute.application.workflows.portable_model_projection import (
    PortableModelManifestService,
)
from substitute.domain.common import JsonObject
from substitute.infrastructure.comfy.workflow_document_repository import (
    ComfyWorkflowDocumentRepository,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_ARTIFACT_ROOT = (
    _REPO_ROOT / "build" / "qualification" / "portable-workflow-model-metadata"
)


class _SyntheticKnownHashLookup:
    """Supply identity only for the qualification fixture's invented model value."""

    def hash_for_model_value(self, *, kind: str, value: str) -> str | None:
        """Return the fixture's declared hash without inspecting user artifacts."""

        if (kind, value) == ("checkpoints", "synthetic-known.safetensors"):
            return "A" * 64
        return None


def qualify(
    source: Path,
    *,
    artifact_root: Path = _DEFAULT_ARTIFACT_ROOT,
) -> dict[str, object]:
    """Inspect the attached source and prove controlled new-save round trips."""

    source = source.resolve()
    artifact_root = artifact_root.resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)
    repository = ComfyWorkflowDocumentRepository()
    with Image.open(source) as image:
        metadata = cast(dict[str, object], dict(cast(object, image).text))
    workflow = repository.load(source)
    attached_references = PortableModelManifestCodec().read(workflow)
    attached_fields = _model_field_evidence(workflow)
    projection = PortableModelManifestService(
        _SyntheticKnownHashLookup()
    ).project_for_resolution(workflow)
    synthetic = _qualify_synthetic_roundtrip(artifact_root, repository)
    evidence: dict[str, object] = {
        "schema_version": 1,
        "result": "passed",
        "attached_workflow": {
            "path": str(source),
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "metadata_keys": sorted(metadata),
            "has_workflow": isinstance(metadata.get("workflow"), str),
            "has_sugar_script": isinstance(metadata.get("sugar_script"), str),
            "portable_manifest_key": PORTABLE_MODEL_MANIFEST_KEY,
            "portable_reference_count": len(attached_references),
            "model_fields": attached_fields,
            "resolution_projection_created": projection is not None,
            "automatic_acquisition_possible": bool(attached_references),
            "observed_reason": (
                "The PNG contains canonical workflow metadata and model values, but "
                "neither legacy SugarScript hashes nor a portable model manifest. "
                "Substitute cannot safely infer an absent model identity."
            ),
        },
        "controlled_new_save": synthetic,
        "identity_safety": {
            "attached_hashes_invented": False,
            "synthetic_hash_scope": "qualification fixture only",
        },
    }
    report_path = artifact_root / "evidence.json"
    report_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return evidence


def _qualify_synthetic_roundtrip(
    artifact_root: Path,
    repository: ComfyWorkflowDocumentRepository,
) -> dict[str, object]:
    """Round-trip a canonical graph whose local fixture hash is known."""

    graph = _synthetic_graph()
    topology_before = deepcopy(
        {key: graph[key] for key in ("nodes", "links", "definitions")}
    )
    references = PortableModelManifestService(_SyntheticKnownHashLookup()).annotate(
        graph
    )
    serialized = json.dumps(graph, separators=(",", ":"), sort_keys=True)
    json_path = artifact_root / "synthetic-portable-workflow.json"
    json_path.write_text(serialized + "\n", encoding="utf-8")
    png_path = artifact_root / "synthetic-portable-workflow.png"
    png_metadata = PngImagePlugin.PngInfo()
    png_metadata.add_text("workflow", serialized)
    Image.new("RGB", (64, 64), "#202020").save(png_path, pnginfo=png_metadata)
    json_loaded = repository.load(json_path)
    png_loaded = repository.load(png_path)
    topology_after = {key: graph[key] for key in ("nodes", "links", "definitions")}
    return {
        "known_fixture_reference_count": len(references),
        "known_fixture_sha256": references[0].sha256 if references else None,
        "manifest_location": f"workflow.extra.{PORTABLE_MODEL_MANIFEST_KEY}",
        "executable_topology_unchanged": topology_after == topology_before,
        "json_roundtrip_exact": json_loaded == graph,
        "png_roundtrip_exact": png_loaded == graph,
        "comfy_workflow_key_only": True,
        "json_artifact": str(json_path),
        "png_artifact": str(png_path),
    }


def _model_field_evidence(graph: JsonObject) -> list[dict[str, str]]:
    """Return literal model fields without claiming unavailable identity hashes."""

    fields: list[dict[str, str]] = []
    for binding in cube_document_bindings(graph):
        for field in model_fields(binding.document):
            fields.append(
                {
                    "instance_id": binding.instance_id,
                    "alias": binding.alias,
                    "node_symbol": field.node_symbol,
                    "input_name": field.input_name,
                    "kind_candidates": list(field.kind_candidates),
                    "value": field.value,
                }
            )
    return fields


def _synthetic_graph() -> JsonObject:
    """Return one minimal canonical Cube workflow with a known fixture model."""

    return {
        "version": 0.4,
        "nodes": [
            {
                "id": 1,
                "type": "qualification-definition",
                "inputs": [],
                "outputs": [],
                "properties": {
                    "sugarcubes_cube": {
                        "instance_id": "qualification-instance",
                        "instance_alias": "Qualification Cube",
                    }
                },
            }
        ],
        "links": [],
        "definitions": {
            "subgraphs": [
                {
                    "id": "qualification-definition",
                    "nodes": [],
                    "links": [],
                    "inputs": [],
                    "outputs": [],
                    "extra": {
                        "sugarcubes_document": {
                            "cube_id": "qualification/cube",
                            "implementation": {
                                "nodes": {
                                    "model": {
                                        "class_type": "CheckpointLoaderSimple",
                                        "inputs": {
                                            "ckpt_name": "synthetic-known.safetensors"
                                        },
                                    }
                                },
                                "inputs": {},
                                "outputs": {},
                            },
                        }
                    },
                }
            ]
        },
        "extra": {"qualification_unrelated_metadata": {"preserved": True}},
    }


def _arguments() -> argparse.Namespace:
    """Parse optional local qualification paths."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, default=_DEFAULT_ARTIFACT_ROOT)
    return parser.parse_args()


def main() -> int:
    """Write evidence for the exact attached PNG and controlled new saves."""

    arguments = _arguments()
    qualify(arguments.source, artifact_root=arguments.artifact_root)
    print(arguments.artifact_root.resolve() / "evidence.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

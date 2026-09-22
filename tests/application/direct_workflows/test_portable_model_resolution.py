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

"""Verify Backend-authoritative resolution of portable canonical metadata."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pytest

from substitute.application.direct_workflows import (
    PortableWorkflowModelResolutionRequired,
    PortableWorkflowModelResolutionService,
)
from substitute.application.recipes import (
    LocalRecipeModel,
    RecipeModelLoadResolver,
    RecipeModelResolutionIndex,
)
from substitute.application.workflows.portable_model_manifest import (
    PortableModelManifestCodec,
)
from substitute.application.workflows.portable_model_projection import (
    PortableModelManifestService,
)
from substitute.domain.common import JsonObject
from substitute.domain.model_metadata import (
    BackendHashLookupMatch,
    BackendHashLookupResult,
    BackendHashLookupStatus,
    BackendModelFile,
    BackendModelSource,
)


def test_resolution_uses_backend_value_and_updates_manifest_and_override() -> None:
    """BackEnd relocation should update every authoritative canonical value."""

    graph = _graph()
    manifest = PortableModelManifestService(_HashLookup())
    manifest.annotate(graph)
    backend = _BackendLookup("Installed/renamed.safetensors")
    resolver = RecipeModelLoadResolver(
        RecipeModelResolutionIndex(
            (
                LocalRecipeModel(
                    kind="checkpoints",
                    backend_value="stale.safetensors",
                    display_name="stale",
                    relative_path="stale.safetensors",
                    sha256="A" * 64,
                ),
            )
        ),
        backend=backend,
    )
    service = PortableWorkflowModelResolutionService(manifest, lambda: resolver)

    result = service.resolve(graph)

    assert backend.calls == [("checkpoints", "A" * 64)]
    assert _model_value(result.workflow) == "Installed/renamed.safetensors"
    references = PortableModelManifestCodec().read(result.workflow)
    assert references[0].value == "Installed/renamed.safetensors"
    assert references[0].sha256 == "A" * 64
    assert _override_value(result.workflow) == "Installed/renamed.safetensors"
    assert _model_value(graph) == "original.safetensors"


def test_missing_model_can_complete_with_downloaded_backend_value() -> None:
    """A user-approved download result should retain the portable hash binding."""

    graph = _graph()
    manifest = PortableModelManifestService(_HashLookup())
    manifest.annotate(graph)
    service = PortableWorkflowModelResolutionService(
        manifest,
        lambda: RecipeModelLoadResolver(
            RecipeModelResolutionIndex(()),
            backend=_BackendLookup(None),
            civitai_missing_model_lookup_enabled=lambda: False,
        ),
    )

    with pytest.raises(PortableWorkflowModelResolutionRequired) as raised:
        service.resolve(graph)

    pending = raised.value.pending
    parsed = pending.required.partial_script
    buffer = cast(dict[str, object], parsed.buffers["Text to Image"])
    nodes = cast(dict[str, object], buffer["nodes"])
    node = cast(dict[str, object], nodes["model"])
    inputs = cast(dict[str, object], node["inputs"])
    inputs["ckpt_name"] = "Downloaded/model.safetensors"
    result = service.complete(pending, parsed)

    assert _model_value(result.workflow) == "Downloaded/model.safetensors"
    assert PortableModelManifestCodec().read(result.workflow)[0].sha256 == "A" * 64


def test_hashless_workflow_loads_unchanged_without_inventing_identity() -> None:
    """An old workflow without hashes cannot and must not invent model identity."""

    graph = _graph()
    service = PortableWorkflowModelResolutionService(
        PortableModelManifestService(_HashLookup()),
        lambda: pytest.fail("resolver must not run for a hashless workflow"),
    )

    result = service.resolve(graph)

    assert result.workflow == graph
    assert PortableModelManifestCodec().read(result.workflow) == ()


class _HashLookup:
    """Return the fixture model's portable identity."""

    def hash_for_model_value(self, *, kind: str, value: str) -> str | None:
        """Return a hash only for the original fixture value."""

        if (kind, value) == ("checkpoints", "original.safetensors"):
            return "A" * 64
        return None


class _BackendLookup:
    """Return one authoritative BackEnd same-hash value or definitive absence."""

    def __init__(self, value: str | None) -> None:
        """Store the optional installed value and lookup evidence."""

        self._value = value
        self.calls: list[tuple[str, str]] = []

    def lookup_model_by_hash(
        self,
        *,
        kind: str,
        sha256: str,
    ) -> BackendHashLookupResult:
        """Return a complete authoritative lookup."""

        self.calls.append((kind, sha256))
        matches = (
            (
                BackendHashLookupMatch(
                    kind=kind,
                    value=self._value,
                    display_name="renamed",
                    source=BackendModelSource(
                        root_id="checkpoints:0",
                        relative_path=self._value,
                    ),
                    file=BackendModelFile(
                        extension=".safetensors",
                        size_bytes=1,
                        modified_at="2026-09-22T00:00:00Z",
                        created_at=None,
                    ),
                ),
            )
            if self._value is not None
            else ()
        )
        return BackendHashLookupResult(
            status=BackendHashLookupStatus.COMPLETE,
            kind=kind,
            sha256=sha256,
            matches=matches,
            job_id=None,
        )


def _graph() -> JsonObject:
    """Return one canonical graph with a stable model field and override relation."""

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
                                    "model": {
                                        "class_type": "CheckpointLoaderSimple",
                                        "inputs": {"ckpt_name": "original.safetensors"},
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
        "extra": {
            "sugarcubes_composition": {
                "schema_version": 1,
                "value_relations": [
                    {
                        "relation_id": "override:ckpt_name",
                        "owner": "substitute",
                        "kind": "global_override",
                        "override_key": "ckpt_name",
                        "value": "original.safetensors",
                        "targets": [
                            {
                                "instance_id": "instance-1",
                                "node_symbol": "model",
                                "input_name": "ckpt_name",
                            }
                        ],
                    }
                ],
            }
        },
    }


def _model_value(graph: Mapping[str, object]) -> object:
    """Return the canonical embedded model field value."""

    definitions = cast(Mapping[str, object], graph["definitions"])
    subgraphs = cast(list[object], definitions["subgraphs"])
    definition = cast(Mapping[str, object], subgraphs[0])
    extra = cast(Mapping[str, object], definition["extra"])
    document = cast(Mapping[str, object], extra["sugarcubes_document"])
    implementation = cast(Mapping[str, object], document["implementation"])
    nodes = cast(Mapping[str, object], implementation["nodes"])
    node = cast(Mapping[str, object], nodes["model"])
    inputs = cast(Mapping[str, object], node["inputs"])
    return inputs["ckpt_name"]


def _override_value(graph: Mapping[str, object]) -> object:
    """Return the canonical persisted global override value."""

    extra = cast(Mapping[str, object], graph["extra"])
    composition = cast(Mapping[str, object], extra["sugarcubes_composition"])
    relations = cast(list[object], composition["value_relations"])
    relation = cast(Mapping[str, object], relations[0])
    return relation["value"]

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

"""Provide typed fakes and builders for recipe-serialization contracts."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from substitute.application.ports.recipe_repository import LoadedRecipeDocument
from substitute.domain.workflow import CubeState


class _FakeRecipeRepository:
    """Simple in-memory recipe repository double for deterministic service tests."""

    def __init__(self) -> None:
        self.saved: list[tuple[Path, str, str]] = []
        self.loaded_path: Path | None = None

    def load_recipe_document(self, path: Path) -> LoadedRecipeDocument:
        """Return deterministic loaded document payload for parse-orchestration tests."""

        self.loaded_path = path
        return LoadedRecipeDocument(
            sugar_script_text=(
                'use "Artificial-Sweetener/Base-Cubes/Text to Image.cube" as A\n'
                "set *.*.seed = 7\n"
                '# global_override_selection {"key":"seed","selected":true}\n'
            ),
            source_path=path,
            source_kind="text",
        )

    def has_embedded_recipe_script(self, path: Path) -> bool:
        """Return deterministic PNG recipe sniffing results by filename."""

        return path.name == "embedded.png"

    def save_recipe_document(
        self,
        path: Path,
        *,
        project_name: str,
        sugar_script_text: str,
    ) -> None:
        """Capture save payload invoked by service orchestration."""

        self.saved.append((path, project_name, sugar_script_text))


class _FakeNodeDefinitionGateway:
    """Node-definition gateway double returning configured object-info payloads."""

    def __init__(self, definitions: dict[str, dict[str, object]]) -> None:
        """Store live definitions by class type."""

        self._definitions = definitions
        self.required_calls: list[str] = []

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return non-blocking live definitions for protocol completeness."""

        return self.get_required_node_definition(node_class)

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return a Comfy object-info response shape for one node class."""

        self.required_calls.append(node_class)
        definition = self._definitions.get(node_class)
        return {node_class: definition} if definition is not None else {}


class _FakeCubeDefinitionProvider:
    """Cube definition provider double for SugarScript label resolution tests."""

    def __init__(self, graphs: dict[str, dict[str, object]]) -> None:
        """Store graphs keyed by cube id."""

        self._graphs = graphs

    def load_cube_definition(
        self,
        cube_id: str,
        *,
        cube_load_trace_id: str = "",
    ) -> SimpleNamespace:
        """Return a loaded cube shape for latest-version recipe parsing."""

        _ = cube_load_trace_id
        return SimpleNamespace(graph=self._graphs[cube_id])

    def load_cube_definition_version(
        self,
        cube_id: str,
        version: str,
        *,
        cube_load_trace_id: str = "",
    ) -> SimpleNamespace:
        """Return a loaded cube shape for pinned-version recipe parsing."""

        _ = version, cube_load_trace_id
        return self.load_cube_definition(cube_id)


class _FakeModelHashLookup:
    """Return deterministic recipe model hashes without slow collaborators."""

    def __init__(self, hashes: dict[tuple[str, str], str]) -> None:
        """Store hashes by model kind and backend value."""

        self.calls: list[tuple[str, str]] = []
        self._hashes = hashes

    def hash_for_model_value(self, *, kind: str, value: str) -> str | None:
        """Return a configured hash for one model value."""

        self.calls.append((kind, value))
        return self._hashes.get((kind, value))


class _FakePromptLoraHashLookup:
    """Return deterministic inline prompt LoRA hashes for recipe saves."""

    def __init__(
        self,
        hashes: dict[str, str],
        *,
        backend_values: dict[str, str] | None = None,
    ) -> None:
        """Store hashes by prompt LoRA name."""

        self.calls: list[str] = []
        self._hashes = hashes
        self._backend_values = backend_values

    def hash_for_prompt_lora_name(self, prompt_name: str) -> str | None:
        """Return a configured hash for one prompt LoRA token name."""

        self.calls.append(prompt_name)
        return self._hashes.get(prompt_name)

    def backend_value_for_prompt_lora_name(self, prompt_name: str) -> str | None:
        """Return a configured backend value shape for protocol completeness."""

        if self._backend_values is not None:
            return self._backend_values.get(prompt_name)
        return prompt_name if prompt_name in self._hashes else None


def _canonical_test_cube_state(**kwargs: Any) -> CubeState:
    """Declare every synthetic fixture input through a canonical cube surface."""

    buffer = cast(dict[str, Any], kwargs["buffer"])
    buffer.setdefault("inputs", {})
    if "surface" not in buffer:
        controls: list[dict[str, str]] = []
        nodes = buffer.get("nodes")
        if isinstance(nodes, dict):
            for node_key, node in nodes.items():
                if not isinstance(node_key, str) or not isinstance(node, dict):
                    continue
                inputs = node.get("inputs")
                if not isinstance(inputs, dict):
                    continue
                class_type = node.get("class_type")
                for input_key in inputs:
                    if not isinstance(input_key, str):
                        continue
                    controls.append(
                        {
                            "control_id": f"{node_key}.{input_key}",
                            "symbol": node_key,
                            "input_name": input_key,
                            "label": input_key,
                            "class_type": (
                                class_type
                                if isinstance(class_type, str)
                                else "SyntheticTestNode"
                            ),
                            "value_type": "object",
                        }
                    )
        buffer["surface"] = {
            "default_flavor_id": "default",
            "controls": controls,
        }
    return CubeState(**kwargs)


def _labeled_upscale_graph() -> dict[str, object]:
    """Return a runtime graph with a labeled wrapper input."""

    wrapper_id = "77a3a6f3-813a-47da-b57d-50fcd211cc28"
    return {
        "cube_id": "upscale",
        "version": "1.0.0",
        "nodes": {
            "upscale_by_factor": {
                "class_type": wrapper_id,
                "inputs": {"value": 1.5},
            }
        },
        "inputs": {},
        "outputs": {},
        "layout": {},
        "definitions": {},
        "subgraphs": [
            {
                "id": wrapper_id,
                "name": "Upscale by Factor",
                "inputs": [
                    {
                        "name": "value",
                        "label": "Scale Factor",
                        "type": "FLOAT",
                        "linkIds": [1],
                    }
                ],
                "outputs": [{"name": "IMAGE", "label": "Image", "type": "IMAGE"}],
                "links": [],
                "nodes": [],
            }
        ],
        "surface": {
            "default_flavor_id": "default",
            "controls": [
                {
                    "control_id": "upscale_by_factor.value",
                    "symbol": "upscale_by_factor",
                    "input_name": "value",
                    "label": "Scale Factor",
                    "class_type": wrapper_id,
                    "value_type": "number",
                }
            ],
        },
    }

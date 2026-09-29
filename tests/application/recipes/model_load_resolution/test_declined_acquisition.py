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

"""Verify recipe loading without acquisition preserves authored model values."""

from __future__ import annotations

from collections import OrderedDict

from substitute.application.recipes import (
    RecipeModelCivitaiState,
    RecipeModelResolutionRequired,
    RecipeModelResolutionSummary,
    RecipeModelUnresolvedReference,
)
from substitute.domain.recipes import ParsedSugarScript


def test_declining_acquisition_removes_only_unresolved_hash_links() -> None:
    """Keep the script, resolved identities, and other inline LoRA links."""

    missing_field = ("Cube", "loader", "ckpt_name")
    resolved_field = ("Cube", "vae", "vae_name")
    prompt_field = ("Cube", "prompt", "text")
    script = ParsedSugarScript(
        buffers=OrderedDict(
            {
                "Cube": OrderedDict(
                    {
                        "nodes": {
                            "loader": {"inputs": {"ckpt_name": "authored.safetensors"}},
                            "prompt": {"inputs": {"text": "<lora:Missing:1>"}},
                        }
                    }
                )
            }
        ),
        global_overrides={},
        global_override_selections={},
        field_control_states_by_alias={},
        override_control_states={},
        model_hashes_by_field={
            missing_field: "A" * 64,
            resolved_field: "B" * 64,
        },
        prompt_lora_hashes_by_field={
            prompt_field: {"missing.safetensors": "C" * 64, "other": "D" * 64}
        },
        project_name=None,
    )
    required = RecipeModelResolutionRequired(
        references=(
            _missing(missing_field, "checkpoints", "authored.safetensors", "A" * 64),
            _missing(prompt_field, "loras", "Missing", "C" * 64),
        ),
        partial_script=script,
        summary=RecipeModelResolutionSummary(hash_matches=1, unresolved_hashes=2),
    )

    resolved = required.continue_without_download()

    assert resolved.parsed_script.buffers == script.buffers
    assert resolved.parsed_script.model_hashes_by_field == {resolved_field: "B" * 64}
    assert resolved.parsed_script.prompt_lora_hashes_by_field == {
        prompt_field: {"other": "D" * 64}
    }
    assert script.model_hashes_by_field[missing_field] == "A" * 64
    assert resolved.summary.hash_matches == 1
    assert resolved.summary.unresolved_hashes == 0


def _missing(
    field: tuple[str, str, str], kind: str, value: str, sha256: str
) -> RecipeModelUnresolvedReference:
    """Build one unresolved model reference for the cancellation contract."""

    return RecipeModelUnresolvedReference(
        alias=field[0],
        node_name=field[1],
        input_key=field[2],
        kind=kind,
        value=value,
        sha256=sha256,
        civitai_state=RecipeModelCivitaiState.DISABLED,
    )

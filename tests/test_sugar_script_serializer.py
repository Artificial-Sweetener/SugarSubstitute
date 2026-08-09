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

"""Verify the typed Sugar script serialization boundary."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
from typing import cast

import pytest

from substitute.domain.recipes.authored_inputs import AuthoredRecipeInput
from substitute.domain.recipes.sugar_script_parser import (
    parse_sugar_script_document,
)
from substitute.domain.recipes.sugar_script_serializer import (
    SugarScriptSerializationError,
    SugarScriptSerializationRequest,
    SugarScriptSerializer,
)


def test_serializer_emits_backend_safe_terminal_quote_prompt() -> None:
    """Delimiter-sensitive prompt text should use an escaped scalar literal."""

    prompt = 'line one\nline two"'
    script = SugarScriptSerializer().serialize(
        SugarScriptSerializationRequest(
            buffers={
                "A": OrderedDict(
                    cube_id="Owner/Repo/demo.cube",
                    nodes={"positive_prompt": {"inputs": {"prompt_template": prompt}}},
                )
            },
            ordered_aliases=("A",),
            authored_inputs_by_alias={
                "A": (
                    AuthoredRecipeInput(
                        node_key="positive_prompt",
                        input_key="prompt_template",
                        value=prompt,
                    ),
                )
            },
        )
    )

    assert 'set A.positive_prompt.prompt_template = "line one\\nline two\\""' in script
    parsed = parse_sugar_script_document(script)
    nodes = cast(Mapping[str, object], parsed.buffers["A"]["nodes"])
    positive_prompt = cast(Mapping[str, object], nodes["positive_prompt"])
    inputs = cast(Mapping[str, object], positive_prompt["inputs"])
    assert inputs["prompt_template"] == prompt


def test_serializer_emits_ordered_literal_list_inputs() -> None:
    """Ordered asset values should remain authored in the generated Sugar script."""

    script = SugarScriptSerializer().serialize(
        SugarScriptSerializationRequest(
            buffers={
                "A": OrderedDict(
                    cube_id="Owner/Repo/demo.cube",
                    nodes={
                        "load_mask_batch": {
                            "inputs": {"image": ["first.png", "second.png"]}
                        }
                    },
                )
            },
            ordered_aliases=("A",),
            authored_inputs_by_alias={
                "A": (
                    AuthoredRecipeInput(
                        node_key="load_mask_batch",
                        input_key="image",
                        value=["first.png", "second.png"],
                    ),
                )
            },
        )
    )

    assert 'set A.load_mask_batch.image = ["first.png", "second.png"]' in script
    parsed = parse_sugar_script_document(script)
    nodes = cast(Mapping[str, object], parsed.buffers["A"]["nodes"])
    load_mask_batch = cast(Mapping[str, object], nodes["load_mask_batch"])
    inputs = cast(Mapping[str, object], load_mask_batch["inputs"])
    assert inputs["image"] == ["first.png", "second.png"]


def test_serializer_omits_cube_internal_node_output_references() -> None:
    """Cube graph links should remain owned by the cube instead of becoming literals."""

    script = SugarScriptSerializer().serialize(
        SugarScriptSerializationRequest(
            buffers={
                "A": OrderedDict(
                    cube_id="Owner/Repo/demo.cube",
                    nodes={
                        "sampler": {
                            "inputs": {
                                "model": ["model_loader", 0],
                                "steps": 20,
                            }
                        }
                    },
                )
            },
            ordered_aliases=("A",),
            authored_inputs_by_alias={
                "A": (
                    AuthoredRecipeInput(
                        node_key="sampler",
                        input_key="steps",
                        value=20,
                    ),
                )
            },
        )
    )

    assert "set A.sampler.model" not in script
    assert "set A.sampler.steps = 20" in script


@pytest.mark.parametrize(
    ("serialization_request", "message"),
    [
        (
            SugarScriptSerializationRequest(
                buffers={},
                ordered_aliases=("A",),
                authored_inputs_by_alias={},
            ),
            "missing buffer for alias 'A'",
        ),
        (
            SugarScriptSerializationRequest(
                buffers={"A": {"cube_id": "demo"}},
                ordered_aliases=("A", "A"),
                authored_inputs_by_alias={"A": ()},
            ),
            "duplicate alias 'A'",
        ),
        (
            SugarScriptSerializationRequest(
                buffers={"A": {"cube_id": ""}},
                ordered_aliases=("A",),
                authored_inputs_by_alias={"A": ()},
            ),
            "alias 'A' has no cube ID",
        ),
    ],
)
def test_serializer_rejects_invalid_stack_state(
    serialization_request: SugarScriptSerializationRequest,
    message: str,
) -> None:
    """Invalid requests should fail before producing partial Sugar text."""

    with pytest.raises(SugarScriptSerializationError, match=message):
        SugarScriptSerializer().serialize(serialization_request)

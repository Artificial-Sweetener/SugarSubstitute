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
        )
    )

    assert 'set A.positive_prompt.prompt_template = "line one\\nline two\\""' in script
    parsed = parse_sugar_script_document(script)
    nodes = cast(Mapping[str, object], parsed.buffers["A"]["nodes"])
    positive_prompt = cast(Mapping[str, object], nodes["positive_prompt"])
    inputs = cast(Mapping[str, object], positive_prompt["inputs"])
    assert inputs["prompt_template"] == prompt


@pytest.mark.parametrize(
    ("serialization_request", "message"),
    [
        (
            SugarScriptSerializationRequest(buffers={}, ordered_aliases=("A",)),
            "missing buffer for alias 'A'",
        ),
        (
            SugarScriptSerializationRequest(
                buffers={"A": {"cube_id": "demo"}},
                ordered_aliases=("A", "A"),
            ),
            "duplicate alias 'A'",
        ),
        (
            SugarScriptSerializationRequest(
                buffers={"A": {"cube_id": ""}},
                ordered_aliases=("A",),
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

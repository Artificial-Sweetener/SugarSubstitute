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

from substitute.presentation.editor.utils.sanitation import (
    deep_sanitize_for_qt,
    sanitize_constraints_for_qt,
)
from substitute.presentation.editor.utils.resolve_definitions import (
    resolve_input_definition,
)
from substitute.application.overrides.link_policy import (
    find_first_cube_with_prompt,
    valid_link_options,
)
from substitute.application.node_behavior import compute_all_hidden_keys
from substitute.domain.links import (
    NodeLinkEndpoint,
    NodeLinkEndpointIndex,
    PromptEndpoint,
    PromptEndpointIndex,
)
from substitute.domain.node_behavior import PromptRole
from substitute.domain.workflow import CubeState, WorkflowState


def test_deep_sanitize_for_qt_recurses_and_limits_ints():
    too_big = 2_147_483_648
    too_small = -2_147_483_649
    src = {
        "a": too_big,
        "b": [1, too_small, {"c": too_big}],
        "ok": 123,
        "negok": -100,
    }
    sanitized = deep_sanitize_for_qt(src)
    assert sanitized["a"] is None
    assert sanitized["b"][1] is None
    assert sanitized["b"][2]["c"] is None
    assert sanitized["ok"] == 123
    assert sanitized["negok"] == -100


def test_sanitize_constraints_for_qt_only_limits_ints():
    too_big = 9_999_999_999
    constraints = {"min": -1, "max": too_big, "step": 0, "other": "val"}
    safe = sanitize_constraints_for_qt(constraints)
    assert safe["min"] == -1
    assert safe["max"] is None
    assert safe["step"] == 0
    assert safe["other"] == "val"


def test_resolve_input_definition_combines_required_optional_and_extracts_constraints():
    definitions = {
        "sampler": {
            "input": {
                "required": {
                    "sampler_name": ["STR", {"min": 0, "max": 10, "step": 1}],
                },
                "optional": {
                    "seed": ["INT"],
                    "schedule": [["a", "b"], {"step": 2}],
                },
            }
        }
    }
    t, meta, field, constraints = resolve_input_definition(
        definitions, "sampler", "sampler_name"
    )
    assert t == "STR"
    assert meta.get("min") == 0
    assert constraints == {"min": 0, "max": 10, "step": 1}

    t2, meta2, field2, constraints2 = resolve_input_definition(
        definitions, "sampler", "schedule"
    )
    assert t2 == "LIST"
    assert constraints2["step"] == 2

    t3, _, field3, constraints3 = resolve_input_definition(
        definitions, "sampler", "seed"
    )
    assert t3 == "INT"
    assert constraints3["min"] is None


def test_inherit_helpers_first_and_options():
    endpoint_index = PromptEndpointIndex.from_endpoints(
        (
            PromptEndpoint(
                cube_alias="Cube1",
                role=PromptRole.POSITIVE,
                node_name="positive_prompt",
                field_key="prompt_template",
            ),
            PromptEndpoint(
                cube_alias="Cube3",
                role=PromptRole.POSITIVE,
                node_name="positive_prompt",
                field_key="prompt_template",
            ),
        )
    )
    stack_order = ["Cube1", "Cube2", "Cube3"]
    assert (
        find_first_cube_with_prompt(
            endpoint_index,
            PromptRole.POSITIVE,
            stack_order,
        )
        == "Cube1"
    )
    # Options for Cube3 should include Cube1 but exclude itself
    opts = valid_link_options(
        "Cube3",
        endpoint_index,
        PromptRole.POSITIVE,
        stack_order,
    )
    assert "Cube1" in opts and "Cube3" not in opts


def test_compute_all_hidden_keys_merges_sources_and_node_links():
    # Build minimal workflow state with canonical node_link active
    cube_buf = {
        "cube_id": "Text To Image",
        "nodes": {
            "positive_prompt": {
                "inputs": {"prompt_template": ""},
                "node_link": {"from_cube": "Other", "from_node": "positive_prompt"},
            }
        },
    }
    cs = CubeState(
        cube_id="Text To Image",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer=cube_buf,
    )
    wf = WorkflowState(cubes={"A": cs}, stack_order=["A"])

    overrides = {"seed": {"value": 123}}
    search_hidden = {("Z", "node", "field")}
    hidden = compute_all_hidden_keys(
        overrides=overrides,
        cubes=wf.cubes,
        node_link_endpoint_index=NodeLinkEndpointIndex.from_endpoints(
            (
                NodeLinkEndpoint(
                    cube_alias="A",
                    node_name="positive_prompt",
                    class_type="PrimitiveStringMultiline",
                    family="prompt:positive",
                    editable_value_keys=("prompt_template",),
                ),
            )
        ),
        search_hidden_keys=search_hidden,
    )
    # Contains override key
    assert "seed" in hidden
    # Contains tuple for prompt_template from node_link
    assert ("A", "positive_prompt", "prompt_template") in hidden
    # Contains provided search hidden key
    assert ("Z", "node", "field") in hidden

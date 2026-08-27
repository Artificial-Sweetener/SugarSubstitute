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

"""Tests for resolving the output path seed token."""

from __future__ import annotations

from substitute.application.generation.output_seed_resolver import resolve_output_seed


def test_resolver_prefers_global_override_seed() -> None:
    """Global seed overrides should win over workflow-local seed inputs."""

    seed = resolve_output_seed(
        sugar_script_text=(
            'use "Text To Image" as A\nset *.*.seed = 1234\nset A.sampler.seed = 999\n'
        ),
        workflow_payload={"node": {"inputs": {"seed": 999}}},
    )

    assert seed == "1234"


def test_resolver_uses_first_workflow_seed() -> None:
    """Workflow fallback should use the first exact seed input in node order."""

    seed = resolve_output_seed(
        sugar_script_text='use "Text To Image" as A\n',
        workflow_payload={
            "node-a": {"inputs": {"steps": 20}},
            "node-b": {"inputs": {"seed": 222}},
            "node-c": {"inputs": {"seed": 333}},
        },
    )

    assert seed == "222"


def test_resolver_supports_wrapped_prompt_payload() -> None:
    """Wrapped backend payloads should expose the prompt node mapping."""

    seed = resolve_output_seed(
        sugar_script_text='use "Text To Image" as A\n',
        workflow_payload={"prompt": {"1": {"inputs": {"seed": 444}}}},
    )

    assert seed == "444"


def test_resolver_ignores_non_exact_seed_names() -> None:
    """Only the exact seed input should contribute to the output token."""

    seed = resolve_output_seed(
        sugar_script_text='use "Text To Image" as A\n',
        workflow_payload={
            "1": {"inputs": {"noise_seed": 111, "main_seed": 222}},
        },
    )

    assert seed == ""


def test_resolver_preserves_zero_seed_values() -> None:
    """Zero is a valid seed token value and must not be treated as missing."""

    global_seed = resolve_output_seed(
        sugar_script_text='use "Text To Image" as A\nset *.*.seed = 0\n',
        workflow_payload={"1": {"inputs": {"seed": 999}}},
    )
    workflow_seed = resolve_output_seed(
        sugar_script_text='use "Text To Image" as A\n',
        workflow_payload={"1": {"inputs": {"seed": 0}}},
    )

    assert global_seed == "0"
    assert workflow_seed == "0"


def test_resolver_returns_empty_text_without_seed() -> None:
    """Missing seed data should render as an empty token value."""

    seed = resolve_output_seed(
        sugar_script_text='use "Text To Image" as A\n',
        workflow_payload={"1": {"inputs": {"steps": 20}}},
    )

    assert seed == ""

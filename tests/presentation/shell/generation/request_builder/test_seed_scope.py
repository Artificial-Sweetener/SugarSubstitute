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

"""Tests for shell generation request-building policy helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from substitute.application.generation import (
    GenerationRequest,
    SeedRandomizationResult,
    SeedValueChange,
)
from substitute.domain.recipes.sugar_ast import GlobalOverrideSerializationScope
from substitute.presentation.shell.workspace_generation_request_builder import (
    synchronize_generation_request_seed_scopes,
)


PROJECT_ROOT = Path(__file__).resolve().parents[5]
SOURCE_PATH = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workspace_generation_request_builder.py"
)


def test_synchronize_generation_request_seed_scopes_uses_randomized_value() -> None:
    """Randomized global seeds should replace stale request-scope values."""

    original_scope = GlobalOverrideSerializationScope(
        override_key="seed",
        value=7,
        mode="global",
        full_participation=True,
        participant_fields=frozenset({("Demo", "KSampler", "seed")}),
    )
    request = GenerationRequest(
        workflow_id="workflow-a",
        workflow_name="Recipe A",
        workflow=cast(Any, SimpleNamespace()),
        global_override_scopes={"seed": original_scope},
    )

    synchronized = synchronize_generation_request_seed_scopes(
        request,
        SeedRandomizationResult(
            changes=(
                SeedValueChange(
                    override_key="seed",
                    previous_value=7,
                    value=41,
                ),
            )
        ),
    )

    assert synchronized is not request
    assert request.global_override_scopes == {"seed": original_scope}
    assert synchronized.global_override_scopes is not None
    assert synchronized.global_override_scopes[
        "seed"
    ] == GlobalOverrideSerializationScope(
        override_key="seed",
        value=41,
        mode="global",
        full_participation=True,
        participant_fields=frozenset({("Demo", "KSampler", "seed")}),
    )

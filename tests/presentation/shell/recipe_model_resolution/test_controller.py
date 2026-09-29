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

"""Tests for shell missing recipe model resolution wiring."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from collections import OrderedDict

import pytest

from substitute.application.recipes import (
    RecipeModelCivitaiState,
    RecipeModelResolutionRequired,
    RecipeModelResolutionSummary,
    RecipeModelUnresolvedReference,
    ResolvedRecipeModelScript,
)
from substitute.domain.recipes import ParsedSugarScript
from substitute.presentation.shell.shell_recipe_model_resolution_controller import (
    ShellRecipeModelResolutionController,
)
import substitute.presentation.shell.shell_recipe_model_resolution_controller as controller_module


def test_resolve_missing_recipe_models_passes_shell_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolution controller should pass shell services to the dialog flow."""

    calls: list[dict[str, object]] = []
    required = cast(RecipeModelResolutionRequired, object())
    download_service = object()
    credential_service = object()

    def prepare_missing_recipe_model_download(**kwargs: object) -> object:
        """Capture flow dependencies and return a deferred request sentinel."""

        calls.append(kwargs)
        return "deferred"

    monkeypatch.setattr(
        controller_module,
        "prepare_missing_recipe_model_download",
        prepare_missing_recipe_model_download,
    )
    shell = SimpleNamespace(
        recipe_model_download_resolution_service=download_service,
        civitai_credential_service=credential_service,
        settings_route_controller=SimpleNamespace(
            project_generation_model_download_settings=lambda: None,
        ),
    )
    controller = ShellRecipeModelResolutionController(shell)

    result = controller.resolve_missing_recipe_models(required)

    assert result == "deferred"
    assert calls == [
        {
            "parent": shell,
            "required": required,
            "download_service": download_service,
            "credential_service": credential_service,
            "open_settings": (
                shell.settings_route_controller.project_generation_model_download_settings
            ),
        }
    ]


def test_recipe_prompt_cancel_continues_without_missing_model_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The recipe shell handler must return a materializable script on Cancel."""

    monkeypatch.setattr(
        controller_module,
        "prepare_missing_recipe_model_download",
        lambda **_kwargs: None,
    )
    field = ("Cube", "loader", "ckpt_name")
    script = ParsedSugarScript(
        buffers=OrderedDict(),
        global_overrides={},
        global_override_selections={},
        field_control_states_by_alias={},
        override_control_states={},
        model_hashes_by_field={field: "A" * 64},
        prompt_lora_hashes_by_field={},
        project_name=None,
    )
    required = RecipeModelResolutionRequired(
        references=(
            RecipeModelUnresolvedReference(
                alias="Cube",
                node_name="loader",
                input_key="ckpt_name",
                kind="checkpoints",
                value="missing.safetensors",
                sha256="A" * 64,
                civitai_state=RecipeModelCivitaiState.DISABLED,
            ),
        ),
        partial_script=script,
        summary=RecipeModelResolutionSummary(unresolved_hashes=1),
    )
    shell = SimpleNamespace(
        recipe_model_download_resolution_service=None,
        civitai_credential_service=object(),
        settings_route_controller=SimpleNamespace(
            project_generation_model_download_settings=lambda: None,
        ),
    )

    result = ShellRecipeModelResolutionController(shell).resolve_missing_recipe_models(
        required
    )

    assert isinstance(result, ResolvedRecipeModelScript)
    assert result.parsed_script.model_hashes_by_field == {}

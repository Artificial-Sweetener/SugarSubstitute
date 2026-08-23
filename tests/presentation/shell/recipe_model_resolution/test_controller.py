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

import pytest

from substitute.application.recipes import RecipeModelResolutionRequired
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

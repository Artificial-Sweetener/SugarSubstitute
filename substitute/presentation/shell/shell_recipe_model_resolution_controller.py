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

"""Coordinate shell dependencies for missing recipe model resolution."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtWidgets import QWidget

from substitute.application.recipes import RecipeModelResolutionRequired
from substitute.presentation.shell.recipe_model_resolution_flow import (
    prepare_missing_recipe_model_download,
)


class ShellRecipeModelResolutionController:
    """Own shell-side missing-model resolution wiring for recipe loads."""

    def __init__(self, shell: Any) -> None:
        """Store the shell whose services should supply resolution dependencies."""

        self._shell = shell

    def resolve_missing_recipe_models(
        self,
        required: RecipeModelResolutionRequired,
    ) -> object | None:
        """Prompt for missing recipe models and defer downloads to the workflow."""

        return prepare_missing_recipe_model_download(
            parent=cast(QWidget, self._shell),
            required=required,
            download_service=self._shell.recipe_model_download_resolution_service,
            credential_service=self._shell.civitai_credential_service,
            open_settings=(
                self._shell.settings_route_controller.project_generation_model_download_settings
            ),
        )


__all__ = ["ShellRecipeModelResolutionController"]

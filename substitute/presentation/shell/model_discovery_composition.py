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

"""Compose shell-scoped model discovery and its deterministic cleanup."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from substitute.presentation.model_discovery import (
    CivitaiModelSuggestionCredentialHandler,
    ModelSuggestionCredentialCoordinator,
)

from .empty_model_picker_discovery_controller import EmptyModelPickerDiscoveryController
from .main_window_dependencies import MainWindowDependencies
from .shell_resource_lifecycle import ShellResourceLifecycle


def compose_empty_model_picker_discovery(
    *,
    parent_widget: QWidget,
    dependencies: MainWindowDependencies,
    lifecycle: ShellResourceLifecycle,
) -> EmptyModelPickerDiscoveryController:
    """Build the empty-picker controller and bind background cleanup to the shell."""

    controller = EmptyModelPickerDiscoveryController(
        parent_widget=parent_widget,
        service=dependencies.empty_model_picker_discovery_service,
        catalog=dependencies.model_catalog_service,
        credentials=ModelSuggestionCredentialCoordinator(
            (
                CivitaiModelSuggestionCredentialHandler(
                    dependencies.civitai_credential_service
                ),
            )
        ),
    )
    lifecycle.register("empty_model_picker_discovery", controller.close)
    return controller


__all__ = ["compose_empty_model_picker_discovery"]

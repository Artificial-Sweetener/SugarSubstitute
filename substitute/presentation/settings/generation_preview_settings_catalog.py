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

"""Describe the generation-preview section of the Settings catalog."""

from __future__ import annotations


from substitute.application.generation import GenerationPreviewPreferenceService
from substitute.presentation.settings.generation_preview_settings import (
    GenerationPreviewSettingsControl,
)
from substitute.presentation.settings.settings_async import (
    SettingsAsyncTaskRunnerFactory,
)
from substitute.presentation.settings.settings_catalog import (
    SettingsControlEntry,
    SettingsSectionEntry,
)


def build_generation_preview_settings_section(
    service: GenerationPreviewPreferenceService,
    task_runner_factory: SettingsAsyncTaskRunnerFactory,
) -> SettingsSectionEntry:
    """Build the cohesive generation-preview Settings catalog section."""

    return SettingsSectionEntry(
        "generation.preview",
        "Preview",
        "",
        10,
        (
            SettingsControlEntry(
                "generation.preview.configuration",
                "Generation previews",
                "Show sampler preview frames while ComfyUI is generating.",
                (
                    "preview",
                    "image",
                    "thumbnail",
                    "picture",
                    "generation",
                    "latent",
                    "rgb",
                    "taesd",
                    "auto",
                    "comfy",
                ),
                10,
                lambda parent: GenerationPreviewSettingsControl(
                    service=service,
                    task_runner_factory=task_runner_factory,
                    parent=parent,
                ),
            ),
        ),
    )


__all__ = ["build_generation_preview_settings_section"]

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

"""Translate observed nodepack acquisition milestones for the recovery splash."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationText
from sugarsubstitute_shared.presentation.localization import app_text

from substitute.infrastructure.comfy.workflow_nodepack_installer import (
    WorkflowNodepackInstallProgress,
    WorkflowNodepackInstallStage,
)


def describe_nodepack_install_progress(
    progress: WorkflowNodepackInstallProgress,
) -> ApplicationText:
    """Explain one real package phase with its name and batch position."""

    name = progress.display_name
    index = progress.package_index
    count = progress.package_count
    match progress.stage:
        case WorkflowNodepackInstallStage.SOURCE:
            return app_text("Getting source for %1 (%2/%3)", name, index, count)
        case WorkflowNodepackInstallStage.DEPENDENCIES:
            return app_text(
                "Installing dependencies for %1 (%2/%3)", name, index, count
            )
        case WorkflowNodepackInstallStage.INSTALLED:
            return app_text("Installed %1 (%2/%3)", name, index, count)
        case WorkflowNodepackInstallStage.FAILED:
            return app_text("Could not install %1 (%2/%3)", name, index, count)
    raise ValueError(f"Unsupported nodepack install stage: {progress.stage}")


__all__ = ["describe_nodepack_install_progress"]

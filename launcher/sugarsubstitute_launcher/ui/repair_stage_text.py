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

"""Translate repair-owned stage identifiers at the presentation boundary."""

from __future__ import annotations

from launcher.sugarsubstitute_launcher.application.repair.progress import RepairStage
from launcher.sugarsubstitute_launcher.localized_text import launcher_text


def repair_stage_text(stage: RepairStage) -> str:
    """Return complete localized copy for every executable repair stage."""
    match stage:
        case RepairStage.VALIDATE_INPUT:
            return launcher_text("Checking repair files")
        case RepairStage.RESTORE_APPLICATION:
            return launcher_text("Restoring the application")
        case RepairStage.PREPARE_RUNTIME:
            return launcher_text("Preparing the app runtime")
        case RepairStage.RESTORE_NODES:
            return launcher_text("Restoring Comfy components")
        case RepairStage.SAVE_STATE:
            return launcher_text("Saving installation settings")
        case RepairStage.VALIDATE_APPLICATION:
            return launcher_text("Checking the repaired application")
        case RepairStage.PREPARE_COMFY:
            return launcher_text("Preparing Comfy")
        case RepairStage.RESTORE_COMFY:
            return launcher_text("Restoring Comfy")
        case RepairStage.VALIDATE_COMFY:
            return launcher_text("Checking the repaired Comfy setup")

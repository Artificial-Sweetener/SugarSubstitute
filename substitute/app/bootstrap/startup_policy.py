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

"""Define bounded optional startup work budgets."""

from __future__ import annotations

LOCAL_EDITOR_WARMUP_BUDGET_SECONDS = 1.0
HIDDEN_GUI_PREHYDRATION_BUDGET_SECONDS = 0.75
CUBE_ICON_GUI_WARMUP_BUDGET_SECONDS = 0.5
OPTIONAL_METADATA_REFRESH_BUDGET_SECONDS = 15.0


__all__ = [
    "CUBE_ICON_GUI_WARMUP_BUDGET_SECONDS",
    "HIDDEN_GUI_PREHYDRATION_BUDGET_SECONDS",
    "LOCAL_EDITOR_WARMUP_BUDGET_SECONDS",
    "OPTIONAL_METADATA_REFRESH_BUDGET_SECONDS",
]

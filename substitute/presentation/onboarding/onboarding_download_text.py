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

"""Format download sizes and the localized checkout action."""

from __future__ import annotations


from sugarsubstitute_shared.localization import ApplicationText, app_text

from substitute.domain.model_recommendations import ModelInstallPlan


def format_model_size(size_bytes: int) -> str:
    """Return a concise binary transfer size for review copy."""

    value = float(size_bytes)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size_bytes} B"


def download_action_text(plan: ModelInstallPlan) -> ApplicationText:
    """Return a fixed-footer action label that keeps total transfer cost visible."""

    return app_text(
        "%1 · %2",
        app_text("Download %1 models", len(plan.files)),
        format_model_size(plan.total_bytes),
    )

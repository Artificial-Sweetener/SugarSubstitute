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

"""Provide typed Output preference test support."""

from __future__ import annotations

from datetime import datetime


from substitute.domain.generation import (
    OutputPreferences,
    OutputPathRenderContext,
)


class MemoryOutputRepository:
    """Persist output organization preferences in memory."""

    def __init__(self) -> None:
        """Create repository with default preferences."""

        self.preferences = OutputPreferences()

    def load(self) -> OutputPreferences:
        """Return stored preferences."""

        return self.preferences

    def save(self, preferences: OutputPreferences) -> None:
        """Store preferences in memory."""

        self.preferences = preferences


def build_render_context(
    *,
    seed: str = "",
    cube_number: int | None = 1,
    folder_image_number: int | None = 1,
) -> OutputPathRenderContext:
    """Return a representative render context."""

    return OutputPathRenderContext(
        workflow_name="My Workflow",
        source="CubeA",
        cube="CubeA",
        output_run_number=7,
        cube_number=cube_number,
        folder_image_number=folder_image_number,
        job_started_at=datetime(2026, 5, 1, 14, 32, 9),
        width=1024,
        height=1024,
        index=1,
        set_index=1,
        seed=seed,
    )

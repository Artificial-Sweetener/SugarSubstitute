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

"""Compile persistence SugarScript into SugarCubes-owned native graph state."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from substitute.domain.comfy_workflow import CanonicalCubeGraphAnalysis


class RecipeCubeGraphCompiler(Protocol):
    """Compile and analyze persistence SugarScript through SugarCubes."""

    def compile_cube_graph(
        self,
        *,
        sugar_script_text: str,
        output_dir: Path,
    ) -> CanonicalCubeGraphAnalysis:
        """Return exact Cube reconciliation and topology in one request."""


class RecipeGraphLoader:
    """Own the one-shot SugarScript-to-canonical-graph load boundary."""

    def __init__(
        self,
        compiler: RecipeCubeGraphCompiler,
    ) -> None:
        """Bind SugarCubes' combined authoring and analysis boundary."""

        self._compiler = compiler

    def load(
        self,
        *,
        sugar_script_text: str,
        source_path: Path,
    ) -> CanonicalCubeGraphAnalysis:
        """Compile and reconcile a persistence artifact in one bounded load step."""

        return self._compiler.compile_cube_graph(
            sugar_script_text=sugar_script_text,
            output_dir=source_path.parent,
        )


__all__ = ["RecipeCubeGraphCompiler", "RecipeGraphLoader"]

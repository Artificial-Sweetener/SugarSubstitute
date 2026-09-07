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

"""Describe an external WebUI model library connected during onboarding."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WebUiModelLibrary:
    """Hold resolved external roots using Comfy model-category semantics."""

    models_root: Path
    checkpoints: tuple[Path, ...] = ()
    diffusion_models: tuple[Path, ...] = ()
    ultralytics: tuple[Path, ...] = ()
    upscale_models: tuple[Path, ...] = ()

    def paths_by_kind(self) -> tuple[tuple[str, tuple[Path, ...]], ...]:
        """Return non-empty category mappings in stable configuration order."""

        return tuple(
            (kind, paths)
            for kind, paths in (
                ("checkpoints", self.checkpoints),
                ("diffusion_models", self.diffusion_models),
                ("ultralytics", self.ultralytics),
                ("upscale_models", self.upscale_models),
            )
            if paths
        )


__all__ = ["WebUiModelLibrary"]

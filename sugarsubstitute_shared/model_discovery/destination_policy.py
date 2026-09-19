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

"""Resolve standard ComfyUI model destinations below one model root."""

from __future__ import annotations

from pathlib import Path

from sugarsubstitute_shared.model_discovery.models import ModelArtifactKind


class ModelArtifactDestinationPolicy:
    """Map each supported model artifact kind to its standard ComfyUI folder."""

    def __init__(self, model_root: Path) -> None:
        """Store the trusted model root without creating directories."""

        self._model_root = Path(model_root)

    def destination_for(self, artifact_kind: ModelArtifactKind) -> Path:
        """Return the artifact-kind-owned destination below the model root."""

        return self._model_root / artifact_kind.value


__all__ = ["ModelArtifactDestinationPolicy"]

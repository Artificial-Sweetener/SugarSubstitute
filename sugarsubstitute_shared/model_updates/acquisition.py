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

"""Acquire explicitly selected model updates beside existing local files."""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path

from sugarsubstitute_shared.model_acquisition import (
    AcquisitionResult,
    ModelAcquisitionService,
)
from sugarsubstitute_shared.model_updates.models import ModelUpdateProposal


def model_update_identity(proposal: ModelUpdateProposal) -> str:
    """Return an exact identity for one reviewed provider update."""

    candidate = proposal.candidate
    return (
        f"{candidate.category.value}:{candidate.model_id}:"
        f"{candidate.version_id}:{candidate.sha256.casefold()}"
    )


class ModelUpdateAcquisitionService:
    """Own safe category destinations for side-by-side model updates."""

    def __init__(
        self,
        *,
        model_root: Path,
        acquisition: ModelAcquisitionService,
    ) -> None:
        """Store the active local model root and verified transfer owner."""

        self._model_root = model_root
        self._acquisition = acquisition

    def download_selected(
        self,
        proposals: Collection[ModelUpdateProposal],
        *,
        selected_identities: Collection[str],
    ) -> tuple[AcquisitionResult, ...]:
        """Download only reviewed exact versions without replacing old files."""

        selected = set(selected_identities)
        results: list[AcquisitionResult] = []
        for proposal in proposals:
            if model_update_identity(proposal) not in selected:
                continue
            results.append(
                self._acquisition.acquire(
                    proposal.candidate,
                    destination_dir=(
                        self._model_root / proposal.candidate.category.value
                    ),
                )
            )
        return tuple(results)


__all__ = ["ModelUpdateAcquisitionService", "model_update_identity"]

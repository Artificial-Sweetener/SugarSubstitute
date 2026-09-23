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

"""Provide one exact-hash model-update fixture across UI tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sugarsubstitute_shared.model_discovery import DiscoveredModel, ModelArtifactKind
from sugarsubstitute_shared.model_updates import ModelUpdateProposal, ModelUsageRecord


def update_proposal(sha256: str) -> ModelUpdateProposal:
    """Create one deterministic exact-file update proposal."""

    return ModelUpdateProposal(
        current=ModelUsageRecord(
            sha256=sha256,
            path=Path("current.safetensors"),
            artifact_kind=ModelArtifactKind.LORAS,
            model_id=7,
            version_id=1,
            base_model="Anima",
            usage_count=1,
            last_used_at=datetime(2026, 9, 22, tzinfo=UTC),
        ),
        candidate=DiscoveredModel(
            artifact_kind=ModelArtifactKind.LORAS,
            model_id=7,
            version_id=2,
            model_name="Model",
            version_name="v2",
            creator=None,
            base_model="Anima",
            file_name="v2.safetensors",
            size_bytes=1,
            sha256="b" * 64,
            download_url="https://civitai.com/api/download/models/2",
            model_page_url="https://civitai.com/models/7",
            thumbnail_url=None,
            provider_rank=1,
        ),
    )

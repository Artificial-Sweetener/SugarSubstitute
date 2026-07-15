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

"""Define passive catalog snapshot contracts shared by editor owners."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass
from enum import StrEnum


class CatalogSnapshotReadiness(StrEnum):
    """Describe whether a prepared catalog snapshot may be consumed."""

    WARM = "warm"
    COLD = "cold"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    REFRESH_FAILED = "refresh_failed"
    DISABLED = "disabled"

    @property
    def consumable(self) -> bool:
        """Return whether foreground consumers may read prepared payload data."""

        return self in {self.WARM, self.STALE}


@dataclass(frozen=True, slots=True)
class CatalogSnapshotIdentity:
    """Identify prepared catalog data enough to reject stale foreground reads."""

    source_revision: int | None = None
    editor_context_id: Hashable | None = None
    panel_context_id: Hashable | None = None
    feature_profile_id: Hashable | None = None
    catalog_revision: Hashable | None = None
    prompt_context_token: Hashable | None = None
    cube_context_token: Hashable | None = None
    scene_context_token: Hashable | None = None
    query_identity: Hashable | None = None
    request_identity: Hashable | None = None
    stale: bool = False
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        """Reject identity states that cannot prove snapshot freshness."""

        if self.source_revision is not None and self.source_revision < 0:
            raise ValueError("source_revision must be non-negative.")
        if self.unavailable_reason == "":
            raise ValueError("unavailable_reason must not be blank.")

    def with_stale_state(
        self,
        *,
        stale: bool,
        unavailable_reason: str | None = None,
    ) -> "CatalogSnapshotIdentity":
        """Return this identity with updated stale/unavailable publication state."""

        return CatalogSnapshotIdentity(
            source_revision=self.source_revision,
            editor_context_id=self.editor_context_id,
            panel_context_id=self.panel_context_id,
            feature_profile_id=self.feature_profile_id,
            catalog_revision=self.catalog_revision,
            prompt_context_token=self.prompt_context_token,
            cube_context_token=self.cube_context_token,
            scene_context_token=self.scene_context_token,
            query_identity=self.query_identity,
            request_identity=self.request_identity,
            stale=stale,
            unavailable_reason=unavailable_reason,
        )


@dataclass(frozen=True, slots=True)
class CatalogSnapshotStatus:
    """Publish catalog snapshot readiness with an inspectable failure reason."""

    readiness: CatalogSnapshotReadiness
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        """Reject ambiguous readiness states before UI owners consume them."""

        if (
            self.readiness
            in {
                CatalogSnapshotReadiness.UNAVAILABLE,
                CatalogSnapshotReadiness.REFRESH_FAILED,
                CatalogSnapshotReadiness.DISABLED,
            }
            and not self.unavailable_reason
        ):
            raise ValueError("non-ready catalog snapshots require a reason.")
        if self.readiness is CatalogSnapshotReadiness.WARM and self.unavailable_reason:
            raise ValueError("warm catalog snapshots must not carry a reason.")

    @property
    def consumable(self) -> bool:
        """Return whether foreground code may consume prepared payload rows."""

        return self.readiness.consumable


__all__ = [
    "CatalogSnapshotIdentity",
    "CatalogSnapshotReadiness",
    "CatalogSnapshotStatus",
]

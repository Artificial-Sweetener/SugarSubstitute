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

"""Define identity-safe prepared feature command requests."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass
from typing import Generic, TypeVar

TPayload = TypeVar("TPayload")


@dataclass(frozen=True, slots=True)
class PromptFeatureSnapshotIdentity:
    """Identify feature state well enough to reject stale command dispatch."""

    source_revision: int | None = None
    feature_profile_id: Hashable | None = None
    catalog_revision: Hashable | None = None
    stale: bool = False
    scene_context_id: Hashable | None = None
    cube_context_id: Hashable | None = None
    query_identity: Hashable | None = None

    def __post_init__(self) -> None:
        """Reject invalid identity fields before commands trust snapshots."""

        if self.source_revision is not None and self.source_revision < 0:
            raise ValueError("source_revision must be non-negative.")

    def with_source_revision(
        self,
        source_revision: int,
        *,
        stale: bool | None = None,
    ) -> "PromptFeatureSnapshotIdentity":
        """Return this identity for a newer source revision."""

        return PromptFeatureSnapshotIdentity(
            source_revision=source_revision,
            feature_profile_id=self.feature_profile_id,
            catalog_revision=self.catalog_revision,
            stale=self.stale if stale is None else stale,
            scene_context_id=self.scene_context_id,
            cube_context_id=self.cube_context_id,
            query_identity=self.query_identity,
        )


@dataclass(frozen=True, slots=True)
class PromptFeatureCommandRequest(Generic[TPayload]):
    """Describe a prepared feature command without executing source mutation."""

    command_name: str
    identity: PromptFeatureSnapshotIdentity
    payload: TPayload

    def __post_init__(self) -> None:
        """Reject unnamed command requests before actions expose them."""

        if not self.command_name.strip():
            raise ValueError("command_name must not be blank.")


__all__ = ["PromptFeatureCommandRequest", "PromptFeatureSnapshotIdentity"]

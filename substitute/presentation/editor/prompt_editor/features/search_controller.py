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

"""Own prompt-editor search highlight snapshots and projection publication."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass
from typing import Protocol

from ..commands import PromptFeatureSnapshotIdentity
from .feature_profile_controller import PromptFeatureProfileController


@dataclass(frozen=True, slots=True)
class PromptSearchHighlightState:
    """Publish prepared source-backed search ranges for projection chrome."""

    match_ranges: tuple[tuple[int, int], ...]
    active_index: int | None


@dataclass(frozen=True, slots=True)
class PromptSearchHighlightSnapshot:
    """Publish prompt-editor search highlight state for foreground consumers."""

    identity: PromptFeatureSnapshotIdentity
    highlights: PromptSearchHighlightState
    projection_ready: bool
    unavailable_reason: str | None = None


class PromptSearchSourceHost(Protocol):
    """Describe source identity reads needed by search feature ownership."""

    def prompt_command_source_identity(self) -> object | None:
        """Return the current source identity when available."""


class PromptSearchProjectionSurface(Protocol):
    """Describe projection search-highlight publication methods."""

    def set_search_matches(
        self,
        matches: tuple[tuple[int, int], ...],
        *,
        active_index: int | None,
    ) -> None:
        """Replace painted search ranges on the projection surface."""

    def clear_search_matches(self) -> None:
        """Clear painted search ranges from the projection surface."""


class PromptSearchFeatureController:
    """Coordinate editor-local search highlight state and projection publication."""

    def __init__(
        self,
        *,
        host: PromptSearchSourceHost,
        surface: PromptSearchProjectionSurface,
        feature_profile: PromptFeatureProfileController,
    ) -> None:
        """Store search collaborators and publish an initial empty snapshot."""

        self._host = host
        self._surface = surface
        self._feature_profile = feature_profile
        self._snapshot = self._build_snapshot(
            match_ranges=(),
            active_index=None,
            query_identity=None,
        )

    @property
    def snapshot(self) -> PromptSearchHighlightSnapshot:
        """Return the last prepared search highlight snapshot."""

        return self._snapshot

    def set_search_matches(
        self,
        matches: tuple[tuple[int, int], ...],
        *,
        active_index: int | None,
        query_identity: Hashable | None = None,
    ) -> PromptSearchHighlightSnapshot:
        """Publish source-backed search ranges and project them for painting."""

        self._snapshot = self._build_snapshot(
            match_ranges=matches,
            active_index=active_index,
            query_identity=query_identity,
        )
        self._surface.set_search_matches(matches, active_index=active_index)
        return self._snapshot

    def clear_search_matches(self) -> PromptSearchHighlightSnapshot:
        """Clear prepared search ranges and projection rendering state."""

        self._snapshot = self._build_snapshot(
            match_ranges=(),
            active_index=None,
            query_identity=None,
        )
        self._surface.clear_search_matches()
        return self._snapshot

    def _build_snapshot(
        self,
        *,
        match_ranges: tuple[tuple[int, int], ...],
        active_index: int | None,
        query_identity: Hashable | None,
        unavailable_reason: str | None = None,
    ) -> PromptSearchHighlightSnapshot:
        """Build the search highlight snapshot for current host state."""

        source_identity = self._host.prompt_command_source_identity()
        raw_source_revision = getattr(source_identity, "source_revision", None)
        source_revision = (
            raw_source_revision if isinstance(raw_source_revision, int) else None
        )
        identity = PromptFeatureSnapshotIdentity(
            source_revision=source_revision,
            feature_profile_id=self._feature_profile.identity.feature_profile_id,
            query_identity=query_identity,
        )
        return PromptSearchHighlightSnapshot(
            identity=identity,
            highlights=PromptSearchHighlightState(
                match_ranges=match_ranges,
                active_index=active_index,
            ),
            projection_ready=True,
            unavailable_reason=unavailable_reason,
        )


__all__ = [
    "PromptSearchFeatureController",
    "PromptSearchHighlightSnapshot",
    "PromptSearchHighlightState",
    "PromptSearchProjectionSurface",
    "PromptSearchSourceHost",
]

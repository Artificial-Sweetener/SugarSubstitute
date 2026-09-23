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

"""Provide deterministic model-discovery acquisition and thumbnail fixtures."""

from __future__ import annotations

import hashlib
from pathlib import Path

from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_suggestions import (
    ModelSuggestion,
    ModelSuggestionContext,
    ModelSuggestionPlan,
)
from sugarsubstitute_shared.model_acquisition import AcquisitionResult


class CatalogFixture:
    """Record targeted catalog invalidation and authoritative refresh."""

    def __init__(self) -> None:
        """Initialize empty call records."""

        self.invalidated: list[str | None] = []
        self.refreshed: list[str] = []

    def invalidate(self, kind: str | None = None) -> None:
        """Record one invalidation."""

        self.invalidated.append(kind)

    def refresh_models(self, kind: str) -> object:
        """Record one authoritative catalog refresh."""

        self.refreshed.append(kind)
        return ()


class FailingCatalogFixture(CatalogFixture):
    """Reject one post-download authoritative refresh."""

    def refresh_models(self, kind: str) -> object:
        """Record and fail a synthetic backend refresh."""

        super().refresh_models(kind)
        raise OSError("synthetic catalog refresh failure")


class DiscoveryServiceFixture:
    """Return a prepared suggestion and materialize its exact backend value."""

    def __init__(self, plan: ModelSuggestionPlan, destination_file: Path) -> None:
        """Store deterministic discovery and acquisition results."""

        self.plan = plan
        self.public_plan = plan
        self.destination_file = destination_file
        self.contexts: list[ModelSuggestionContext] = []
        self.acquired: list[str] = []

    def plan_empty_picker(self, context: ModelSuggestionContext) -> ModelSuggestionPlan:
        """Return the prepared plan."""

        self.contexts.append(context)
        return self.plan

    def plan_public_picker(
        self, context: ModelSuggestionContext
    ) -> ModelSuggestionPlan:
        """Return the configured key-free suggestion plan."""

        self.contexts.append(context)
        return self.public_plan

    def fetch_thumbnail(self, suggestion: ModelSuggestion) -> object:
        """Reject unexpected preview requests in this no-thumbnail fixture."""

        raise AssertionError(suggestion)

    def acquire(
        self,
        plan: ModelSuggestionPlan,
        suggestion_identity: str,
        *,
        provider_id: str | None = None,
        cancellation: object | None = None,
    ) -> tuple[ModelSuggestion, AcquisitionResult]:
        """Create the reviewed file and return its verified result."""

        _ = (cancellation, provider_id)
        self.acquired.append(suggestion_identity)
        self.destination_file.parent.mkdir(parents=True, exist_ok=True)
        payload = b"verified"
        self.destination_file.write_bytes(payload)
        return (
            plan.suggestions[0],
            AcquisitionResult(
                path=self.destination_file,
                sha256=hashlib.sha256(payload).hexdigest(),
                size_bytes=len(payload),
                reused_existing=False,
            ),
        )


class FailingThumbnailServiceFixture(DiscoveryServiceFixture):
    """Fail one thumbnail while settling every remaining card."""

    def __init__(self, plan: ModelSuggestionPlan, destination_file: Path) -> None:
        """Store deterministic work and preview calls."""

        super().__init__(plan, destination_file)
        self.thumbnail_calls: list[str] = []

    def fetch_thumbnail(self, suggestion: ModelSuggestion) -> object:
        """Fail the first card and return a deliberately undecodable second asset."""

        self.thumbnail_calls.append(suggestion.identity)
        if len(self.thumbnail_calls) == 1:
            raise OSError("synthetic thumbnail failure")
        return ThumbnailAsset("synthetic", 1, 1, 0, 4, "png", b"invalid")

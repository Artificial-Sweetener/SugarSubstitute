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

"""Prepare scene-aware autocomplete context outside interaction owners."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass
from typing import Protocol

from substitute.application.prompt_editor import (
    PromptAutocompleteQuery,
    effective_prompt_text_at_source_position,
)

from .autocomplete_result_controller import PromptAutocompleteTagContext
from ..commands import PromptFeatureSnapshotIdentity


class PromptAutocompleteSceneContextSourceIdentity(Protocol):
    """Describe source identity fields used by scene autocomplete context."""

    @property
    def source_revision(self) -> int:
        """Return the source revision for scene-context identity."""
        ...

    @property
    def source_length(self) -> int | None:
        """Return the source length when the source owner can provide it."""
        ...


class PromptAutocompleteSceneContextProvider(Protocol):
    """Publish scene and cube identity already owned by the scene feature."""

    @property
    def scene_context_identity(self) -> PromptFeatureSnapshotIdentity:
        """Return the current scene context identity."""
        ...


@dataclass(frozen=True, slots=True)
class PromptAutocompleteSceneContextSnapshot:
    """Carry prepared scene-aware context for one tag autocomplete query."""

    identity: PromptFeatureSnapshotIdentity
    source_text: str
    effective_prompt_text: str
    source_position: int
    query_identity: Hashable | None
    ready: bool
    stale: bool = False
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        """Reject ambiguous prepared scene-context states."""

        if self.source_position < 0:
            raise ValueError("source_position must be non-negative.")
        if self.ready and self.stale:
            raise ValueError("ready scene contexts cannot be stale.")
        if self.ready and self.unavailable_reason is not None:
            raise ValueError("ready scene contexts cannot be unavailable.")
        if self.unavailable_reason == "":
            raise ValueError("unavailable_reason must not be blank.")

    @property
    def tag_context(self) -> PromptAutocompleteTagContext:
        """Return the result-controller tag context for this scene snapshot."""

        return PromptAutocompleteTagContext(
            source_text=self.source_text,
            effective_prompt_text=self.effective_prompt_text,
        )


class PromptAutocompleteSceneContextController:
    """Prepare scene-aware autocomplete context from source snapshots."""

    def __init__(
        self,
        *,
        scene_context_provider: PromptAutocompleteSceneContextProvider | None = None,
    ) -> None:
        """Store the scene identity provider without owning interactions."""

        self._scene_context_provider = scene_context_provider

    def context_for_tag_query(
        self,
        query: PromptAutocompleteQuery,
        *,
        source_text: str,
        source_identity: PromptAutocompleteSceneContextSourceIdentity | None,
        feature_profile_identity: PromptFeatureSnapshotIdentity | None,
        query_identity: Hashable | None,
    ) -> PromptAutocompleteSceneContextSnapshot:
        """Return prepared effective prompt context for one tag query."""

        identity = self._identity(
            query=query,
            source_text=source_text,
            source_identity=source_identity,
            feature_profile_identity=feature_profile_identity,
            query_identity=query_identity,
            stale=False,
        )
        return PromptAutocompleteSceneContextSnapshot(
            identity=identity,
            source_text=source_text,
            effective_prompt_text=effective_prompt_text_at_source_position(
                text=source_text,
                source_position=query.word_start,
            ),
            source_position=query.word_start,
            query_identity=query_identity,
            ready=True,
        )

    def unavailable_context(
        self,
        *,
        source_text: str,
        source_position: int,
        source_identity: PromptAutocompleteSceneContextSourceIdentity | None,
        feature_profile_identity: PromptFeatureSnapshotIdentity | None,
        query_identity: Hashable | None,
        unavailable_reason: str,
    ) -> PromptAutocompleteSceneContextSnapshot:
        """Return an explicit stale unavailable scene autocomplete context."""

        return PromptAutocompleteSceneContextSnapshot(
            identity=self._identity_for_position(
                source_text=source_text,
                source_position=source_position,
                source_identity=source_identity,
                feature_profile_identity=feature_profile_identity,
                query_identity=query_identity,
                stale=True,
                unavailable_reason=unavailable_reason,
            ),
            source_text=source_text,
            effective_prompt_text=source_text,
            source_position=source_position,
            query_identity=query_identity,
            ready=False,
            stale=True,
            unavailable_reason=unavailable_reason,
        )

    def _identity(
        self,
        *,
        query: PromptAutocompleteQuery,
        source_text: str,
        source_identity: PromptAutocompleteSceneContextSourceIdentity | None,
        feature_profile_identity: PromptFeatureSnapshotIdentity | None,
        query_identity: Hashable | None,
        stale: bool,
        unavailable_reason: str | None = None,
    ) -> PromptFeatureSnapshotIdentity:
        """Return scene-context identity for one tag query."""

        return self._identity_for_position(
            source_text=source_text,
            source_position=query.word_start,
            source_identity=source_identity,
            feature_profile_identity=feature_profile_identity,
            query_identity=query_identity,
            stale=stale,
            unavailable_reason=unavailable_reason,
        )

    def _identity_for_position(
        self,
        *,
        source_text: str,
        source_position: int,
        source_identity: PromptAutocompleteSceneContextSourceIdentity | None,
        feature_profile_identity: PromptFeatureSnapshotIdentity | None,
        query_identity: Hashable | None,
        stale: bool,
        unavailable_reason: str | None = None,
    ) -> PromptFeatureSnapshotIdentity:
        """Return scene-context identity for one source position."""

        scene_identity = self._scene_identity()
        source_revision = (
            None if source_identity is None else source_identity.source_revision
        )
        source_length = (
            len(source_text)
            if source_identity is None or source_identity.source_length is None
            else source_identity.source_length
        )
        return PromptFeatureSnapshotIdentity(
            source_revision=source_revision,
            feature_profile_id=(
                None
                if feature_profile_identity is None
                else feature_profile_identity.feature_profile_id
            ),
            stale=stale,
            scene_context_id=scene_identity.scene_context_id,
            cube_context_id=scene_identity.cube_context_id,
            query_identity=(
                "autocomplete_scene_context",
                source_position,
                source_length,
                hash(source_text),
                query_identity,
                unavailable_reason,
            ),
        )

    def _scene_identity(self) -> PromptFeatureSnapshotIdentity:
        """Return the current scene feature identity or an empty identity."""

        provider = self._scene_context_provider
        if provider is None:
            return PromptFeatureSnapshotIdentity()
        return provider.scene_context_identity


__all__ = [
    "PromptAutocompleteSceneContextController",
    "PromptAutocompleteSceneContextProvider",
    "PromptAutocompleteSceneContextSnapshot",
    "PromptAutocompleteSceneContextSourceIdentity",
]

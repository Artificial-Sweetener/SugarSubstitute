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

"""Publish immutable workflow scene state for foreground feature consumers."""

from __future__ import annotations

from collections.abc import Callable, Hashable

from substitute.application.prompt_editor.document.semantics import (
    PromptDocumentSemantics,
)

from ..commands.feature_commands import PromptFeatureSnapshotIdentity
from ..core.state.revisions import PromptSourceIdentity
from .feature_profile_controller import PromptFeatureProfileController
from .scene_models import (
    PromptSceneAutocompleteState,
    PromptSceneContextSnapshot,
    PromptSceneQueueActionState,
)


class PromptSceneContextPublication:
    """Own workflow scene titles, queue keys, context identity, and snapshots."""

    def __init__(
        self,
        *,
        source_identity: Callable[[], PromptSourceIdentity | None],
        feature_profile: PromptFeatureProfileController,
        document_semantics: PromptDocumentSemantics,
    ) -> None:
        """Publish an initial empty scene snapshot."""

        self._source_identity = source_identity
        self._feature_profile = feature_profile
        self._document_semantics = document_semantics
        self._scene_autocomplete_titles: tuple[str, ...] = ()
        self._queueable_scene_keys: frozenset[str] = frozenset()
        self._cube_context_id: Hashable | None = None
        self._scene_context_id: Hashable | None = None
        self._snapshot = self._build_snapshot(action_scene_key=None)

    @property
    def snapshot(self) -> PromptSceneContextSnapshot:
        """Return the latest immutable scene context snapshot."""

        return self._snapshot

    @property
    def scene_context_identity(self) -> PromptFeatureSnapshotIdentity:
        """Return scene and cube identity for autocomplete freshness."""

        return self._snapshot.identity

    def set_context_identity(
        self,
        *,
        cube_context_id: Hashable | None,
        scene_context_id: Hashable | None,
    ) -> None:
        """Publish new workflow and cube identity."""

        self._cube_context_id = cube_context_id
        self._scene_context_id = scene_context_id
        self._snapshot = self._build_snapshot(action_scene_key=None)

    def set_scene_autocomplete_titles(self, titles: tuple[str, ...]) -> None:
        """Publish scene titles available to line-start autocomplete."""

        self._scene_autocomplete_titles = titles
        self._snapshot = self._build_snapshot(action_scene_key=None)

    def set_queueable_scene_keys(self, scene_keys: frozenset[str]) -> None:
        """Publish normalized scene keys eligible for queue actions."""

        self._queueable_scene_keys = scene_keys
        self._snapshot = self._build_snapshot(action_scene_key=None)

    def publish_queue_action(self, scene_key: str | None) -> None:
        """Publish queue action readiness from prepared position context."""

        action_scene_key = (
            scene_key
            if self._document_semantics.scenes_enabled
            and scene_key is not None
            and scene_key in self._queueable_scene_keys
            else None
        )
        self._snapshot = self._build_snapshot(action_scene_key=action_scene_key)

    def _build_snapshot(
        self,
        *,
        action_scene_key: str | None,
    ) -> PromptSceneContextSnapshot:
        """Build one snapshot from the current publication state."""

        source = self._source_identity()
        source_revision = None if source is None else source.source_revision
        scenes_enabled = self._document_semantics.scenes_enabled
        return PromptSceneContextSnapshot(
            identity=PromptFeatureSnapshotIdentity(
                source_revision=source_revision,
                feature_profile_id=self._feature_profile.identity.feature_profile_id,
                scene_context_id=self._scene_context_id,
                cube_context_id=self._cube_context_id,
            ),
            autocomplete=PromptSceneAutocompleteState(
                titles=self._scene_autocomplete_titles if scenes_enabled else (),
                ready=bool(self._scene_autocomplete_titles) and scenes_enabled,
            ),
            queue_action=PromptSceneQueueActionState(
                queueable_scene_keys=(
                    self._queueable_scene_keys if scenes_enabled else frozenset()
                ),
                action_ready=action_scene_key is not None,
                scene_key=action_scene_key,
            ),
        )


__all__ = ["PromptSceneContextPublication"]

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

"""Prepare and cache scene context for explicit source-position requests."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable

from substitute.application.prompt_editor.document.semantics import (
    PromptDocumentSemantics,
)
from substitute.application.prompt_editor.scenes.projection import (
    effective_prompt_text_at_source_position,
    prompt_scene_key_at_projection_source_position,
)
from substitute.shared.diagnostics.prompt_editor_work import (
    PromptEditorWorkEvent,
    prompt_editor_work_event,
)

from ..commands.feature_commands import PromptFeatureSnapshotIdentity
from ..core.state.revisions import PromptSourceIdentity
from .scene_models import (
    PromptScenePositionContext,
    PromptScenePositionContextCacheKey,
    PromptScenePositionContextSnapshot,
)
from .scene_publication import PromptSceneContextPublication

_POSITION_CONTEXT_CACHE_LIMIT = 64


class PromptScenePositionContextPreparation:
    """Own source-derived scene context, cache keys, freshness, and invalidation."""

    def __init__(
        self,
        *,
        source_text: Callable[[], str],
        source_identity: Callable[[], PromptSourceIdentity | None],
        publication: PromptSceneContextPublication,
        document_semantics: PromptDocumentSemantics,
    ) -> None:
        """Store only focused source queries and immutable scene publication."""

        self._source_text = source_text
        self._source_identity = source_identity
        self._publication = publication
        self._document_semantics = document_semantics
        self._cache: OrderedDict[
            PromptScenePositionContextCacheKey,
            PromptScenePositionContextSnapshot,
        ] = OrderedDict()

    @property
    def cached_position_count(self) -> int:
        """Return the bounded number of prepared source-position snapshots."""

        return len(self._cache)

    def prepare_position_context(
        self,
        source_position: int,
        *,
        reason: str,
    ) -> PromptScenePositionContextSnapshot:
        """Compute and cache one scene context at an explicit preparation boundary."""

        _require_non_blank(reason, field_name="reason")
        _require_non_negative_position(source_position)
        text = self._source_text()
        snapshot = self._publication.snapshot
        cache_key = self._cache_key(
            source_position=source_position,
            source_text=text,
            queueable_scene_keys=snapshot.queue_action.queueable_scene_keys,
            publication_identity=snapshot.identity,
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            self._cache.move_to_end(cache_key)
            self._publication.publish_queue_action(
                None if cached.context is None else cached.context.queueable_scene_key
            )
            return cached

        scene_key = self._scene_key(text=text, source_position=source_position)
        queueable_scene_key = (
            scene_key
            if scene_key is not None
            and scene_key in snapshot.queue_action.queueable_scene_keys
            else None
        )
        context = PromptScenePositionContext(
            source_position=source_position,
            scene_key=scene_key,
            queueable_scene_key=queueable_scene_key,
            effective_prompt_text=self._effective_prompt_text(
                text=text,
                source_position=source_position,
            ),
        )
        prepared = PromptScenePositionContextSnapshot(
            identity=self._position_identity(
                source_position=source_position,
                source_length=len(text),
                stale=False,
                unavailable_reason=None,
            ),
            source_position=source_position,
            context=context,
            ready=True,
        )
        self._cache[cache_key] = prepared
        self._cache.move_to_end(cache_key)
        if len(self._cache) > _POSITION_CONTEXT_CACHE_LIMIT:
            self._cache.popitem(last=False)
        self._publication.publish_queue_action(queueable_scene_key)
        return prepared

    def request_position_context(self, source_position: int, *, reason: str) -> bool:
        """Prepare source-position state for one explicit consumer request."""

        _ = self.prepare_position_context(source_position, reason=reason)
        return True

    @prompt_editor_work_event(PromptEditorWorkEvent.CONTEXT_MENU_SCENE_CONTEXT)
    def prepared_position_context(
        self,
        source_position: int,
    ) -> PromptScenePositionContextSnapshot:
        """Read cached scene context without source access or fresh derivation."""

        _require_non_negative_position(source_position)
        source = self._source_identity()
        if source is None:
            return self._unavailable(
                source_position=source_position,
                unavailable_reason="source_revision_unavailable",
            )
        cache_key = self._prepared_cache_key(
            source_position=source_position,
            source=source,
            queueable_scene_keys=self._publication.snapshot.queue_action.queueable_scene_keys,
            publication_identity=self._publication.snapshot.identity,
        )
        cached = self._cache.get(cache_key)
        if cached is None:
            return self._unavailable(
                source_position=source_position,
                unavailable_reason="scene_position_context_unprepared",
            )
        return cached

    def position_context(self, source_position: int) -> PromptScenePositionContext:
        """Return materialized context for a non-menu position consumer."""

        prepared = self.prepare_position_context(
            source_position,
            reason="legacy_position_context",
        )
        if prepared.context is not None:
            return prepared.context
        text = self._source_text()
        return PromptScenePositionContext(
            source_position=source_position,
            scene_key=None,
            queueable_scene_key=None,
            effective_prompt_text=text,
        )

    def effective_prompt_text_for_source_position(self, source_position: int) -> str:
        """Materialize the scene-effective prompt for one source position."""

        _require_non_negative_position(source_position)
        return self._effective_prompt_text(
            text=self._source_text(),
            source_position=source_position,
        )

    def effective_prompt_texts(self) -> tuple[str, ...]:
        """Return each effective scene prompt exactly once."""

        text = self._source_text()
        if not self._document_semantics.scenes_enabled:
            return (self._document_semantics.prompt_content_text(text),)
        positions = (0, *(index + 1 for index, char in enumerate(text) if char == "\n"))
        return tuple(
            dict.fromkeys(
                self._effective_prompt_text(text=text, source_position=position)
                for position in positions
            )
        )

    def _cache_key(
        self,
        *,
        source_position: int,
        source_text: str,
        queueable_scene_keys: frozenset[str],
        publication_identity: PromptFeatureSnapshotIdentity,
    ) -> PromptScenePositionContextCacheKey:
        """Build the complete cache identity while source text is available."""

        source = self._source_identity()
        return (
            source_position,
            None if source is None else source.source_revision,
            len(source_text),
            queueable_scene_keys,
            publication_identity.cube_context_id,
            publication_identity.scene_context_id,
            publication_identity.feature_profile_id,
            self._document_semantics.identity,
            source_text if source is None else None,
        )

    def _prepared_cache_key(
        self,
        *,
        source_position: int,
        source: PromptSourceIdentity,
        queueable_scene_keys: frozenset[str],
        publication_identity: PromptFeatureSnapshotIdentity,
    ) -> PromptScenePositionContextCacheKey:
        """Build the cache identity available to a menu-safe prepared read."""

        return (
            source_position,
            source.source_revision,
            0 if source.source_length is None else source.source_length,
            queueable_scene_keys,
            publication_identity.cube_context_id,
            publication_identity.scene_context_id,
            publication_identity.feature_profile_id,
            self._document_semantics.identity,
            None,
        )

    def _position_identity(
        self,
        *,
        source_position: int,
        source_length: int | None,
        stale: bool,
        unavailable_reason: str | None,
    ) -> PromptFeatureSnapshotIdentity:
        """Build the revisioned identity of one prepared position snapshot."""

        publication_identity = self._publication.snapshot.identity
        source = self._source_identity()
        return PromptFeatureSnapshotIdentity(
            source_revision=None if source is None else source.source_revision,
            feature_profile_id=publication_identity.feature_profile_id,
            stale=stale,
            scene_context_id=publication_identity.scene_context_id,
            cube_context_id=publication_identity.cube_context_id,
            query_identity=(
                "scene_position_context",
                source_position,
                source_length,
                self._publication.snapshot.queue_action.queueable_scene_keys,
                self._document_semantics.identity,
                unavailable_reason,
            ),
        )

    def _unavailable(
        self,
        *,
        source_position: int,
        unavailable_reason: str,
    ) -> PromptScenePositionContextSnapshot:
        """Return an explicit stale snapshot without reading prompt source."""

        return PromptScenePositionContextSnapshot(
            identity=self._position_identity(
                source_position=source_position,
                source_length=None,
                stale=True,
                unavailable_reason=unavailable_reason,
            ),
            source_position=source_position,
            context=None,
            ready=False,
            stale=True,
            unavailable_reason=unavailable_reason,
        )

    def _scene_key(self, *, text: str, source_position: int) -> str | None:
        """Resolve one normalized scene key when scenes are enabled."""

        if not self._document_semantics.scenes_enabled:
            return None
        return prompt_scene_key_at_projection_source_position(
            text=text,
            source_position=source_position,
        )

    def _effective_prompt_text(self, *, text: str, source_position: int) -> str:
        """Return scene-effective text or the scene-free prompt content."""

        if self._document_semantics.scenes_enabled:
            return effective_prompt_text_at_source_position(
                text=text,
                source_position=source_position,
            )
        return self._document_semantics.prompt_content_text(text)


def _require_non_blank(value: str, *, field_name: str) -> None:
    """Reject blank scene preparation labels."""

    if not value.strip():
        raise ValueError(f"{field_name} must not be blank.")


def _require_non_negative_position(source_position: int) -> None:
    """Reject invalid source-position requests before cache interaction."""

    if source_position < 0:
        raise ValueError("source_position must be non-negative.")


__all__ = ["PromptScenePositionContextPreparation"]

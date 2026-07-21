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

"""Own prompt scene context snapshots and scene-aware action readiness."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass
from typing import Protocol

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor import (
    PromptSceneAutocompleteQuery,
    effective_prompt_text_at_source_position,
    prompt_scene_key_at_projection_source_position,
)
from substitute.application.prompt_editor.prompt_document_semantics import (
    OrdinaryPromptDocumentSemantics,
    PromptDocumentSemantics,
)

from ..commands import PromptFeatureSnapshotIdentity
from .feature_profile_controller import PromptFeatureProfileController


@dataclass(frozen=True, slots=True)
class PromptScenePositionContext:
    """Describe scene context prepared for one source position."""

    source_position: int
    scene_key: str | None
    queueable_scene_key: str | None
    effective_prompt_text: str


@dataclass(frozen=True, slots=True)
class PromptScenePositionContextSnapshot:
    """Publish prepared scene context for one source position."""

    identity: PromptFeatureSnapshotIdentity
    source_position: int
    context: PromptScenePositionContext | None
    ready: bool
    stale: bool = False
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        """Reject ambiguous scene-position snapshot states."""

        if self.source_position < 0:
            raise ValueError("source_position must be non-negative.")
        if self.ready and self.context is None:
            raise ValueError("ready scene-position snapshots require context.")
        if self.ready and self.unavailable_reason is not None:
            raise ValueError("ready scene-position snapshots cannot be unavailable.")
        if self.unavailable_reason == "":
            raise ValueError("unavailable_reason must not be blank.")


@dataclass(frozen=True, slots=True)
class PromptSceneAutocompleteState:
    """Publish workflow scene-title autocomplete readiness."""

    titles: tuple[str, ...]
    ready: bool


@dataclass(frozen=True, slots=True)
class PromptSceneQueueActionState:
    """Publish scene queue action readiness for context menus."""

    queueable_scene_keys: frozenset[str]
    action_ready: bool
    scene_key: str | None = None


@dataclass(frozen=True, slots=True)
class PromptSceneContextSnapshot:
    """Publish prepared scene context state for foreground consumers."""

    identity: PromptFeatureSnapshotIdentity
    autocomplete: PromptSceneAutocompleteState
    queue_action: PromptSceneQueueActionState
    unavailable_reason: str | None = None


class PromptSceneSourceHost(Protocol):
    """Describe source reads needed by scene feature ownership."""

    def toPlainText(self) -> str:
        """Return the current prompt source text."""

    def prompt_command_source_identity(self) -> object | None:
        """Return the current source identity when available."""


type _PositionContextCacheKey = tuple[
    int,
    int | None,
    int,
    frozenset[str],
    Hashable | None,
    Hashable | None,
    Hashable | None,
    Hashable,
    str | None,
]


class PromptSceneFeatureController:
    """Coordinate prompt scene titles, queue readiness, and effective context."""

    def __init__(
        self,
        *,
        host: PromptSceneSourceHost,
        feature_profile: PromptFeatureProfileController,
        document_semantics: PromptDocumentSemantics | None = None,
    ) -> None:
        """Store scene collaborators and publish an initial empty snapshot."""

        self._host = host
        self._feature_profile = feature_profile
        self._document_semantics = (
            document_semantics or OrdinaryPromptDocumentSemantics()
        )
        self._scene_autocomplete_titles: tuple[str, ...] = ()
        self._queueable_scene_keys: frozenset[str] = frozenset()
        self._cube_context_id: Hashable | None = None
        self._scene_context_id: Hashable | None = None
        self._position_context_cache: dict[
            _PositionContextCacheKey,
            PromptScenePositionContextSnapshot,
        ] = {}
        self._snapshot = self._build_snapshot()

    @property
    def snapshot(self) -> PromptSceneContextSnapshot:
        """Return the last prepared scene context snapshot."""

        return self._snapshot

    @property
    def scene_context_identity(self) -> PromptFeatureSnapshotIdentity:
        """Return the current scene/cube identity for autocomplete context."""

        return self._snapshot.identity

    def set_context_identity(
        self,
        *,
        cube_context_id: Hashable | None,
        scene_context_id: Hashable | None,
    ) -> None:
        """Update editor/cube identity carried by future scene snapshots."""

        self._cube_context_id = cube_context_id
        self._scene_context_id = scene_context_id
        self._position_context_cache.clear()
        self._snapshot = self._build_snapshot()

    def set_scene_autocomplete_titles(self, titles: tuple[str, ...]) -> None:
        """Replace workflow scene titles offered by line-start autocomplete."""

        self._scene_autocomplete_titles = titles
        self._snapshot = self._build_snapshot()

    def scene_autocomplete_suggestions(
        self,
        query: PromptSceneAutocompleteQuery,
        *,
        limit: int,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return prepared scene autocomplete rows for one query."""

        if limit <= 0 or not self._document_semantics.scenes_enabled:
            return ()
        normalized_prefix = query.prefix.strip().casefold()
        matches: list[PromptAutocompleteSuggestion] = []
        seen_titles: set[str] = set()
        for title in self._scene_autocomplete_titles:
            normalized_title = title.strip().casefold()
            if not normalized_title or normalized_title in seen_titles:
                continue
            seen_titles.add(normalized_title)
            if normalized_prefix and not normalized_title.startswith(normalized_prefix):
                continue
            if normalized_prefix and normalized_title == normalized_prefix:
                continue
            matches.append(
                PromptAutocompleteSuggestion(
                    tag=title,
                    popularity=None,
                    source_label="Scene",
                    source_kind="scene",
                )
            )
            if len(matches) >= limit:
                break
        return tuple(matches)

    def set_queueable_scene_keys(self, scene_keys: frozenset[str]) -> None:
        """Replace normalized scene keys that may be queued from this editor."""

        self._queueable_scene_keys = scene_keys
        self._position_context_cache.clear()
        self._snapshot = self._build_snapshot()

    def scene_key_for_source_position(self, source_position: int) -> str | None:
        """Return the normalized scene key containing one source position."""

        if not self._document_semantics.scenes_enabled:
            return None
        return prompt_scene_key_at_projection_source_position(
            text=self._host.toPlainText(),
            source_position=source_position,
        )

    def queueable_scene_key_for_source_position(
        self,
        source_position: int,
    ) -> str | None:
        """Return a queueable scene key containing one source position."""

        scene_key = self.scene_key_for_source_position(source_position)
        if scene_key is None or scene_key not in self._queueable_scene_keys:
            self._snapshot = self._build_snapshot(action_scene_key=None)
            return None
        self._snapshot = self._build_snapshot(action_scene_key=scene_key)
        return scene_key

    def position_context(self, source_position: int) -> PromptScenePositionContext:
        """Compute scene context for a non-menu source-position consumer."""

        snapshot = self.prepare_position_context(
            source_position,
            reason="legacy_position_context",
        )
        if snapshot.context is None:
            return PromptScenePositionContext(
                source_position=source_position,
                scene_key=None,
                queueable_scene_key=None,
                effective_prompt_text=self._host.toPlainText(),
            )
        return snapshot.context

    def prepare_position_context(
        self,
        source_position: int,
        *,
        reason: str,
    ) -> PromptScenePositionContextSnapshot:
        """Compute and publish scene context for an explicit preparation boundary."""

        _require_non_blank(reason, field_name="reason")
        if source_position < 0:
            raise ValueError("source_position must be non-negative.")

        text = self._host.toPlainText()
        cache_key = self._position_context_cache_key(
            source_position=source_position,
            source_text=text,
        )
        cached_context = self._position_context_cache.get(cache_key)
        if cached_context is not None:
            self._snapshot = self._build_snapshot(
                action_scene_key=(
                    None
                    if cached_context.context is None
                    else cached_context.context.queueable_scene_key
                )
            )
            return cached_context

        scene_key = self.scene_key_for_source_position(source_position)
        queueable_scene_key = (
            scene_key
            if scene_key is not None and scene_key in self._queueable_scene_keys
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
        snapshot = PromptScenePositionContextSnapshot(
            identity=self._scene_position_identity(
                source_position=source_position,
                source_text=text,
                stale=False,
            ),
            source_position=source_position,
            context=context,
            ready=True,
        )
        self._position_context_cache[cache_key] = snapshot
        self._snapshot = self._build_snapshot(action_scene_key=queueable_scene_key)
        return snapshot

    def request_position_context(self, source_position: int, *, reason: str) -> bool:
        """Prepare one scene context from an explicit non-menu request boundary."""

        _ = self.prepare_position_context(source_position, reason=reason)
        return True

    def prepared_position_context(
        self,
        source_position: int,
    ) -> PromptScenePositionContextSnapshot:
        """Return prepared scene context without computing on menu-open paths."""

        if source_position < 0:
            raise ValueError("source_position must be non-negative.")
        cache_key = self._prepared_position_context_cache_key(
            source_position=source_position
        )
        if cache_key is None:
            return self._unavailable_position_context(
                source_position=source_position,
                unavailable_reason="source_revision_unavailable",
            )
        cached_context = self._position_context_cache.get(cache_key)
        if cached_context is None:
            return self._unavailable_position_context(
                source_position=source_position,
                unavailable_reason="scene_position_context_unprepared",
            )
        return cached_context

    def effective_prompt_text_for_source_position(self, source_position: int) -> str:
        """Compute effective prompt text for transitional non-menu consumers."""

        return self._effective_prompt_text(
            text=self._host.toPlainText(),
            source_position=source_position,
        )

    def effective_prompt_texts(self) -> tuple[str, ...]:
        """Return unique effective prompts for all source scene boundaries."""

        source_text = self._host.toPlainText()
        if not self._document_semantics.scenes_enabled:
            return (self._document_semantics.prompt_content_text(source_text),)
        positions = (
            0,
            *(index + 1 for index, char in enumerate(source_text) if char == "\n"),
        )
        prompts = dict.fromkeys(
            self.effective_prompt_text_for_source_position(position)
            for position in positions
        )
        return tuple(prompts)

    def _effective_prompt_text(self, *, text: str, source_position: int) -> str:
        """Return the scene-effective prompt or complete scene-free document."""

        if self._document_semantics.scenes_enabled:
            return effective_prompt_text_at_source_position(
                text=text,
                source_position=source_position,
            )
        return self._document_semantics.prompt_content_text(text)

    def _position_context_cache_key(
        self,
        *,
        source_position: int,
        source_text: str,
    ) -> _PositionContextCacheKey:
        """Return the freshness key for prepared source-position scene context."""

        source_identity = self._host.prompt_command_source_identity()
        raw_source_revision = getattr(source_identity, "source_revision", None)
        source_revision = (
            raw_source_revision if isinstance(raw_source_revision, int) else None
        )
        fallback_text = source_text if source_revision is None else None
        return (
            source_position,
            source_revision,
            len(source_text),
            self._queueable_scene_keys,
            self._cube_context_id,
            self._scene_context_id,
            self._feature_profile.identity.feature_profile_id,
            self._document_semantics.identity,
            fallback_text,
        )

    def _prepared_position_context_cache_key(
        self,
        *,
        source_position: int,
    ) -> _PositionContextCacheKey | None:
        """Return a cache key for cheap prepared-context reads."""

        source_identity = self._host.prompt_command_source_identity()
        raw_source_revision = getattr(source_identity, "source_revision", None)
        source_revision = (
            raw_source_revision if isinstance(raw_source_revision, int) else None
        )
        raw_source_length = getattr(source_identity, "source_length", None)
        source_length = raw_source_length if isinstance(raw_source_length, int) else 0
        if source_revision is None:
            return None
        return (
            source_position,
            source_revision,
            source_length,
            self._queueable_scene_keys,
            self._cube_context_id,
            self._scene_context_id,
            self._feature_profile.identity.feature_profile_id,
            self._document_semantics.identity,
            None,
        )

    def _unavailable_position_context(
        self,
        *,
        source_position: int,
        unavailable_reason: str,
    ) -> PromptScenePositionContextSnapshot:
        """Return an explicit unavailable prepared scene-position snapshot."""

        return PromptScenePositionContextSnapshot(
            identity=self._scene_position_identity(
                source_position=source_position,
                source_text=None,
                stale=True,
                unavailable_reason=unavailable_reason,
            ),
            source_position=source_position,
            context=None,
            ready=False,
            stale=True,
            unavailable_reason=unavailable_reason,
        )

    def _scene_position_identity(
        self,
        *,
        source_position: int,
        source_text: str | None,
        stale: bool,
        unavailable_reason: str | None = None,
    ) -> PromptFeatureSnapshotIdentity:
        """Return freshness identity for one prepared scene-position snapshot."""

        source_identity = self._host.prompt_command_source_identity()
        raw_source_revision = getattr(source_identity, "source_revision", None)
        source_revision = (
            raw_source_revision if isinstance(raw_source_revision, int) else None
        )
        source_length = (
            getattr(source_identity, "source_length", None)
            if source_text is None
            else len(source_text)
        )
        query_identity: tuple[object, ...] = (
            "scene_position_context",
            source_position,
            source_length,
            self._queueable_scene_keys,
            self._document_semantics.identity,
            unavailable_reason,
        )
        return PromptFeatureSnapshotIdentity(
            source_revision=source_revision,
            feature_profile_id=self._feature_profile.identity.feature_profile_id,
            stale=stale,
            scene_context_id=self._scene_context_id,
            cube_context_id=self._cube_context_id,
            query_identity=query_identity,
        )

    def _build_snapshot(
        self,
        *,
        action_scene_key: str | None = None,
        unavailable_reason: str | None = None,
    ) -> PromptSceneContextSnapshot:
        """Build the scene context snapshot for current host state."""

        source_identity = self._host.prompt_command_source_identity()
        raw_source_revision = getattr(source_identity, "source_revision", None)
        source_revision = (
            raw_source_revision if isinstance(raw_source_revision, int) else None
        )
        identity = PromptFeatureSnapshotIdentity(
            source_revision=source_revision,
            feature_profile_id=self._feature_profile.identity.feature_profile_id,
            scene_context_id=self._scene_context_id,
            cube_context_id=self._cube_context_id,
        )
        return PromptSceneContextSnapshot(
            identity=identity,
            autocomplete=PromptSceneAutocompleteState(
                titles=(
                    self._scene_autocomplete_titles
                    if self._document_semantics.scenes_enabled
                    else ()
                ),
                ready=(
                    bool(self._scene_autocomplete_titles)
                    and self._document_semantics.scenes_enabled
                ),
            ),
            queue_action=PromptSceneQueueActionState(
                queueable_scene_keys=(
                    self._queueable_scene_keys
                    if self._document_semantics.scenes_enabled
                    else frozenset()
                ),
                action_ready=(
                    action_scene_key is not None
                    and self._document_semantics.scenes_enabled
                ),
                scene_key=(
                    action_scene_key
                    if self._document_semantics.scenes_enabled
                    else None
                ),
            ),
            unavailable_reason=unavailable_reason,
        )


__all__ = [
    "PromptSceneAutocompleteState",
    "PromptSceneContextSnapshot",
    "PromptSceneFeatureController",
    "PromptScenePositionContext",
    "PromptScenePositionContextSnapshot",
    "PromptSceneQueueActionState",
    "PromptSceneSourceHost",
]


def _require_non_blank(value: str, *, field_name: str) -> None:
    """Reject blank scene preparation labels."""

    if not value.strip():
        raise ValueError(f"{field_name} must not be blank.")

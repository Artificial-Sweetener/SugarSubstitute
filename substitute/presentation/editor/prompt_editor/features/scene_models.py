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

"""Define immutable Qt-free scene values exchanged by prompt feature owners."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass

from ..commands.feature_commands import PromptFeatureSnapshotIdentity


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


type PromptScenePositionContextCacheKey = tuple[
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


__all__ = [
    "PromptSceneAutocompleteState",
    "PromptSceneContextSnapshot",
    "PromptScenePositionContext",
    "PromptScenePositionContextCacheKey",
    "PromptScenePositionContextSnapshot",
    "PromptSceneQueueActionState",
]

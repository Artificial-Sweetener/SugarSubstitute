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

"""Define immutable, Qt-free values exchanged by prompt context-menu owners."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Hashable

from substitute.presentation.editor.catalog.snapshots import CatalogSnapshotIdentity

from ..commands.feature_commands import PromptFeatureSnapshotIdentity
from .danbooru_actions import PromptDanbooruActionSnapshot
from .diagnostic_menu_actions import PromptContextMenuAction
from .lora_context_menu import PromptLoraTriggerWordsAction
from .prompt_segment_preset_models import PromptSegmentPresetSnapshot
from .scene_models import PromptScenePositionContext


@dataclass(frozen=True, slots=True)
class PromptContextMenuSnapshotRequest:
    """Describe cheap per-open state used to read a prepared menu snapshot."""

    source_position: int
    selected_text: str
    selection_range: tuple[int, int] | None
    read_only: bool
    rich_prompt_rendering_enabled: bool

    def __post_init__(self) -> None:
        """Reject impossible menu request positions before identity publication."""

        if self.source_position < 0:
            raise ValueError("source_position must be non-negative.")


@dataclass(frozen=True, slots=True)
class PromptContextMenuActionSnapshot:
    """Publish prompt-specific menu actions without constructing Qt widgets."""

    source_position: int
    selected_text: str
    scene_context: PromptScenePositionContext
    diagnostic_actions: tuple[PromptContextMenuAction, ...]
    lora_picker_ready: bool
    lora_trigger_word_actions: tuple[PromptLoraTriggerWordsAction, ...]
    segment_snapshot: PromptSegmentPresetSnapshot
    danbooru_snapshot: PromptDanbooruActionSnapshot
    read_only: bool
    rich_prompt_rendering_enabled: bool

    @property
    def queue_scene_key(self) -> str | None:
        """Return the scene key that may be queued from this menu opening."""

        return self.scene_context.queueable_scene_key

    @property
    def effective_prompt_text(self) -> str:
        """Return the scene-aware prompt text used by feature actions."""

        return self.scene_context.effective_prompt_text


@dataclass(frozen=True, slots=True)
class PromptContextMenuSnapshotIdentity:
    """Identify a prepared prompt context-menu snapshot and dependencies."""

    source_revision: int | None
    source_position: int
    selected_text_identity: tuple[str, int, int]
    selection_range_identity: tuple[int, int] | None
    feature_profile_id: Hashable | None
    cube_context_id: Hashable | None
    scene_context_id: Hashable | None
    scene_snapshot_identity: PromptFeatureSnapshotIdentity | None
    scene_position_snapshot_identity: PromptFeatureSnapshotIdentity | None
    diagnostics_snapshot_identity: PromptFeatureSnapshotIdentity | None
    diagnostic_action_snapshot_identity: PromptFeatureSnapshotIdentity | None
    lora_catalog_revision: Hashable | None
    lora_action_identity: CatalogSnapshotIdentity | None
    prompt_segment_catalog_identity: CatalogSnapshotIdentity
    danbooru_snapshot_identity: PromptFeatureSnapshotIdentity | None
    read_only: bool
    rich_prompt_rendering_enabled: bool

    def __post_init__(self) -> None:
        """Reject impossible identity values before menu code trusts them."""

        if self.source_revision is not None and self.source_revision < 0:
            raise ValueError("source_revision must be non-negative.")
        if self.source_position < 0:
            raise ValueError("source_position must be non-negative.")


class PromptContextMenuConcern(StrEnum):
    """Name independently prepared concerns inside a context-menu snapshot."""

    SCENE = "scene"
    DIAGNOSTICS = "diagnostics"
    LORA = "lora"
    PROMPT_SEGMENT = "prompt_segment"
    DANBOORU = "danbooru"
    EDITING_STATE = "editing_state"
    RENDERING_STATE = "rendering_state"


@dataclass(frozen=True, slots=True)
class PromptContextMenuConcernReadiness:
    """Publish readiness for one context-menu concern."""

    concern: PromptContextMenuConcern
    ready: bool
    stale: bool = False
    unavailable_reason: str | None = None
    identity: Hashable | None = None

    def __post_init__(self) -> None:
        """Reject ambiguous concern readiness state."""

        if self.ready and self.unavailable_reason is not None:
            raise ValueError("ready concerns must not carry an unavailable reason.")
        if self.unavailable_reason == "":
            raise ValueError("unavailable_reason must not be blank.")


@dataclass(frozen=True, slots=True)
class PromptContextMenuSnapshotReadiness:
    """Publish per-concern readiness for one context-menu snapshot."""

    concerns: tuple[PromptContextMenuConcernReadiness, ...]

    def concern(
        self,
        concern: PromptContextMenuConcern,
    ) -> PromptContextMenuConcernReadiness:
        """Return readiness for one prepared menu concern."""

        for item in self.concerns:
            if item.concern is concern:
                return item
        raise KeyError(concern)


@dataclass(frozen=True, slots=True)
class PromptContextMenuSnapshot:
    """Publish one identity-bearing prepared context-menu snapshot."""

    identity: PromptContextMenuSnapshotIdentity
    readiness: PromptContextMenuSnapshotReadiness
    actions: PromptContextMenuActionSnapshot


__all__ = [
    "PromptContextMenuActionSnapshot",
    "PromptContextMenuConcern",
    "PromptContextMenuConcernReadiness",
    "PromptContextMenuSnapshot",
    "PromptContextMenuSnapshotIdentity",
    "PromptContextMenuSnapshotReadiness",
    "PromptContextMenuSnapshotRequest",
]

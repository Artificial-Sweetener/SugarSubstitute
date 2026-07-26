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

"""Define narrow prepared-state ports consumed by context-menu assembly."""

from __future__ import annotations

from typing import Protocol

from .danbooru_actions import PromptDanbooruActionSnapshot
from .diagnostics_presentation import (
    PromptDiagnosticMenuActionSnapshot,
    PromptDiagnosticsSnapshot,
)
from .lora_action_snapshots import PromptLoraActionSnapshot
from .lora_metadata_presentation import PromptLoraMetadataSnapshot
from .prompt_segment_preset_models import PromptSegmentPresetSnapshot
from .scene_models import PromptSceneContextSnapshot, PromptScenePositionContextSnapshot


class PromptContextMenuDiagnosticsPort(Protocol):
    """Read prepared diagnostics state for context-menu assembly."""

    @property
    def snapshot(self) -> PromptDiagnosticsSnapshot:
        """Return the latest prepared diagnostics snapshot."""

    def prepared_menu_actions_for_source_position(
        self,
        source_position: int,
    ) -> PromptDiagnosticMenuActionSnapshot:
        """Return prepared diagnostic actions for one source position."""


class PromptContextMenuLoraMetadataPort(Protocol):
    """Read prepared LoRA catalog metadata for context-menu assembly."""

    @property
    def snapshot(self) -> PromptLoraMetadataSnapshot:
        """Return the latest prepared LoRA metadata snapshot."""

    @property
    def lora_picker_ready(self) -> bool:
        """Return whether the LoRA picker action may be offered."""


class PromptContextMenuLoraTriggerWordPort(Protocol):
    """Read prepared LoRA trigger-word state for context-menu assembly."""

    def snapshot_for_prompt(
        self,
        *,
        prompt_text: str,
    ) -> PromptLoraActionSnapshot:
        """Project trigger actions from authoritative cached prompt context."""

    def unavailable_snapshot(
        self,
        *,
        unavailable_reason: str,
    ) -> PromptLoraActionSnapshot:
        """Return unavailable trigger actions for stale menu context."""


class PromptContextMenuSceneSnapshotPort(Protocol):
    """Read immutable scene publication for context-menu assembly."""

    @property
    def snapshot(self) -> PromptSceneContextSnapshot:
        """Return the latest prepared scene snapshot."""


class PromptContextMenuScenePositionPort(Protocol):
    """Read prepared source-position scene state for context-menu assembly."""

    def prepared_position_context(
        self,
        source_position: int,
    ) -> PromptScenePositionContextSnapshot:
        """Return prepared position context without performing fresh work."""


class PromptContextMenuSegmentPort(Protocol):
    """Read prepared prompt-segment state for context-menu assembly."""

    @property
    def snapshot(self) -> PromptSegmentPresetSnapshot:
        """Return the latest prepared prompt-segment snapshot."""

    def prepared_menu_snapshot_for_selection(
        self,
        *,
        selected_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
    ) -> PromptSegmentPresetSnapshot:
        """Return prepared selected-text state without deriving it."""


class PromptContextMenuDanbooruPort(Protocol):
    """Read prepared Danbooru state for context-menu assembly."""

    @property
    def snapshot(self) -> PromptDanbooruActionSnapshot:
        """Return the latest prepared Danbooru snapshot."""

    def prepared_menu_snapshot_for_selection(
        self,
        *,
        selection_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
    ) -> PromptDanbooruActionSnapshot:
        """Return prepared selected-text Danbooru state without deriving it."""


__all__ = [
    "PromptContextMenuDanbooruPort",
    "PromptContextMenuDiagnosticsPort",
    "PromptContextMenuLoraMetadataPort",
    "PromptContextMenuLoraTriggerWordPort",
    "PromptContextMenuScenePositionPort",
    "PromptContextMenuSceneSnapshotPort",
    "PromptContextMenuSegmentPort",
]

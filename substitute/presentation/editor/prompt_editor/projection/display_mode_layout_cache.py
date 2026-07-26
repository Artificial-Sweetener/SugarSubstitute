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

"""Reuse exact raw and projected prompt layouts across display-mode toggles."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSemanticIdentity,
)

from .applicator import PromptProjectionRebuildResult
from ..layout.checkpoints import (
    PromptProjectionLayoutCheckpoint,
    capture_layout_checkpoint,
    restore_layout_checkpoint,
)
from ..layout.contracts import PromptLayoutOutput
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretState,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from .session import PromptProjectionSession
from .paint_input import PromptProjectionPaintInput


@dataclass(frozen=True, slots=True)
class PromptProjectionDisplayModeLayoutIdentity:
    """Identify every canonical input that can change mode-specific geometry."""

    semantic_identity: PromptSemanticIdentity
    expanded_source_range: tuple[int, int] | None
    transient_neutral_emphasis: object | None
    exact_weight_edit: object | None
    decoration_accent_ranges: tuple[tuple[int, int], ...]
    scene_error_keys: frozenset[str]

    @classmethod
    def from_projection_state(
        cls,
        *,
        semantic_identity: PromptSemanticIdentity,
        session: PromptProjectionSession,
        decoration_accent_ranges: tuple[tuple[int, int], ...],
        scene_error_keys: frozenset[str],
    ) -> PromptProjectionDisplayModeLayoutIdentity:
        """Build a strict identity without materializing source or syntax data."""

        return cls(
            semantic_identity=semantic_identity,
            expanded_source_range=session.expanded_source_range,
            transient_neutral_emphasis=session.transient_neutral_emphasis,
            exact_weight_edit=session.exact_weight_edit,
            decoration_accent_ranges=decoration_accent_ranges,
            scene_error_keys=scene_error_keys,
        )


@dataclass(frozen=True, slots=True)
class _PromptProjectionDisplayModeLayoutEntry:
    """Pair one canonical identity with its exact layout checkpoint."""

    identity: PromptProjectionDisplayModeLayoutIdentity
    checkpoint: PromptProjectionLayoutCheckpoint


@dataclass(frozen=True, slots=True)
class PromptProjectionDisplayModeRestore:
    """Carry restored layout output and caret-resolved projection state."""

    layout_output: PromptLayoutOutput
    projection_rebuild: PromptProjectionRebuildResult


class PromptProjectionDisplayModeLayoutCache:
    """Own bounded exact-layout checkpoints for the two display modes."""

    def __init__(self) -> None:
        """Initialize an empty two-entry mode cache."""

        self._entries: dict[
            PromptProjectionDisplayMode,
            _PromptProjectionDisplayModeLayoutEntry,
        ] = {}

    def clear(self) -> None:
        """Discard layouts after any non-mode canonical projection change."""

        self._entries.clear()

    def remember(
        self,
        display_mode: PromptProjectionDisplayMode,
        layout_output: PromptLayoutOutput,
        paint_input: PromptProjectionPaintInput,
        *,
        identity: PromptProjectionDisplayModeLayoutIdentity,
    ) -> None:
        """Remember the exact current layout when source ownership is canonical."""

        checkpoint = capture_layout_checkpoint(
            layout_output,
            palette_key=int(paint_input.palette.cacheKey()),
            semantic_palette=paint_input.semantic_palette,
        )
        if (
            checkpoint is None
            or checkpoint.projection_document.display_mode is not display_mode
        ):
            self._entries.pop(display_mode, None)
            return
        self._entries[display_mode] = _PromptProjectionDisplayModeLayoutEntry(
            identity=identity,
            checkpoint=checkpoint,
        )

    def try_restore(
        self,
        display_mode: PromptProjectionDisplayMode,
        current_output: PromptLayoutOutput,
        paint_input: PromptProjectionPaintInput,
        *,
        identity: PromptProjectionDisplayModeLayoutIdentity,
        expected_source_text: str,
        previous_cursor_state: PromptProjectionCaretState,
        previous_anchor_state: PromptProjectionCaretState,
    ) -> PromptProjectionDisplayModeRestore | None:
        """Restore one exact matching mode layout and remap source carets."""

        entry = self._entries.get(display_mode)
        if (
            entry is None
            or entry.identity != identity
            or entry.checkpoint.projection_document.display_mode is not display_mode
            or entry.checkpoint.projection_document.source_text != expected_source_text
        ):
            self._entries.pop(display_mode, None)
            return None
        checkpoint = entry.checkpoint
        layout_output = restore_layout_checkpoint(
            checkpoint,
            configuration=current_output.configuration,
            palette_key=int(paint_input.palette.cacheKey()),
            semantic_palette=paint_input.semantic_palette,
        )
        if layout_output is None:
            self._entries.pop(display_mode, None)
            return None
        projection_document = checkpoint.projection_document
        return PromptProjectionDisplayModeRestore(
            layout_output=layout_output,
            projection_rebuild=PromptProjectionRebuildResult(
                projection_document=projection_document,
                active_span_range=None,
                cursor_state=projection_document.caret_map.resolve_state(
                    previous_cursor_state
                ),
                anchor_state=projection_document.caret_map.resolve_state(
                    previous_anchor_state
                ),
            ),
        )


__all__ = [
    "PromptProjectionDisplayModeLayoutCache",
    "PromptProjectionDisplayModeLayoutIdentity",
    "PromptProjectionDisplayModeRestore",
]

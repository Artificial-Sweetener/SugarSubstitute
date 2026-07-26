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

"""Own explicit feature preparation before a prompt context menu opens."""

from __future__ import annotations

from collections.abc import Callable

from .scene_models import PromptScenePositionContextSnapshot


class PromptContextMenuPreparationLifecycle:
    """Dispatch explicit selected-text and source-position menu preparation."""

    def __init__(
        self,
        *,
        prepare_segment_selection: Callable[
            [str, tuple[int, int] | None, bool, str], object
        ],
        prepare_danbooru_selection: Callable[
            [str, tuple[int, int] | None, bool, str], object
        ],
        prepare_scene_position: Callable[
            [int, str], PromptScenePositionContextSnapshot
        ],
        prewarm_trigger_words: Callable[[str], bool],
    ) -> None:
        """Store only feature preparation ports."""

        self._prepare_segment_selection = prepare_segment_selection
        self._prepare_danbooru_selection = prepare_danbooru_selection
        self._prepare_scene_position = prepare_scene_position
        self._prewarm_trigger_words = prewarm_trigger_words

    def prepare_selection(
        self,
        *,
        selected_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
        reason: str,
    ) -> None:
        """Prepare only selection-dependent feature state."""

        self._prepare_segment_selection(
            selected_text, selection_range, read_only, reason
        )
        self._prepare_danbooru_selection(
            selected_text, selection_range, read_only, reason
        )

    def prepare_opening(self, *, source_position: int, reason: str) -> None:
        """Prepare scene and trigger state for one menu opening."""

        snapshot = self._prepare_scene_position(source_position, reason)
        if snapshot.context is not None and snapshot.ready and not snapshot.stale:
            self._prewarm_trigger_words(snapshot.context.effective_prompt_text)

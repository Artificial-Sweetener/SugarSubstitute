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

"""Verify prompt-editor catalog refresh publication."""

from __future__ import annotations

from dataclasses import dataclass, field

from substitute.presentation.editor.prompt_editor.catalog_refresh_facade import (
    PromptEditorCatalogRefreshBindings,
    PromptEditorCatalogRefreshFacade,
)


@dataclass(slots=True)
class _CatalogRefreshRecorder:
    """Record externally visible catalog refresh effects."""

    calls: list[object] = field(default_factory=list)

    def clear_thumbnails(self) -> None:
        """Record thumbnail invalidation."""

        self.calls.append("clear")

    def refresh_thumbnail_paint(self, reason: str) -> None:
        """Record projection thumbnail repaint publication."""

        self.calls.append(("paint", reason))

    def update_host(self) -> None:
        """Record host repaint publication."""

        self.calls.append("update")

    def refresh_segments(self, reason: str) -> object:
        """Record saved-segment refresh publication."""

        self.calls.append(("segments", reason))
        return None


def test_thumbnail_invalidation_repaints_projection_before_host() -> None:
    """Every decoded-thumbnail consumer observes one ordered invalidation."""

    recorder = _CatalogRefreshRecorder()
    facade = _facade(recorder)

    facade.clear_lora_thumbnail_cache()

    assert recorder.calls == [
        "clear",
        ("paint", "lora_thumbnail_cache_clear"),
        "update",
    ]


def test_segment_refresh_preserves_publication_reason() -> None:
    """Saved-segment refreshes retain their diagnostic reason."""

    recorder = _CatalogRefreshRecorder()
    facade = _facade(recorder)

    facade.refresh_prompt_segment_presets(reason="panel_context_changed")

    assert recorder.calls == [("segments", "panel_context_changed")]


def _facade(recorder: _CatalogRefreshRecorder) -> PromptEditorCatalogRefreshFacade:
    """Bind one recorder to the production catalog refresh facade."""

    return PromptEditorCatalogRefreshFacade(
        bindings=PromptEditorCatalogRefreshBindings(
            mark_lora_metadata_dirty=lambda: None,
            refresh_lora_metadata_if_visible=lambda: False,
            schedule_lora_metadata_catchup=lambda: None,
            clear_thumbnail_cache=recorder.clear_thumbnails,
            refresh_thumbnail_paint=recorder.refresh_thumbnail_paint,
            update_host=recorder.update_host,
            refresh_segment_presets=recorder.refresh_segments,
        ),
    )

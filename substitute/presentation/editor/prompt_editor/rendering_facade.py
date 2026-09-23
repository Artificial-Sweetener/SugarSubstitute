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

"""Own mounted prompt-editor rendering-mode publication."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .core.projection.document import PromptProjectionDisplayMode
from .interactions import PromptInteractionController
from .projection.surface import PromptProjectionSurface


@dataclass(frozen=True, slots=True)
class PromptEditorRenderingBindings:
    """Declare rendering state and dependent publication operations."""

    display_mode: Callable[[], PromptProjectionDisplayMode]
    set_display_mode: Callable[[PromptProjectionDisplayMode], None]
    set_exact_source_editing: Callable[[bool], None]
    publish_cursor_position_changed: Callable[[], None]
    publish_rich_rendering_changed: Callable[[bool], None]


@dataclass(frozen=True, slots=True)
class PromptEditorRenderingFacade:
    """Coordinate display mode with exact editing and feature refresh."""

    bindings: PromptEditorRenderingBindings

    @property
    def display_mode(self) -> PromptProjectionDisplayMode:
        """Return the current visible prompt display mode."""

        return self.bindings.display_mode()

    def set_display_mode(self, display_mode: PromptProjectionDisplayMode) -> None:
        """Publish a display mode and refresh cursor-dependent features."""

        self.bindings.set_display_mode(display_mode)
        self.bindings.publish_cursor_position_changed()

    @property
    def rich_rendering_enabled(self) -> bool:
        """Return whether projected prompt rendering is active."""

        return self.display_mode is PromptProjectionDisplayMode.PROJECTED

    def set_rich_rendering_enabled(self, enabled: bool) -> None:
        """Coordinate projected rendering with normalized source editing."""

        was_enabled = self.rich_rendering_enabled
        self.bindings.set_exact_source_editing(not enabled)
        self.set_display_mode(
            PromptProjectionDisplayMode.PROJECTED
            if enabled
            else PromptProjectionDisplayMode.RAW
        )
        if was_enabled != enabled:
            self.bindings.publish_rich_rendering_changed(enabled)


def build_prompt_editor_rendering_facade(
    surface: PromptProjectionSurface,
    interaction: PromptInteractionController,
    publish_rich_rendering_changed: Callable[[bool], None],
) -> PromptEditorRenderingFacade:
    """Bind mounted rendering owners to the editor's public facade."""

    return PromptEditorRenderingFacade(
        PromptEditorRenderingBindings(
            display_mode=surface.display_mode,
            set_display_mode=surface.set_display_mode,
            set_exact_source_editing=surface.set_exact_source_editing_enabled,
            publish_cursor_position_changed=(
                interaction.handle_cursor_position_changed
            ),
            publish_rich_rendering_changed=publish_rich_rendering_changed,
        )
    )


__all__ = [
    "PromptEditorRenderingBindings",
    "PromptEditorRenderingFacade",
    "build_prompt_editor_rendering_facade",
]

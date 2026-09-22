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

"""Verify mounted prompt-editor rendering-mode coordination."""

from __future__ import annotations

from dataclasses import dataclass, field

from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from substitute.presentation.editor.prompt_editor.rendering_facade import (
    PromptEditorRenderingBindings,
    PromptEditorRenderingFacade,
)


@dataclass(slots=True)
class _RenderingRecorder:
    """Record display-mode and dependent feature publications."""

    mode: PromptProjectionDisplayMode
    calls: list[object] = field(default_factory=list)

    def display_mode(self) -> PromptProjectionDisplayMode:
        """Return the current recorded display mode."""

        return self.mode

    def set_display_mode(self, mode: PromptProjectionDisplayMode) -> None:
        """Record and apply a display-mode change."""

        self.calls.append(("mode", mode))
        self.mode = mode

    def set_exact_source_editing(self, enabled: bool) -> None:
        """Record exact-source editing state."""

        self.calls.append(("exact", enabled))

    def publish_cursor(self) -> None:
        """Record cursor-dependent feature refresh."""

        self.calls.append("cursor")

    def publish_rich(self, enabled: bool) -> None:
        """Record public rich-rendering publication."""

        self.calls.append(("rich", enabled))


def test_display_mode_always_refreshes_cursor_dependent_features() -> None:
    """Explicit mode publication preserves the existing cursor refresh contract."""

    recorder = _RenderingRecorder(PromptProjectionDisplayMode.PROJECTED)
    facade = _facade(recorder)

    facade.set_display_mode(PromptProjectionDisplayMode.RAW)

    assert recorder.calls == [
        ("mode", PromptProjectionDisplayMode.RAW),
        "cursor",
    ]


def test_disabling_rich_rendering_enables_exact_source_before_raw_mode() -> None:
    """Raw editing becomes exact before the projection switches presentation."""

    recorder = _RenderingRecorder(PromptProjectionDisplayMode.PROJECTED)
    facade = _facade(recorder)

    facade.set_rich_rendering_enabled(False)

    assert recorder.calls == [
        ("exact", True),
        ("mode", PromptProjectionDisplayMode.RAW),
        "cursor",
        ("rich", False),
    ]


def test_republishing_current_rich_mode_does_not_emit_change_signal() -> None:
    """A stable rich-mode request still refreshes mode without false change."""

    recorder = _RenderingRecorder(PromptProjectionDisplayMode.PROJECTED)
    facade = _facade(recorder)

    facade.set_rich_rendering_enabled(True)

    assert recorder.calls == [
        ("exact", False),
        ("mode", PromptProjectionDisplayMode.PROJECTED),
        "cursor",
    ]


def _facade(recorder: _RenderingRecorder) -> PromptEditorRenderingFacade:
    """Bind one recorder to the production rendering facade."""

    return PromptEditorRenderingFacade(
        PromptEditorRenderingBindings(
            display_mode=recorder.display_mode,
            set_display_mode=recorder.set_display_mode,
            set_exact_source_editing=recorder.set_exact_source_editing,
            publish_cursor_position_changed=recorder.publish_cursor,
            publish_rich_rendering_changed=recorder.publish_rich,
        )
    )

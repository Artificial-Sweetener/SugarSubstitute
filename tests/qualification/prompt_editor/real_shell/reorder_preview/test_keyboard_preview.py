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

"""Verify keyboard-held reorder preview composition through the real shell."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
import pytest

from tests.support.prompt_editor.real_shell.models import (
    PromptReorderChipChromeSnapshot,
)
from tests.support.prompt_editor.real_shell.reorder_rendering import (
    capture_reorder_chip_chrome,
    capture_reorder_layout,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


@pytest.mark.parametrize(
    ("initial_text", "cursor_text", "movement_key"),
    (
        ("alpha, beta, gamma", "beta", Qt.Key.Key_Left),
        ("alpha,\n\nbeta,", "beta", Qt.Key.Key_Up),
        (
            (
                "glowing red eyes, long white hair, swept bangs, "
                "elegant seductive pose, twintails, pink hair ribbon, "
                "white eyebrows, see-through dress, iridescent belt, "
                "spaghetti strap, short white oni horns, "
            ),
            "pink hair ribbon",
            Qt.Key.Key_Right,
        ),
    ),
)
def test_real_shell_alt_arrow_preview_layout_matches_settled_layout(
    real_shell_scenario: PromptEditorRealShellScenario,
    initial_text: str,
    cursor_text: str,
    movement_key: Qt.Key,
) -> None:
    """Match the held-Alt reorder frame to its committed settled layout."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=initial_text)
    real_shell_scenario.input.set_source_cursor_position(
        field,
        initial_text.index(cursor_text) + 1,
    )
    editor = field.editor
    real_shell_scenario.input.focus_editor(field)

    QTest.keyPress(editor, Qt.Key.Key_Alt)
    real_shell_scenario.wait_for_queued_delivery()
    QTest.keyPress(
        editor,
        movement_key,
        Qt.KeyboardModifier.AltModifier,
    )
    real_shell_scenario.wait_for_queued_delivery()
    preview = capture_reorder_layout(field, label="alt-arrow-preview")

    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    real_shell_scenario.wait_until(
        lambda: (
            cast(Any, editor)._surface._reorder_preview_projection.preview_frame is None
        )
    )
    real_shell_scenario.wait_for_queued_delivery()
    settled = capture_reorder_layout(field, label="alt-arrow-settled")

    assert preview.preview_active
    assert not settled.preview_active
    assert preview.source_text == settled.source_text
    assert preview.projection_text == settled.projection_text
    assert preview.content_size == settled.content_size
    assert preview.line_rects == settled.line_rects
    assert preview.fragments == settled.fragments
    assert preview.region_divider_lines == settled.region_divider_lines
    assert preview.region_rail_lines == settled.region_rail_lines


def test_real_shell_alt_arrow_keeps_held_chip_border_owned(
    real_shell_scenario: PromptEditorRealShellScenario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep one stable active border through keyboard-held chip animation."""

    initial_text = "alpha, beta, gamma"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=initial_text)
    real_shell_scenario.input.set_source_cursor_position(
        field,
        initial_text.index("beta") + 1,
    )
    editor = field.editor
    real_shell_scenario.input.focus_editor(field)

    QTest.keyPress(editor, Qt.Key.Key_Alt)
    real_shell_scenario.wait_for_queued_delivery()
    overlay = cast(Any, editor)._segment_overlay
    held_segment_index = overlay.active_segment_index()
    assert held_segment_index is not None
    before_move = capture_reorder_chip_chrome(
        field,
        segment_index=held_segment_index,
        label="before-move",
    )
    animation_owner = overlay._animation_presentation
    animation_owner.set_duration_ms(1000)
    render_owner = overlay._render_publication
    original_sync = render_owner.sync
    animation_frames: list[PromptReorderChipChromeSnapshot] = []

    def capture_animation_frame(*, reason: str) -> None:
        """Capture prepared chrome after every production animation sync."""

        original_sync(reason=reason)
        if reason == "animation_frame":
            animation_frames.append(
                capture_reorder_chip_chrome(
                    field,
                    segment_index=held_segment_index,
                    label=f"animation-frame-{len(animation_frames)}",
                )
            )

    monkeypatch.setattr(render_owner, "sync", capture_animation_frame)

    QTest.keyPress(
        editor,
        Qt.Key.Key_Left,
        Qt.KeyboardModifier.AltModifier,
    )
    real_shell_scenario.wait_for_queued_delivery()

    animated_frames = [
        frame for frame in animation_frames if frame.animation_override_active
    ]
    assert before_move.paint_owners == ("surface",)
    assert len(before_move.border_colors) == 1
    assert animated_frames
    assert all(frame.paint_owners == ("overlay",) for frame in animated_frames)
    assert all(
        frame.border_colors == before_move.border_colors for frame in animated_frames
    )
    assert all(not frame.unsafe_transient for frame in animated_frames)

    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    real_shell_scenario.wait_for_queued_delivery()

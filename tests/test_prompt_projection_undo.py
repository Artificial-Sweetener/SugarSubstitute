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

"""Tests for prompt projection undo and edit coalescing behavior."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionSurface,
)
from substitute.presentation.editor.prompt_editor.projection.transient_edit_overlays import (
    PromptProjectionTransientDeletionOverlay,
)
from tests.prompt_projection_test_helpers import show_prompt_editor, surface_for
from tests.prompt_projection_surface_test_helpers import (
    delay_projection_update_scheduler,
    first_emphasis_token,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
    surface_edit_controller,
    valid_transient_insertion_overlay,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "projection surface tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def _valid_transient_deletion_overlay(
    surface: PromptProjectionSurface,
) -> PromptProjectionTransientDeletionOverlay | None:
    """Return controller-owned transient deletion overlay state for assertions."""

    return surface._transient_edit_overlays.valid_deletion_overlay(  # noqa: SLF001
        freshness_is_stale_safe=surface.has_stale_projection_geometry(),
        source_revision=surface._source_revision,  # noqa: SLF001
    )


def test_projection_surface_undo_groups_held_backspace(
    widgets: list[QWidget],
) -> None:
    """A physical Backspace hold should undo as one edit transaction."""

    box = show_prompt_editor(
        widgets,
        text="alpha",
        width=360,
    )
    surface = surface_for(box)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyPress(box, Qt.Key.Key_Backspace)
    QTest.keyPress(box, Qt.Key.Key_Backspace)
    QTest.keyPress(box, Qt.Key.Key_Backspace)
    QTest.keyRelease(box, Qt.Key.Key_Backspace)

    assert box.toPlainText() == "al"

    box.undo()

    assert box.toPlainText() == "alpha"


def test_projection_surface_baseline_source_text_is_state_zero(
    widgets: list[QWidget],
) -> None:
    """Baseline source replacement should not leave an undo step to empty text."""

    box = show_prompt_editor(
        widgets,
        text="",
        width=360,
    )

    box.replaceBaselineSourceText("recipe prompt")

    assert box.toPlainText() == "recipe prompt"
    assert box.canUndo() is False
    assert box.canRedo() is False

    box.undo()
    box.redo()

    assert box.toPlainText() == "recipe prompt"
    assert box.canUndo() is False
    assert box.canRedo() is False


def test_projection_surface_baseline_source_text_clears_prior_user_history(
    widgets: list[QWidget],
) -> None:
    """Loading a new baseline should discard stale edit history from prior text."""

    box = show_prompt_editor(
        widgets,
        text="",
        width=360,
    )
    surface = surface_for(box)
    box.replaceBaselineSourceText("alpha ")
    surface.set_cursor_positions(cursor_position=6, anchor_position=6)
    QTest.keyClicks(box, "beta")

    box.undo()

    assert box.toPlainText() == "alpha "
    assert box.canRedo() is True

    box.replaceBaselineSourceText("recipe prompt")
    box.undo()

    assert box.toPlainText() == "recipe prompt"
    assert box.canUndo() is False
    assert box.canRedo() is False


def test_projection_surface_typing_word_coalesces_for_undo(
    widgets: list[QWidget],
) -> None:
    """Plain adjacent word typing should undo as one editor transaction."""

    box = show_prompt_editor(
        widgets,
        text="",
        width=360,
    )
    surface = surface_for(box)
    box.replaceBaselineSourceText("alpha ")
    surface.set_cursor_positions(cursor_position=6, anchor_position=6)

    QTest.keyClicks(box, "beta")

    assert box.toPlainText() == "alpha beta"

    box.undo()

    assert box.toPlainText() == "alpha "
    assert box.canRedo() is True


def test_projection_surface_idle_separated_typing_keeps_separate_undo_steps(
    widgets: list[QWidget],
) -> None:
    """Typing bursts separated by idle should become separate undo transactions."""

    box = show_prompt_editor(
        widgets,
        text="",
        width=360,
    )
    surface = surface_for(box)
    box.replaceBaselineSourceText("a")
    surface.set_cursor_positions(cursor_position=1, anchor_position=1)

    QTest.keyClicks(box, "b")
    surface_edit_controller(surface).finish_pending_key_edit_block(reason="test_idle")
    QTest.keyClicks(box, "c")

    assert box.toPlainText() == "abc"

    box.undo()

    assert box.toPlainText() == "ab"


def test_projection_surface_prompt_boundaries_split_typing_undo_steps(
    widgets: list[QWidget],
) -> None:
    """Comma and space boundaries should keep prompt tag undo steps predictable."""

    box = show_prompt_editor(
        widgets,
        text="",
        width=360,
    )

    box.replaceBaselineSourceText("")
    QTest.keyClicks(box, "cat, dog")

    assert box.toPlainText() == "cat, dog"

    box.undo()

    assert box.toPlainText() == "cat, "


def test_projection_surface_paste_does_not_merge_with_prior_typing(
    widgets: list[QWidget],
) -> None:
    """Paste should remain an independent transaction after a typing burst."""

    box = show_prompt_editor(
        widgets,
        text="",
        width=360,
    )
    surface = surface_for(box)
    box.replaceBaselineSourceText("alpha ")
    surface.set_cursor_positions(cursor_position=6, anchor_position=6)
    QTest.keyClicks(box, "beta")
    QApplication.clipboard().setText(" gamma")

    box.paste()

    assert box.toPlainText() == "alpha beta gamma"

    box.undo()

    assert box.toPlainText() == "alpha beta"


def test_projection_surface_rapid_backspace_clicks_coalesce_for_undo(
    widgets: list[QWidget],
) -> None:
    """Rapid Backspace taps should undo as one professional-editor transaction."""

    box = show_prompt_editor(
        widgets,
        text="alpha",
        width=360,
    )
    surface = surface_for(box)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClick(box, Qt.Key.Key_Backspace)
    QTest.keyClick(box, Qt.Key.Key_Backspace)

    assert box.toPlainText() == "alp"

    box.undo()

    assert box.toPlainText() == "alpha"


def test_projection_surface_idle_backspace_groups_stay_separate_undo_steps(
    widgets: list[QWidget],
) -> None:
    """A pause between Backspace taps should commit separate undo transactions."""

    box = show_prompt_editor(
        widgets,
        text="alpha",
        width=360,
    )
    surface = surface_for(box)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClick(box, Qt.Key.Key_Backspace)
    surface_edit_controller(surface).finish_pending_key_edit_block(reason="test_idle")
    QTest.keyClick(box, Qt.Key.Key_Backspace)

    assert box.toPlainText() == "alp"

    box.undo()

    assert box.toPlainText() == "alph"


def test_projection_surface_undo_restores_stored_projection_state(
    widgets: list[QWidget],
) -> None:
    """Undo should not rebuild through an empty syntax projection snapshot."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), alpha",
        width=360,
    )
    surface = surface_for(box)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    assert first_emphasis_token(box).display_text == "cat"

    QTest.keyClick(box, Qt.Key.Key_Backspace)
    box.undo()

    assert box.toPlainText() == "(cat:1.05), alpha"
    assert first_emphasis_token(box).display_text == "cat"


def test_projection_surface_backspace_clears_pending_insert_overlay(
    widgets: list[QWidget],
) -> None:
    """Backspace over deferred typed text should commit authoritative geometry."""

    box = show_prompt_editor(
        widgets,
        text="alpha",
        width=360,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClicks(box, "xy")
    QTest.keyClick(box, Qt.Key.Key_Backspace)

    insertion_overlay = valid_transient_insertion_overlay(surface)
    deletion_overlay = _valid_transient_deletion_overlay(surface)
    assert box.toPlainText() == "alphax"
    assert insertion_overlay is None
    assert deletion_overlay is None
    assert surface.has_stale_projection_geometry() is False

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

"""Exercise one support.PromptEditor sizing behavior owner."""

from __future__ import annotations

import pytest

from . import sizing_support as support

pytestmark = pytest.mark.usefixtures("qt_clipboard_owner")

prompt_editors = support.prompt_editors


def test_prompt_editor_disables_qfluent_smooth_scrolling(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Prompt editors should scroll immediately without QFluent wheel smoothing."""

    box = support.show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(20)),
        width=600,
    )
    scroll_delegate = box.scrollDelegate

    assert scroll_delegate.useAni is False
    assert (
        scroll_delegate.verticalSmoothScroll.smoothMode is support.SmoothMode.NO_SMOOTH
    )
    assert (
        scroll_delegate.horizonSmoothScroll.smoothMode is support.SmoothMode.NO_SMOOTH
    )
    assert scroll_delegate.vScrollBar.duration == 0
    assert scroll_delegate.hScrollBar.duration == 0


def test_prompt_editor_visible_scrollbar_tracks_editor_scrollbar_metrics(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """The visible QFluent scrollbar should mirror the editor scroll owner metadata."""

    box = support.show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(20)),
        width=600,
    )
    support.semantic_wait.wait_for_qt_condition(
        lambda: (
            box.scrollDelegate.vScrollBar.pageStep()
            == box.verticalScrollBar().pageStep()
            and box.scrollDelegate.vScrollBar.singleStep()
            == box.verticalScrollBar().singleStep()
        )
    )


def test_prompt_editor_scroll_keeps_projection_surface_pinned_in_shell_viewport(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Scrolling should move rendered content, not the projection surface widget itself."""

    app = support.ensure_qapp()
    box = support.show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(30)),
        width=320,
    )
    surface = getattr(box, "_surface")
    host_scrollbar = support.QFluentTextEdit.verticalScrollBar(box)
    editor_scrollbar = box.verticalScrollBar()

    editor_scrollbar.setValue(
        editor_scrollbar.singleStep() * support.QApplication.wheelScrollLines()
    )
    support.process_events(app)

    assert surface.pos().y() == 0
    assert host_scrollbar.value() == 0
    assert box.scrollDelegate.vScrollBar.value() == editor_scrollbar.value()


def test_prompt_editor_one_wheel_notch_uses_line_based_scroll_delta(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """One mouse-wheel notch should match the support.Qt multiline text-edit scroll delta."""

    app = support.ensure_qapp()
    box = support.show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(30)),
        width=320,
    )
    reference = support.QTextEdit()
    reference.resize(box.width(), box.height())
    reference.setPlainText("\n".join(f"line {index}" for index in range(30)))
    reference.show()
    support.process_events(app)
    surface = getattr(box, "_surface")
    host_scrollbar = support.QFluentTextEdit.verticalScrollBar(box)
    scrollbar = box.verticalScrollBar()
    scrollbar.setValue(0)
    reference.verticalScrollBar().setValue(0)
    support.process_events(app)
    wheel_event = support.QWheelEvent(
        support.QPointF(box.viewport().rect().center()),
        support.QPointF(box.viewport().mapToGlobal(box.viewport().rect().center())),
        support.QPoint(0, 0),
        support.QPoint(0, -120),
        support.Qt.MouseButton.NoButton,
        support.Qt.KeyboardModifier.NoModifier,
        support.Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    reference_wheel_event = support.QWheelEvent(
        support.QPointF(reference.viewport().rect().center()),
        support.QPointF(
            reference.viewport().mapToGlobal(reference.viewport().rect().center())
        ),
        support.QPoint(0, 0),
        support.QPoint(0, -120),
        support.Qt.MouseButton.NoButton,
        support.Qt.KeyboardModifier.NoModifier,
        support.Qt.ScrollPhase.ScrollUpdate,
        False,
    )

    support.QApplication.sendEvent(reference.viewport(), reference_wheel_event)
    support.QApplication.sendEvent(box.viewport(), wheel_event)
    support.process_events(app)

    assert scrollbar.value() == reference.verticalScrollBar().value()
    assert surface.pos().y() == 0
    assert host_scrollbar.value() == 0

    reference.close()
    reference.deleteLater()
    support.process_events(app)


def test_prompt_editor_keeps_projection_surface_pinned_after_viewport_resize_event(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Projection viewport resize events should re-pin the surface to shell geometry."""

    app = support.ensure_qapp()
    box = support.PromptEditor(
        prompt_autocomplete_gateway=support.EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=support.EmptyPromptWildcardCatalogGateway(),
        prompt_syntax_profile=support.prompt_syntax_profile("emphasis", "wildcard"),
        prompt_task_executor_factory=support.immediate_prompt_task_executor_factory(),
    )
    box.setFixedWidth(578)
    prompt_editors.append(box)

    box.setPlainText(
        "landscape photography, cinematic lighting, hyper detailed, dramatic "
        "sky, volumetric fog, sharp focus, 35mm film, subtle grain"
    )
    projection_viewport = box.viewport()
    initial_viewport_width = projection_viewport.width()
    surface = getattr(box, "_surface")
    shell_viewport = support.cast(
        support.Callable[[], support.QWidget], getattr(box, "_shell_viewport")
    )
    shell_width = shell_viewport().width()

    projection_viewport.resize(638, projection_viewport.height())
    support.process_events(app)

    assert projection_viewport.width() > initial_viewport_width + 200
    assert surface.width() == shell_width
    assert box.scrollDelegate.vScrollBar.isVisible() is False


def test_prompt_editor_preserves_baseline_text_edit_commands(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Copy, paste, undo, redo, and selection changes should stay text-edit native."""

    app = support.ensure_qapp()
    box = support.show_prompt_editor(prompt_editors, text="alpha", width=320)
    clipboard = support.QApplication.clipboard()
    clipboard.setText("")

    cursor = box.textCursor()
    cursor.setPosition(0, support.QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(5, support.QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)

    assert box.textCursor().selectionStart() == 0
    assert box.textCursor().selectionEnd() == 5

    box.copy()
    support.process_events(app)
    assert clipboard.text() == "alpha"

    clipboard.setText("beta")
    box.paste()
    support.process_events(app)

    assert box.toPlainText() == "beta"

    box.undo()
    support.process_events(app)

    assert box.toPlainText() == "alpha"

    box.redo()
    support.process_events(app)

    assert box.toPlainText() == "beta"

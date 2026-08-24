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

from . import sizing_support as support

prompt_editors = support.prompt_editors


def test_shell_geometry_sync_ignores_deleted_qt_wrappers(
    monkeypatch: support.pytest.MonkeyPatch,
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Queued geometry sync should no-op after its editor C++ object is gone."""

    box = support.show_prompt_editor(prompt_editors, text="prompt", width=320)
    editor = support.cast(support.Any, box)
    scroll_delegate = support.cast(support.Any, editor._scroll_delegate)
    scroll_delegate.geometry_sync_pending = True
    scroll_delegate.geometry_follow_up_pending = True
    monkeypatch.setattr(
        support.scroll_delegate_module,
        "qt_object_is_alive",
        lambda _obj: False,
    )

    editor._scroll_delegate.sync_shell_geometry()

    assert scroll_delegate.geometry_sync_pending is False
    assert scroll_delegate.geometry_follow_up_pending is False


def test_manual_height_reapply_ignores_deleted_qt_wrappers(
    monkeypatch: support.pytest.MonkeyPatch,
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Queued manual-height layout work should no-op after its editor is gone."""

    box = support.show_prompt_editor(prompt_editors, text="prompt", width=320)
    editor = support.cast(support.Any, box)
    sizing = support.cast(support.Any, editor._sizing)
    sizing._manual_height_layout_reapply_pending = True
    sizing._manual_scroll_height = box.height()
    monkeypatch.setattr(
        support.sizing_controller_module,
        "qt_object_is_alive",
        lambda _obj: False,
    )

    editor._sizing.reapply_manual_height_for_current_layout()

    assert sizing._manual_height_layout_reapply_pending is False
    assert sizing._manual_scroll_height == box.height()


def test_prompt_editor_recomputes_height_when_width_increases_without_typing(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Widening the editor should shrink wrapped prompt height without needing input."""

    box = support.show_prompt_editor(
        prompt_editors,
        text=(
            "landscape photography, cinematic lighting, hyper detailed, dramatic "
            "sky, volumetric fog, sharp focus, 35mm film, subtle grain"
        ),
        width=180,
    )
    tall_height = box.height()

    box.resize(600, box.height())
    support.semantic_wait.wait_for_qt_condition(lambda: box.height() < tall_height)

    assert box.height() < tall_height
    assert box.scrollDelegate.vScrollBar.isVisible() is False


def test_prompt_editor_shell_geometry_waits_for_pending_projection_height(
    monkeypatch: support.pytest.MonkeyPatch,
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Host geometry sync should not consume stale prompt height during safe typing."""

    box = support.show_prompt_editor(prompt_editors, text="(cat:1.05), ", width=240)
    support.delay_projection_update_scheduler(box)
    cursor = box.textCursor()
    cursor.setPosition(len(box.toPlainText()))
    box.setTextCursor(cursor)

    support.QTest.keyClicks(box, "x")
    support.flush_semantic_refresh(box)

    surface = support.cast(support.Any, getattr(box, "_surface"))
    assert surface.has_pending_projection_update() is True
    applied_heights: list[float] = []
    monkeypatch.setattr(
        support.cast(support.Any, box)._scroll_delegate,
        "_handle_content_height_changed",
        lambda content_height: applied_heights.append(float(content_height)),
    )

    support.cast(support.Any, box)._scroll_delegate.sync_shell_geometry()

    assert applied_heights == []
    assert surface.has_pending_projection_update() is True
    support.flush_projection_update_scheduler(box)


def test_prompt_editor_same_line_backspace_does_not_commit_height(
    monkeypatch: support.pytest.MonkeyPatch,
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Plain same-line backspace should not publish a public height change."""

    app = support.ensure_qapp()
    box = support.show_prompt_editor(prompt_editors, text="alpha beta", width=600)
    support.delay_projection_update_scheduler(box)
    support.process_events(app)
    cursor = box.textCursor()
    cursor.setPosition(len(box.toPlainText()))
    box.setTextCursor(cursor)
    initial_height = box.height()
    applied_heights: list[int] = []
    sizing = support.cast(support.Any, getattr(box, "_sizing"))
    apply_preferred_height = support.cast(
        support.Callable[[int], None],
        getattr(sizing, "apply_preferred_height"),
    )

    def record_height(preferred_height: int) -> None:
        """Record visible height commits while preserving production behavior."""

        applied_heights.append(preferred_height)
        apply_preferred_height(preferred_height)

    monkeypatch.setattr(sizing, "apply_preferred_height", record_height)

    support.QTest.keyClick(box, support.Qt.Key.Key_Backspace)
    support.process_events(app)

    assert box.toPlainText() == "alpha bet"
    assert box.height() == initial_height
    assert applied_heights == []

    support.flush_projection_update_scheduler(box)
    support.process_events(app)

    assert box.height() == initial_height
    assert applied_heights == []


def test_prompt_editor_line_break_backspace_height_commit_is_single(
    monkeypatch: support.pytest.MonkeyPatch,
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Deleting a hard line break should settle through one public height change."""

    app = support.ensure_qapp()
    box = support.show_prompt_editor(prompt_editors, text="alpha\nbeta", width=600)
    support.process_events(app)
    cursor = box.textCursor()
    cursor.setPosition(len("alpha\n"))
    box.setTextCursor(cursor)
    initial_height = box.height()
    applied_heights: list[int] = []
    sizing = support.cast(support.Any, getattr(box, "_sizing"))
    apply_preferred_height = support.cast(
        support.Callable[[int], None],
        getattr(sizing, "apply_preferred_height"),
    )

    def record_height(preferred_height: int) -> None:
        """Record visible height commits while preserving production behavior."""

        applied_heights.append(preferred_height)
        apply_preferred_height(preferred_height)

    monkeypatch.setattr(sizing, "apply_preferred_height", record_height)

    support.QTest.keyClick(box, support.Qt.Key.Key_Backspace)
    support.process_events(app)

    assert box.toPlainText() == "alphabeta"
    assert box.height() < initial_height
    assert applied_heights == [box.height()]


def test_prompt_editor_reports_live_height_in_size_hints(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Size hints should match the current fixed editor height used by layouts."""

    box = support.show_prompt_editor(prompt_editors, text="short prompt", width=600)

    assert box.sizeHint().height() == box.height()
    assert box.minimumSizeHint().height() == box.height()


def test_prompt_editor_empty_value_uses_single_line_height_without_scrollbar(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Empty prompts should render as a single visible line without scrollbars."""

    box = support.show_prompt_editor(prompt_editors, text="", width=600)

    assert box.height() == box.minimumEditorHeight()
    assert box.scrollDelegate.vScrollBar.isVisible() is False


def test_prompt_editor_one_line_shell_metrics_match_qfluent_reference(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Prompt editors should preserve QFluent host text metrics and padding."""

    app = support.ensure_qapp()
    box = support.show_prompt_editor(prompt_editors, text="alpha", width=600)
    reference = support.QFluentTextEdit()
    reference.resize(box.width(), box.height())
    reference.setPlainText("alpha")
    reference.show()
    support.process_events(app)

    assert box.contentsMargins().left() == reference.contentsMargins().left()
    assert box.contentsMargins().right() == reference.contentsMargins().right()
    assert box.document().documentMargin() == reference.document().documentMargin()
    assert abs(box.lineHeight() - reference.fontMetrics().lineSpacing()) <= 1
    assert box.lineHeight() == support.math.ceil(
        support.cast(support.Any, box)._surface.text_line_height()
    )
    assert box.viewport().width() == reference.viewport().width()
    assert box.viewport().height() == reference.viewport().height()
    assert (
        box.verticalScrollBar().singleStep()
        == reference.verticalScrollBar().singleStep()
    )

    reference.close()
    reference.deleteLater()
    support.process_events(app)


def test_prompt_editor_caps_height_at_ten_lines_and_enables_scrollbar(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Prompt editors should stop growing after ten visible lines."""

    box = support.show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(20)),
        width=600,
    )

    assert box.height() == box.lineHeight() * 10 + support.height_padding(box)
    assert box.scrollDelegate.vScrollBar.isVisible() is True


def test_prompt_editor_fill_plane_preserves_qfluent_shell_geometry(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Prompt fill effects should not alter QFluent shell metrics."""

    box = support.show_prompt_editor(
        prompt_editors,
        text="**one\nwide shot\n**two\nclose portrait",
        width=600,
    )
    layer = support.fill_plane_for(box)
    projection_rect = support.cast(support.Any, layer)._projection_viewport_rect()
    clip_region = support.cast(support.Any, layer).fill_clip_region()
    left_padding_point = support.QPoint(
        max(1, projection_rect.left() - 1),
        projection_rect.top() + box.lineHeight(),
    )

    assert (
        layer.testAttribute(support.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        is True
    )
    assert layer.focusPolicy() == support.Qt.FocusPolicy.NoFocus
    shell_viewport = support.cast(
        support.Callable[[], support.QWidget], getattr(box, "_shell_viewport")
    )

    assert layer.geometry() == shell_viewport().rect()
    assert clip_region.contains(left_padding_point) is True
    assert clip_region.contains(projection_rect.center()) is True


def test_prompt_editor_fill_plane_maps_sibling_widgets_without_qt_warning(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Prompt fill geometry should not call support.QWidget.mapTo across sibling widgets."""

    box = support.show_prompt_editor(
        prompt_editors,
        text="**one\nwide shot\n**two\nclose portrait",
        width=600,
    )
    layer = support.fill_plane_for(box)
    surface = support.cast(support.Any, getattr(box, "_surface"))
    projection_viewport = support.cast(support.QWidget, surface.viewport())
    messages: list[str] = []

    assert support.widget_has_ancestor(projection_viewport, layer) is False
    expected_top_left = layer.mapFromGlobal(
        projection_viewport.mapToGlobal(support.QPoint(0, 0))
    )

    previous_handler = support.qInstallMessageHandler(
        lambda _mode, _context, message: messages.append(message)
    )
    try:
        projection_rect = support.cast(support.Any, layer)._projection_viewport_rect()
        support.cast(support.Any, layer).mapped_prompt_fill_band_rects()
        support.cast(support.Any, layer).fill_clip_region()
    finally:
        support.qInstallMessageHandler(previous_handler)

    assert projection_rect.topLeft() == expected_top_left
    assert not any(
        "parent must be in parent hierarchy" in message for message in messages
    )

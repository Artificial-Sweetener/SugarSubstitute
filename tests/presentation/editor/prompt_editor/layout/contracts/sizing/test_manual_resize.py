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


def test_prompt_editor_shows_resize_handle_only_in_scroll_mode(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Only scrollable prompt editors should expose manual viewport resizing."""

    short_box = support.show_prompt_editor(
        prompt_editors, text="short prompt", width=600
    )
    long_box = support.show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(20)),
        width=600,
    )

    assert support.resize_handle_for(short_box).isVisible() is False
    assert support.resize_handle_for(long_box).isVisible() is True


def test_prompt_editor_manual_scroll_height_updates_size_and_scroll_metrics(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Manual scroll height should resize the shell and refresh scroll metrics."""

    app = support.ensure_qapp()
    box = support.show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(40)),
        width=600,
    )
    original_height = box.height()
    original_page_step = box.verticalScrollBar().pageStep()
    target_height = original_height + box.lineHeight() * 3

    support.set_manual_scroll_height(box, target_height)
    support.process_events(app)

    assert box.height() == target_height
    assert box.sizeHint().height() == target_height
    assert box.minimumSizeHint().height() == target_height
    assert box.verticalScrollBar().pageStep() > original_page_step
    assert box.verticalScrollBar().maximum() >= 0
    assert support.resize_handle_for(box).isVisible() is True


def test_prompt_editor_public_manual_scroll_height_api_reports_stored_height(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Public manual height API should expose the stored user-owned cap."""

    app = support.ensure_qapp()
    box = support.show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(40)),
        width=600,
    )
    target_height = box.height() + box.lineHeight() * 2

    box.setManualScrollHeight(target_height)
    support.process_events(app)

    assert box.manualScrollHeight() == target_height
    assert box.height() == target_height


def test_prompt_editor_manual_scroll_height_signal_emits_only_for_stored_changes(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Manual height signal should ignore duplicate clamps and emit clear events."""

    app = support.ensure_qapp()
    box = support.show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(40)),
        width=600,
    )
    changes: list[object] = []
    target_height = box.height() + box.lineHeight() * 2
    box.manualScrollHeightChanged.connect(changes.append)

    box.setManualScrollHeight(target_height)
    box.setManualScrollHeight(target_height)
    box.setManualScrollHeight(None)
    support.process_events(app)

    assert changes == [target_height, None]
    assert box.manualScrollHeight() is None


def test_prompt_editor_automatic_resize_does_not_emit_manual_height_change(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Width-driven automatic reflow should not look like user manual resizing."""

    app = support.ensure_qapp()
    box = support.show_prompt_editor(
        prompt_editors,
        text=(
            "landscape photography, cinematic lighting, hyper detailed, dramatic "
            "sky, volumetric fog, sharp focus, 35mm film, subtle grain"
        ),
        width=180,
    )
    changes: list[object] = []
    box.manualScrollHeightChanged.connect(changes.append)

    box.resize(600, box.height())
    support.process_events(app)

    assert changes == []
    assert box.manualScrollHeight() is None


def test_prompt_editor_resize_handle_drag_does_not_move_text_cursor(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """The resize affordance should capture mouse drags outside text editing."""

    app = support.ensure_qapp()
    box = support.show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(40)),
        width=600,
    )
    cursor = box.textCursor()
    cursor.setPosition(5)
    box.setTextCursor(cursor)
    initial_height = box.height()
    handle = support.resize_handle_for(box)
    start_position = handle.rect().center()

    support.QTest.mousePress(
        handle, support.Qt.MouseButton.LeftButton, pos=start_position
    )
    support.QTest.mouseMove(
        handle,
        support.QPoint(start_position.x(), start_position.y() + box.lineHeight() * 2),
    )
    support.QTest.mouseRelease(
        handle,
        support.Qt.MouseButton.LeftButton,
        pos=support.QPoint(
            start_position.x(), start_position.y() + box.lineHeight() * 2
        ),
    )
    support.process_events(app)

    assert box.height() > initial_height
    assert box.textCursor().position() == 5


def test_prompt_editor_manual_scroll_height_is_bounded(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Visible manual height should stay inside current prompt layout bounds."""

    app = support.ensure_qapp()
    box = support.show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(80)),
        width=600,
    )
    minimum_height = support.default_scroll_height(box)

    support.set_manual_scroll_height(box, minimum_height - box.lineHeight() * 4)
    support.process_events(app)
    assert box.manualScrollHeight() == minimum_height
    assert box.height() == minimum_height

    support.set_manual_scroll_height(box, minimum_height * 6)
    support.process_events(app)
    assert box.manualScrollHeight() == minimum_height * 6
    assert box.height() == minimum_height * 2


def test_prompt_editor_can_shrink_after_expanding_to_fit_content(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """A fully expanded prompt should keep the handle available for shrinking."""

    app = support.ensure_qapp()
    box = support.show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(14)),
        width=600,
    )
    minimum_height = support.default_scroll_height(box)

    support.set_manual_scroll_height(box, minimum_height * 6)
    support.process_events(app)

    assert box.height() > minimum_height
    assert box.scrollDelegate.vScrollBar.isVisible() is False
    assert support.resize_handle_for(box).isVisible() is True

    support.set_manual_scroll_height(box, minimum_height)
    support.process_events(app)

    assert box.height() == minimum_height
    assert box.scrollDelegate.vScrollBar.isVisible() is True
    assert support.resize_handle_for(box).isVisible() is True


def test_prompt_editor_manual_height_does_not_expand_beyond_content_height(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Manual mode should keep visible height inside normal content bounds."""

    app = support.ensure_qapp()
    original_text = "\n".join(f"line {index}" for index in range(14))
    box = support.show_prompt_editor(prompt_editors, text=original_text, width=600)
    minimum_height = support.default_scroll_height(box)

    support.set_manual_scroll_height(box, minimum_height * 6)
    support.process_events(app)
    expanded_height = box.height()

    box.setPlainText(f"{original_text}\nnew line")
    support.process_events(app)

    assert box.manualScrollHeight() == minimum_height * 6
    sizing = support.cast(support.Any, getattr(box, "_sizing"))
    assert box.height() == support.cast(int, sizing.last_natural_height)
    assert box.height() > expanded_height
    manual_height = box.manualScrollHeight()
    assert manual_height is not None
    assert box.height() < manual_height
    assert box.scrollDelegate.vScrollBar.isVisible() is False
    assert support.resize_handle_for(box).isVisible() is True


def test_prompt_editor_shorter_content_collapses_below_manual_scroll_height(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Short content should auto-fit while retaining latent manual preference."""

    app = support.ensure_qapp()
    box = support.show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(40)),
        width=600,
    )
    manual_height = box.height() + box.lineHeight() * 3
    support.set_manual_scroll_height(box, manual_height)
    support.process_events(app)

    box.setPlainText("short prompt")
    support.process_events(app)

    assert box.manualScrollHeight() == manual_height
    assert box.height() == box.minimumEditorHeight()
    assert box.scrollDelegate.vScrollBar.isVisible() is False
    assert support.resize_handle_for(box).isVisible() is False


def test_prompt_editor_manual_height_catches_up_when_layout_bounds_expand() -> None:
    """A restored manual preference should survive a temporary startup clamp."""

    app = support.ensure_qapp()
    host = support.ManualResizeScrollHost()
    scroll_area = host.scroll_surface
    content = support.QWidget()
    layout = support.QVBoxLayout(content)
    box = support.PromptEditor(
        prompt_autocomplete_gateway=support.EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=support.EmptyPromptWildcardCatalogGateway(),
        prompt_syntax_profile=support.prompt_syntax_profile("emphasis", "wildcard"),
        prompt_task_executor_factory=support.immediate_prompt_task_executor_factory(),
    )
    box.setPlainText("\n".join(f"line {index}" for index in range(120)))
    layout.addWidget(box)
    scroll_area.setWidgetResizable(True)
    scroll_area.setWidget(content)
    constrained_height = support.default_scroll_height(box) + box.lineHeight()
    scroll_area.resize(360, constrained_height)
    host.resize(360, constrained_height)
    scroll_area.setGeometry(host.rect())
    host.show()
    support.process_events(app)
    changes: list[object] = []
    box.manualScrollHeightChanged.connect(changes.append)
    restored_height = support.default_scroll_height(box) * 6

    support.set_manual_scroll_height(box, restored_height)
    support.process_events(app)
    constrained_box_height = box.height()
    host.resize(360, restored_height * 2)
    scroll_area.setGeometry(host.rect())
    support.process_events(app)

    assert box.manualScrollHeight() == restored_height
    assert constrained_box_height < restored_height
    assert box.height() == restored_height
    assert changes == [restored_height]

    support.destroy_widget_roots((host,))


def test_prompt_editor_width_changes_keep_manual_scroll_preference(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Width-driven reflow should not discard the remembered manual scroll height."""

    app = support.ensure_qapp()
    box = support.show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(40)),
        width=600,
    )
    manual_height = box.height() + box.lineHeight() * 2
    support.set_manual_scroll_height(box, manual_height)
    support.process_events(app)

    box.resize(420, box.height())
    support.process_events(app)

    assert box.height() == manual_height
    assert support.resize_handle_for(box).isVisible() is True


def test_prompt_editor_manual_resize_refreshes_editor_panel_scroll_metrics(
    prompt_editors: list[support.PromptEditor],
) -> None:
    """Editor-panel scroll metrics should update after a prompt editor grows."""

    app = support.ensure_qapp()
    scroll_area = support.EditorPanelScrollSurface()
    content = support.QWidget()
    layout = support.QVBoxLayout(content)
    box = support.PromptEditor(
        prompt_autocomplete_gateway=support.EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=support.EmptyPromptWildcardCatalogGateway(),
        prompt_syntax_profile=support.prompt_syntax_profile("emphasis", "wildcard"),
        prompt_task_executor_factory=support.immediate_prompt_task_executor_factory(),
    )
    box.setPlainText("\n".join(f"line {index}" for index in range(40)))
    layout.addWidget(box)
    scroll_area.setWidgetResizable(True)
    scroll_area.setWidget(content)
    scroll_area.resize(360, max(1, support.default_scroll_height(box) // 2))
    scroll_area.show()
    support.semantic_wait.wait_for_qt_condition(
        lambda: scroll_area.verticalScrollBar().maximum() > 0,
        description="editor panel to expose initial prompt overflow",
        state=lambda: {
            "viewport_height": scroll_area.viewport().height(),
            "content_height": content.height(),
            "scroll_maximum": scroll_area.verticalScrollBar().maximum(),
        },
    )
    refresh_count = 0

    def record_refresh() -> None:
        nonlocal refresh_count
        refresh_count += 1

    scroll_area.metrics_refreshed.connect(record_refresh)
    original_maximum = scroll_area.verticalScrollBar().maximum()

    support.set_manual_scroll_height(box, box.height() + box.lineHeight() * 4)
    support.semantic_wait.wait_for_qt_condition(
        lambda: (
            refresh_count > 0
            and scroll_area.verticalScrollBar().maximum() > original_maximum
        ),
        description="editor panel metrics to reflect manual prompt growth",
        state=lambda: {
            "refresh_count": refresh_count,
            "original_maximum": original_maximum,
            "scroll_maximum": scroll_area.verticalScrollBar().maximum(),
        },
    )

    assert refresh_count > 0
    assert scroll_area.verticalScrollBar().maximum() > original_maximum

    scroll_area.close()
    scroll_area.deleteLater()
    support.process_events(app)

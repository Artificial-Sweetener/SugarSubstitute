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

"""Contract tests for prompt-editor sizing and scrollbar behavior."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt, qInstallMessageHandler
from PySide6.QtGui import QTextCursor, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTextEdit, QVBoxLayout, QWidget
from qfluentwidgets import TextEdit as QFluentTextEdit  # type: ignore[import-untyped]
from qfluentwidgets.common.smooth_scroll import (  # type: ignore[import-untyped]
    SmoothMode,
)

from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.shell import (
    sizing_controller as sizing_controller_module,
)
from substitute.presentation.editor.prompt_editor.shell import (
    scroll_delegate as scroll_delegate_module,
)
from substitute.presentation.editor.panel.widgets.scroll_surface import (
    EditorPanelScrollSurface,
)
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)
from tests.execution_test_helpers import immediate_prompt_task_executor_factory

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "real PromptEditor sizing tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def ensure_qapp() -> QApplication:
    """Return a running Qt application for prompt-editor widget tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def process_events(app: QApplication, cycles: int = 3) -> None:
    """Flush a few event-loop turns so widget geometry settles deterministically."""

    for _ in range(cycles):
        app.processEvents()


@pytest.fixture()
def prompt_editors() -> Iterator[list[PromptEditor]]:
    """Track prompt editors created during one test and dispose them safely afterward."""

    boxes: list[PromptEditor] = []
    yield boxes
    app = ensure_qapp()
    for box in boxes:
        box.close()
        box.deleteLater()
    process_events(app)


def show_prompt_editor(
    prompt_editors: list[PromptEditor], *, text: str, width: int
) -> PromptEditor:
    """Create, size, and show one prompt editor for sizing assertions."""

    app = ensure_qapp()
    box = PromptEditor(
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        prompt_syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    box.resize(width, 100)
    box.setPlainText(text)
    box.show()
    process_events(app)
    prompt_editors.append(box)
    return box


def test_shell_geometry_sync_ignores_deleted_qt_wrappers(
    monkeypatch: pytest.MonkeyPatch,
    prompt_editors: list[PromptEditor],
) -> None:
    """Queued geometry sync should no-op after its editor C++ object is gone."""

    box = show_prompt_editor(prompt_editors, text="prompt", width=320)
    editor = cast(Any, box)
    scroll_delegate = cast(Any, editor._scroll_delegate)
    scroll_delegate.geometry_sync_pending = True
    scroll_delegate.geometry_follow_up_pending = True
    monkeypatch.setattr(
        scroll_delegate_module,
        "qt_object_is_alive",
        lambda _obj: False,
    )

    editor._scroll_delegate.sync_shell_geometry()

    assert scroll_delegate.geometry_sync_pending is False
    assert scroll_delegate.geometry_follow_up_pending is False


def test_manual_height_reapply_ignores_deleted_qt_wrappers(
    monkeypatch: pytest.MonkeyPatch,
    prompt_editors: list[PromptEditor],
) -> None:
    """Queued manual-height layout work should no-op after its editor is gone."""

    box = show_prompt_editor(prompt_editors, text="prompt", width=320)
    editor = cast(Any, box)
    sizing = cast(Any, editor._sizing)
    sizing._manual_height_layout_reapply_pending = True
    sizing._manual_scroll_height = box.height()
    monkeypatch.setattr(
        sizing_controller_module,
        "qt_object_is_alive",
        lambda _obj: False,
    )

    editor._sizing.reapply_manual_height_for_current_layout()

    assert sizing._manual_height_layout_reapply_pending is False
    assert sizing._manual_scroll_height == box.height()


def height_padding(box: PromptEditor) -> int:
    """Return the current prompt-editor height padding above its document height."""

    return box.minimumEditorHeight() - box.lineHeight()


def default_scroll_height(box: PromptEditor) -> int:
    """Return the default prompt-editor scroll-mode height."""

    return box.lineHeight() * 10 + height_padding(box)


def resize_handle_for(box: PromptEditor) -> QWidget:
    """Return the prompt editor's private resize handle for contract tests."""

    return cast(QWidget, getattr(box, "_resize_handle"))


def set_manual_scroll_height(box: PromptEditor, height: int) -> None:
    """Set the prompt editor's private manual scroll height for contract tests."""

    setter = cast(Any, getattr(box, "setManualScrollHeight"))
    setter(height)


def fill_plane_for(box: PromptEditor) -> QWidget:
    """Return the prompt editor's private fill plane."""

    return cast(QWidget, getattr(box, "_fill_plane"))


def delay_projection_update_scheduler(box: PromptEditor) -> None:
    """Keep safe-typing projection updates pending until a test flushes them."""

    surface = cast(Any, getattr(box, "_surface"))
    scheduler = surface._projection_freshness_controller.update_scheduler  # noqa: SLF001
    scheduler._fixed_interval_ms = 1000  # noqa: SLF001
    scheduler._interval_ms = 1000  # noqa: SLF001
    scheduler._timer.setInterval(1000)  # noqa: SLF001


def flush_projection_update_scheduler(box: PromptEditor) -> None:
    """Apply any delayed safe-typing projection update before test cleanup."""

    surface = cast(Any, getattr(box, "_surface"))
    surface._projection_freshness_controller.update_scheduler.flush_now(reason="test")  # noqa: SLF001


def flush_semantic_refresh(box: PromptEditor) -> None:
    """Apply queued semantic prompt state before projection scheduling assertions."""

    cast(Any, box)._interaction_controller.flush_pending_semantic_refresh(  # noqa: SLF001
        reason="test"
    )


def widget_has_ancestor(widget: QWidget, ancestor: QWidget) -> bool:
    """Return whether one widget is parented under another widget."""

    parent = widget.parentWidget()
    while parent is not None:
        if parent is ancestor:
            return True
        parent = parent.parentWidget()
    return False


class ManualResizeScrollHost(QWidget):
    """Host an editor scroll surface with the panel API PromptEditor discovers."""

    def __init__(self) -> None:
        """Create the scroll host expected by prompt-editor resize bounds."""

        super().__init__()
        self.scroll_surface = EditorPanelScrollSurface(self)
        setattr(self, "scroll", self.scroll_surface)

    def handle_external_wheel(self, event: QWheelEvent) -> None:
        """Accept bubbled wheel events in tests without changing scroll state."""

        event.ignore()


def test_prompt_editor_recomputes_height_when_width_increases_without_typing(
    prompt_editors: list[PromptEditor],
) -> None:
    """Widening the editor should shrink wrapped prompt height without needing input."""

    app = ensure_qapp()
    box = show_prompt_editor(
        prompt_editors,
        text=(
            "landscape photography, cinematic lighting, hyper detailed, dramatic "
            "sky, volumetric fog, sharp focus, 35mm film, subtle grain"
        ),
        width=180,
    )
    tall_height = box.height()

    box.resize(600, box.height())
    process_events(app)

    assert box.height() < tall_height
    assert box.scrollDelegate.vScrollBar.isVisible() is False


def test_prompt_editor_shell_geometry_waits_for_pending_projection_height(
    monkeypatch: pytest.MonkeyPatch,
    prompt_editors: list[PromptEditor],
) -> None:
    """Host geometry sync should not consume stale prompt height during safe typing."""

    box = show_prompt_editor(prompt_editors, text="(cat:1.05), ", width=240)
    delay_projection_update_scheduler(box)
    cursor = box.textCursor()
    cursor.setPosition(len(box.toPlainText()))
    box.setTextCursor(cursor)

    QTest.keyClicks(box, "x")
    flush_semantic_refresh(box)

    surface = cast(Any, getattr(box, "_surface"))
    assert surface.has_pending_projection_update() is True
    applied_heights: list[float] = []
    monkeypatch.setattr(
        cast(Any, box)._scroll_delegate,
        "_handle_content_height_changed",
        lambda content_height: applied_heights.append(float(content_height)),
    )

    cast(Any, box)._scroll_delegate.sync_shell_geometry()

    assert applied_heights == []
    assert surface.has_pending_projection_update() is True
    flush_projection_update_scheduler(box)


def test_prompt_editor_same_line_backspace_does_not_commit_height(
    monkeypatch: pytest.MonkeyPatch,
    prompt_editors: list[PromptEditor],
) -> None:
    """Plain same-line backspace should not publish a public height change."""

    app = ensure_qapp()
    box = show_prompt_editor(prompt_editors, text="alpha beta", width=600)
    delay_projection_update_scheduler(box)
    process_events(app, cycles=10)
    cursor = box.textCursor()
    cursor.setPosition(len(box.toPlainText()))
    box.setTextCursor(cursor)
    initial_height = box.height()
    applied_heights: list[int] = []
    sizing = cast(Any, getattr(box, "_sizing"))
    apply_preferred_height = cast(
        Callable[[int], None],
        getattr(sizing, "apply_preferred_height"),
    )

    def record_height(preferred_height: int) -> None:
        """Record visible height commits while preserving production behavior."""

        applied_heights.append(preferred_height)
        apply_preferred_height(preferred_height)

    monkeypatch.setattr(sizing, "apply_preferred_height", record_height)

    QTest.keyClick(box, Qt.Key.Key_Backspace)
    process_events(app, cycles=4)

    assert box.toPlainText() == "alpha bet"
    assert box.height() == initial_height
    assert applied_heights == []

    flush_projection_update_scheduler(box)
    process_events(app, cycles=8)

    assert box.height() == initial_height
    assert applied_heights == []


def test_prompt_editor_line_break_backspace_height_commit_is_single(
    monkeypatch: pytest.MonkeyPatch,
    prompt_editors: list[PromptEditor],
) -> None:
    """Deleting a hard line break should settle through one public height change."""

    app = ensure_qapp()
    box = show_prompt_editor(prompt_editors, text="alpha\nbeta", width=600)
    process_events(app, cycles=10)
    cursor = box.textCursor()
    cursor.setPosition(len("alpha\n"))
    box.setTextCursor(cursor)
    initial_height = box.height()
    applied_heights: list[int] = []
    sizing = cast(Any, getattr(box, "_sizing"))
    apply_preferred_height = cast(
        Callable[[int], None],
        getattr(sizing, "apply_preferred_height"),
    )

    def record_height(preferred_height: int) -> None:
        """Record visible height commits while preserving production behavior."""

        applied_heights.append(preferred_height)
        apply_preferred_height(preferred_height)

    monkeypatch.setattr(sizing, "apply_preferred_height", record_height)

    QTest.keyClick(box, Qt.Key.Key_Backspace)
    process_events(app, cycles=8)

    assert box.toPlainText() == "alphabeta"
    assert box.height() < initial_height
    assert applied_heights == [box.height()]


def test_prompt_editor_reports_live_height_in_size_hints(
    prompt_editors: list[PromptEditor],
) -> None:
    """Size hints should match the current fixed editor height used by layouts."""

    box = show_prompt_editor(prompt_editors, text="short prompt", width=600)

    assert box.sizeHint().height() == box.height()
    assert box.minimumSizeHint().height() == box.height()


def test_prompt_editor_empty_value_uses_single_line_height_without_scrollbar(
    prompt_editors: list[PromptEditor],
) -> None:
    """Empty prompts should render as a single visible line without scrollbars."""

    box = show_prompt_editor(prompt_editors, text="", width=600)

    assert box.height() == box.minimumEditorHeight()
    assert box.scrollDelegate.vScrollBar.isVisible() is False


def test_prompt_editor_one_line_shell_metrics_match_qfluent_reference(
    prompt_editors: list[PromptEditor],
) -> None:
    """Prompt editors should preserve QFluent host text metrics and padding."""

    app = ensure_qapp()
    box = show_prompt_editor(prompt_editors, text="alpha", width=600)
    reference = QFluentTextEdit()
    reference.resize(box.width(), box.height())
    reference.setPlainText("alpha")
    reference.show()
    process_events(app)

    assert box.contentsMargins().left() == reference.contentsMargins().left()
    assert box.contentsMargins().right() == reference.contentsMargins().right()
    assert box.document().documentMargin() == reference.document().documentMargin()
    assert box.lineHeight() == reference.fontMetrics().lineSpacing()
    assert box.lineHeight() == int(
        cast(Any, box)._surface._layout.metrics.text_line_height  # noqa: SLF001
    )
    assert box.viewport().width() == reference.viewport().width()
    assert box.viewport().height() == reference.viewport().height()
    assert (
        box.verticalScrollBar().singleStep()
        == reference.verticalScrollBar().singleStep()
    )

    reference.close()
    reference.deleteLater()
    process_events(app)


def test_prompt_editor_caps_height_at_ten_lines_and_enables_scrollbar(
    prompt_editors: list[PromptEditor],
) -> None:
    """Prompt editors should stop growing after ten visible lines."""

    box = show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(20)),
        width=600,
    )

    assert box.height() == box.lineHeight() * 10 + height_padding(box)
    assert box.scrollDelegate.vScrollBar.isVisible() is True


def test_prompt_editor_fill_plane_preserves_qfluent_shell_geometry(
    prompt_editors: list[PromptEditor],
) -> None:
    """Prompt fill effects should not alter QFluent shell metrics."""

    box = show_prompt_editor(
        prompt_editors,
        text="**one\nwide shot\n**two\nclose portrait",
        width=600,
    )
    layer = fill_plane_for(box)
    projection_rect = cast(Any, layer)._projection_viewport_rect()
    clip_region = cast(Any, layer).fill_clip_region()
    left_padding_point = QPoint(
        max(1, projection_rect.left() - 1),
        projection_rect.top() + box.lineHeight(),
    )

    assert layer.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) is True
    assert layer.focusPolicy() == Qt.FocusPolicy.NoFocus
    shell_viewport = cast(Callable[[], QWidget], getattr(box, "_shell_viewport"))

    assert layer.geometry() == shell_viewport().rect()
    assert clip_region.contains(left_padding_point) is True
    assert clip_region.contains(projection_rect.center()) is True


def test_prompt_editor_fill_plane_maps_sibling_widgets_without_qt_warning(
    prompt_editors: list[PromptEditor],
) -> None:
    """Prompt fill geometry should not call QWidget.mapTo across sibling widgets."""

    box = show_prompt_editor(
        prompt_editors,
        text="**one\nwide shot\n**two\nclose portrait",
        width=600,
    )
    layer = fill_plane_for(box)
    surface = cast(Any, getattr(box, "_surface"))
    projection_viewport = cast(QWidget, surface.viewport())
    messages: list[str] = []

    assert widget_has_ancestor(projection_viewport, layer) is False
    expected_top_left = layer.mapFromGlobal(
        projection_viewport.mapToGlobal(QPoint(0, 0))
    )

    previous_handler = qInstallMessageHandler(
        lambda _mode, _context, message: messages.append(message)
    )
    try:
        projection_rect = cast(Any, layer)._projection_viewport_rect()
        cast(Any, layer).mapped_prompt_fill_band_rects()
        cast(Any, layer).fill_clip_region()
    finally:
        qInstallMessageHandler(previous_handler)

    assert projection_rect.topLeft() == expected_top_left
    assert not any(
        "parent must be in parent hierarchy" in message for message in messages
    )


def test_prompt_editor_shows_resize_handle_only_in_scroll_mode(
    prompt_editors: list[PromptEditor],
) -> None:
    """Only scrollable prompt editors should expose manual viewport resizing."""

    short_box = show_prompt_editor(prompt_editors, text="short prompt", width=600)
    long_box = show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(20)),
        width=600,
    )

    assert resize_handle_for(short_box).isVisible() is False
    assert resize_handle_for(long_box).isVisible() is True


def test_prompt_editor_manual_scroll_height_updates_size_and_scroll_metrics(
    prompt_editors: list[PromptEditor],
) -> None:
    """Manual scroll height should resize the shell and refresh scroll metrics."""

    app = ensure_qapp()
    box = show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(40)),
        width=600,
    )
    original_height = box.height()
    original_page_step = box.verticalScrollBar().pageStep()
    target_height = original_height + box.lineHeight() * 3

    set_manual_scroll_height(box, target_height)
    process_events(app)

    assert box.height() == target_height
    assert box.sizeHint().height() == target_height
    assert box.minimumSizeHint().height() == target_height
    assert box.verticalScrollBar().pageStep() > original_page_step
    assert box.verticalScrollBar().maximum() >= 0
    assert resize_handle_for(box).isVisible() is True


def test_prompt_editor_public_manual_scroll_height_api_reports_stored_height(
    prompt_editors: list[PromptEditor],
) -> None:
    """Public manual height API should expose the stored user-owned cap."""

    app = ensure_qapp()
    box = show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(40)),
        width=600,
    )
    target_height = box.height() + box.lineHeight() * 2

    box.setManualScrollHeight(target_height)
    process_events(app)

    assert box.manualScrollHeight() == target_height
    assert box.height() == target_height


def test_prompt_editor_manual_scroll_height_signal_emits_only_for_stored_changes(
    prompt_editors: list[PromptEditor],
) -> None:
    """Manual height signal should ignore duplicate clamps and emit clear events."""

    app = ensure_qapp()
    box = show_prompt_editor(
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
    process_events(app)

    assert changes == [target_height, None]
    assert box.manualScrollHeight() is None


def test_prompt_editor_automatic_resize_does_not_emit_manual_height_change(
    prompt_editors: list[PromptEditor],
) -> None:
    """Width-driven automatic reflow should not look like user manual resizing."""

    app = ensure_qapp()
    box = show_prompt_editor(
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
    process_events(app)

    assert changes == []
    assert box.manualScrollHeight() is None


def test_prompt_editor_resize_handle_drag_does_not_move_text_cursor(
    prompt_editors: list[PromptEditor],
) -> None:
    """The resize affordance should capture mouse drags outside text editing."""

    app = ensure_qapp()
    box = show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(40)),
        width=600,
    )
    cursor = box.textCursor()
    cursor.setPosition(5)
    box.setTextCursor(cursor)
    initial_height = box.height()
    handle = resize_handle_for(box)
    start_position = handle.rect().center()

    QTest.mousePress(handle, Qt.MouseButton.LeftButton, pos=start_position)
    QTest.mouseMove(
        handle,
        QPoint(start_position.x(), start_position.y() + box.lineHeight() * 2),
    )
    QTest.mouseRelease(
        handle,
        Qt.MouseButton.LeftButton,
        pos=QPoint(start_position.x(), start_position.y() + box.lineHeight() * 2),
    )
    process_events(app)

    assert box.height() > initial_height
    assert box.textCursor().position() == 5


def test_prompt_editor_manual_scroll_height_is_bounded(
    prompt_editors: list[PromptEditor],
) -> None:
    """Visible manual height should stay inside current prompt layout bounds."""

    app = ensure_qapp()
    box = show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(80)),
        width=600,
    )
    minimum_height = default_scroll_height(box)

    set_manual_scroll_height(box, minimum_height - box.lineHeight() * 4)
    process_events(app)
    assert box.manualScrollHeight() == minimum_height
    assert box.height() == minimum_height

    set_manual_scroll_height(box, minimum_height * 6)
    process_events(app)
    assert box.manualScrollHeight() == minimum_height * 6
    assert box.height() == minimum_height * 2


def test_prompt_editor_can_shrink_after_expanding_to_fit_content(
    prompt_editors: list[PromptEditor],
) -> None:
    """A fully expanded prompt should keep the handle available for shrinking."""

    app = ensure_qapp()
    box = show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(14)),
        width=600,
    )
    minimum_height = default_scroll_height(box)

    set_manual_scroll_height(box, minimum_height * 6)
    process_events(app)

    assert box.height() > minimum_height
    assert box.scrollDelegate.vScrollBar.isVisible() is False
    assert resize_handle_for(box).isVisible() is True

    set_manual_scroll_height(box, minimum_height)
    process_events(app)

    assert box.height() == minimum_height
    assert box.scrollDelegate.vScrollBar.isVisible() is True
    assert resize_handle_for(box).isVisible() is True


def test_prompt_editor_manual_height_does_not_expand_beyond_content_height(
    prompt_editors: list[PromptEditor],
) -> None:
    """Manual mode should keep visible height inside normal content bounds."""

    app = ensure_qapp()
    original_text = "\n".join(f"line {index}" for index in range(14))
    box = show_prompt_editor(prompt_editors, text=original_text, width=600)
    minimum_height = default_scroll_height(box)

    set_manual_scroll_height(box, minimum_height * 6)
    process_events(app)
    expanded_height = box.height()

    box.setPlainText(f"{original_text}\nnew line")
    process_events(app)

    assert box.manualScrollHeight() == minimum_height * 6
    sizing = cast(Any, getattr(box, "_sizing"))
    assert box.height() == cast(int, sizing.last_natural_height)
    assert box.height() > expanded_height
    manual_height = box.manualScrollHeight()
    assert manual_height is not None
    assert box.height() < manual_height
    assert box.scrollDelegate.vScrollBar.isVisible() is False
    assert resize_handle_for(box).isVisible() is True


def test_prompt_editor_shorter_content_collapses_below_manual_scroll_height(
    prompt_editors: list[PromptEditor],
) -> None:
    """Short content should auto-fit while retaining latent manual preference."""

    app = ensure_qapp()
    box = show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(40)),
        width=600,
    )
    manual_height = box.height() + box.lineHeight() * 3
    set_manual_scroll_height(box, manual_height)
    process_events(app)

    box.setPlainText("short prompt")
    process_events(app)

    assert box.manualScrollHeight() == manual_height
    assert box.height() == box.minimumEditorHeight()
    assert box.scrollDelegate.vScrollBar.isVisible() is False
    assert resize_handle_for(box).isVisible() is False


def test_prompt_editor_manual_height_catches_up_when_layout_bounds_expand(
    prompt_editors: list[PromptEditor],
) -> None:
    """A restored manual preference should survive a temporary startup clamp."""

    app = ensure_qapp()
    host = ManualResizeScrollHost()
    scroll_area = host.scroll_surface
    content = QWidget()
    layout = QVBoxLayout(content)
    box = PromptEditor(
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        prompt_syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    prompt_editors.append(box)
    box.setPlainText("\n".join(f"line {index}" for index in range(120)))
    layout.addWidget(box)
    scroll_area.setWidgetResizable(True)
    scroll_area.setWidget(content)
    constrained_height = default_scroll_height(box) + box.lineHeight()
    scroll_area.resize(360, constrained_height)
    host.resize(360, constrained_height)
    scroll_area.setGeometry(host.rect())
    host.show()
    process_events(app, cycles=8)
    changes: list[object] = []
    box.manualScrollHeightChanged.connect(changes.append)
    restored_height = default_scroll_height(box) * 6

    set_manual_scroll_height(box, restored_height)
    process_events(app, cycles=8)
    constrained_box_height = box.height()
    host.resize(360, restored_height * 2)
    scroll_area.setGeometry(host.rect())
    process_events(app, cycles=12)

    assert box.manualScrollHeight() == restored_height
    assert constrained_box_height < restored_height
    assert box.height() == restored_height
    assert changes == [restored_height]

    host.close()
    host.deleteLater()
    process_events(app)


def test_prompt_editor_width_changes_keep_manual_scroll_preference(
    prompt_editors: list[PromptEditor],
) -> None:
    """Width-driven reflow should not discard the remembered manual scroll height."""

    app = ensure_qapp()
    box = show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(40)),
        width=600,
    )
    manual_height = box.height() + box.lineHeight() * 2
    set_manual_scroll_height(box, manual_height)
    process_events(app)

    box.resize(420, box.height())
    process_events(app)

    assert box.height() == manual_height
    assert resize_handle_for(box).isVisible() is True


def test_prompt_editor_manual_resize_refreshes_editor_panel_scroll_metrics(
    prompt_editors: list[PromptEditor],
) -> None:
    """Editor-panel scroll metrics should update after a prompt editor grows."""

    app = ensure_qapp()
    scroll_area = EditorPanelScrollSurface()
    content = QWidget()
    layout = QVBoxLayout(content)
    box = PromptEditor(
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        prompt_syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    box.setPlainText("\n".join(f"line {index}" for index in range(40)))
    layout.addWidget(box)
    scroll_area.setWidgetResizable(True)
    scroll_area.setWidget(content)
    scroll_area.resize(360, default_scroll_height(box) + box.lineHeight())
    scroll_area.show()
    process_events(app)
    refresh_count = 0

    def record_refresh() -> None:
        nonlocal refresh_count
        refresh_count += 1

    scroll_area.metrics_refreshed.connect(record_refresh)
    original_maximum = scroll_area.verticalScrollBar().maximum()

    set_manual_scroll_height(box, box.height() + box.lineHeight() * 4)
    process_events(app, cycles=8)

    assert refresh_count > 0
    assert scroll_area.verticalScrollBar().maximum() > original_maximum

    scroll_area.close()
    scroll_area.deleteLater()
    process_events(app)


def test_prompt_editor_disables_qfluent_smooth_scrolling(
    prompt_editors: list[PromptEditor],
) -> None:
    """Prompt editors should scroll immediately without QFluent wheel smoothing."""

    box = show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(20)),
        width=600,
    )
    scroll_delegate = box.scrollDelegate

    assert scroll_delegate.useAni is False
    assert scroll_delegate.verticalSmoothScroll.smoothMode is SmoothMode.NO_SMOOTH
    assert scroll_delegate.horizonSmoothScroll.smoothMode is SmoothMode.NO_SMOOTH
    assert scroll_delegate.vScrollBar.duration == 0
    assert scroll_delegate.hScrollBar.duration == 0


def test_prompt_editor_visible_scrollbar_tracks_editor_scrollbar_metrics(
    prompt_editors: list[PromptEditor],
) -> None:
    """The visible QFluent scrollbar should mirror the editor scroll owner metadata."""

    box = show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(20)),
        width=600,
    )
    editor_scrollbar = box.verticalScrollBar()
    visible_scrollbar = box.scrollDelegate.vScrollBar

    assert visible_scrollbar.pageStep() == editor_scrollbar.pageStep()
    assert visible_scrollbar.singleStep() == editor_scrollbar.singleStep()


def test_prompt_editor_scroll_keeps_projection_surface_pinned_in_shell_viewport(
    prompt_editors: list[PromptEditor],
) -> None:
    """Scrolling should move rendered content, not the projection surface widget itself."""

    app = ensure_qapp()
    box = show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(30)),
        width=320,
    )
    surface = getattr(box, "_surface")
    host_scrollbar = QFluentTextEdit.verticalScrollBar(box)
    editor_scrollbar = box.verticalScrollBar()

    editor_scrollbar.setValue(
        editor_scrollbar.singleStep() * QApplication.wheelScrollLines()
    )
    process_events(app)

    assert surface.pos().y() == 0
    assert host_scrollbar.value() == 0
    assert box.scrollDelegate.vScrollBar.value() == editor_scrollbar.value()


def test_prompt_editor_one_wheel_notch_uses_line_based_scroll_delta(
    prompt_editors: list[PromptEditor],
) -> None:
    """One mouse-wheel notch should match the Qt multiline text-edit scroll delta."""

    app = ensure_qapp()
    box = show_prompt_editor(
        prompt_editors,
        text="\n".join(f"line {index}" for index in range(30)),
        width=320,
    )
    reference = QTextEdit()
    reference.resize(box.width(), box.height())
    reference.setPlainText("\n".join(f"line {index}" for index in range(30)))
    reference.show()
    process_events(app)
    surface = getattr(box, "_surface")
    host_scrollbar = QFluentTextEdit.verticalScrollBar(box)
    scrollbar = box.verticalScrollBar()
    scrollbar.setValue(0)
    reference.verticalScrollBar().setValue(0)
    process_events(app)
    wheel_event = QWheelEvent(
        QPointF(box.viewport().rect().center()),
        QPointF(box.viewport().mapToGlobal(box.viewport().rect().center())),
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    reference_wheel_event = QWheelEvent(
        QPointF(reference.viewport().rect().center()),
        QPointF(reference.viewport().mapToGlobal(reference.viewport().rect().center())),
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )

    QApplication.sendEvent(reference.viewport(), reference_wheel_event)
    QApplication.sendEvent(box.viewport(), wheel_event)
    process_events(app)

    assert scrollbar.value() == reference.verticalScrollBar().value()
    assert surface.pos().y() == 0
    assert host_scrollbar.value() == 0

    reference.close()
    reference.deleteLater()
    process_events(app)


def test_prompt_editor_keeps_projection_surface_pinned_after_viewport_resize_event(
    prompt_editors: list[PromptEditor],
) -> None:
    """Projection viewport resize events should re-pin the surface to shell geometry."""

    app = ensure_qapp()
    box = PromptEditor(
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        prompt_syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
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
    shell_viewport = cast(Callable[[], QWidget], getattr(box, "_shell_viewport"))
    shell_width = shell_viewport().width()

    projection_viewport.resize(638, projection_viewport.height())
    process_events(app)

    assert projection_viewport.width() > initial_viewport_width + 200
    assert surface.width() == shell_width
    assert box.scrollDelegate.vScrollBar.isVisible() is False


def test_prompt_editor_preserves_baseline_text_edit_commands(
    prompt_editors: list[PromptEditor],
) -> None:
    """Copy, paste, undo, redo, and selection changes should stay text-edit native."""

    app = ensure_qapp()
    box = show_prompt_editor(prompt_editors, text="alpha", width=320)
    clipboard = QApplication.clipboard()
    clipboard.setText("")

    cursor = box.textCursor()
    cursor.setPosition(0, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)

    assert box.textCursor().selectionStart() == 0
    assert box.textCursor().selectionEnd() == 5

    box.copy()
    process_events(app)
    assert clipboard.text() == "alpha"

    clipboard.setText("beta")
    box.paste()
    process_events(app)

    assert box.toPlainText() == "beta"

    box.undo()
    process_events(app)

    assert box.toPlainText() == "alpha"

    box.redo()
    process_events(app)

    assert box.toPlainText() == "beta"

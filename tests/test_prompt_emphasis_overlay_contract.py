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

"""Contract tests for projection-engine emphasis controls and token behavior."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QTextCursor, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptTokenWeightControls,
)
from tests.prompt_projection_test_helpers import (
    emphasis_controls_for,
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)
from tests.execution_test_helpers import immediate_prompt_task_executor_factory

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "real prompt emphasis control tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


@pytest.fixture()
def widgets() -> Iterator[list[QWidget]]:
    """Track widgets created during one projection emphasis contract test."""

    created: list[QWidget] = []
    yield created
    app = ensure_qapp()
    for widget in reversed(created):
        widget.close()
        widget.deleteLater()
    process_events(app)


def set_cursor_position(box: PromptEditor, position: int) -> None:
    """Move the prompt-editor caret to one raw source position."""

    app = ensure_qapp()
    cursor = box.textCursor()
    cursor.setPosition(position, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    process_events(app)


def emphasis_token_for(
    box: PromptEditor,
    *,
    index: int = 0,
) -> PromptProjectionToken:
    """Return one collapsed emphasis token from the live projection document."""

    surface = surface_for(box)
    tokens = [
        _effective_token_for_paint(surface, token)
        for token in surface.projection_document().tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    ]
    assert len(tokens) > index
    return tokens[index]


def lora_token_for(
    box: PromptEditor,
    *,
    index: int = 0,
) -> PromptProjectionToken:
    """Return one collapsed LoRA token from the live projection document."""

    surface = surface_for(box)
    tokens = [
        _effective_token_for_paint(surface, token)
        for token in surface.projection_document().tokens
        if token.kind is PromptProjectionTokenKind.LORA
    ]
    assert len(tokens) > index
    return tokens[index]


def _effective_token_for_paint(
    surface: object,
    token: PromptProjectionToken,
) -> PromptProjectionToken:
    """Return the token with geometry-neutral paint state applied."""

    layout = cast(Any, surface)._layout
    return cast(
        PromptProjectionToken,
        layout.effective_token_for_paint(token.token_id) or token,
    )


def show_lora_prompt_editor(
    widgets: list[QWidget],
    *,
    text: str,
    width: int,
    height: int = 340,
) -> PromptEditor:
    """Create, show, and populate one prompt editor with LoRA syntax enabled."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(max(240, width + 48), height)
    box = PromptEditor(
        host,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        prompt_syntax_profile=prompt_syntax_profile("emphasis", "wildcard", "lora"),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    box.setGeometry(20, 20, width, box.minimumEditorHeight())
    host.show()
    host.activateWindow()
    box.show()
    box.setFocus()
    box.setPlainText(text)
    process_events(app)
    widgets.extend([host, box])
    return box


def token_rect_for(box: PromptEditor, token: PromptProjectionToken) -> QRectF:
    """Return the viewport-local rect occupied by one collapsed projection token."""

    token_rect = surface_for(box)._layout.token_rect(  # noqa: SLF001
        token,
        scroll_offset=float(box.verticalScrollBar().value()),
    )
    assert token_rect is not None
    return token_rect


def anchor_rect_for(box: PromptEditor, token: PromptProjectionToken) -> QRectF:
    """Return the viewport-local anchor rect used by one emphasis token."""

    anchor_rect = surface_for(box).token_anchor_rect(token)
    assert anchor_rect is not None
    return anchor_rect


def weight_rect_for(box: PromptEditor, token: PromptProjectionToken) -> QRectF:
    """Return the viewport-local painted number rect used for exact weight editing."""

    weight_rect = surface_for(box).token_weight_text_rect(token)
    assert weight_rect is not None
    return weight_rect


def reveal_emphasis_controls(
    box: PromptEditor,
    token: PromptProjectionToken,
) -> PromptTokenWeightControls:
    """Reveal emphasis controls with a deterministic hover sequence."""

    app = ensure_qapp()
    controls = emphasis_controls_for(box)
    reset_point = QPoint(
        max(1, box.viewport().width() - 3), max(1, box.viewport().height() - 3)
    )
    QTest.mouseMove(box.viewport(), reset_point)
    process_events(app, cycles=3)
    QTest.mouseMove(box.viewport(), anchor_rect_for(box, token).center().toPoint())
    process_events(app, cycles=6)
    controls.refresh_geometry()
    process_events(app, cycles=6)
    return controls


def click_control_rect(overlay: QWidget, host_rect: QRectF) -> None:
    """Click the center of one host-local control rect."""

    app = ensure_qapp()
    local_point = overlay.mapFromParent(host_rect.center().toPoint())
    QTest.mouseClick(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        local_point,
    )
    process_events(app)


def start_exact_weight_edit(
    box: PromptEditor,
    token: PromptProjectionToken,
) -> PromptTokenWeightControls:
    """Start exact weight editing by double clicking the painted number only."""

    app = ensure_qapp()
    controls = emphasis_controls_for(box)
    if (
        controls.visible_token is not None
        and controls.visible_token.token_id == token.token_id
        and controls._weight_hit_rect is not None  # noqa: SLF001
    ):
        weight_point = controls.mapFromParent(
            controls._weight_hit_rect.center().toPoint()  # noqa: SLF001
        )
        click_target: QWidget = controls
    else:
        weight_point = weight_rect_for(box, token).center().toPoint()
        click_target = box.viewport()
    QTest.mouseClick(click_target, Qt.MouseButton.LeftButton, pos=weight_point)
    process_events(app, cycles=2)
    QTest.mouseClick(click_target, Qt.MouseButton.LeftButton, pos=weight_point)
    process_events(app, cycles=4)
    return controls


def exact_weight_edit_token(box: PromptEditor) -> PromptProjectionToken | None:
    """Return the projection-owned token currently carrying exact edit state."""

    return surface_for(box).exact_weight_edit_token()


def wheel_widget_at_point(
    widget: QWidget,
    *,
    local_point: QPoint,
    angle_delta_y: int,
) -> bool:
    """Send one wheel event to the supplied widget-local position."""

    app = ensure_qapp()
    global_point = widget.mapToGlobal(local_point)
    wheel_event = QWheelEvent(
        QPointF(local_point),
        QPointF(global_point),
        QPoint(0, 0),
        QPoint(0, angle_delta_y),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    QApplication.sendEvent(widget, wheel_event)
    process_events(app)
    return wheel_event.isAccepted()


def point_outside_token(box: PromptEditor, token: PromptProjectionToken) -> QPoint:
    """Return a same-row viewport point safely outside one rendered token."""

    token_rect = token_rect_for(box, token)
    return QPoint(
        min(box.viewport().width() - 4, int(token_rect.right()) + 80),
        int(token_rect.center().y()),
    )


def shell_viewport_for(box: PromptEditor) -> QWidget:
    """Return the outer prompt viewport that can receive first wheel events."""

    return cast(QWidget, getattr(box, "_shell_viewport")())


def _visible_triangle_edge(rect: QRectF, *, direction: str) -> float:
    """Return the edge of the painted triangle nearest the emphasis number."""

    vertical_inset = max(2.0, rect.height() * 0.30)
    if direction == "up":
        return rect.bottom() - vertical_inset
    return rect.top() + vertical_inset


def test_prompt_editor_emphasis_controls_follow_caret_active_token(
    widgets: list[QWidget],
) -> None:
    """Hovering the weight label should expose controls anchored from that number."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), middle, (dog:1.15)",
        width=260,
    )
    controls = emphasis_controls_for(box)

    set_cursor_position(box, 2)
    token = emphasis_token_for(box)
    anchor_rect = anchor_rect_for(box, token)
    token_rect = token_rect_for(box, token)
    parent = controls.parentWidget()

    assert controls.visible_token is None

    reveal_emphasis_controls(box, token)

    assert controls.visible_token is not None
    assert controls.visible_token.token_id == token.token_id
    assert emphasis_token_for(box).decoration_accented is True
    assert controls.increase_rect is not None
    assert controls.decrease_rect is not None
    assert parent is not None
    host_anchor_rect = QRectF(
        parent.mapFromGlobal(
            box.viewport().mapToGlobal(anchor_rect.topLeft().toPoint())
        ),
        anchor_rect.size(),
    )
    host_anchor_center = parent.mapFromGlobal(
        box.viewport().mapToGlobal(anchor_rect.center().toPoint())
    )
    host_token_rect = QRectF(
        parent.mapFromGlobal(
            box.viewport().mapToGlobal(token_rect.topLeft().toPoint())
        ),
        token_rect.size(),
    )

    assert controls.increase_rect.center().x() == pytest.approx(
        host_anchor_center.x(),
        abs=6.0,
    )
    assert host_anchor_center.y() < host_token_rect.bottom()
    assert _visible_triangle_edge(
        controls.increase_rect, direction="up"
    ) == pytest.approx(
        host_anchor_rect.top() - 0.5,
        abs=1.0,
    )
    assert _visible_triangle_edge(
        controls.decrease_rect,
        direction="down",
    ) == pytest.approx(
        host_anchor_rect.bottom() + 0.5,
        abs=1.0,
    )
    assert controls.increase_rect.bottom() <= controls.decrease_rect.top()


def test_prompt_editor_emphasis_controls_can_render_above_top_row_without_clipping(
    widgets: list[QWidget],
) -> None:
    """Top-row emphasis controls should escape the viewport clip and stay on-screen."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    controls = emphasis_controls_for(box)

    set_cursor_position(box, 2)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)

    assert controls.parentWidget() is box.window()
    assert controls.increase_rect is not None
    assert controls.increase_rect.top() < box.geometry().top()
    assert controls.increase_rect.top() >= 0


def test_prompt_editor_emphasis_controls_stay_hidden_until_number_hover(
    widgets: list[QWidget],
) -> None:
    """Caret focus alone should not show controls until the pointer reaches the number."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), middle",
        width=220,
    )
    controls = emphasis_controls_for(box)

    set_cursor_position(box, 2)

    assert controls.visible_token is None
    assert controls.isVisible() is False
    assert emphasis_token_for(box).decoration_accented is False


def test_idle_typing_does_not_prepare_token_weight_geometry(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep dormant control geometry out of the synchronous typing path."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text=", ".join(f"(decorated token {index}:1.10)" for index in range(80)),
        width=260,
    )
    controls = emphasis_controls_for(box)
    geometry_builds = 0
    original_build_snapshot = controls._geometry.build_snapshot  # noqa: SLF001

    def record_geometry_build() -> object:
        """Record an otherwise production-owned geometry snapshot build."""

        nonlocal geometry_builds
        geometry_builds += 1
        return original_build_snapshot()

    monkeypatch.setattr(
        controls._geometry,  # noqa: SLF001
        "build_snapshot",
        record_geometry_build,
    )
    original_text = box.toPlainText()
    box.setFocus()
    QTest.keyClicks(box, "key slam")
    process_events(app)

    assert box.toPlainText().endswith("key slam")
    assert box.toPlainText() == original_text + "key slam"
    assert controls.visible_token is None
    assert geometry_builds == 0


def test_prompt_editor_emphasis_controls_hover_updates_without_breaking_typing_flow(
    widgets: list[QWidget],
) -> None:
    """Hover should reveal controls while the prompt editor remains directly editable."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="prefix, (alpha beta gamma:1.10)",
        width=220,
    )
    controls = emphasis_controls_for(box)
    token = emphasis_token_for(box)
    hover_point = anchor_rect_for(box, token).center().toPoint()
    original_text = box.toPlainText()

    assert controls.visible_token is None

    QTest.mouseMove(
        box.viewport(),
        QPoint(max(1, box.viewport().width() - 3), max(1, box.viewport().height() - 3)),
    )
    process_events(app, cycles=3)
    QTest.mouseMove(box.viewport(), hover_point)
    process_events(app, cycles=6)
    controls.refresh_geometry()
    process_events(app, cycles=6)

    hovered_token = surface_for(box).hovered_token()
    assert hovered_token is not None
    assert hovered_token.token_id == token.token_id
    assert hovered_token.decoration_accented is True
    assert controls.visible_token is not None
    assert controls.visible_token.token_id == token.token_id
    assert box.hasFocus() is True

    QTest.keyClicks(box, "!")
    process_events(app)

    assert box.toPlainText() != original_text
    QApplication.sendEvent(box.viewport(), QEvent(QEvent.Type.Leave))
    process_events(app)

    assert surface_for(box).hovered_token() is None


def test_prompt_editor_emphasis_controls_remain_stable_while_pointer_moves_into_arrow(
    widgets: list[QWidget],
) -> None:
    """Moving from the number into one arrow should not collapse the controls."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    controls = emphasis_controls_for(box)
    set_cursor_position(box, 2)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)

    assert controls.increase_rect is not None
    QTest.mouseMove(
        controls,
        controls.mapFromParent(controls.increase_rect.center().toPoint()),
    )
    process_events(app)

    assert controls.visible_token is not None
    assert controls.visible_token.token_id == token.token_id
    assert controls.isVisible() is True


def test_prompt_editor_emphasis_controls_hide_after_pointer_leaves_activation_zone(
    widgets: list[QWidget],
) -> None:
    """Controls should linger briefly, then hide after the pointer leaves the activation zone."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="prefix, (cat:1.05)",
        width=220,
    )
    controls = emphasis_controls_for(box)

    set_cursor_position(box, 2)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)

    assert controls.visible_token is not None
    assert controls.visible_token.token_id == token.token_id
    QTest.mouseMove(box.viewport(), QPoint(2, 2))
    process_events(app)

    assert controls.visible_token is not None
    assert controls.visible_token.token_id == token.token_id
    QTest.qWait(220)
    process_events(app)

    assert controls.visible_token is None
    assert controls.isVisible() is False
    assert emphasis_token_for(box).decoration_accented is False


def test_prompt_editor_emphasis_controls_recompute_geometry_on_resize(
    widgets: list[QWidget],
) -> None:
    """Resizing the prompt editor should rebuild token anchor and control geometry."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(alpha beta gamma delta epsilon zeta:1.10)",
        width=260,
    )
    controls = emphasis_controls_for(box)

    set_cursor_position(box, 4)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    before_resize = controls.increase_rect

    box.resize(140, box.height())
    process_events(app)

    assert controls.increase_rect is not None
    assert controls.increase_rect != before_resize


def test_prompt_editor_emphasis_controls_track_viewport_scroll_geometry(
    widgets: list[QWidget],
) -> None:
    """Scrolling should move visible emphasis controls with the projection layout."""

    app = ensure_qapp()
    lines = [f"line {index}" for index in range(12)]
    lines[5] = "(scroll target words here:1.10)"
    box = show_prompt_editor(
        widgets,
        text="\n".join(lines),
        width=220,
    )
    controls = emphasis_controls_for(box)
    scrollbar = box.verticalScrollBar()

    set_cursor_position(box, box.toPlainText().index("target"))
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    before_scroll = controls.increase_rect
    assert scrollbar.maximum() > 0

    scrollbar.setValue(scrollbar.singleStep() * 2 or 32)
    process_events(app)

    assert controls.increase_rect is not None
    assert controls.increase_rect != before_scroll


def test_inline_increase_click_updates_prompt_text_without_selecting_emphasis_content(
    widgets: list[QWidget],
) -> None:
    """Clicking the visible up control should mutate text without leaving selection highlight."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    controls = emphasis_controls_for(box)

    set_cursor_position(box, 2)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.increase_rect is not None

    click_control_rect(controls, controls.increase_rect)

    cursor = box.textCursor()
    assert box.toPlainText() == "(cat:1.10)"
    assert box.hasFocus() is True
    assert cursor.selectionStart() == 2
    assert cursor.selectionEnd() == 2
    assert controls.visible_token is not None
    assert controls.isVisible() is True
    assert controls.increase_rect is not None
    assert emphasis_token_for(box).decoration_accented is True
    assert controls._gestures.weight_preview_text == "1.10"  # noqa: SLF001
    assert controls._gestures.weight_preview_rect is not None  # noqa: SLF001
    assert (
        controls._gestures.weight_preview_rect.bottom()  # noqa: SLF001
        >= controls.increase_rect.center().y() - 6.0
    )


def test_inline_emphasis_clicks_keep_controls_visible_without_mouse_rehover(
    widgets: list[QWidget],
) -> None:
    """Successive arrow clicks should not require pointer movement to keep the controls alive."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    controls = emphasis_controls_for(box)

    set_cursor_position(box, 2)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.increase_rect is not None

    click_control_rect(controls, controls.increase_rect)
    process_events(ensure_qapp())
    assert box.toPlainText() == "(cat:1.10)"
    assert controls.visible_token is not None
    assert controls.isVisible() is True
    assert controls.increase_rect is not None

    click_control_rect(controls, controls.increase_rect)
    process_events(ensure_qapp())
    assert box.toPlainText() == "(cat:1.15)"
    assert controls.visible_token is not None
    assert controls.isVisible() is True
    assert controls.increase_rect is not None


def test_emphasis_controls_keep_a_stable_horizontal_anchor_while_values_change(
    widgets: list[QWidget],
) -> None:
    """Repeated emphasis adjustments should not shift the arrow stack horizontally."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    controls = emphasis_controls_for(box)

    set_cursor_position(box, 2)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.increase_rect is not None
    initial_center_x = controls.increase_rect.center().x()

    click_control_rect(controls, controls.increase_rect)
    process_events(ensure_qapp())
    assert controls.increase_rect is not None
    assert controls.increase_rect.center().x() == pytest.approx(initial_center_x)

    assert controls.decrease_rect is not None
    click_control_rect(controls, controls.decrease_rect)
    process_events(ensure_qapp())
    assert controls.increase_rect is not None
    assert controls.increase_rect.center().x() == pytest.approx(initial_center_x)


def test_double_clicking_the_painted_weight_number_starts_exact_edit_mode(
    widgets: list[QWidget],
) -> None:
    """Only the painted number should enter native-looking exact weight edit mode."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    token = emphasis_token_for(box)
    controls = start_exact_weight_edit(box, token)
    exact_edit_token = exact_weight_edit_token(box)

    assert exact_edit_token is not None
    assert exact_edit_token.editing_value_text == "1.05"
    assert exact_edit_token.editing_select_all is True
    assert controls.increase_rect is None
    assert controls.decrease_rect is None
    assert controls.isVisible() is False
    assert surface_for(box).projection_document().tokens != ()


def test_double_clicking_lora_weight_starts_exact_edit_mode(
    widgets: list[QWidget],
) -> None:
    """LoRA weight numbers should enter the same exact edit mode as emphasis."""

    box = show_lora_prompt_editor(
        widgets,
        text="<lora:Mineru:0.80>",
        width=240,
    )
    token = lora_token_for(box)
    controls = start_exact_weight_edit(box, token)
    exact_edit_token = exact_weight_edit_token(box)

    assert exact_edit_token is not None
    assert exact_edit_token.kind is PromptProjectionTokenKind.LORA
    assert exact_edit_token.editing_value_text == "0.80"
    assert exact_edit_token.editing_select_all is True
    assert controls.increase_rect is None
    assert controls.decrease_rect is None
    assert controls.isVisible() is False


def test_lora_exact_weight_edit_commits_exact_value(
    widgets: list[QWidget],
) -> None:
    """LoRA exact edits should update the first schedule weight."""

    box = show_lora_prompt_editor(
        widgets,
        text="<lora:Mineru:0.80>",
        width=240,
    )
    token = lora_token_for(box)
    start_exact_weight_edit(box, token)

    QTest.keyClicks(box, "1.25")
    process_events(ensure_qapp(), cycles=2)
    assert exact_weight_edit_token(box) is not None

    QTest.keyClick(box, Qt.Key.Key_Return)
    process_events(ensure_qapp(), cycles=4)

    assert box.toPlainText() == "<lora:Mineru:1.25>"
    assert exact_weight_edit_token(box) is None


def test_double_clicking_emphasis_words_selects_only_the_inner_prompt_text(
    widgets: list[QWidget],
) -> None:
    """Double clicking emphasized words should select only the visible prompt text."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(alpha beta:1.05)",
        width=220,
    )
    token = emphasis_token_for(box)
    assert token.content_start is not None
    assert token.content_end is not None
    token_rect = token_rect_for(box, token)
    weight_rect = weight_rect_for(box, token)
    word_point = QPoint(
        int((token_rect.left() + weight_rect.left()) / 2.0),
        int(token_rect.center().y()),
    )

    QTest.mouseDClick(box.viewport(), Qt.MouseButton.LeftButton, pos=word_point)
    process_events(app, cycles=4)

    cursor = box.textCursor()
    assert exact_weight_edit_token(box) is None
    assert cursor.selectionStart() == token.content_start
    assert cursor.selectionEnd() == token.content_end
    assert cursor.selectedText() == "alpha beta"
    assert surface_for(box).projection_document().tokens != ()


def test_double_clicking_emphasis_parens_selects_only_the_inner_prompt_text(
    widgets: list[QWidget],
) -> None:
    """Paren double clicks should still select only the inner prompt text."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    token = emphasis_token_for(box)
    assert token.content_start is not None
    assert token.content_end is not None
    token_rect = token_rect_for(box, token)
    paren_point = QPoint(int(token_rect.left() + 1), int(token_rect.center().y()))

    QTest.mouseDClick(box.viewport(), Qt.MouseButton.LeftButton, pos=paren_point)
    process_events(app, cycles=4)

    cursor = box.textCursor()
    assert exact_weight_edit_token(box) is None
    assert cursor.selectionStart() == token.content_start
    assert cursor.selectionEnd() == token.content_end
    assert cursor.selectedText() == "cat"
    assert surface_for(box).projection_document().tokens != ()


def test_double_clicking_emphasis_arrows_does_not_start_exact_edit_mode(
    widgets: list[QWidget],
) -> None:
    """Arrow double clicks should stay on the step-control path and never open exact edit."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    token = emphasis_token_for(box)
    controls = reveal_emphasis_controls(box, token)
    assert controls.increase_rect is not None
    assert controls.decrease_rect is not None

    QTest.mouseDClick(
        controls,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        controls.mapFromParent(controls.increase_rect.center().toPoint()),
    )
    process_events(ensure_qapp(), cycles=4)
    assert exact_weight_edit_token(box) is None

    token = emphasis_token_for(box)
    controls = reveal_emphasis_controls(box, token)
    assert controls.decrease_rect is not None
    QTest.mouseDClick(
        controls,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        controls.mapFromParent(controls.decrease_rect.center().toPoint()),
    )
    process_events(ensure_qapp(), cycles=4)
    assert exact_weight_edit_token(box) is None


def test_weight_click_candidate_cannot_promote_overlap_down_click_into_exact_edit(
    widgets: list[QWidget],
) -> None:
    """A prior weight click must not let the down-arrow overlap open exact edit."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.10)",
        width=180,
    )
    token = emphasis_token_for(box)
    controls = reveal_emphasis_controls(box, token)
    assert controls.decrease_rect is not None
    assert controls._weight_hit_rect is not None  # noqa: SLF001

    overlap_rect = controls.decrease_rect.intersected(controls._weight_hit_rect)  # noqa: SLF001
    assert overlap_rect.isEmpty() is False

    weight_point = controls.mapFromParent(controls._weight_hit_rect.center().toPoint())  # noqa: SLF001
    overlap_point = controls.mapFromParent(overlap_rect.center().toPoint())

    QTest.mouseClick(controls, Qt.MouseButton.LeftButton, pos=weight_point)
    process_events(ensure_qapp(), cycles=2)
    QTest.mouseClick(controls, Qt.MouseButton.LeftButton, pos=overlap_point)
    process_events(ensure_qapp(), cycles=4)

    assert exact_weight_edit_token(box) is None
    assert box.toPlainText() == "(cat:1.05)"


def test_exact_weight_edit_commits_exact_value_and_hides_step_controls(
    widgets: list[QWidget],
) -> None:
    """Exact weight editing should commit through Enter without exposing arrow controls."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    token = emphasis_token_for(box)
    controls = start_exact_weight_edit(box, token)

    QTest.keyClicks(box, "1.20")
    process_events(ensure_qapp(), cycles=2)
    assert exact_weight_edit_token(box) is not None
    assert controls.increase_rect is None
    assert controls.decrease_rect is None

    QTest.keyClick(box, Qt.Key.Key_Return)
    process_events(ensure_qapp(), cycles=4)

    assert box.toPlainText() == "(cat:1.20)"
    assert exact_weight_edit_token(box) is None


def test_exact_weight_edit_committing_one_unwraps_to_plain_text(
    widgets: list[QWidget],
) -> None:
    """Entering `1` should commit `1.00` and unwrap the source text."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    token = emphasis_token_for(box)
    start_exact_weight_edit(box, token)

    QTest.keyClicks(box, "1")
    QTest.keyClick(box, Qt.Key.Key_Return)
    process_events(ensure_qapp(), cycles=4)

    assert box.toPlainText() == "cat"


def test_exact_weight_edit_can_restore_subneutral_emphasis_from_transient_neutral_token(
    widgets: list[QWidget],
) -> None:
    """Synthetic neutral tokens should support exact weight entry the same way as real shells."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    controls = emphasis_controls_for(box)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.decrease_rect is not None

    click_control_rect(controls, controls.decrease_rect)
    process_events(ensure_qapp(), cycles=4)
    synthetic_token = controls.visible_token
    assert synthetic_token is not None
    assert synthetic_token.synthetic is True

    start_exact_weight_edit(box, synthetic_token)
    QTest.keyClicks(box, "0.95")
    QTest.keyClick(box, Qt.Key.Key_Return)
    process_events(ensure_qapp(), cycles=4)

    assert box.toPlainText() == "(cat:0.95)"


def test_exact_weight_edit_escape_cancels_without_mutating_the_prompt(
    widgets: list[QWidget],
) -> None:
    """Escape should dismiss exact edit mode and leave the prompt text unchanged."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    token = emphasis_token_for(box)
    start_exact_weight_edit(box, token)

    QTest.keyClicks(box, "1.20")
    QTest.keyClick(box, Qt.Key.Key_Escape)
    process_events(ensure_qapp(), cycles=4)

    assert box.toPlainText() == "(cat:1.05)"
    assert exact_weight_edit_token(box) is None


def test_exact_weight_edit_ignores_wheel_adjustment_while_active(
    widgets: list[QWidget],
) -> None:
    """Exact edit mode should suppress wheel-based step adjustment for the active token."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    token = emphasis_token_for(box)
    start_exact_weight_edit(box, token)
    exact_edit_token = exact_weight_edit_token(box)
    assert exact_edit_token is not None
    exact_weight_rect = weight_rect_for(box, exact_edit_token)

    wheel_widget_at_point(
        box.viewport(),
        local_point=exact_weight_rect.center().toPoint(),
        angle_delta_y=120,
    )

    assert box.toPlainText() == "(cat:1.05)"
    assert exact_weight_edit_token(box) is not None


def test_exact_weight_edit_outside_click_commits_and_still_reaches_editor(
    widgets: list[QWidget],
) -> None:
    """Outside clicks should finalize exact edit and then continue through normal editor hit testing."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    token = emphasis_token_for(box)
    start_exact_weight_edit(box, token)
    QTest.keyClicks(box, "1.20")
    process_events(app, cycles=2)
    token_rect = token_rect_for(box, emphasis_token_for(box))
    click_point = QPoint(int(token_rect.left() + 2), int(token_rect.center().y()))
    expected_position = (
        surface_for(box)
        ._layout.hit_test(  # noqa: SLF001
            QPointF(click_point),
            scroll_offset=float(box.verticalScrollBar().value()),
        )
        .source_position
    )

    QTest.mouseClick(box.viewport(), Qt.MouseButton.LeftButton, pos=click_point)
    process_events(app, cycles=4)

    assert box.toPlainText() == "(cat:1.20)"
    assert exact_weight_edit_token(box) is None
    assert box.textCursor().position() == expected_position


def test_exact_weight_edit_invalid_outside_click_cancels_and_still_reaches_editor(
    widgets: list[QWidget],
) -> None:
    """Outside clicks should cancel invalid exact edits and still continue into the editor."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    token = emphasis_token_for(box)
    start_exact_weight_edit(box, token)
    QTest.keyClick(box, Qt.Key.Key_Backspace)
    process_events(app, cycles=2)
    token_rect = token_rect_for(box, emphasis_token_for(box))
    click_point = QPoint(int(token_rect.left() + 2), int(token_rect.center().y()))
    expected_position = (
        surface_for(box)
        ._layout.hit_test(  # noqa: SLF001
            QPointF(click_point),
            scroll_offset=float(box.verticalScrollBar().value()),
        )
        .source_position
    )

    QTest.mouseClick(box.viewport(), Qt.MouseButton.LeftButton, pos=click_point)
    process_events(app, cycles=4)

    assert box.toPlainText() == "(cat:1.05)"
    assert exact_weight_edit_token(box) is None
    assert box.textCursor().position() == expected_position


def test_inline_decrease_click_unwraps_neutral_emphasis(
    widgets: list[QWidget],
) -> None:
    """Clicking down to neutral should unwrap source text but keep a visible `1.00` step."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    controls = emphasis_controls_for(box)

    set_cursor_position(box, 2)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.decrease_rect is not None

    click_control_rect(controls, controls.decrease_rect)
    process_events(ensure_qapp())

    cursor = box.textCursor()
    assert box.toPlainText() == "cat"
    assert cursor.selectionStart() == 2
    assert cursor.selectionEnd() == 2
    visible_token = controls.visible_token
    assert visible_token is not None
    assert controls.isVisible() is True
    assert controls.decrease_rect is not None
    assert visible_token.synthetic is True
    assert visible_token.value_text == "1.00"
    assert controls._gestures.weight_preview_text is None  # noqa: SLF001


def test_inline_decrease_click_can_continue_below_transient_neutral_emphasis(
    widgets: list[QWidget],
) -> None:
    """A second down-click from the transient neutral step should create sub-neutral emphasis."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    controls = emphasis_controls_for(box)

    set_cursor_position(box, 2)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.decrease_rect is not None

    click_control_rect(controls, controls.decrease_rect)
    process_events(ensure_qapp())
    assert box.toPlainText() == "cat"
    assert controls.isVisible() is True
    assert controls.decrease_rect is not None

    click_control_rect(controls, controls.decrease_rect)
    process_events(ensure_qapp())

    assert box.toPlainText() == "(cat:0.95)"


def test_inline_increase_click_can_restore_emphasis_from_transient_neutral_step(
    widgets: list[QWidget],
) -> None:
    """The transient neutral step should support an immediate increase back to `1.05`."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    controls = emphasis_controls_for(box)

    set_cursor_position(box, 2)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.decrease_rect is not None

    click_control_rect(controls, controls.decrease_rect)
    process_events(ensure_qapp())
    assert box.toPlainText() == "cat"
    assert controls.isVisible() is True
    assert controls.increase_rect is not None

    click_control_rect(controls, controls.increase_rect)
    process_events(ensure_qapp())

    assert box.toPlainText() == "(cat:1.05)"


def test_inline_decrease_click_keeps_transient_neutral_visible_when_caret_is_elsewhere(
    widgets: list[QWidget],
) -> None:
    """Overlay-owned neutral emphasis should survive even when the caret is outside."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), dog",
        width=220,
    )
    controls = emphasis_controls_for(box)

    set_cursor_position(box, len(box.toPlainText()))
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.decrease_rect is not None

    click_control_rect(controls, controls.decrease_rect)
    process_events(ensure_qapp())

    assert box.toPlainText() == "cat, dog"
    visible_token = controls.visible_token
    assert visible_token is not None
    assert visible_token.synthetic is True
    assert visible_token.value_text == "1.00"
    assert controls.isVisible() is True


def test_inline_decrease_click_with_caret_elsewhere_can_continue_below_transient_neutral(
    widgets: list[QWidget],
) -> None:
    """Overlay-owned neutral emphasis should support a second click below neutral."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), dog",
        width=220,
    )
    controls = emphasis_controls_for(box)

    set_cursor_position(box, len(box.toPlainText()))
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.decrease_rect is not None

    click_control_rect(controls, controls.decrease_rect)
    process_events(ensure_qapp())
    assert box.toPlainText() == "cat, dog"
    assert controls.decrease_rect is not None

    click_control_rect(controls, controls.decrease_rect)
    process_events(ensure_qapp())

    assert box.toPlainText() == "(cat:0.95), dog"


def test_overlay_owned_transient_neutral_emphasis_survives_caret_moves(
    widgets: list[QWidget],
) -> None:
    """Overlay-owned neutral emphasis should ignore caret movement until overlay ownership ends."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), dog",
        width=220,
    )
    controls = emphasis_controls_for(box)

    set_cursor_position(box, 2)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.decrease_rect is not None

    click_control_rect(controls, controls.decrease_rect)
    process_events(app)
    assert box.toPlainText() == "cat, dog"
    assert controls.visible_token is not None

    set_cursor_position(box, 7)
    process_events(app)

    tokens = [
        token
        for token in surface_for(box).projection_document().tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    ]
    assert len(tokens) == 1
    assert tokens[0].synthetic is True


def test_overlay_owned_transient_neutral_emphasis_clears_when_controls_hide(
    widgets: list[QWidget],
) -> None:
    """Overlay-owned neutral emphasis should clear once the overlay stops owning the token."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), dog",
        width=220,
    )
    controls = emphasis_controls_for(box)

    set_cursor_position(box, len(box.toPlainText()))
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.decrease_rect is not None

    click_control_rect(controls, controls.decrease_rect)
    process_events(app)
    assert box.toPlainText() == "cat, dog"
    assert controls.visible_token is not None

    QTest.mouseMove(
        box.viewport(),
        QPoint(max(1, box.viewport().width() - 3), max(1, box.viewport().height() - 3)),
    )
    process_events(app, cycles=3)
    QTest.qWait(180)
    process_events(app, cycles=3)

    tokens = [
        token
        for token in surface_for(box).projection_document().tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    ]
    assert tokens == []


def test_emphasis_controls_round_trip_through_editor_undo_stack(
    widgets: list[QWidget],
) -> None:
    """Projection-engine emphasis control clicks should remain undoable and redoable."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    controls = emphasis_controls_for(box)

    set_cursor_position(box, 2)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.increase_rect is not None
    click_control_rect(controls, controls.increase_rect)
    assert box.toPlainText() == "(cat:1.10)"

    box.undo()
    process_events(app)
    assert box.toPlainText() == "(cat:1.05)"

    box.redo()
    process_events(app)
    assert box.toPlainText() == "(cat:1.10)"


def test_visible_emphasis_controls_accept_mouse_wheel_like_a_spinbox(
    widgets: list[QWidget],
) -> None:
    """Wheel input over the token or controls should adjust emphasis on the source text."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    controls = emphasis_controls_for(box)
    token = emphasis_token_for(box)
    token_center = anchor_rect_for(box, token).center().toPoint()

    wheel_widget_at_point(box.viewport(), local_point=token_center, angle_delta_y=120)
    assert box.toPlainText() == "(cat:1.10)"
    assert emphasis_token_for(box).value_text == "1.10"
    assert controls._gestures.weight_preview_text is None  # noqa: SLF001

    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.increase_rect is not None
    wheel_widget_at_point(
        controls,
        local_point=controls.mapFromParent(controls.increase_rect.center().toPoint()),
        angle_delta_y=-120,
    )
    assert box.toPlainText() == "(cat:1.05)"

    wheel_widget_at_point(
        controls,
        local_point=controls.mapFromParent(controls.increase_rect.center().toPoint()),
        angle_delta_y=-120,
    )
    process_events(ensure_qapp())
    assert box.toPlainText() == "cat"
    assert controls._gestures.weight_preview_text == "1.00"  # noqa: SLF001
    assert controls.visible_token is not None
    assert controls.isVisible() is True
    assert controls.increase_rect is not None
    assert controls.visible_token.synthetic is True
    assert controls.visible_token.value_text == "1.00"

    wheel_widget_at_point(
        controls,
        local_point=controls.mapFromParent(controls.increase_rect.center().toPoint()),
        angle_delta_y=-120,
    )
    process_events(ensure_qapp())
    assert box.toPlainText() == "(cat:0.95)"
    assert controls._gestures.weight_preview_text == "0.95"  # noqa: SLF001


def test_wheel_outside_emphasis_token_does_not_adjust_when_caret_is_inside_token(
    widgets: list[QWidget],
) -> None:
    """Wheel targeting should ignore caret-owned emphasis when the pointer is outside."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05) plain text that extends right",
        width=420,
    )
    token = emphasis_token_for(box)
    set_cursor_position(box, 2)

    accepted = wheel_widget_at_point(
        box.viewport(),
        local_point=point_outside_token(box, token),
        angle_delta_y=120,
    )

    assert box.toPlainText() == "(cat:1.05) plain text that extends right"
    assert accepted is False


def test_wheel_outside_lora_chip_does_not_adjust_when_caret_is_inside_token(
    widgets: list[QWidget],
) -> None:
    """Wheel targeting should ignore caret-owned LoRA chips when the pointer is outside."""

    box = show_lora_prompt_editor(
        widgets,
        text="<lora:Mineru:0.80> plain text that extends right",
        width=460,
    )
    token = lora_token_for(box)
    set_cursor_position(box, 3)

    wheel_widget_at_point(
        box.viewport(),
        local_point=point_outside_token(box, token),
        angle_delta_y=120,
    )

    assert box.toPlainText() == "<lora:Mineru:0.80> plain text that extends right"


def test_wheel_outside_weighted_tokens_scrolls_when_scrollbar_available(
    widgets: list[QWidget],
) -> None:
    """Wheel input outside weighted tokens should remain available for scrolling."""

    source = "(cat:1.05)\n" + "\n".join(f"line {index}" for index in range(20))
    box = show_prompt_editor(
        widgets,
        text=source,
        width=420,
    )
    token = emphasis_token_for(box)
    set_cursor_position(box, 2)
    scroll_bar = box.verticalScrollBar()
    assert scroll_bar.maximum() > scroll_bar.minimum()
    initial_scroll_value = scroll_bar.value()

    wheel_widget_at_point(
        box.viewport(),
        local_point=point_outside_token(box, token),
        angle_delta_y=-120,
    )

    assert box.toPlainText() == source
    assert scroll_bar.value() > initial_scroll_value


def test_wheel_over_emphasis_token_adjusts_by_pointer(
    widgets: list[QWidget],
) -> None:
    """Pointer hit testing should adjust emphasis even when the caret is elsewhere."""

    box = show_prompt_editor(
        widgets,
        text="prefix (cat:1.05)",
        width=240,
    )
    token = emphasis_token_for(box)
    set_cursor_position(box, 0)

    wheel_widget_at_point(
        box.viewport(),
        local_point=token_rect_for(box, token).center().toPoint(),
        angle_delta_y=120,
    )

    assert box.toPlainText() == "prefix (cat:1.10)"


def test_host_viewport_wheel_over_emphasis_token_adjusts_on_first_tick(
    widgets: list[QWidget],
) -> None:
    """The outer prompt host should give weighted tokens first chance at wheel input."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)\n" + "\n".join(f"line {index}" for index in range(20)),
        width=420,
    )
    token = emphasis_token_for(box)
    host_viewport = shell_viewport_for(box)
    token_center = token_rect_for(box, token).center().toPoint()
    initial_scroll_value = box.verticalScrollBar().value()

    accepted = wheel_widget_at_point(
        host_viewport,
        local_point=token_center,
        angle_delta_y=120,
    )

    assert accepted is True
    assert box.toPlainText().startswith("(cat:1.10)")
    assert box.verticalScrollBar().value() == initial_scroll_value


def test_wheel_over_lora_chip_adjusts_by_pointer(
    widgets: list[QWidget],
) -> None:
    """Pointer hit testing should adjust LoRA weights across the whole chip."""

    box = show_lora_prompt_editor(
        widgets,
        text="prefix <lora:Mineru:0.80>",
        width=360,
    )
    token = lora_token_for(box)
    token_rect = token_rect_for(box, token)
    weight_rect = weight_rect_for(box, token)
    chip_point = QPoint(int(token_rect.left()) + 8, int(token_rect.center().y()))
    assert not weight_rect.contains(QPointF(chip_point))
    set_cursor_position(box, 0)

    wheel_widget_at_point(
        box.viewport(),
        local_point=chip_point,
        angle_delta_y=120,
    )

    assert box.toPlainText() == "prefix <lora:Mineru:0.85>"


def test_overlay_wheel_to_neutral_keeps_caret_at_plain_text_content_end(
    widgets: list[QWidget],
) -> None:
    """Wheel adjustment to neutral should leave caret at the plain-text content end."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    surface = surface_for(box)
    token = emphasis_token_for(box)
    cursor = box.textCursor()
    cursor.setPosition(token.content_end, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    process_events(app)

    wheel_widget_at_point(
        box.viewport(),
        local_point=anchor_rect_for(box, token).center().toPoint(),
        angle_delta_y=-120,
    )
    process_events(app)

    assert box.textCursor().position() == 3
    assert box.textCursor().selectionStart() == 3
    assert box.textCursor().selectionEnd() == 3
    assert surface._cursor_state.source_position == 3


def test_down_control_does_not_show_pointer_weight_preview(
    widgets: list[QWidget],
) -> None:
    """Down-arrow clicks should not show the floating weight preview bubble."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.10)",
        width=180,
    )
    controls = emphasis_controls_for(box)

    set_cursor_position(box, 2)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.decrease_rect is not None

    click_control_rect(controls, controls.decrease_rect)

    assert box.toPlainText() == "(cat:1.05)"
    assert controls._gestures.weight_preview_text is None  # noqa: SLF001
    assert controls._gestures.weight_preview_rect is None  # noqa: SLF001


def test_wheel_over_emphasis_words_does_not_show_pointer_weight_preview(
    widgets: list[QWidget],
) -> None:
    """Wheel adjustments away from the number and up arrow should not show the preview bubble."""

    box = show_prompt_editor(
        widgets,
        text="(alpha beta gamma:1.05)",
        width=220,
    )
    controls = emphasis_controls_for(box)
    token = emphasis_token_for(box)
    anchor_rect = anchor_rect_for(box, token)
    token_rect = token_rect_for(box, token)
    text_point = QPoint(
        int((token_rect.left() + anchor_rect.left()) / 2.0),
        int(token_rect.center().y()),
    )

    wheel_widget_at_point(box.viewport(), local_point=text_point, angle_delta_y=120)

    assert box.toPlainText() == "(alpha beta gamma:1.10)"
    assert controls._gestures.weight_preview_text is None  # noqa: SLF001
    assert controls._gestures.weight_preview_rect is None  # noqa: SLF001

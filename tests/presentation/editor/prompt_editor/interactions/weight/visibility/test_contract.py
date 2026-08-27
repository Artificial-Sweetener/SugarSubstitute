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

"""Verify prompt weight-control visibility and geometry."""

from __future__ import annotations
import pytest
from PySide6.QtCore import QEvent, QPoint, QRectF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from tests.support.prompt_editor.projection_engine_support import (
    token_weight_controls_for,
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition
from ..mounting import (
    anchor_rect_for,
    emphasis_token_for,
    reveal_emphasis_controls,
    set_cursor_position,
    token_rect_for,
    wait_for_hide_linger_timeout,
)


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
    controls = token_weight_controls_for(box)

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
    controls = token_weight_controls_for(box)

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
    controls = token_weight_controls_for(box)

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
    controls = token_weight_controls_for(box)
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
    controls = token_weight_controls_for(box)
    token = emphasis_token_for(box)
    hover_point = anchor_rect_for(box, token).center().toPoint()
    original_text = box.toPlainText()

    assert controls.visible_token is None

    QTest.mouseMove(
        box.viewport(),
        QPoint(max(1, box.viewport().width() - 3), max(1, box.viewport().height() - 3)),
    )
    QTest.mouseMove(box.viewport(), hover_point)
    controls.refresh_geometry()
    wait_for_qt_condition(
        lambda: (
            (visible_token := controls.visible_token) is not None
            and visible_token.token_id == token.token_id
        )
    )

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
    controls = token_weight_controls_for(box)
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
    controls = token_weight_controls_for(box)

    set_cursor_position(box, 2)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)

    assert controls.visible_token is not None
    assert controls.visible_token.token_id == token.token_id
    QTest.mouseMove(box.viewport(), QPoint(2, 2))
    process_events(app)

    assert controls.visible_token is not None
    assert controls.visible_token.token_id == token.token_id
    wait_for_hide_linger_timeout(controls)
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
    controls = token_weight_controls_for(box)

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
    controls = token_weight_controls_for(box)
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

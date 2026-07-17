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

"""Contract tests for wildcard rendering on the projection-engine prompt surface."""

from __future__ import annotations

import os
from collections.abc import Iterator

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QFontMetricsF, QPalette, QTextCursor, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.ports import PromptWildcardResolution
from substitute.presentation.editor.prompt_editor.projection.model import (
    OBJECT_REPLACEMENT_CHARACTER,
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.projection.tokens import (
    PromptWildcardInlineObjectRenderer,
)
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptTokenWeightControls,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from tests.prompt_projection_test_helpers import (
    StaticPromptWildcardCatalogGateway,
    emphasis_controls_for,
    ensure_qapp,
    process_events,
    projection_paint_state_for,
    show_prompt_editor,
    surface_for,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "real prompt wildcard projection tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


@pytest.fixture()
def widgets() -> Iterator[list[QWidget]]:
    """Track widgets created during one wildcard projection contract test."""

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


def wildcard_tokens_for(box: PromptEditor) -> list[PromptProjectionToken]:
    """Return the collapsed wildcard tokens from the live projection document."""

    return [
        token
        for token in surface_for(box).projection_document().tokens
        if token.kind is PromptProjectionTokenKind.WILDCARD
    ]


def wildcard_token_for_range(
    box: PromptEditor,
    *,
    source_start: int,
    source_end: int,
) -> PromptProjectionToken:
    """Return one wildcard token by its raw outer source range."""

    for token in wildcard_tokens_for(box):
        if (token.source_start, token.source_end) == (source_start, source_end):
            return token
    raise AssertionError(
        f"Missing wildcard token for outer range {(source_start, source_end)}."
    )


def token_rect_for(box: PromptEditor, token: PromptProjectionToken) -> QRectF:
    """Return the viewport-local rect occupied by one wildcard token."""

    token_rect = surface_for(box)._layout.token_rect(  # noqa: SLF001
        token,
        scroll_offset=float(box.verticalScrollBar().value()),
    )
    assert token_rect is not None
    return token_rect


def rect_tuple(rect: QRectF) -> tuple[float, float, float, float]:
    """Round one token rect into a stable assertion tuple."""

    return (
        round(rect.left(), 2),
        round(rect.top(), 2),
        round(rect.width(), 2),
        round(rect.height(), 2),
    )


def reveal_wildcard_controls(
    box: PromptEditor,
    token: PromptProjectionToken,
) -> PromptTokenWeightControls:
    """Reveal token controls over one wildcard tag through a deterministic hover path."""

    app = ensure_qapp()
    controls = emphasis_controls_for(box)
    reset_point = QPoint(
        max(1, box.viewport().width() - 3),
        max(1, box.viewport().height() - 3),
    )
    QTest.mouseMove(box.viewport(), reset_point)
    process_events(app, cycles=3)
    anchor_rect = surface_for(box).token_anchor_rect(token) or token_rect_for(
        box, token
    )
    QTest.mouseMove(box.viewport(), anchor_rect.center().toPoint())
    controls._set_pointer_from_viewport(anchor_rect.center())  # noqa: SLF001
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
    process_events(app, cycles=4)


def wheel_viewport_at_point(
    box: PromptEditor,
    *,
    local_point: QPoint,
    angle_delta_y: int,
) -> bool:
    """Send one wheel event to the prompt viewport and return whether it was accepted."""

    app = ensure_qapp()
    global_point = box.viewport().mapToGlobal(local_point)
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
    QApplication.sendEvent(box.viewport(), wheel_event)
    process_events(app, cycles=4)
    return wheel_event.isAccepted()


def test_prompt_editor_wildcard_projection_collapses_resolved_placeholder_tokens(
    widgets: list[QWidget],
) -> None:
    """Resolved wildcard spans should become one collapsed inline syntax token."""

    box = show_prompt_editor(
        widgets,
        text="{pokemon/gen1/very_long_identifier}, suffix",
        width=200,
        wildcard_gateway=StaticPromptWildcardCatalogGateway(
            {
                (
                    "pokemon/gen1/very_long_identifier",
                    "simple",
                    None,
                ): PromptWildcardResolution(
                    identifier="pokemon/gen1/very_long_identifier",
                    wildcard_form="simple",
                    exists=True,
                ),
            }
        ),
    )
    surface = surface_for(box)

    tokens = wildcard_tokens_for(box)

    assert (
        surface.projection_document().projection_text.count(
            OBJECT_REPLACEMENT_CHARACTER
        )
        == 1
    )
    assert len(tokens) == 1
    assert tokens[0].display_text == "pokemon/gen1/very_long_identifier"
    assert tokens[0].status_text is None
    assert tokens[0].wildcard_display_tag is None
    assert tokens[0].exists is True
    assert token_rect_for(box, tokens[0]).isValid() is True


def test_prompt_editor_wildcard_projection_reserves_inline_italic_tag_geometry(
    widgets: list[QWidget],
) -> None:
    """Wildcard italic tag suffixes should be measured as part of inline syntax layout."""

    single_box = show_prompt_editor(
        widgets,
        text="{animal}",
        width=240,
        wildcard_gateway=StaticPromptWildcardCatalogGateway({}),
    )
    tagged_box = show_prompt_editor(
        widgets,
        text="{animal}, {animal|2}, {animal|one}",
        width=360,
        wildcard_gateway=StaticPromptWildcardCatalogGateway({}),
    )

    single_token = wildcard_tokens_for(single_box)[0]
    tagged_tokens = wildcard_tokens_for(tagged_box)
    single_width = token_rect_for(single_box, single_token).width()
    implicit_width = token_rect_for(tagged_box, tagged_tokens[0]).width()
    numeric_width = token_rect_for(tagged_box, tagged_tokens[1]).width()
    word_width = token_rect_for(tagged_box, tagged_tokens[2]).width()

    assert [token.wildcard_display_tag for token in tagged_tokens] == [
        "1",
        "2",
        "one",
    ]
    assert [token.status_text for token in tagged_tokens] == [None, None, None]
    assert implicit_width > single_width
    assert numeric_width > single_width
    assert word_width > numeric_width


def test_prompt_editor_wildcard_projection_places_italic_tag_on_body_baseline(
    widgets: list[QWidget],
) -> None:
    """Wildcard tags should be italic suffixes with no spacing after the closing brace."""

    box = show_prompt_editor(
        widgets,
        text="{animal|2}",
        width=240,
        wildcard_gateway=StaticPromptWildcardCatalogGateway({}),
    )
    token = wildcard_tokens_for(box)[0]
    run = surface_for(box).projection_document().runs_for_token(token.token_id)[0]
    renderer = PromptWildcardInlineObjectRenderer()
    token_rect = token_rect_for(box, token)
    tag_rect = renderer.weight_text_rect(run, token, token_rect, base_font=box.font())
    base_metrics = QFontMetricsF(box.font())
    tag_font = renderer._tag_font(box.font())  # noqa: SLF001
    tag_metrics = QFontMetricsF(tag_font)
    brace_metrics = QFontMetricsF(renderer._brace_font(box.font()))  # noqa: SLF001
    expected_baseline = (
        token_rect.top()
        + max(0.0, (token_rect.height() - base_metrics.height()) / 2.0)
        + base_metrics.ascent()
    )
    expected_tag_left = (
        token_rect.left()
        + brace_metrics.horizontalAdvance("{")
        + renderer._BRACE_GAP  # noqa: SLF001
        + base_metrics.horizontalAdvance(run.display_text)
        + renderer._BRACE_GAP  # noqa: SLF001
        + brace_metrics.horizontalAdvance("}")
    )

    assert tag_rect is not None
    assert tag_font.italic() is True
    assert renderer._TAG_GAP == 0.0  # noqa: SLF001
    assert tag_rect.left() == pytest.approx(expected_tag_left)
    assert tag_rect.top() == pytest.approx(expected_baseline - tag_metrics.ascent())


def test_prompt_editor_missing_wildcard_uses_normal_syntax_color(
    widgets: list[QWidget],
) -> None:
    """Missing wildcard syntax should rely on diagnostics, not red inline text."""

    box = show_prompt_editor(
        widgets,
        text="{missing|2}",
        width=240,
        wildcard_gateway=StaticPromptWildcardCatalogGateway({}),
    )
    token = wildcard_tokens_for(box)[0]
    renderer = PromptWildcardInlineObjectRenderer()
    accent_color = renderer._accent_color_for_token(  # noqa: SLF001
        token,
        palette=box.palette(),
    )
    normal_color = box.palette().color(QPalette.ColorRole.Text)

    assert token.exists is False
    assert token.decoration_accented is False
    assert accent_color.rgba() == normal_color.rgba()


def test_prompt_editor_wildcard_numeric_controls_persist_implicit_group_edit(
    widgets: list[QWidget],
) -> None:
    """Increasing an implicit wildcard tag should write an explicit tag suffix."""

    box = show_prompt_editor(
        widgets,
        text="{animal}, {animal}",
        width=260,
        wildcard_gateway=StaticPromptWildcardCatalogGateway({}),
    )
    token = wildcard_token_for_range(box, source_start=10, source_end=18)
    controls = reveal_wildcard_controls(box, token)

    assert controls.visible_token is not None
    assert controls.visible_token.token_id == token.token_id
    assert projection_paint_state_for(box).is_token_decoration_accented(token.token_id)
    assert controls.increase_rect is not None

    click_control_rect(controls, controls.increase_rect)

    assert box.toPlainText() == "{animal}, {animal|2}"


def test_prompt_editor_wildcard_numeric_controls_ignore_nonnumeric_tags(
    widgets: list[QWidget],
) -> None:
    """Nonnumeric wildcard tags should render without numeric step controls."""

    box = show_prompt_editor(
        widgets,
        text="{animal|one}",
        width=220,
        wildcard_gateway=StaticPromptWildcardCatalogGateway({}),
    )
    token = wildcard_tokens_for(box)[0]
    controls = reveal_wildcard_controls(box, token)

    assert token.wildcard_display_tag == "one"
    assert token.wildcard_can_step_tag is False
    assert controls.visible_token is None
    assert controls.increase_rect is None
    assert controls.decrease_rect is None


def test_prompt_editor_wildcard_wheel_steps_numeric_tag(
    widgets: list[QWidget],
) -> None:
    """Wheel input over a numeric wildcard tag should persist the adjusted tag."""

    box = show_prompt_editor(
        widgets,
        text="{animal|2}",
        width=220,
        wildcard_gateway=StaticPromptWildcardCatalogGateway({}),
    )
    token = wildcard_tokens_for(box)[0]
    accepted = wheel_viewport_at_point(
        box,
        local_point=token_rect_for(box, token).center().toPoint(),
        angle_delta_y=-120,
    )

    assert accepted is True
    assert box.toPlainText() == "{animal|1}"


def test_prompt_editor_wildcard_copy_uses_underlying_source_text(
    widgets: list[QWidget],
) -> None:
    """Selecting decorated wildcards should copy the saved prompt source text."""

    box = show_prompt_editor(
        widgets,
        text="prefix {animal|2} suffix",
        width=260,
        wildcard_gateway=StaticPromptWildcardCatalogGateway({}),
    )
    cursor = box.textCursor()
    cursor.setPosition(7, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(17, QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    process_events(ensure_qapp())

    box.copy()

    assert QApplication.clipboard().text() == "{animal|2}"


def test_prompt_editor_wildcard_projection_tracks_caret_active_token_by_source_range(
    widgets: list[QWidget],
) -> None:
    """Caret movement should retag the active collapsed wildcard token in the projection."""

    box = show_prompt_editor(
        widgets,
        text="{animal}, middle, {csv:monster:color}",
        width=280,
        wildcard_gateway=StaticPromptWildcardCatalogGateway(
            {
                ("animal", "simple", None): PromptWildcardResolution(
                    identifier="animal",
                    wildcard_form="simple",
                    exists=True,
                ),
                ("monster", "csv", "color"): PromptWildcardResolution(
                    identifier="monster",
                    wildcard_form="csv",
                    csv_column="color",
                    exists=True,
                    matched_csv_column="Color",
                    available_csv_columns=("Color", "Size"),
                ),
            }
        ),
    )

    set_cursor_position(box, 2)
    first_token = wildcard_token_for_range(box, source_start=0, source_end=8)
    second_token = wildcard_token_for_range(box, source_start=18, source_end=37)
    paint_state = projection_paint_state_for(box)
    assert paint_state.is_token_active(first_token.token_id)
    assert not paint_state.is_token_active(second_token.token_id)
    assert first_token.status_text is None

    set_cursor_position(box, 24)
    first_token = wildcard_token_for_range(box, source_start=0, source_end=8)
    second_token = wildcard_token_for_range(box, source_start=18, source_end=37)
    paint_state = projection_paint_state_for(box)
    assert not paint_state.is_token_active(first_token.token_id)
    assert paint_state.is_token_active(second_token.token_id)
    assert second_token.display_text == "monster:Color"
    assert second_token.status_text is None


def test_prompt_editor_wildcard_projection_hover_updates_without_breaking_typing_flow(
    widgets: list[QWidget],
) -> None:
    """Hover should target the wildcard token while the prompt editor remains editable."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="prefix, {animal}, suffix",
        width=240,
        wildcard_gateway=StaticPromptWildcardCatalogGateway(
            {
                ("animal", "simple", None): PromptWildcardResolution(
                    identifier="animal",
                    wildcard_form="simple",
                    exists=False,
                ),
            }
        ),
    )
    token = wildcard_tokens_for(box)[0]
    original_text = box.toPlainText()

    QTest.mouseMove(box.viewport(), token_rect_for(box, token).center().toPoint())
    process_events(app)

    hovered_token = surface_for(box).hovered_token()
    assert hovered_token is not None
    assert hovered_token.source_start == token.source_start
    assert hovered_token.source_end == token.source_end
    assert box.hasFocus() is True

    QTest.keyClicks(box, "!")
    process_events(app)

    assert box.toPlainText() != original_text
    QApplication.sendEvent(box.viewport(), QEvent(QEvent.Type.Leave))
    process_events(app)

    assert surface_for(box).hovered_token() is None


def test_prompt_editor_wildcard_projection_recomputes_token_geometry_on_resize(
    widgets: list[QWidget],
) -> None:
    """Narrower editor widths should rebuild the wrapped wildcard token geometry."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="{pokemon/gen1/very_long_identifier}, suffix",
        width=260,
        wildcard_gateway=StaticPromptWildcardCatalogGateway(
            {
                (
                    "pokemon/gen1/very_long_identifier",
                    "simple",
                    None,
                ): PromptWildcardResolution(
                    identifier="pokemon/gen1/very_long_identifier",
                    wildcard_form="simple",
                    exists=True,
                ),
            }
        ),
    )
    before_resize = rect_tuple(token_rect_for(box, wildcard_tokens_for(box)[0]))

    box.resize(140, box.height())
    process_events(app)

    after_resize = rect_tuple(token_rect_for(box, wildcard_tokens_for(box)[0]))

    assert after_resize != before_resize


def test_prompt_editor_wildcard_projection_tracks_viewport_scroll_geometry(
    widgets: list[QWidget],
) -> None:
    """Scrolling should move the visible wildcard token rect with the viewport."""

    app = ensure_qapp()
    lines = [f"line {index}" for index in range(12)]
    lines[5] = "{csv:monster:color}"
    box = show_prompt_editor(
        widgets,
        text="\n".join(lines),
        width=220,
        wildcard_gateway=StaticPromptWildcardCatalogGateway(
            {
                ("monster", "csv", "color"): PromptWildcardResolution(
                    identifier="monster",
                    wildcard_form="csv",
                    csv_column="color",
                    exists=True,
                    matched_csv_column="Color",
                    available_csv_columns=("Color", "Size"),
                ),
            }
        ),
    )
    scrollbar = box.verticalScrollBar()
    token = wildcard_tokens_for(box)[0]

    assert scrollbar.maximum() > 0
    before_scroll = rect_tuple(token_rect_for(box, token))

    scrollbar.setValue(scrollbar.singleStep() * 2 or 32)
    process_events(app)

    assert rect_tuple(token_rect_for(box, wildcard_tokens_for(box)[0])) != before_scroll


def test_prompt_editor_wildcard_tokens_coexist_with_emphasis_controls(
    widgets: list[QWidget],
) -> None:
    """Wildcard tokens should coexist with the non-clipping emphasis controls."""

    box = show_prompt_editor(
        widgets,
        text="{animal}, (cat:1.05)",
        width=220,
        wildcard_gateway=StaticPromptWildcardCatalogGateway(
            {
                ("animal", "simple", None): PromptWildcardResolution(
                    identifier="animal",
                    wildcard_form="simple",
                    exists=True,
                ),
            }
        ),
    )

    assert len(wildcard_tokens_for(box)) == 1

    set_cursor_position(box, box.toPlainText().index("cat"))
    emphasis_token = next(
        token
        for token in surface_for(box).projection_document().tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    )
    anchor_rect = surface_for(box).token_anchor_rect(emphasis_token)
    assert anchor_rect is not None
    QTest.mouseMove(box.viewport(), anchor_rect.center().toPoint())
    process_events(ensure_qapp(), cycles=6)
    emphasis_controls_for(box).refresh_geometry()
    process_events(ensure_qapp(), cycles=6)

    visible_token = emphasis_controls_for(box).visible_token
    assert visible_token is not None
    assert visible_token.token_id == emphasis_token.token_id

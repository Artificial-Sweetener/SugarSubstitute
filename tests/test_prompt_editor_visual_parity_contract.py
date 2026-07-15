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

"""Visual parity contracts for the QFluent-hosted prompt editor shell."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QImage, QPalette, QTextCursor
from PySide6.QtTest import QTest
from qfluentwidgets import Theme, setTheme  # type: ignore[import-untyped]

from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionDisplayMode,
)
from tests.prompt_visual_test_helpers import (
    create_prompt_editor,
    create_reference_text_edit,
    ensure_qapp,
    equalize_reference_height,
    fluent_theme,
    pixel_rgba,
    process_events,
    show_text_widget,
    widget_image,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "real PromptEditor visual parity tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def _assert_rgba_close(
    actual: tuple[int, int, int, int],
    expected: tuple[int, int, int, int],
    *,
    tolerance: int = 8,
) -> None:
    """Assert that two captured widget pixels are visually equivalent."""

    assert all(
        abs(actual_channel - expected_channel) <= tolerance
        for actual_channel, expected_channel in zip(actual, expected)
    ), (actual, expected)


def _first_ink_x(
    image: QImage,
    *,
    row: int,
    background: tuple[int, int, int, int],
    tolerance: int = 8,
) -> int:
    """Return the first x coordinate whose pixel differs from the shell background."""

    for x in range(image.width()):
        pixel = pixel_rgba(image, x, row)
        if any(
            abs(channel - background_channel) > tolerance
            for channel, background_channel in zip(pixel, background)
        ):
            return x
    raise AssertionError(f"No foreground ink found on row {row}.")


def _dispose_widgets(*widgets: object) -> None:
    """Close and delete any QWidget instances created by visual parity tests."""

    app = ensure_qapp()
    for widget in widgets:
        if widget is None:
            continue
        q_widget = widget
        if hasattr(q_widget, "close"):
            q_widget.close()
        if hasattr(q_widget, "deleteLater"):
            q_widget.deleteLater()
    process_events(app)


def test_prompt_editor_projection_palette_refreshes_after_qfluent_theme_switch() -> (
    None
):
    """Projection text and highlight colors should follow QFluent theme refresh."""

    app = ensure_qapp()
    with fluent_theme(Theme.DARK):
        prompt_editor = create_prompt_editor()
        try:
            show_text_widget(
                prompt_editor,
                width=320,
                text="alpha beta gamma",
                focused=True,
            )
            process_events(app)

            setTheme(Theme.LIGHT)
            process_events(app, cycles=10)

            projection_palette = prompt_editor._surface._layout._palette
            host_palette = prompt_editor.palette()
            for role in (
                QPalette.ColorRole.Text,
                QPalette.ColorRole.Highlight,
                QPalette.ColorRole.HighlightedText,
            ):
                assert projection_palette.color(role) == host_palette.color(role)
        finally:
            _dispose_widgets(prompt_editor)


def test_prompt_editor_shell_metrics_match_qfluent_reference_in_light_and_dark() -> (
    None
):
    """Shell metrics should match the live QFluent `TextEdit` in both theme modes."""

    app = ensure_qapp()
    for theme in (Theme.LIGHT, Theme.DARK):
        with fluent_theme(theme):
            prompt_editor = create_prompt_editor()
            reference = create_reference_text_edit()
            try:
                show_text_widget(prompt_editor, width=320, text="alpha beta")
                equalize_reference_height(reference, prompt_editor, width=320)
                show_text_widget(reference, width=320, height=prompt_editor.height())

                reference.setPlainText("alpha beta")
                reference_cursor = reference.textCursor()
                reference_cursor.movePosition(QTextCursor.MoveOperation.End)
                reference.setTextCursor(reference_cursor)
                process_events(app)

                assert prompt_editor.contentsMargins() == reference.contentsMargins()
                assert prompt_editor.font().families() == reference.font().families()
                assert prompt_editor.font().pixelSize() == reference.font().pixelSize()
                assert (
                    prompt_editor.fontMetrics().lineSpacing()
                    == reference.fontMetrics().lineSpacing()
                )
                assert (
                    prompt_editor.document().documentMargin()
                    == reference.document().documentMargin()
                )
                assert prompt_editor.height() == reference.height()
                assert (
                    prompt_editor.viewport().rect().height()
                    == reference.viewport().rect().height()
                )
                assert prompt_editor.cursorRect().top() == reference.cursorRect().top()
                assert (
                    prompt_editor.cursorRect().height()
                    == reference.cursorRect().height()
                )
                assert (
                    prompt_editor.cursorRect().left() == reference.cursorRect().left()
                )
            finally:
                _dispose_widgets(reference, prompt_editor)


def test_prompt_editor_placeholder_ink_origin_matches_qfluent_reference() -> None:
    """Placeholder text should begin on the same visual inset as the QFluent shell."""

    app = ensure_qapp()
    for theme in (Theme.LIGHT, Theme.DARK):
        with fluent_theme(theme):
            prompt_editor = create_prompt_editor()
            reference = create_reference_text_edit()
            try:
                show_text_widget(
                    prompt_editor,
                    width=320,
                    placeholder="Prompt placeholder",
                    focused=True,
                )
                prompt_image = widget_image(prompt_editor)

                equalize_reference_height(reference, prompt_editor, width=320)
                show_text_widget(
                    reference,
                    width=320,
                    height=prompt_editor.height(),
                    placeholder="Prompt placeholder",
                    focused=True,
                )

                reference_image = widget_image(reference)
                prompt_background = pixel_rgba(
                    prompt_image,
                    prompt_image.width() - 20,
                    10,
                )
                reference_background = pixel_rgba(
                    reference_image,
                    reference_image.width() - 20,
                    10,
                )
                prompt_ink_x = _first_ink_x(
                    prompt_image,
                    row=10,
                    background=prompt_background,
                )
                reference_ink_x = _first_ink_x(
                    reference_image,
                    row=10,
                    background=reference_background,
                )

                assert prompt_ink_x == reference_ink_x
                _assert_rgba_close(
                    pixel_rgba(prompt_image, 5, prompt_image.height() - 2),
                    pixel_rgba(reference_image, 5, reference_image.height() - 2),
                )
                process_events(app)
            finally:
                _dispose_widgets(reference, prompt_editor)


def test_prompt_editor_plain_text_pixels_match_qfluent_focus_and_background() -> None:
    """Plain text mode should keep the same text inset and shell chrome as QFluent."""

    app = ensure_qapp()
    for theme in (Theme.LIGHT, Theme.DARK):
        with fluent_theme(theme):
            prompt_editor = create_prompt_editor()
            reference = create_reference_text_edit()
            try:
                show_text_widget(
                    prompt_editor,
                    width=320,
                    text="alpha beta",
                    focused=True,
                )
                prompt_image = widget_image(prompt_editor)

                equalize_reference_height(reference, prompt_editor, width=320)
                show_text_widget(
                    reference,
                    width=320,
                    height=prompt_editor.height(),
                    text="alpha beta",
                    focused=True,
                )

                reference_cursor = reference.textCursor()
                reference_cursor.movePosition(QTextCursor.MoveOperation.End)
                reference.setTextCursor(reference_cursor)
                process_events(app)

                reference_image = widget_image(reference)
                prompt_background = pixel_rgba(
                    prompt_image,
                    prompt_image.width() - 20,
                    10,
                )
                reference_background = pixel_rgba(
                    reference_image,
                    reference_image.width() - 20,
                    10,
                )

                assert _first_ink_x(
                    prompt_image,
                    row=10,
                    background=prompt_background,
                ) == _first_ink_x(
                    reference_image,
                    row=10,
                    background=reference_background,
                )
                _assert_rgba_close(
                    pixel_rgba(prompt_image, 5, prompt_image.height() - 2),
                    pixel_rgba(reference_image, 5, reference_image.height() - 2),
                )
                _assert_rgba_close(
                    pixel_rgba(prompt_image, prompt_image.width() - 20, 10),
                    pixel_rgba(reference_image, reference_image.width() - 20, 10),
                )
            finally:
                _dispose_widgets(reference, prompt_editor)


def test_prompt_editor_raw_mode_with_prompt_syntax_matches_qfluent_reference() -> None:
    """Raw display mode should render syntax-bearing text like the QFluent reference."""

    app = ensure_qapp()
    syntax_text = "(cat:1.05), suffix"
    for theme in (Theme.LIGHT, Theme.DARK):
        with fluent_theme(theme):
            prompt_editor = create_prompt_editor()
            prompt_editor.setDisplayMode(PromptProjectionDisplayMode.RAW)
            reference = create_reference_text_edit()
            try:
                show_text_widget(
                    prompt_editor,
                    width=320,
                    text=syntax_text,
                    focused=True,
                )
                prompt_image = widget_image(prompt_editor)

                equalize_reference_height(reference, prompt_editor, width=320)
                show_text_widget(
                    reference,
                    width=320,
                    height=prompt_editor.height(),
                    text=syntax_text,
                    focused=True,
                )

                reference_cursor = reference.textCursor()
                reference_cursor.movePosition(QTextCursor.MoveOperation.End)
                reference.setTextCursor(reference_cursor)
                process_events(app)

                reference_image = widget_image(reference)
                prompt_background = pixel_rgba(
                    prompt_image,
                    prompt_image.width() - 20,
                    10,
                )
                reference_background = pixel_rgba(
                    reference_image,
                    reference_image.width() - 20,
                    10,
                )

                assert _first_ink_x(
                    prompt_image,
                    row=10,
                    background=prompt_background,
                ) == _first_ink_x(
                    reference_image,
                    row=10,
                    background=reference_background,
                )
                _assert_rgba_close(
                    pixel_rgba(prompt_image, 5, prompt_image.height() - 2),
                    pixel_rgba(reference_image, 5, reference_image.height() - 2),
                )
                _assert_rgba_close(
                    pixel_rgba(prompt_image, prompt_image.width() - 20, 10),
                    pixel_rgba(reference_image, reference_image.width() - 20, 10),
                )
            finally:
                _dispose_widgets(reference, prompt_editor)


def test_prompt_editor_overflow_scrollbar_geometry_matches_qfluent_reference() -> None:
    """Overflow state should keep the same visible scrollbar geometry as QFluent."""

    app = ensure_qapp()
    overflow_text = "\n".join(f"line {index}" for index in range(20))
    for theme in (Theme.LIGHT, Theme.DARK):
        with fluent_theme(theme):
            prompt_editor = create_prompt_editor()
            reference = create_reference_text_edit()
            try:
                show_text_widget(prompt_editor, width=320, text=overflow_text)
                equalize_reference_height(reference, prompt_editor, width=320)
                show_text_widget(
                    reference,
                    width=320,
                    height=prompt_editor.height(),
                    text=overflow_text,
                )
                process_events(app)

                prompt_scrollbar = prompt_editor.scrollDelegate.vScrollBar
                reference_scrollbar = reference.scrollDelegate.vScrollBar
                assert prompt_scrollbar.isVisible() is True
                assert reference_scrollbar.isVisible() is True
                assert (
                    prompt_scrollbar.geometry().width()
                    == reference_scrollbar.geometry().width()
                )
                assert (
                    prompt_scrollbar.geometry().height()
                    == reference_scrollbar.geometry().height()
                )
            finally:
                _dispose_widgets(reference, prompt_editor)


def test_prompt_editor_disabled_shell_pixels_match_qfluent_reference() -> None:
    """Disabled prompt shells should use the same background and border colors as QFluent."""

    app = ensure_qapp()
    for theme in (Theme.LIGHT, Theme.DARK):
        with fluent_theme(theme):
            prompt_editor = create_prompt_editor()
            reference = create_reference_text_edit()
            try:
                show_text_widget(
                    prompt_editor,
                    width=320,
                    text="alpha beta",
                    disabled=True,
                )
                prompt_image = widget_image(prompt_editor)

                equalize_reference_height(reference, prompt_editor, width=320)
                show_text_widget(
                    reference,
                    width=320,
                    height=prompt_editor.height(),
                    text="alpha beta",
                    disabled=True,
                )
                reference_image = widget_image(reference)

                _assert_rgba_close(
                    pixel_rgba(prompt_image, 10, 10),
                    pixel_rgba(reference_image, 10, 10),
                )
                _assert_rgba_close(
                    pixel_rgba(prompt_image, 5, prompt_image.height() - 2),
                    pixel_rgba(reference_image, 5, reference_image.height() - 2),
                )
                process_events(app)
            finally:
                _dispose_widgets(reference, prompt_editor)


def test_prompt_editor_hover_shell_pixels_match_qfluent_reference() -> None:
    """Hover-only state should use the same shell background tint as the QFluent host."""

    app = ensure_qapp()
    for theme in (Theme.LIGHT, Theme.DARK):
        with fluent_theme(theme):
            prompt_editor = create_prompt_editor()
            reference = create_reference_text_edit()
            try:
                show_text_widget(prompt_editor, width=320, text="alpha beta")
                QTest.mouseMove(prompt_editor, prompt_editor.rect().center())
                process_events(app)
                prompt_image = widget_image(prompt_editor)

                equalize_reference_height(reference, prompt_editor, width=320)
                show_text_widget(
                    reference,
                    width=320,
                    height=prompt_editor.height(),
                    text="alpha beta",
                )
                QTest.mouseMove(reference, reference.rect().center())
                process_events(app)
                reference_image = widget_image(reference)

                _assert_rgba_close(
                    pixel_rgba(prompt_image, prompt_image.width() - 20, 10),
                    pixel_rgba(reference_image, reference_image.width() - 20, 10),
                )
            finally:
                _dispose_widgets(reference, prompt_editor)


def test_prompt_editor_read_only_pixels_match_qfluent_reference() -> None:
    """Read-only prompt shells should keep the same plain-text presentation as QFluent."""

    app = ensure_qapp()
    for theme in (Theme.LIGHT, Theme.DARK):
        with fluent_theme(theme):
            prompt_editor = create_prompt_editor()
            reference = create_reference_text_edit()
            try:
                show_text_widget(
                    prompt_editor,
                    width=320,
                    text="alpha beta",
                    read_only=True,
                )
                prompt_image = widget_image(prompt_editor)

                equalize_reference_height(reference, prompt_editor, width=320)
                show_text_widget(
                    reference,
                    width=320,
                    height=prompt_editor.height(),
                    text="alpha beta",
                    read_only=True,
                )
                reference_image = widget_image(reference)

                _assert_rgba_close(
                    pixel_rgba(prompt_image, prompt_image.width() - 20, 10),
                    pixel_rgba(reference_image, reference_image.width() - 20, 10),
                )
                _assert_rgba_close(
                    pixel_rgba(prompt_image, 5, prompt_image.height() - 2),
                    pixel_rgba(reference_image, 5, reference_image.height() - 2),
                )
                process_events(app)
            finally:
                _dispose_widgets(reference, prompt_editor)

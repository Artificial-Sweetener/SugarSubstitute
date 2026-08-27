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

"""Test the Comfy output titlebar toggle contract."""

from __future__ import annotations

from collections.abc import Iterator

from PySide6.QtWidgets import QApplication
import pytest
from qframelesswindow.titlebar.title_bar_buttons import (  # type: ignore[import-untyped]
    TitleBarButtonState,
)

from substitute.presentation.shell.titlebar_buttons import ComfyOutputToggleButton
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.shell.window_frame import (
    SubstituteWindowFrame,
)
from tests.support.qt.lifecycle import ensure_qt_application


@pytest.fixture(scope="module", autouse=True)
def output_toggle_qt_application() -> Iterator[QApplication]:
    """Keep one worker-local Qt application alive for output-toggle tests."""

    application = ensure_qt_application()
    yield application


def _app() -> QApplication:
    """Return the shared QApplication used by frameless-window contract tests."""

    return ensure_qt_application()


def test_comfy_output_toggle_uses_window_console_app_icon() -> None:
    """The console toggle should use the vendored Fluent window console icon."""

    _app()
    button = ComfyOutputToggleButton()

    assert button._icon is AppIcon.WINDOW_CONSOLE_20_FILLED

    button.close()


def test_comfy_output_toggle_uses_qframeless_hover_backgrounds_when_checked() -> None:
    """Checked console hover and press backgrounds should follow TitleBarButton."""

    _app()
    button = ComfyOutputToggleButton()
    button.setChecked(True)

    button.setState(TitleBarButtonState.HOVER)
    assert button._background_color() == button.getHoverBackgroundColor()

    button.setState(TitleBarButtonState.PRESSED)
    assert button._background_color() == button.getPressedBackgroundColor()

    button.close()


def test_comfy_output_toggle_paints_hover_when_under_mouse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Console hover paint should survive missed qframeless enter transitions."""

    _app()
    button = ComfyOutputToggleButton()
    button.setState(TitleBarButtonState.NORMAL)
    monkeypatch.setattr(button, "underMouse", lambda: True)

    assert button._background_color() == button.getHoverBackgroundColor()

    button.close()


def test_shell_frame_styles_comfy_output_toggle_like_min_max_buttons() -> None:
    """The console toggle should use the same hover policy as min/max buttons."""

    _app()
    frame = SubstituteWindowFrame(
        create_menu_container=True,
        create_comfy_output_toggle=True,
    )
    assert frame.comfyOutputToggleButton is not None

    output_button = frame.comfyOutputToggleButton
    assert output_button.getHoverBackgroundColor() == (
        frame.titleBar.minBtn.getHoverBackgroundColor()
    )
    assert output_button.getPressedBackgroundColor() == (
        frame.titleBar.minBtn.getPressedBackgroundColor()
    )
    assert output_button.getNormalBackgroundColor() == (
        frame.titleBar.minBtn.getNormalBackgroundColor()
    )

    output_button.setChecked(True)
    output_button.setState(TitleBarButtonState.HOVER)
    assert output_button._background_color() == (
        frame.titleBar.minBtn.getHoverBackgroundColor()
    )

    output_button.setState(TitleBarButtonState.PRESSED)
    assert output_button._background_color() == (
        frame.titleBar.minBtn.getPressedBackgroundColor()
    )

    frame.close()

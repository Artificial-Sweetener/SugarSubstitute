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

"""Cover platform-specific bootstrap window integration."""

from __future__ import annotations

from typing import Any, cast

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.app.bootstrap import composition
from substitute.presentation.shell.window_effects import ShellBackdropMode
from tests.support.qt.lifecycle import destroy_widget_roots


def _ensure_runtime_qapplication() -> None:
    """Ensure platform integration tests have a real Qt application owner."""

    if QApplication.instance() is None:
        QApplication([])


def _noop_shutdown_request(_parent: QWidget | None = None) -> None:
    """Provide a typed no-op shell shutdown callback."""


def _destroy_qt_widgets(*widgets: QWidget) -> None:
    """Synchronously dispose test-owned Qt widgets."""

    destroy_widget_roots(widgets)


def test_custom_window_requests_mica_alt_without_frame_body_material(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The main shell should use Mica Alt without washing the menu row twice."""

    init_calls: list[dict[str, object]] = []

    def fake_frame_init(self: object, **kwargs: object) -> None:
        """Record shell-frame construction options without creating a real window."""

        _ = self
        init_calls.append(kwargs)

    monkeypatch.setattr(
        "substitute.app.bootstrap.composition.SubstituteWindowFrame.__init__",
        fake_frame_init,
    )

    window = composition.CustomWindow(
        appearance_runtime=cast(Any, object()),
        shutdown_request=_noop_shutdown_request,
    )

    assert window._shutdown_request is _noop_shutdown_request
    assert window._allow_direct_close is False
    assert init_calls == [
        {
            "create_menu_container": True,
            "create_comfy_output_toggle": True,
            "create_generation_action_cluster": True,
            "create_startup_diagnostics_button": True,
            "create_app_orb_menu": True,
            "backdrop_mode": ShellBackdropMode.MICA_ALT,
            "create_body_material_surface": False,
        }
    ]


def test_inactive_shell_requests_platform_attention_after_activation_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A visible but unfocused shell should request attention instead of stealing focus."""

    _ensure_runtime_qapplication()
    alerts: list[tuple[QWidget, int]] = []

    class _Frame(QWidget):
        """Expose a visible shell that the platform declined to activate."""

        def isActiveWindow(self) -> bool:
            """Report the denied foreground activation deterministically."""

            return False

    class _AttentionApplication:
        """Record the Qt platform-attention request."""

        @staticmethod
        def alert(widget: QWidget, milliseconds: int) -> None:
            """Record the widget and lifetime supplied to Qt."""

            alerts.append((widget, milliseconds))

    frame = _Frame()
    monkeypatch.setattr(
        "substitute.presentation.shell.window_attention.QApplication",
        _AttentionApplication,
    )

    composition._request_shell_attention_if_inactive(frame)

    assert alerts == [(frame, 0)]
    _destroy_qt_widgets(frame)

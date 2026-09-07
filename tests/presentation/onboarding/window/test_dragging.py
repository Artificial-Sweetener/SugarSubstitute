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

"""Verify one cohesive onboarding-window capability."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from PySide6.QtCore import QPointF, QEvent, Qt
from PySide6.QtGui import QMouseEvent

from substitute.presentation.onboarding.onboarding_controller import (
    OnboardingController,
)
from substitute.presentation.onboarding.onboarding_models import (
    OnboardingDraft,
    OnboardingFlowMode,
    OnboardingTargetMode,
)
from substitute.presentation.onboarding.onboarding_window import (
    OnboardingWindow,
)

from tests.support.qt.lifecycle import ensure_qt_application

from .controller_double import _FakeController


def test_onboarding_window_starts_drag_from_passive_surface(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Passive Mica-backed onboarding surfaces should initiate system drag."""

    ensure_qt_application()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
    )
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            _FakeController(draft, OnboardingFlowMode.FIRST_RUN),
        )
    )

    class _FakeHandle:
        def __init__(self) -> None:
            self.started = False

        def startSystemMove(self) -> None:
            self.started = True

    fake_handle = _FakeHandle()
    monkeypatch.setattr(window, "windowHandle", lambda: fake_handle)
    monkeypatch.setattr(window, "childAt", lambda _: window.identity_rail)
    mouse_press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(4.0, 4.0),
        QPointF(4.0, 4.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    handled = window.eventFilter(window.identity_rail, mouse_press)

    assert handled is True
    assert fake_handle.started is True
    window._emit_close_requested_on_close = False
    window.close()


def test_onboarding_window_does_not_start_drag_from_content_widgets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Content widgets should not drag even if the event arrives on a drag surface."""

    ensure_qt_application()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
    )
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            _FakeController(draft, OnboardingFlowMode.FIRST_RUN),
        )
    )

    class _FakeHandle:
        def __init__(self) -> None:
            self.started = False

        def startSystemMove(self) -> None:
            self.started = True

    fake_handle = _FakeHandle()
    monkeypatch.setattr(window, "windowHandle", lambda: fake_handle)
    monkeypatch.setattr(window, "childAt", lambda _: window.brand_bar.wordmark)
    label_center = window.brand_bar.wordmark.rect().center()
    label_point = window.brand_bar.wordmark.mapTo(window.identity_rail, label_center)
    mouse_press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(float(label_point.x()), float(label_point.y())),
        QPointF(float(label_point.x()), float(label_point.y())),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    handled = window.eventFilter(window.identity_rail, mouse_press)

    assert handled is False
    assert fake_handle.started is False
    window._emit_close_requested_on_close = False
    window.close()

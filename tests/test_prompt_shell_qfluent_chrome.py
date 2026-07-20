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

"""Cover prompt-editor QFluent chrome focus-transition ownership."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
import pytest

from substitute.presentation.editor.prompt_editor.shell.qfluent_chrome import (
    PromptShellQFluentChrome,
)


def test_active_window_focus_churn_does_not_clean_up_without_a_focus_widget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ignore unresolved focus loss caused by window activation routing."""

    cleanup_calls = _schedule_focus_cleanup(
        monkeypatch,
        focus_widget=None,
        reason=Qt.FocusReason.ActiveWindowFocusReason,
    )

    assert cleanup_calls == []


def test_mouse_focus_loss_cleans_up_without_a_focus_widget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Honor an intentional click-away even when Qt leaves focus unresolved."""

    cleanup_calls = _schedule_focus_cleanup(
        monkeypatch,
        focus_widget=None,
        reason=Qt.FocusReason.MouseFocusReason,
    )

    assert cleanup_calls == [True]


def test_editor_descendant_focus_does_not_clean_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep editor interactions while the projection surface owns focus."""

    projection_surface = cast(QWidget, object())
    cleanup_calls = _schedule_focus_cleanup(
        monkeypatch,
        focus_widget=projection_surface,
        reason=Qt.FocusReason.OtherFocusReason,
        owns_focus=lambda widget: widget is projection_surface,
    )

    assert cleanup_calls == []


def _schedule_focus_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    *,
    focus_widget: QWidget | None,
    reason: Qt.FocusReason,
    owns_focus: Callable[[QWidget], bool] = lambda _widget: False,
) -> list[bool]:
    """Resolve one deferred focus transition through the chrome owner."""

    module = __import__(
        "substitute.presentation.editor.prompt_editor.shell.qfluent_chrome",
        fromlist=("QApplication",),
    )
    monkeypatch.setattr(
        module,
        "QApplication",
        SimpleNamespace(focusWidget=lambda: focus_widget),
    )
    monkeypatch.setattr(
        module,
        "QTimer",
        SimpleNamespace(singleShot=lambda _delay, callback: callback()),
    )
    cleanup_calls: list[bool] = []
    host = cast(
        Any,
        SimpleNamespace(isAncestorOf=owns_focus),
    )
    chrome = PromptShellQFluentChrome(
        host=host,
        shell_viewport=cast(QWidget, object()),
        content_viewport=lambda: None,
        apply_host_placeholder=lambda _text: None,
        source_text=lambda: "",
        surface=lambda: None,
        shell_padding_fill_plane=lambda: None,
        fill_plane=lambda: None,
        sync_surface_scroll_metrics_from_host=lambda: None,
        update_backing_fill=lambda _rect: None,
        finish_pending_key_edit_block=lambda _reason: None,
        schedule_lora_metadata_catchup=lambda: None,
        handle_focus_out=lambda: cleanup_calls.append(True),
        handle_hide=lambda: None,
        handle_move=lambda: None,
        schedule_manual_height_layout_reapply=lambda: None,
        observes_manual_resize_bounds_viewport=lambda _watched: False,
        schedule_shell_geometry_sync=lambda: None,
        handle_viewport_wheel_event=lambda _event: False,
    )
    chrome.schedule_focus_out_cleanup(reason)
    return cleanup_calls

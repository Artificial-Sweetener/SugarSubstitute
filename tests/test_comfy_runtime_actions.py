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

"""Cover Comfy runtime shell actions outside MainWindow."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from substitute.domain.onboarding import ComfyEndpoint
from substitute.presentation.shell.comfy_runtime_actions import ComfyRuntimeActions


def test_output_panel_visibility_emits_and_autosaves_only_on_change() -> None:
    """Output panel visibility should emit and autosave only when state flips."""

    emitted: list[bool] = []
    autosaves: list[object] = []
    panel = _Panel()
    shell = _runtime_shell(
        comfy_output_panel=panel,
        comfy_output_panel_visibility_changed=SimpleNamespace(
            emit=lambda visible: emitted.append(visible)
        ),
        request_session_autosave=lambda: autosaves.append(object()),
    )

    actions = ComfyRuntimeActions(shell)
    actions.set_comfy_output_panel_visible(False)
    actions.set_comfy_output_panel_visible(True)
    actions.set_comfy_output_panel_visible(True)
    actions.set_comfy_output_panel_visible(False)

    assert emitted == [True, False]
    assert len(autosaves) == 2
    assert actions.is_comfy_output_panel_visible() is False


def test_restart_request_invokes_bootstrap_handler() -> None:
    """Comfy restart requests should delegate to the bootstrap-owned handler."""

    calls: list[object] = []
    shell = _runtime_shell(
        _comfy_restart_request_handler=lambda: calls.append(object())
    )

    ComfyRuntimeActions(shell).request_comfy_restart()

    assert len(calls) == 1


def test_missing_restart_handler_warns_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Comfy restart requests without a handler should fail closed with a warning."""

    warnings: list[tuple[object, str, str]] = []

    def warning(parent: object, title: str, message: str) -> None:
        """Record one warning dialog request."""

        warnings.append((parent, title, message))

    monkeypatch.setattr(
        "substitute.presentation.shell.comfy_runtime_actions.QMessageBox.warning",
        warning,
    )
    shell = _runtime_shell(_comfy_restart_request_handler=None)

    ComfyRuntimeActions(shell).request_comfy_restart()

    assert warnings == [
        (
            shell,
            "Restart ComfyUI",
            "ComfyUI restart is not available in this session.",
        )
    ]


def test_open_settings_webview_uses_current_connection_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Comfy Settings should open against the current configured endpoint."""

    endpoint = ComfyEndpoint(host="127.0.0.1", port=8188)
    opened: list[tuple[ComfyEndpoint, object]] = []
    dialog = object()

    def open_webview(*, endpoint: ComfyEndpoint, parent: object) -> object:
        """Record one Comfy Settings webview request."""

        opened.append((endpoint, parent))
        return dialog

    monkeypatch.setattr(
        "substitute.presentation.shell.comfy_runtime_actions."
        "comfy_settings_webview.WEBENGINE_AVAILABLE",
        True,
    )
    monkeypatch.setattr(
        "substitute.presentation.shell.comfy_runtime_actions."
        "comfy_settings_webview.open_comfy_settings_webview",
        open_webview,
    )
    shell = _runtime_shell(
        comfy_connection_settings_service=SimpleNamespace(
            load_snapshot=lambda: SimpleNamespace(
                target=SimpleNamespace(endpoint=endpoint)
            )
        )
    )

    ComfyRuntimeActions(shell).open_comfyui_settings_webview()

    assert opened == [(endpoint, shell)]
    assert shell._comfy_settings_webview_dialog is dialog


def test_open_settings_webview_warns_when_webengine_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Comfy Settings should not try to open when Qt WebEngine is unavailable."""

    warnings: list[tuple[object, str, str]] = []
    unavailable_logs: list[object] = []

    def warning(parent: object, title: str, message: str) -> None:
        """Record one warning dialog request."""

        warnings.append((parent, title, message))

    monkeypatch.setattr(
        "substitute.presentation.shell.comfy_runtime_actions."
        "comfy_settings_webview.WEBENGINE_AVAILABLE",
        False,
    )
    monkeypatch.setattr(
        "substitute.presentation.shell.comfy_runtime_actions."
        "comfy_settings_webview.log_webengine_unavailable",
        lambda: unavailable_logs.append(object()),
    )
    monkeypatch.setattr(
        "substitute.presentation.shell.comfy_runtime_actions.QMessageBox.warning",
        warning,
    )
    shell = _runtime_shell()

    ComfyRuntimeActions(shell).open_comfyui_settings_webview()

    assert len(unavailable_logs) == 1
    assert warnings == [
        (
            shell,
            "ComfyUI Settings",
            "Qt WebEngine is not available, so ComfyUI Settings cannot open here.",
        )
    ]


def test_open_settings_webview_failure_warns_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Comfy Settings webview failures should be reported without escaping."""

    warnings: list[tuple[object, str, str]] = []

    def warning(parent: object, title: str, message: str) -> None:
        """Record one warning dialog request."""

        warnings.append((parent, title, message))

    def fail_open_webview(*, endpoint: ComfyEndpoint, parent: object) -> object:
        """Raise one representative webview startup failure."""

        _ = endpoint, parent
        raise RuntimeError("webengine failed")

    monkeypatch.setattr(
        "substitute.presentation.shell.comfy_runtime_actions."
        "comfy_settings_webview.WEBENGINE_AVAILABLE",
        True,
    )
    monkeypatch.setattr(
        "substitute.presentation.shell.comfy_runtime_actions."
        "comfy_settings_webview.open_comfy_settings_webview",
        fail_open_webview,
    )
    monkeypatch.setattr(
        "substitute.presentation.shell.comfy_runtime_actions.QMessageBox.warning",
        warning,
    )
    shell = _runtime_shell()

    ComfyRuntimeActions(shell).open_comfyui_settings_webview()

    assert warnings == [
        (
            shell,
            "ComfyUI Settings",
            "ComfyUI Settings could not be opened in the embedded webview.",
        )
    ]
    assert shell._comfy_settings_webview_dialog is None


class _Panel:
    """Record output-panel visibility changes."""

    def __init__(self) -> None:
        """Initialize hidden panel state."""

        self.visible = False

    def is_panel_visible(self) -> bool:
        """Return current panel visibility."""

        return self.visible

    def set_panel_visible(self, visible: bool) -> None:
        """Set current panel visibility."""

        self.visible = visible


def _runtime_shell(**overrides: object) -> SimpleNamespace:
    """Build a shell fake with default Comfy runtime collaborators."""

    endpoint = ComfyEndpoint(host="127.0.0.1", port=8188)
    values: dict[str, object] = {
        "comfy_output_panel": _Panel(),
        "comfy_output_panel_visibility_changed": SimpleNamespace(
            emit=lambda _visible: None
        ),
        "request_session_autosave": lambda: None,
        "_comfy_restart_request_handler": None,
        "comfy_connection_settings_service": SimpleNamespace(
            load_snapshot=lambda: SimpleNamespace(
                target=SimpleNamespace(endpoint=endpoint)
            )
        ),
        "_comfy_settings_webview_dialog": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)

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

"""Verify startup checks only the default ComfyUI endpoint."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from qfluentwidgets import Dialog  # type: ignore[import-untyped]

from substitute.app.bootstrap import default_comfy_preflight
from substitute.domain.onboarding import LocalComfyProcess, LocalComfyTerminationResult
from tests.support.qt.lifecycle import ensure_qt_application


def test_preflight_continues_without_default_port_comfy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No process scan or dialog is needed when 127.0.0.1:8188 is absent."""

    probes: list[tuple[str, int]] = []

    def report_absent(host: str, port: int) -> bool:
        """Record the sole endpoint probe and report it absent."""

        probes.append((host, port))
        return False

    monkeypatch.setattr(
        default_comfy_preflight,
        "is_endpoint_listening",
        report_absent,
    )
    monkeypatch.setattr(
        default_comfy_preflight,
        "_verified_listener_process",
        lambda: pytest.fail("Custom-port processes must not be scanned."),
    )

    assert default_comfy_preflight.negotiate_default_comfy_listener() is True
    assert probes == [("127.0.0.1", 8188)]


def test_preflight_configures_theme_only_when_a_dialog_can_be_shown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A deferred startup theme must be applied before showing Fluent UI."""

    configured: list[bool] = []
    monkeypatch.setattr(
        default_comfy_preflight, "is_endpoint_listening", lambda _host, _port: True
    )
    monkeypatch.setattr(
        default_comfy_preflight, "_verified_listener_process", lambda: None
    )
    monkeypatch.setattr(
        default_comfy_preflight, "_show_manual_close_required", lambda: None
    )

    assert (
        default_comfy_preflight.negotiate_default_comfy_listener(
            ensure_theme=lambda: configured.append(True)
        )
        is False
    )
    assert configured == [True]


def test_preflight_closes_only_the_verified_default_port_process(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An approved shutdown must target only the listener identity shown to the user."""

    process = LocalComfyProcess(
        pid=123,
        create_time=456.0,
        python_executable=tmp_path / "python.exe",
        workspace=tmp_path / "ComfyUI",
    )
    terminated: list[tuple[LocalComfyProcess, ...]] = []

    def terminate(
        processes: tuple[LocalComfyProcess, ...],
    ) -> LocalComfyTerminationResult:
        """Record the exact approved process identity."""

        terminated.append(processes)
        return LocalComfyTerminationResult((123,), (123,), (), ())

    gateway = SimpleNamespace(
        terminate=terminate,
    )
    monkeypatch.setattr(
        default_comfy_preflight,
        "is_endpoint_listening",
        lambda host, port: (host, port) == ("127.0.0.1", 8188),
    )
    monkeypatch.setattr(
        default_comfy_preflight, "_verified_listener_process", lambda: process
    )
    monkeypatch.setattr(
        default_comfy_preflight, "_confirm_close_comfy", lambda candidate: True
    )
    monkeypatch.setattr(
        default_comfy_preflight,
        "PsutilLocalComfyProcessGateway",
        lambda: gateway,
    )

    assert default_comfy_preflight.negotiate_default_comfy_listener() is True
    assert terminated == [(process,)]


def test_preflight_never_terminates_an_unverified_listener(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Comfy response without exact process identity requires manual closure."""

    warnings: list[bool] = []
    monkeypatch.setattr(
        default_comfy_preflight, "is_endpoint_listening", lambda _host, _port: True
    )
    monkeypatch.setattr(
        default_comfy_preflight, "_verified_listener_process", lambda: None
    )
    monkeypatch.setattr(
        default_comfy_preflight,
        "_show_manual_close_required",
        lambda: warnings.append(True),
    )
    monkeypatch.setattr(
        default_comfy_preflight,
        "PsutilLocalComfyProcessGateway",
        lambda: pytest.fail("Unverified processes must never be terminated."),
    )

    assert default_comfy_preflight.negotiate_default_comfy_listener() is False
    assert warnings == [True]


def test_verified_listener_inspects_only_the_exact_default_port_pid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Process discovery must inspect the 8188 listener instead of scanning all Comfys."""

    process = LocalComfyProcess(
        pid=8188,
        create_time=1.0,
        python_executable=tmp_path / "python.exe",
        workspace=tmp_path / "ComfyUI",
    )
    inspected: list[int] = []

    def inspect(pid: int) -> LocalComfyProcess:
        """Record the exact listener PID selected for verification."""

        inspected.append(pid)
        return process

    gateway = SimpleNamespace(
        inspect=inspect,
    )
    monkeypatch.setattr(
        default_comfy_preflight, "get_listener_pid", lambda _h, _p: 8188
    )
    monkeypatch.setattr(
        default_comfy_preflight,
        "PsutilLocalComfyProcessGateway",
        lambda: gateway,
    )

    assert default_comfy_preflight._verified_listener_process() is process
    assert inspected == [8188]


def test_default_comfy_dialog_uses_fluent_controls_with_safe_defaults(
    tmp_path: Path,
) -> None:
    """Use Fluent controls while making the destructive choice explicit."""

    _ = ensure_qt_application()
    process = LocalComfyProcess(
        pid=123,
        create_time=1.0,
        python_executable=tmp_path / "python.exe",
        workspace=tmp_path / "ComfyUI",
    )

    dialog = default_comfy_preflight._build_default_comfy_dialog(process)

    assert isinstance(dialog, Dialog)
    assert dialog.objectName() == "defaultComfyConflictDialog"
    assert dialog.yesButton.isDefault()
    assert dialog.yesButton.text() == "Close ComfyUI and continue"
    assert dialog.cancelButton.text() == "Cancel"
    assert "8188" in dialog.contentLabel.text()
    assert dialog.property("verifiedComfyWorkspace") == str(process.workspace)

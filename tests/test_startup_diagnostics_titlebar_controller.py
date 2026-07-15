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

"""Tests for the startup diagnostics titlebar controller."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
import pytest

from substitute.application.comfy_startup_diagnostics import (
    StartupDiagnosticsTitlebarState,
    render_startup_diagnostics_report,
)
from substitute.domain.comfy_startup_diagnostics import (
    ComfyStartupIncident,
    ComfyStartupIncidentKind,
    ComfyStartupIncidentSeverity,
)
from substitute.presentation.shell.startup_diagnostics_titlebar_controller import (
    StartupDiagnosticsTitlebarController,
)
from substitute.presentation.shell.titlebar_buttons import (
    StartupDiagnosticsTitleBarButton,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "titlebar controller Qt tests require non-xdist execution",
        allow_module_level=True,
    )


class _Callout:
    """Callout double recording show and dismiss requests."""

    def __init__(self) -> None:
        """Initialize recorded calls."""

        self.shown: list[tuple[QWidget, str, bool]] = []
        self.dismiss_count = 0

    def show_for(self, anchor: QWidget, message: str, *, has_errors: bool) -> None:
        """Record one anchored callout display."""

        self.shown.append((anchor, message, has_errors))

    def dismiss(self) -> None:
        """Record one callout dismiss request."""

        self.dismiss_count += 1


class _IgnoreRepository:
    """Ignore repository double."""

    def __init__(self, fingerprints: frozenset[str] = frozenset()) -> None:
        """Store initial ignored fingerprints."""

        self._fingerprints = fingerprints
        self.saved: list[frozenset[str]] = []

    def load_ignored_fingerprints(self) -> frozenset[str]:
        """Return current ignored fingerprints."""

        return self._fingerprints

    def save_ignored_fingerprints(self, fingerprints: frozenset[str]) -> None:
        """Record and store updated ignored fingerprints."""

        self.saved.append(fingerprints)
        self._fingerprints = fingerprints


def _app() -> QApplication:
    """Return the shared QApplication used by controller tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def test_controller_hides_button_for_empty_state() -> None:
    """Setting no diagnostics state should collapse the titlebar button."""

    _app()
    parent = QWidget()
    button = StartupDiagnosticsTitleBarButton(parent)
    callout = _Callout()
    controller = StartupDiagnosticsTitlebarController(
        button=button,
        parent=parent,
        ignore_repository=_IgnoreRepository(),
        callout=callout,
    )

    controller.set_state(None)

    assert button.is_collapsed() is True
    assert callout.dismiss_count == 1

    parent.close()


def test_controller_updates_button_and_shows_first_callout() -> None:
    """Visible diagnostics should update the button and show the callout once."""

    _app()
    parent = QWidget()
    button = StartupDiagnosticsTitleBarButton(parent)
    callout = _Callout()
    controller = StartupDiagnosticsTitlebarController(
        button=button,
        parent=parent,
        ignore_repository=_IgnoreRepository(),
        callout=callout,
    )
    state = _state((_incident("a", ComfyStartupIncidentSeverity.ERROR),))

    controller.set_state(state)
    QTest.qWait(200)
    _app().processEvents()
    controller.set_state(state)

    assert button.count() == 1
    assert button.has_errors() is True
    assert button.is_collapsed() is False
    assert callout.shown == [(button, "ComfyUI reported errors during startup", True)]

    parent.close()


def test_controller_uses_warning_callout_for_warning_only_state() -> None:
    """Warning-only diagnostics should use warning callout copy."""

    _app()
    parent = QWidget()
    button = StartupDiagnosticsTitleBarButton(parent)
    callout = _Callout()
    controller = StartupDiagnosticsTitlebarController(
        button=button,
        parent=parent,
        ignore_repository=_IgnoreRepository(),
        callout=callout,
    )

    controller.set_state(
        _state((_incident("w", ComfyStartupIncidentSeverity.WARNING),))
    )
    QTest.qWait(200)
    _app().processEvents()

    assert button.has_errors() is False
    assert callout.shown == [
        (button, "ComfyUI reported warnings during startup", False)
    ]

    parent.close()


def test_controller_waits_for_button_expansion_before_callout() -> None:
    """Callout should wait until the titlebar button reports final geometry."""

    app = _app()
    parent = QWidget()
    button = StartupDiagnosticsTitleBarButton(parent)
    callout = _Callout()
    controller = StartupDiagnosticsTitlebarController(
        button=button,
        parent=parent,
        ignore_repository=_IgnoreRepository(),
        callout=callout,
    )

    controller.set_state(_state((_incident("a", ComfyStartupIncidentSeverity.ERROR),)))

    assert callout.shown == []

    QTest.qWait(200)
    app.processEvents()

    assert callout.shown == [(button, "ComfyUI reported errors during startup", True)]

    parent.close()


def test_controller_opens_dialog_from_button_click_without_ignores() -> None:
    """Clicking the titlebar button should open the diagnostics dialog factory."""

    app = _app()
    parent = QWidget()
    button = StartupDiagnosticsTitleBarButton(parent)
    callout = _Callout()
    opened: list[StartupDiagnosticsTitlebarState] = []
    state = _state((_incident("a", ComfyStartupIncidentSeverity.ERROR),))

    controller = StartupDiagnosticsTitlebarController(
        button=button,
        parent=parent,
        ignore_repository=_IgnoreRepository(),
        callout=callout,
        dialog_factory=_dialog_factory(opened, frozenset()),
    )
    controller.set_state(state)
    QTest.qWait(200)
    app.processEvents()

    QTest.mouseClick(button, Qt.MouseButton.LeftButton)

    assert opened == [state]
    assert button.is_collapsed() is False
    assert callout.dismiss_count == 1

    parent.close()


def test_controller_ignoring_some_incidents_updates_count() -> None:
    """Selected ignores should persist and leave remaining incidents visible."""

    _app()
    parent = QWidget()
    button = StartupDiagnosticsTitleBarButton(parent)
    callout = _Callout()
    repository = _IgnoreRepository(frozenset({"existing"}))
    first = _incident("a", ComfyStartupIncidentSeverity.ERROR)
    second = _incident("b", ComfyStartupIncidentSeverity.WARNING)
    controller = StartupDiagnosticsTitlebarController(
        button=button,
        parent=parent,
        ignore_repository=repository,
        callout=callout,
        dialog_factory=_dialog_factory([], frozenset({first.fingerprint})),
    )

    controller.set_state(_state((first, second), ignored_count=2))
    controller.open_dialog()

    assert repository.saved == [frozenset({"existing", first.fingerprint})]
    assert button.count() == 1
    assert button.has_errors() is False
    assert button.is_collapsed() is False

    parent.close()


def test_controller_ignoring_all_incidents_hides_button() -> None:
    """Ignoring every visible incident should collapse the titlebar button."""

    _app()
    parent = QWidget()
    button = StartupDiagnosticsTitleBarButton(parent)
    callout = _Callout()
    incident = _incident("a", ComfyStartupIncidentSeverity.ERROR)
    controller = StartupDiagnosticsTitlebarController(
        button=button,
        parent=parent,
        ignore_repository=_IgnoreRepository(),
        callout=callout,
        dialog_factory=_dialog_factory([], frozenset({incident.fingerprint})),
    )

    controller.set_state(_state((incident,)))
    controller.open_dialog()

    assert button.is_collapsed() is True
    assert callout.dismiss_count == 2

    parent.close()


def test_controller_dialog_state_contains_transcript_and_enriched_values() -> None:
    """Dialog factory state should retain reportable transcript and metadata fields."""

    _app()
    parent = QWidget()
    button = StartupDiagnosticsTitleBarButton(parent)
    incident = _incident(
        "a",
        ComfyStartupIncidentSeverity.ERROR,
        values={"repository_url": "https://github.com/example/a"},
    )
    opened: list[StartupDiagnosticsTitlebarState] = []
    controller = StartupDiagnosticsTitlebarController(
        button=button,
        parent=parent,
        ignore_repository=_IgnoreRepository(),
        callout=_Callout(),
        dialog_factory=_dialog_factory(opened, frozenset()),
    )

    controller.set_state(_state((incident,), transcript=("startup line",)))
    controller.open_dialog()

    report = render_startup_diagnostics_report(
        opened[0].incidents,
        transcript=opened[0].transcript,
    )
    assert "Repository: https://github.com/example/a" in report
    assert "startup line" in report

    parent.close()


def _dialog_factory(
    opened: list[StartupDiagnosticsTitlebarState],
    selected: frozenset[str],
) -> Callable[[QWidget, StartupDiagnosticsTitlebarState], frozenset[str]]:
    """Return a dialog factory double that records opened state."""

    def factory(
        _parent: QWidget,
        state: StartupDiagnosticsTitlebarState,
    ) -> frozenset[str]:
        """Record state and return configured selected ignores."""

        opened.append(state)
        return selected

    return factory


def _state(
    incidents: tuple[ComfyStartupIncident, ...],
    *,
    ignored_count: int = 0,
    transcript: tuple[str, ...] = (),
) -> StartupDiagnosticsTitlebarState:
    """Return titlebar state for controller tests."""

    return StartupDiagnosticsTitlebarState(
        incidents=incidents,
        ignored_count=ignored_count,
        transcript=transcript,
    )


def _incident(
    name: str,
    severity: ComfyStartupIncidentSeverity,
    *,
    values: dict[str, object] | None = None,
) -> ComfyStartupIncident:
    """Return one deterministic startup incident."""

    return ComfyStartupIncident(
        kind=ComfyStartupIncidentKind.CUSTOM_NODE_IMPORT_FAILED,
        severity=severity,
        title="Extension failed to load",
        message="startup issue",
        source=name,
        fingerprint=f"fingerprint-{name}",
        values=values or {},
    )

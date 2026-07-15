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

"""Coordinate startup diagnostics titlebar indicator behavior."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PySide6.QtWidgets import QWidget

from substitute.application.comfy_startup_diagnostics import (
    StartupDiagnosticsTitlebarState,
    render_startup_diagnostics_report,
)
from substitute.application.ports.startup_diagnostics_ignore_repository import (
    StartupDiagnosticsIgnoreRepository,
)
from substitute.presentation.shell.startup_diagnostics_callout import (
    StartupDiagnosticsCallout,
    startup_diagnostics_callout_message,
)
from substitute.presentation.shell.titlebar_buttons import (
    StartupDiagnosticsTitleBarButton,
)


class _SignalLike(Protocol):
    """Describe a Qt-like signal used by titlebar controller tests."""

    def connect(self, callback: object) -> None:
        """Connect one callback to the signal."""


class _StartupDiagnosticsButton(Protocol):
    """Describe the titlebar button surface controlled here."""

    activated: _SignalLike
    expanded: _SignalLike

    def set_count(self, count: int, *, has_errors: bool) -> None:
        """Update count and severity treatment."""

    def set_collapsed(self, collapsed: bool, *, animated: bool = True) -> None:
        """Show or hide the button through its titlebar collapse behavior."""


class _StartupDiagnosticsCallout(Protocol):
    """Describe the speech-bubble surface controlled here."""

    def show_for(self, anchor: QWidget, message: str, *, has_errors: bool) -> None:
        """Show a message aimed at the titlebar anchor."""

    def dismiss(self) -> None:
        """Hide the callout."""


DialogFactory = Callable[[QWidget, StartupDiagnosticsTitlebarState], frozenset[str]]


class StartupDiagnosticsTitlebarController:
    """Coordinate startup diagnostics titlebar indicator and modal presentation."""

    def __init__(
        self,
        *,
        button: StartupDiagnosticsTitleBarButton,
        parent: QWidget,
        ignore_repository: StartupDiagnosticsIgnoreRepository,
        callout: _StartupDiagnosticsCallout | None = None,
        dialog_factory: DialogFactory | None = None,
    ) -> None:
        """Store titlebar dependencies and connect button activation."""

        self._button: _StartupDiagnosticsButton = button
        self._button_widget = button
        self._parent = parent
        self._ignore_repository = ignore_repository
        self._callout = callout or StartupDiagnosticsCallout(parent)
        self._dialog_factory = dialog_factory or _present_dialog
        self._state: StartupDiagnosticsTitlebarState | None = None
        self._callout_fingerprint_set: frozenset[str] | None = None
        self._pending_callout_fingerprint_set: frozenset[str] | None = None
        self._pending_callout_message = ""
        self._pending_callout_has_errors = False
        self._button.activated.connect(self.open_dialog)
        self._button.expanded.connect(self._show_pending_callout)
        self._button.set_collapsed(True, animated=False)

    def set_state(self, state: StartupDiagnosticsTitlebarState | None) -> None:
        """Apply new startup diagnostics state to the titlebar indicator."""

        self._state = state
        if state is None or state.total_count == 0:
            self._clear_pending_callout()
            self._callout.dismiss()
            self._button.set_collapsed(True)
            return

        self._button.set_count(state.total_count, has_errors=state.has_errors)
        self._button.set_collapsed(False)
        if state.fingerprint_set != self._callout_fingerprint_set:
            self._callout_fingerprint_set = state.fingerprint_set
            self._prepare_callout(state)

    def open_dialog(self) -> None:
        """Open the startup diagnostics modal for the current state."""

        state = self._state
        if state is None or state.total_count == 0:
            return
        self._clear_pending_callout()
        self._callout.dismiss()
        self._callout_fingerprint_set = state.fingerprint_set
        selected = self._dialog_factory(self._parent, state)
        if not selected:
            return
        ignored_fingerprints = self._ignore_repository.load_ignored_fingerprints()
        self._ignore_repository.save_ignored_fingerprints(
            ignored_fingerprints | selected
        )
        remaining = tuple(
            incident
            for incident in state.incidents
            if incident.fingerprint not in selected
        )
        if not remaining:
            self.set_state(None)
            return
        self.set_state(
            StartupDiagnosticsTitlebarState(
                incidents=remaining,
                ignored_count=state.ignored_count
                + len(state.incidents)
                - len(remaining),
                transcript=state.transcript,
            )
        )

    def _prepare_callout(self, state: StartupDiagnosticsTitlebarState) -> None:
        """Queue the callout until the titlebar button has finished expanding."""

        self._pending_callout_fingerprint_set = state.fingerprint_set
        self._pending_callout_message = startup_diagnostics_callout_message(
            has_errors=state.has_errors
        )
        self._pending_callout_has_errors = state.has_errors
        if self._button_widget.width() >= self._button_widget.visible_width:
            self._show_pending_callout()

    def _show_pending_callout(self) -> None:
        """Show the queued callout when its diagnostics state is still current."""

        state = self._state
        if (
            state is None
            or self._pending_callout_fingerprint_set is None
            or state.fingerprint_set != self._pending_callout_fingerprint_set
        ):
            return
        message = self._pending_callout_message
        has_errors = self._pending_callout_has_errors
        self._clear_pending_callout()
        self._callout.show_for(self._button_widget, message, has_errors=has_errors)

    def _clear_pending_callout(self) -> None:
        """Cancel any callout waiting for button expansion."""

        self._pending_callout_fingerprint_set = None
        self._pending_callout_message = ""
        self._pending_callout_has_errors = False


def _present_dialog(
    parent: QWidget,
    state: StartupDiagnosticsTitlebarState,
) -> frozenset[str]:
    """Present the startup diagnostics modal and return selected ignores."""

    from substitute.presentation.dialogs.startup_diagnostics_dialog import (
        StartupDiagnosticsDialog,
    )

    dialog = StartupDiagnosticsDialog(
        incidents=state.incidents,
        report_text=render_startup_diagnostics_report(
            state.incidents,
            transcript=state.transcript,
        ),
        ignored_count=state.ignored_count,
        parent=parent,
    )
    result = dialog.exec()
    selected = dialog.selected_ignored_fingerprints()
    dialog.deleteLater()
    return selected if result and selected else frozenset()


__all__ = ["DialogFactory", "StartupDiagnosticsTitlebarController"]

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

"""Verify active-shell adaptation for terminal session finalization."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from substitute.app.bootstrap.shell_session_finalization_adapter import (
    ShellSessionFinalizationAdapter,
)
from substitute.application.workspace_state import (
    PreparedSessionSave,
    SessionFinalizationReason,
)


def test_shutdown_uses_exact_requesting_shell_over_mutable_current_state() -> None:
    """Keep close finalization bound to the shell supplied by closeEvent."""

    current_shell = object()
    source_shell = object()
    prepared = cast(PreparedSessionSave, object())
    reasons: list[SessionFinalizationReason] = []

    def prepare(reason: SessionFinalizationReason) -> PreparedSessionSave:
        """Record and return exact-source preparation."""

        reasons.append(reason)
        return prepared

    controller = SimpleNamespace(
        prepare_session_finalization=prepare,
        begin_session_finalization=lambda _reason: object(),
    )
    source_window = SimpleNamespace(session_autosave_controller=controller)
    adapter = ShellSessionFinalizationAdapter(
        current_shell=lambda: current_shell,
        main_window_for_shell=lambda shell: (
            source_window if shell is source_shell else None
        ),
    )

    result = adapter.prepare_shutdown(source_shell)

    assert result is prepared
    assert reasons == [SessionFinalizationReason.SHUTDOWN]


def test_app_level_shutdown_falls_back_to_current_shell() -> None:
    """Resolve current shell when application quit has no source widget."""

    current_shell = object()
    prepared = cast(PreparedSessionSave, object())
    controller = SimpleNamespace(
        prepare_session_finalization=lambda _reason: prepared,
        begin_session_finalization=lambda _reason: object(),
    )
    current_window = SimpleNamespace(session_autosave_controller=controller)
    resolved_shells: list[object] = []

    def main_window_for_shell(shell: object) -> object:
        """Record current-shell fallback resolution."""

        resolved_shells.append(shell)
        return current_window

    adapter = ShellSessionFinalizationAdapter(
        current_shell=lambda: current_shell,
        main_window_for_shell=main_window_for_shell,
    )

    assert adapter.prepare_shutdown(None) is prepared
    assert resolved_shells == [current_shell]

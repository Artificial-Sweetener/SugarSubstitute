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

"""Provide typed restore-lifecycle doubles for ready-shell tests."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

import pytest

from substitute.app.bootstrap import ready_shell_restore_controller


class _Timer:
    """Record startup timer marks."""

    def __init__(self, calls: list[str]) -> None:
        """Store call records."""

        self._calls = calls

    def mark(self, name: str) -> None:
        """Record one timer mark."""

        self._calls.append(f"mark:{name}")


class _PhaseTimer:
    """Record startup timer phases."""

    def __init__(self, calls: list[str]) -> None:
        """Store call records."""

        self._calls = calls

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        """Record phase entry and exit."""

        self._calls.append(f"phase:start:{name}")
        try:
            yield
        finally:
            self._calls.append(f"phase:end:{name}")


class _MainWindow:
    """Expose shell restore collaborators for hydration tests."""

    def __init__(
        self,
        *,
        workspace_restore_controller: object | None,
        prehydrated_restore_controller: object | None,
    ) -> None:
        """Store controller doubles."""

        self.workspace_restore_controller = workspace_restore_controller
        self.shell_prehydrated_restore_controller = prehydrated_restore_controller


class _WorkspaceRestoreController:
    """Record workspace hydration requests."""

    def __init__(self, calls: list[str], *, prehydrate_result: bool = True) -> None:
        """Store call records."""

        self._calls = calls
        self._prehydrate_result = prehydrate_result

    def prehydrate_initial_workspace(self, workspace: object) -> bool:
        """Record a prehydration request."""

        self._calls.append(f"prehydrate:{id(workspace)}")
        return self._prehydrate_result

    def hydrate_initial_workspace(self, workspace: object | None = None) -> None:
        """Record a full hydration request."""

        if workspace is None:
            self._calls.append("hydrate:blank")
            return
        self._calls.append(f"hydrate:{id(workspace)}")


class _PrehydratedRestoreController:
    """Record prehydrated restore finalization requests."""

    def __init__(
        self,
        calls: list[str],
        *,
        prepare_runtime_error: Exception | None = None,
        finish_layout_result: bool = True,
        finalization_pending: bool = False,
    ) -> None:
        """Store behavior flags and call records."""

        self._calls = calls
        self._prepare_runtime_error = prepare_runtime_error
        self._finish_layout_result = finish_layout_result
        self._finalization_pending = finalization_pending

    def prepare_initial_workspace_restore_runtime(self) -> bool:
        """Record restore-runtime preparation."""

        self._calls.append("prepare_runtime")
        if self._prepare_runtime_error is not None:
            raise self._prepare_runtime_error
        return True

    def finalize_initial_workspace_restore(self, workspace: object | None) -> None:
        """Record finalization for one workspace."""

        self._calls.append(f"finalize:{id(workspace)}")

    def finish_initial_workspace_restore_layout(self) -> bool:
        """Record restore-layout finishing."""

        self._calls.append("finish_layout")
        return self._finish_layout_result

    def restore_layout_finalization_pending(self) -> bool:
        """Return whether restore layout finalization is pending."""

        return self._finalization_pending


def _patch_trace(
    monkeypatch: pytest.MonkeyPatch,
    events: list[tuple[str, dict[str, object]]],
) -> None:
    """Patch trace recording for deterministic assertions."""

    def trace(event_name: str, **fields: object) -> None:
        """Record one trace event."""

        events.append((event_name, fields))

    monkeypatch.setattr(ready_shell_restore_controller, "trace_mark", trace)


def _clock(*values: float) -> Callable[[], float]:
    """Return one callable clock from fixed values."""

    iterator = iter(values)
    return iterator.__next__

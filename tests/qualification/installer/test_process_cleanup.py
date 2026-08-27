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

"""Qualify native owned-process cleanup boundaries."""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace

import pytest

from tools.ci import installer_ui_qualification
from tools.ci.installer_ui_qualification import (
    terminate_verified_process,
)


def test_verified_process_cleanup_accepts_an_already_exited_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A child-exit race must not fail cleanup after the verified root is gone."""

    monkeypatch.setattr(
        "tools.ci.installer_ui_qualification.os.name",
        "nt",
    )
    monkeypatch.setattr(
        "tools.ci.installer_ui_qualification.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1,
            stderr=b"child already exited",
        ),
    )
    monkeypatch.setattr(
        "tools.ci.installer_ui_qualification._windows_process_exists",
        lambda _pid: False,
    )

    terminate_verified_process(5678)


def test_posix_verified_process_cleanup_waits_then_kills_only_owned_tree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Historical cleanup must finish before the updater starts its next launch."""

    events: list[tuple[str, int]] = []

    class _Process:
        """Record cleanup operations for one owned process."""

        def __init__(self, pid: int, children: tuple[_Process, ...] = ()) -> None:
            """Store the deterministic process tree."""

            self.pid = pid
            self._children = children

        def children(self, *, recursive: bool) -> list[_Process]:
            """Return the owned descendants requested by qualification."""

            assert recursive is True
            return list(self._children)

        def terminate(self) -> None:
            """Record a graceful termination request."""

            events.append(("terminate", self.pid))

        def kill(self) -> None:
            """Record a forced termination after the grace period."""

            events.append(("kill", self.pid))

    child = _Process(5679)
    root = _Process(5678, (child,))
    waits: list[tuple[tuple[int, ...], float]] = []
    wait_results: Iterator[tuple[list[_Process], list[_Process]]] = iter(
        (
            ([], [child, root]),
            ([child, root], []),
        )
    )

    def _wait_procs(
        processes: tuple[_Process, ...] | list[_Process],
        *,
        timeout: float,
    ) -> tuple[list[_Process], list[_Process]]:
        """Record bounded reaping and return the configured liveness state."""

        waits.append((tuple(process.pid for process in processes), timeout))
        return next(wait_results)

    monkeypatch.setattr(
        "tools.ci.installer_ui_qualification.psutil.Process",
        lambda pid: root if pid == root.pid else None,
    )
    monkeypatch.setattr(
        "tools.ci.installer_ui_qualification.psutil.wait_procs",
        _wait_procs,
    )

    installer_ui_qualification._terminate_posix_process_tree(root.pid)

    assert events == [
        ("terminate", child.pid),
        ("terminate", root.pid),
        ("kill", child.pid),
        ("kill", root.pid),
    ]
    assert waits == [
        ((child.pid, root.pid), 5.0),
        ((child.pid, root.pid), 5.0),
    ]

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

"""Verify semantic reliability governance for test-owned support tools."""

from __future__ import annotations

import ast
from pathlib import Path

from tools.test_governance.discovery import discover_test_candidates
from tools.test_governance.loading import load_test_policy
from tools.test_governance.network_resource_patterns import (
    PORT_HANDOFF_RULE,
    closed_ephemeral_port_candidates,
)
from tools.test_governance.semantic_patterns import DRAIN_RULE

from .support import write, write_fixture


def test_discovery_rejects_manual_qt_event_polling_in_test_support_roots(
    tmp_path: Path,
) -> None:
    """Test-owned tools must use bounded owner conditions instead of manual pumps."""

    write_fixture(tmp_path)
    policy_path = tmp_path / "TEST_POLICY.toml"
    write(
        tmp_path / "tools/test_support/settling.py",
        """def risky_wait(app: object) -> None:
    while pending():
        app.processEvents()

def one_synchronous_delivery(app: object) -> None:
    app.processEvents()
""",
    )

    policy = load_test_policy(policy_path)
    candidates = [
        candidate
        for candidate in discover_test_candidates(tmp_path, policy)
        if candidate.rule == DRAIN_RULE
    ]

    assert [candidate.locator for candidate in candidates] == [
        "<module>:manual-qt-event-poll:1"
    ]
    assert candidates[0].path == "tools/test_support/settling.py"


def test_discovery_rejects_returning_a_port_after_its_socket_closes(
    tmp_path: Path,
) -> None:
    """A numeric port is not a reservation after its owning context exits."""

    write_fixture(tmp_path)
    policy_path = tmp_path / "TEST_POLICY.toml"
    write(
        tmp_path / "tools/test_support/ports.py",
        """import socket

def direct_race() -> int:
    with socket.socket() as listener:
        listener.bind((\"127.0.0.1\", 0))
        return int(listener.getsockname()[1])

def assigned_race() -> int:
    with socket.socket() as listener:
        listener.bind((\"127.0.0.1\", 0))
        port = listener.getsockname()[1]
    return int(port)

def retained_owner() -> socket.socket:
    listener = socket.socket()
    listener.bind((\"127.0.0.1\", 0))
    return listener
""",
    )

    candidates = [
        candidate
        for candidate in discover_test_candidates(
            tmp_path,
            load_test_policy(policy_path),
        )
        if candidate.rule == PORT_HANDOFF_RULE
    ]

    assert [candidate.locator for candidate in candidates] == [
        "assigned_race:closed-port-handoff:2",
        "direct_race:closed-port-handoff:1",
    ]


def test_ci_support_has_no_closed_ephemeral_port_handoffs() -> None:
    """Keep every CI child endpoint owned until its immediate launch handoff."""

    repository_root = Path(__file__).resolve().parents[3]
    candidates = []
    for path in sorted((repository_root / "tools" / "ci").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        candidates.extend(
            closed_ephemeral_port_candidates(
                path=path.relative_to(repository_root).as_posix(),
                tree=tree,
            )
        )

    assert candidates == []

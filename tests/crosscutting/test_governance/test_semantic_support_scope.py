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

from pathlib import Path

from tools.test_governance.discovery import discover_test_candidates
from tools.test_governance.loading import load_test_policy
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

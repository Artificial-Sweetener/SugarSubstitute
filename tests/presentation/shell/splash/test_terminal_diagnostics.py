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

"""Verify native-crash snapshots survive successive splash stages."""

from __future__ import annotations

import json
from pathlib import Path

from tests.presentation.shell.splash.terminal_diagnostics import TerminalDiagnostics


def test_terminal_diagnostics_preserves_prior_stages(tmp_path: Path) -> None:
    """Every synchronous record leaves complete evidence for an abrupt worker exit."""
    destination = tmp_path / "splash-diagnostics" / "worker-test.json"
    diagnostics = TerminalDiagnostics(destination, nodeid="splash::activity")
    diagnostics.record("pending", {"scroll_value": 0})
    assert json.loads(destination.read_text(encoding="utf-8")) == {
        "nodeid": "splash::activity",
        "stages": [{"stage": "pending", "state": {"scroll_value": 0}}],
    }
    diagnostics.record("delivered", {"scroll_value": 10})
    assert json.loads(destination.read_text(encoding="utf-8")) == {
        "nodeid": "splash::activity",
        "stages": [
            {"stage": "pending", "state": {"scroll_value": 0}},
            {"stage": "delivered", "state": {"scroll_value": 10}},
        ],
    }

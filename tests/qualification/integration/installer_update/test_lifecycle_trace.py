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

"""Verify installer lifecycle trace qualification policy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.ci.installer_lifecycle_errors import InstallerLifecycleError
from tools.ci.installer_ui_qualification import assert_startup_trace_sequence


def test_lifecycle_requires_ordered_splash_to_main_shell_trace(tmp_path: Path) -> None:
    """The install proof should accept only the production reveal sequence."""

    trace_path = tmp_path / "startup-trace.jsonl"
    trace_path.write_text(
        "\n".join(
            json.dumps({"event": event})
            for event in (
                "launch_splash.started",
                "launch_splash.closed",
                "main_shell.shown",
            )
        ),
        encoding="utf-8",
    )

    assert_startup_trace_sequence(trace_path)


def test_lifecycle_rejects_main_shell_without_completed_splash(tmp_path: Path) -> None:
    """A main-window event alone must not count as button-launch proof."""

    trace_path = tmp_path / "startup-trace.jsonl"
    trace_path.write_text(
        json.dumps({"event": "main_shell.shown"}),
        encoding="utf-8",
    )

    with pytest.raises(InstallerLifecycleError, match="splash-to-shell sequence"):
        assert_startup_trace_sequence(trace_path)

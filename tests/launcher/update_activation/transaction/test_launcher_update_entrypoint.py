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

"""Verify the permanent bootstrap's private launcher-update command."""

from __future__ import annotations

from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.launcher_update_entrypoint import (
    run_launcher_update_invocation,
)


def test_entrypoint_leaves_ordinary_launcher_arguments_unclaimed() -> None:
    """Keep update mutation separate from normal startup argument parsing."""

    assert run_launcher_update_invocation(("--no-update-check",)) is None


def test_entrypoint_runs_exact_request(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Delegate one absolute request to bootstrap-owned updater code."""

    request = tmp_path / "pending.json"
    observed: list[Path] = []
    monkeypatch.setattr(
        "sugarsubstitute_shared.launcher_update.helper.apply_launcher_update_request",
        observed.append,
    )

    assert (
        run_launcher_update_invocation(("--apply-launcher-update", str(request))) == 0
    )
    assert observed == [request.resolve()]


def test_entrypoint_rejects_incomplete_private_invocation() -> None:
    """Reject a private mutation mode without its persisted request identity."""

    with pytest.raises(ValueError, match="REQUEST_PATH"):
        run_launcher_update_invocation(("--apply-launcher-update",))

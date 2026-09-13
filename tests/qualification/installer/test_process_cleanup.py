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

import pytest

from tools.ci.installer_ui_qualification import (
    terminate_verified_process,
)


def test_verified_process_cleanup_delegates_to_the_shared_owned_tree_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Installer cleanup should reuse the qualified process-tree owner."""

    cleaned: list[int] = []
    monkeypatch.setattr(
        "tools.ci.installer_ui_qualification.terminate_owned_process_tree",
        cleaned.append,
    )

    terminate_verified_process(5678)

    assert cleaned == [5678]


def test_verified_process_cleanup_reports_shared_tree_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Installer cleanup should retain its actionable lifecycle error contract."""

    def fail_cleanup(_pid: int) -> None:
        """Model the shared process owner failing to reap a verified tree."""

        raise RuntimeError("process 5678 remains")

    monkeypatch.setattr(
        "tools.ci.installer_ui_qualification.terminate_owned_process_tree",
        fail_cleanup,
    )

    with pytest.raises(RuntimeError, match="Could not terminate verified app"):
        terminate_verified_process(5678)

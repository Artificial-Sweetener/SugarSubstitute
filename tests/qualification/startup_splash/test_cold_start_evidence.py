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

"""Verify deterministic packaged splash qualification evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from tools.single_instance_cold_start_evidence import (
    assert_cold_start_snapshot,
    qualification_app_pids,
)


def test_cold_start_evidence_records_latency_without_gating_on_it() -> None:
    """Accept any measured duration when the presentation contract is valid."""

    assert_cold_start_snapshot(
        _snapshot(launch_to_first_paint_ms=999_999.0),
        expected_launcher_pids=(101,),
        expected_app_pid=202,
    )


def test_cold_start_evidence_rejects_out_of_order_presentation_phases() -> None:
    """Reject causal ordering violations independently of machine speed."""

    snapshot = _snapshot(launch_to_first_paint_ms=1.0)
    surfaces = snapshot["splash_surfaces"]
    assert isinstance(surfaces, list)
    surface = surfaces[0]
    assert isinstance(surface, dict)
    phases = surface["startup_phase_ms"]
    assert isinstance(phases, dict)
    phases["first_paint"] = 6.0
    phases["splash_constructed"] = 7.0

    with pytest.raises(AssertionError, match="out of order"):
        assert_cold_start_snapshot(
            snapshot,
            expected_launcher_pids=(101,),
            expected_app_pid=202,
        )


def test_qualification_owner_markers_reject_reused_process_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ignore stale marker PIDs that now identify an unrelated process."""

    layout = InstallLayout.from_root(tmp_path / "install")
    marker_dir = layout.user_dir / "qualification-owners"
    marker_dir.mkdir(parents=True)
    marker_dir.joinpath("101.json").write_text(
        json.dumps({"pid": 101, "parent_pid": 201}),
        encoding="utf-8",
    )
    marker_dir.joinpath("102.json").write_text(
        json.dumps({"pid": 102, "parent_pid": 202}),
        encoding="utf-8",
    )

    class _Process:
        """Expose stable process identity for one marker PID."""

        def __init__(self, pid: int) -> None:
            """Retain the selected marker PID."""

            self._pid = pid

        def cmdline(self) -> list[str]:
            """Return the qualification entrypoint for both process IDs."""

            return ["python.exe", str(layout.app_entrypoint.resolve())]

        def ppid(self) -> int:
            """Make the second marker stale through parent identity mismatch."""

            return 201 if self._pid == 101 else 999

    monkeypatch.setattr(
        "tools.single_instance_cold_start_evidence.psutil.Process",
        _Process,
    )

    assert qualification_app_pids(layout) == (101,)


def _snapshot(*, launch_to_first_paint_ms: float) -> dict[str, object]:
    """Build one complete splash observation with deterministic identities."""

    phase_names = (
        "host_process_requested",
        "host_module_started",
        "host_main_entered",
        "arguments_parsed",
        "application_ready",
        "icon_ready",
        "splash_module_ready",
        "splash_constructed",
        "first_paint",
    )
    return {
        "application_owner_pids": [202],
        "packaged_launcher_pids": [101],
        "splash_adoptions": [
            {
                "app_pid": 202,
                "splash_host_pid": 303,
                "close_acknowledged": True,
            }
        ],
        "splash_surfaces": [
            {
                "host_pid": 303,
                "splash_is_visible": True,
                "first_paint_confirmed": True,
                "launch_to_first_paint_ms": launch_to_first_paint_ms,
                "top_level_surface_count": 1,
                "visible_top_level_surface_count": 1,
                "platform_name": "offscreen",
                "startup_phase_ms": {
                    name: float(index) for index, name in enumerate(phase_names)
                },
            }
        ],
    }

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

import pytest

from tools.single_instance_cold_start_evidence import assert_cold_start_snapshot


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

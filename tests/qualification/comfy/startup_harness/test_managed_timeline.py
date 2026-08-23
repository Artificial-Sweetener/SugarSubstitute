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

"""Test managed Comfy output timeline extraction and summaries."""

from __future__ import annotations

from __future__ import annotations
from pathlib import Path
from typing import Mapping, cast
import pytest
from tools import startup_harness


def test_run_app_managed_cycle_parses_managed_comfy_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """App-managed summaries should include mirrored child Comfy diagnostics."""

    paths = startup_harness.HarnessPaths.from_roots(
        sugar_substitute_root=tmp_path / "SugarSubstitute",
        comfy_root=tmp_path / "ComfyUI",
        substitute_backend_root=None,
        sugarcubes_root=None,
    )

    def fake_run_server_process(**kwargs: object) -> startup_harness.CommandRunResult:
        """Write managed child output to the harness-requested mirror path."""

        env = cast(Mapping[str, str], kwargs["env"])
        Path(env[startup_harness.APP_MANAGED_COMFY_OUTPUT_LOG_ENV]).write_text(
            (
                "SugarCubes cube library diagnostic "
                "event=sugarcubes_library_readiness_timing ready=True\n"
            ),
            encoding="utf-8",
        )
        Path(env[startup_harness.APP_MANAGED_COMFY_OUTPUT_TIMELINE_ENV]).write_text(
            (
                '{"event":"managed_comfy_output","monotonicNs":1,'
                '"elapsedMs":1.0,"line":"Starting server"}\n'
            ),
            encoding="utf-8",
        )
        return startup_harness.CommandRunResult(
            name="app-managed",
            command=("python", "main.py"),
            cwd=paths.sugar_substitute_root,
            exit_code=1,
            termination_kind="killed_after_ready",
            timed_out=False,
            ready=True,
            elapsed_ms=1.0,
            output_path=tmp_path / "app-managed.log",
            route_measurements=(),
            parsed_import_times=(),
        )

    monkeypatch.setattr(
        startup_harness,
        "http_endpoint_is_reachable",
        lambda *_, **__: False,
    )
    monkeypatch.setattr(startup_harness, "_run_server_process", fake_run_server_process)

    result = startup_harness.run_app_managed_cycle(
        paths=paths,
        cycle_dir=tmp_path,
        host="127.0.0.1",
        port=8188,
        ready_timeout_seconds=1.0,
        settle_seconds=0.0,
        log=lambda _message: None,
    )

    assert result.diagnostic_events == (
        {
            "source": "SugarCubes",
            "channel": "cube_library",
            "event": "sugarcubes_library_readiness_timing",
            "fields": {"ready": True},
        },
    )
    assert result.diagnostic_artifacts == (
        {
            "name": "managed_comfy_output",
            "path": str(tmp_path / "app-managed-comfy-output.log"),
        },
        {
            "name": "managed_comfy_output_timeline",
            "path": str(tmp_path / "app-managed-comfy-output-timeline.jsonl"),
        },
    )
    assert result.managed_comfy_timeline_measurements == {
        "eventCount": 1,
        "firstOutputMs": 1.0,
        "firstOutputTimestampNs": 1,
        "lastOutputMs": 1.0,
        "firstMilestoneMs": {"starting_server": 1.0},
        "firstMilestoneTimestampNs": {"starting_server": 1},
        "milestoneLines": {"starting_server": "Starting server"},
        "largestOutputGaps": (),
        "largestChildOutputGaps": (),
    }


def test_parse_managed_comfy_output_timeline_summarizes_milestones() -> None:
    """Managed Comfy output timeline should expose repeatable startup milestones."""

    timeline = "\n".join(
        [
            (
                '{"event":"managed_comfy_output","monotonicNs":10,'
                '"elapsedMs":100.0,"line":"Launching ComfyUI."}'
            ),
            (
                '{"event":"managed_comfy_output","monotonicNs":15,'
                '"elapsedMs":150.0,"line":"\\u001b[32m[INFO]\\u001b[0m '
                'Substitute BackEnd configured ComfyUI model root: E:\\\\ImageGen Models"}'
            ),
            (
                '{"event":"managed_comfy_output","monotonicNs":20,'
                '"elapsedMs":350.0,"line":"\\u001b[32m[INFO]\\u001b[0m '
                '[ComfyUI-Manager] network_mode: public"}'
            ),
            (
                '{"event":"managed_comfy_output","monotonicNs":30,'
                '"elapsedMs":1000.0,"line":"FETCH ComfyRegistry Data: 5/159"}'
            ),
            (
                '{"event":"managed_comfy_output","monotonicNs":40,'
                '"elapsedMs":1250.0,"line":"\\u001b[32m[INFO]\\u001b[0m '
                'Starting server"}'
            ),
            (
                '{"event":"managed_comfy_output","monotonicNs":50,'
                '"elapsedMs":1300.0,"line":"\\u001b[32m[INFO]\\u001b[0m '
                'To see the GUI go to: http://127.0.0.1:8188"}'
            ),
        ]
    )

    measurements = startup_harness.parse_managed_comfy_output_timeline(timeline)

    assert measurements["eventCount"] == 6
    assert measurements["firstOutputMs"] == 100.0
    assert measurements["firstOutputTimestampNs"] == 10
    assert measurements["lastOutputMs"] == 1300.0
    assert measurements["firstMilestoneMs"] == {
        "launching_comfy": 100.0,
        "managed_model_root_applied": 150.0,
        "manager_network_mode": 350.0,
        "manager_fetch_registry": 1000.0,
        "starting_server": 1250.0,
        "gui_url_printed": 1300.0,
    }
    assert measurements["firstMilestoneTimestampNs"] == {
        "launching_comfy": 10,
        "managed_model_root_applied": 15,
        "manager_network_mode": 20,
        "manager_fetch_registry": 30,
        "starting_server": 40,
        "gui_url_printed": 50,
    }
    assert measurements["milestoneLines"] == {
        "launching_comfy": "Launching ComfyUI.",
        "managed_model_root_applied": (
            "Substitute BackEnd configured ComfyUI model root: E:\\ImageGen Models"
        ),
        "manager_network_mode": "[ComfyUI-Manager] network_mode: public",
        "manager_fetch_registry": "FETCH ComfyRegistry Data: 5/159",
        "starting_server": "Starting server",
        "gui_url_printed": "To see the GUI go to: http://127.0.0.1:8188",
    }
    largest_output_gaps = cast(
        tuple[dict[str, object], ...],
        measurements["largestOutputGaps"],
    )
    largest_child_output_gaps = cast(
        tuple[dict[str, object], ...],
        measurements["largestChildOutputGaps"],
    )
    assert largest_output_gaps[0] == {
        "gapMs": 650.0,
        "fromMs": 350.0,
        "toMs": 1000.0,
        "fromLine": "[ComfyUI-Manager] network_mode: public",
        "toLine": "FETCH ComfyRegistry Data: 5/159",
    }
    assert largest_child_output_gaps[0] == largest_output_gaps[0]


def test_parse_managed_comfy_output_timeline_reports_child_only_gaps() -> None:
    """Managed parent readiness messages should not hide child output gaps."""

    timeline = "\n".join(
        [
            (
                '{"event":"managed_comfy_output","monotonicNs":10,'
                '"elapsedMs":100.0,"line":"Launching ComfyUI."}'
            ),
            (
                '{"event":"managed_comfy_output","monotonicNs":20,'
                '"elapsedMs":1100.0,"line":"Waiting for ComfyUI to become ready..."}'
            ),
            (
                '{"event":"managed_comfy_output","monotonicNs":30,'
                '"elapsedMs":1200.0,"line":"\\u001b[32m[INFO]\\u001b[0m '
                'Substitute BackEnd configured ComfyUI model root: E:\\\\ImageGen Models"}'
            ),
            (
                '{"event":"managed_comfy_output","monotonicNs":40,'
                '"elapsedMs":1800.0,"line":"Waiting for ComfyUI to become ready..."}'
            ),
            (
                '{"event":"managed_comfy_output","monotonicNs":50,'
                '"elapsedMs":1900.0,"line":"Found comfy_kitchen backend cuda"}'
            ),
            (
                '{"event":"managed_comfy_output","monotonicNs":60,'
                '"elapsedMs":2500.0,"line":"ComfyUI-GGUF: Allowing full torch compile"}'
            ),
        ]
    )

    measurements = startup_harness.parse_managed_comfy_output_timeline(timeline)
    largest_output_gaps = cast(
        tuple[dict[str, object], ...],
        measurements["largestOutputGaps"],
    )
    largest_child_output_gaps = cast(
        tuple[dict[str, object], ...],
        measurements["largestChildOutputGaps"],
    )

    assert largest_output_gaps[0]["toLine"] == "Waiting for ComfyUI to become ready..."
    assert largest_child_output_gaps[0] == {
        "gapMs": 700.0,
        "fromMs": 1200.0,
        "toMs": 1900.0,
        "fromLine": "Substitute BackEnd configured ComfyUI model root: E:\\ImageGen Models",
        "toLine": "Found comfy_kitchen backend cuda",
    }

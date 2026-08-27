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

"""Test HTTP readiness, loopback probing, process output, and CLI behavior."""

from __future__ import annotations

from __future__ import annotations
import sys
import time as time_module
import urllib.parse
import urllib.request
from pathlib import Path
from typing import cast
import pytest
from tools import startup_harness


def test_wait_for_http_ready_uses_supplied_probe_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Harness raw-ready probing should not use a hard-coded URL timeout."""

    observed: dict[str, object] = {}

    class _Response:
        """Minimal urlopen context manager."""

        status = 200

        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, *_exc: object) -> None:
            return None

    def fake_urlopen(url: str, *, timeout: float) -> _Response:
        """Capture the requested timeout and return an OK response."""

        observed["url"] = url
        observed["timeout"] = timeout
        return _Response()

    monkeypatch.setattr(
        startup_harness,
        "url_loopback_port_is_available",
        lambda _url: False,
    )
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monotonic_values = iter((0.0, 0.0))
    monkeypatch.setattr(time_module, "monotonic", lambda: next(monotonic_values))

    assert (
        startup_harness.wait_for_http_ready(
            "http://127.0.0.1:8188/system_stats",
            timeout_seconds=0.75,
        )
        is True
    )
    assert observed == {
        "url": "http://127.0.0.1:8188/system_stats",
        "timeout": 0.75,
    }


def test_run_server_process_writes_timestamped_output_timeline(
    tmp_path: Path,
) -> None:
    """Direct process runs should produce parseable output timelines."""

    output_timeline_path = tmp_path / "direct-comfy-output-timeline.jsonl"

    result = startup_harness._run_server_process(
        name="direct-comfy",
        command=(
            sys.executable,
            "-c",
            (
                "import time; "
                "print('Starting server', flush=True); "
                "print('To see the GUI go to: http://127.0.0.1:8188', flush=True); "
                "time.sleep(2)"
            ),
        ),
        cwd=tmp_path,
        output_path=tmp_path / "direct-comfy.log",
        output_timeline_path=output_timeline_path,
        ready_url=None,
        route_urls=(),
        ready_timeout_seconds=5.0,
        settle_seconds=0.1,
        env=startup_harness._process_env({}),
        log=lambda _message: None,
    )

    assert result.ready is True
    assert result.diagnostic_artifacts == (
        {
            "name": "direct-comfy_output_timeline",
            "path": str(output_timeline_path),
        },
    )
    assert output_timeline_path.exists()
    assert result.comfy_output_timeline_measurements is not None
    milestones = cast(
        dict[str, float],
        result.comfy_output_timeline_measurements["firstMilestoneMs"],
    )
    assert set(milestones) == {"starting_server", "gui_url_printed"}
    assert 0.0 <= milestones["starting_server"] <= 5000.0
    assert milestones["starting_server"] <= milestones["gui_url_printed"] <= 5000.0


def test_wait_for_http_ready_skips_http_probe_when_loopback_port_is_bindable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Harness raw-ready probing should not wait on an absent local server."""

    def fail_urlopen(*_args: object, **_kwargs: object) -> object:
        """Fail if a bindable loopback port still falls through to HTTP."""

        raise AssertionError("urlopen should not be called for a bindable port")

    monkeypatch.setattr(
        startup_harness,
        "url_loopback_port_is_available",
        lambda _url: True,
    )
    monkeypatch.setattr(urllib.request, "urlopen", fail_urlopen)
    monotonic_values = iter((0.0, 0.0))
    monkeypatch.setattr(time_module, "monotonic", lambda: next(monotonic_values))

    assert (
        startup_harness.wait_for_http_ready(
            "http://127.0.0.1:8188/system_stats",
            timeout_seconds=0.75,
        )
        is False
    )


def test_http_endpoint_is_reachable_skips_http_probe_when_loopback_port_is_bindable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Harness preflight checks should be cheap when a loopback port is unused."""

    def fail_urlopen(*_args: object, **_kwargs: object) -> object:
        """Fail if a bindable loopback port still falls through to HTTP."""

        raise AssertionError("urlopen should not be called for a bindable port")

    monkeypatch.setattr(
        startup_harness,
        "url_loopback_port_is_available",
        lambda _url: True,
    )
    monkeypatch.setattr(urllib.request, "urlopen", fail_urlopen)

    assert (
        startup_harness.http_endpoint_is_reachable(
            "http://127.0.0.1:8188/system_stats",
            timeout_seconds=1.0,
        )
        is False
    )


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://127.0.0.1:8188/system_stats", True),
        ("http://[::1]:8188/system_stats", True),
        ("http://localhost:8188/system_stats", False),
        ("http://example.invalid:8188/system_stats", False),
    ],
)
def test_url_loopback_port_is_available_checks_literal_loopback_hosts_only(
    monkeypatch: pytest.MonkeyPatch,
    url: str,
    expected: bool,
) -> None:
    """Only literal loopback hosts should use bindability as readiness evidence."""

    calls: list[tuple[str, int]] = []

    def fake_local_port_is_available(*, host: str, port: int) -> bool:
        """Capture the parsed literal loopback target."""

        calls.append((host, port))
        return True

    monkeypatch.setattr(
        startup_harness,
        "_local_port_is_available",
        fake_local_port_is_available,
    )

    assert startup_harness.url_loopback_port_is_available(url) is expected
    if expected:
        parsed_host = urllib.parse.urlparse(url).hostname
        assert parsed_host is not None
        assert calls == [(parsed_host, 8188)]
    else:
        assert calls == []


def test_parse_args_defaults_to_non_app_modes() -> None:
    """Default harness mode should avoid launching the Qt app until requested."""

    args = startup_harness._parse_args([])

    assert args.mode == ("direct-comfy", "sugarcubes-maintenance")


def test_create_run_dir_adds_suffix_on_timestamp_collision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parallel harness invocations should not collide on timestamped run paths."""

    monkeypatch.setattr(
        startup_harness,
        "_timestamp_for_path",
        lambda: "run-20260708-103208",
    )
    first_run = tmp_path / "run-20260708-103208"
    first_run.mkdir()

    run_dir = startup_harness._create_run_dir(tmp_path)

    assert run_dir == tmp_path / "run-20260708-103208-01"
    assert run_dir.exists()

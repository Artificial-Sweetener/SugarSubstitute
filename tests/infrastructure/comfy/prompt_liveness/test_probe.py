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

"""Tests for Comfy queue and history prompt-liveness inspection."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.prompt_liveness import (
    ComfyPromptLivenessProbe,
)


@dataclass
class _Response:
    """Provide one requests-compatible JSON response."""

    payload: object

    def raise_for_status(self) -> None:
        """Accept the response status."""

    def json(self) -> object:
        """Return the configured response payload."""

        return self.payload


def test_prompt_liveness_reports_active_from_native_comfy_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Native priority-first queue entries should keep a prompt alive."""

    calls: list[str] = []

    def get(url: str, *, timeout: float) -> _Response:
        """Return one running queue entry without consulting history."""

        calls.append(url)
        assert timeout == 2.0
        return _Response({"queue_running": [[0.0, "pid-1", {}, {}]]})

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.prompt_liveness.requests.get",
        get,
    )

    result = ComfyPromptLivenessProbe(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        timeout_seconds=2.0,
    ).observe("pid-1")

    assert result.state == "active"
    assert calls == ["http://127.0.0.1:8188/queue"]


@pytest.mark.parametrize(
    ("status", "expected_state"),
    [
        ({"status_str": "success", "completed": True}, "succeeded"),
        ({"status_str": "error", "completed": False}, "failed"),
    ],
)
def test_prompt_liveness_reads_terminal_history(
    monkeypatch: pytest.MonkeyPatch,
    status: dict[str, object],
    expected_state: str,
) -> None:
    """An absent queue prompt should resolve from targeted Comfy history."""

    responses = iter(
        [
            _Response({"queue_running": [], "queue_pending": []}),
            _Response({"pid-1": {"status": status}}),
        ]
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.prompt_liveness.requests.get",
        lambda *_args, **_kwargs: next(responses),
    )

    result = ComfyPromptLivenessProbe(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
    ).observe("pid-1")

    assert result.state == expected_state


def test_prompt_liveness_distinguishes_missing_and_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing prompt state and failed transport must remain distinguishable."""

    responses = iter([_Response({}), _Response({})])
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.prompt_liveness.requests.get",
        lambda *_args, **_kwargs: next(responses),
    )
    probe = ComfyPromptLivenessProbe(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
    )

    assert probe.observe("pid-1").state == "missing"

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.prompt_liveness.requests.get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("offline")),
    )

    assert probe.observe("pid-1").state == "unavailable"

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

"""Verify listener terminal behavior when Comfy no longer owns a prompt."""

from __future__ import annotations

from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from tests.infrastructure.comfy.listener.contract_harness import (
    _build_callbacks,
    _build_request,
    _import_listener_module,
)


def test_run_emits_failure_when_idle_prompt_is_verified_missing(
    monkeypatch: MonkeyPatch,
) -> None:
    """Fail deterministically when timeout verification finds no queued prompt."""

    module = _import_listener_module(monkeypatch)
    callbacks, _, _, _, failures, completed = _build_callbacks()

    class FakeWebSocket:
        """Raise the deterministic receive timeout that triggers liveness proof."""

        def connect(self, _url: str) -> None:
            """Accept listener connection."""

        def send(self, _payload: str) -> None:
            """Accept listener handshake."""

        def recv(self) -> object:
            """Simulate an idle listener transport."""

            raise TimeoutError("socket timeout")

        def close(self) -> None:
            """Accept listener cleanup."""

    class EmptyResponse:
        """Return an empty Comfy queue or history response."""

        def raise_for_status(self) -> None:
            """Accept the fake HTTP response."""

        def json(self) -> dict[str, object]:
            """Return the verified absence payload."""

            return {}

    monkeypatch.setattr(module.websocket, "WebSocket", FakeWebSocket)
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.prompt_liveness.requests.get",
        lambda *_args, **_kwargs: EmptyResponse(),
    )
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=Path("."),
            workflow_payload={"1": {"class_type": "KSampler"}},
        ),
        callbacks=callbacks,
        receive_timeout_seconds=1.0,
    )

    runnable.run()

    assert len(failures) == 1
    assert "could not be found" in failures[0].error
    assert len(completed) == 1
    assert completed[0].workflow_id == "wf-1"
    assert completed[0].prompt_id == "pid-1"

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

"""Tests for model catalog websocket listener logging behavior."""

from __future__ import annotations

import logging

import pytest

from substitute.application.execution import CancellationSource
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.model_catalog_event_listener import (
    ModelCatalogEventListener,
)


class _RefusingWebSocket:
    """Refuse connections until the listener test stops the reconnect loop."""

    def __init__(
        self,
        *,
        attempts: list[int],
        cancellation: CancellationSource,
        stop_after: int,
    ) -> None:
        """Store shared attempt state and listener stop target."""

        self._attempts = attempts
        self._cancellation = cancellation
        self._stop_after = stop_after

    def connect(self, _url: str, timeout: float | None = None) -> None:
        """Raise a connection refusal and stop the loop after enough attempts."""

        del timeout
        self._attempts[0] += 1
        if self._attempts[0] > self._stop_after:
            pytest.fail("listener continued reconnecting after test cancellation")
        if self._attempts[0] >= self._stop_after:
            self._cancellation.cancel(reason="test_complete")
        raise ConnectionRefusedError(10061, "connection refused")

    def close(self) -> None:
        """Accept close calls after failed connects."""


def test_listener_warns_once_for_repeated_expected_disconnects(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Expected reconnect loops should not emit repeated warnings."""

    attempts = [0]
    cancellation = CancellationSource(generation=1)
    listener = ModelCatalogEventListener(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        on_update=lambda _update: None,
        websocket_factory=lambda: _RefusingWebSocket(
            attempts=attempts,
            cancellation=cancellation,
            stop_after=3,
        ),
        backoff_seconds=(0.0,),
    )

    with caplog.at_level(
        logging.INFO,
        logger="sugarsubstitute.infrastructure.comfy.model_catalog_event_listener",
    ):
        getattr(listener, "_run")(cancellation)

    reconnect_records = [
        record
        for record in caplog.records
        if record.message.startswith(
            "Model catalog websocket listener disconnected; reconnecting"
        )
    ]
    assert [record.levelno for record in reconnect_records] == [
        logging.WARNING,
        logging.INFO,
    ]
    assert attempts == [3]

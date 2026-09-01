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

"""Verify deterministic timing controls for packaged launch qualification."""

from collections.abc import Callable
import json
import os
from pathlib import Path

import pytest

from tools.single_instance_qualification_app import (
    APPLICATION_CLAIM_DELAY_ENV,
    _delay_application_claim,
    application_preclaim_marker_path,
)


def test_application_claim_delay_is_explicit_and_one_shot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Delay only the selected qualification application claim."""

    observed: list[tuple[float, int]] = []
    marker_path = application_preclaim_marker_path(tmp_path)

    def observe_preclaim(delay: float) -> None:
        """Capture the durable synchronization marker during the delay."""

        payload = json.loads(marker_path.read_text(encoding="utf-8"))
        observed.append((delay, payload["pid"]))

    sleep: Callable[[float], None] = observe_preclaim
    monkeypatch.setenv(APPLICATION_CLAIM_DELAY_ENV, "1.25")
    monkeypatch.setattr("tools.single_instance_qualification_app.time.sleep", sleep)

    _delay_application_claim(tmp_path)
    _delay_application_claim(tmp_path)

    assert observed == [(1.25, os.getpid())]
    assert not marker_path.exists()

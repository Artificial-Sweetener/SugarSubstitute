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

"""Enforce deterministic external boundaries for listener tests."""

from __future__ import annotations

from typing import NoReturn

import pytest
import requests


@pytest.fixture(autouse=True)
def prohibit_uncontrolled_http_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail listener tests that attempt an unconfigured HTTP request."""

    def reject_http_request(
        _session: requests.Session,
        _method: str,
        url: str,
        **_kwargs: object,
    ) -> NoReturn:
        """Report the escaped network boundary at its first request."""

        pytest.fail(f"Listener test attempted an uncontrolled HTTP request: {url}")

    monkeypatch.setattr(requests.sessions.Session, "request", reject_http_request)

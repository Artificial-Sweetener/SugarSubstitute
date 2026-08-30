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

"""Verify package inventory and operation-plan mapping."""

from __future__ import annotations

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external import SubstituteBackendEnvironmentClient

from .support import _FakeResponse, _operation_plan_payload, _packages_payload


def test_environment_client_maps_packages_and_operation_plan() -> None:
    """Map package provenance and reviewed operation plans."""

    def get(url: str, **_kwargs: object) -> _FakeResponse:
        assert url.endswith("/packages")
        return _FakeResponse(_packages_payload())

    def post(url: str, **kwargs: object) -> _FakeResponse:
        assert url.endswith("/operations/plan")
        assert kwargs["json"] == {
            "operation": "update-component",
            "componentId": "pytorch",
        }
        return _FakeResponse(_operation_plan_payload())

    client = SubstituteBackendEnvironmentClient(
        ComfyEndpoint(host="10.0.0.2", port=8189), http_get=get, http_post=post
    )
    package = client.list_packages()[0]
    plan = client.plan_operation(
        {"operation": "update-component", "componentId": "pytorch"}
    )
    assert package.summary_source == "installed-metadata"
    assert package.claimants[0].required_via == "aiohttp"
    assert plan is not None and plan.affected_packages == (
        "torch",
        "torchvision",
        "torchaudio",
    )

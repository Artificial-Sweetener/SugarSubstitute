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

"""Verify backend-owned maintenance-plan mutation contracts."""

from __future__ import annotations

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external import SubstituteBackendEnvironmentClient

from .support import (
    _FakeResponse,
    _empty_maintenance_plan_payload,
    _maintenance_plan_payload,
)


def test_environment_client_mutates_and_validates_maintenance_plan() -> None:
    """Keep every maintenance-plan mutation at its backend-owned route."""

    calls: list[tuple[str, object]] = []

    def get(url: str, **_kwargs: object) -> _FakeResponse:
        assert url.endswith("/maintenance-plan")
        calls.append(("GET", None))
        return _FakeResponse(_maintenance_plan_payload())

    def post(url: str, **kwargs: object) -> _FakeResponse:
        calls.append(("POST", kwargs["json"]))
        return _FakeResponse(_maintenance_plan_payload())

    def delete(url: str, **_kwargs: object) -> _FakeResponse:
        calls.append(("DELETE", url))
        return _FakeResponse(
            _empty_maintenance_plan_payload()
            if url.endswith("/maintenance-plan")
            else _maintenance_plan_payload()
        )

    client = SubstituteBackendEnvironmentClient(
        ComfyEndpoint(host="10.0.0.2", port=8189),
        http_get=get,
        http_post=post,
        http_delete=delete,
    )
    assert client.get_maintenance_plan().items[1].target.target_id == "triton"  # type: ignore[union-attr]
    assert (
        client.add_maintenance_plan_item(
            {"operation": "update-runtime", "runtimeId": "pytorch"}
        )
        is not None
    )
    assert (
        client.reorder_maintenance_plan_items(
            revision=4, item_ids=("plan-item-2", "plan-item-1", "plan-item-3")
        )
        is not None
    )
    assert client.remove_maintenance_plan_item("plan-item-1") is not None
    assert client.validate_maintenance_plan() is not None
    assert client.clear_maintenance_plan().items == ()  # type: ignore[union-attr]
    assert (
        "POST",
        {"revision": 4, "itemIds": ["plan-item-2", "plan-item-1", "plan-item-3"]},
    ) in calls

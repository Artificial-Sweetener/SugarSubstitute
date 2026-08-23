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

"""Verify environment restart and job-status mapping."""

from __future__ import annotations

from substitute.domain.comfy_environment import ComfyEnvironmentJobStatus
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external import SubstituteBackendEnvironmentClient

from .support import _FakeResponse, _job_payload


def test_environment_client_maps_restart_apply_and_job_routes() -> None:
    """Map asynchronous environment job ownership without polling policy."""

    def get(url: str, **_kwargs: object) -> _FakeResponse:
        assert url.endswith("/jobs/envjob-1")
        return _FakeResponse(_job_payload("succeeded"))

    def post(url: str, **kwargs: object) -> _FakeResponse:
        assert kwargs["json"] in ({}, {"revision": 4})
        assert url.endswith(("/restart", "/maintenance-plan/apply"))
        return _FakeResponse(_job_payload("queued"))

    client = SubstituteBackendEnvironmentClient(
        ComfyEndpoint(host="10.0.0.2", port=8189), http_get=get, http_post=post
    )
    restart_job = client.restart_comfy()
    apply_job = client.apply_maintenance_plan(revision=4)
    polled_job = client.get_environment_job("envjob-1")

    assert restart_job is not None
    assert restart_job.status is ComfyEnvironmentJobStatus.QUEUED
    assert apply_job is not None
    assert apply_job.status is ComfyEnvironmentJobStatus.QUEUED
    assert polled_job is not None
    assert polled_job.status is ComfyEnvironmentJobStatus.SUCCEEDED

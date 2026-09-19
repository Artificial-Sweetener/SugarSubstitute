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

"""Preserve the released launch endpoint during native identity migration."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_election import (
    ApplicationInstanceReservation,
)
from sugarsubstitute_shared.application_instance_forwarding import (
    forward_application_invocation,
)
from sugarsubstitute_shared.application_instance_identity import instance_identity
from sugarsubstitute_shared.application_instance_protocol import ApplicationInvocation
from sugarsubstitute_shared.application_instance_transport import (
    bind_instance_listener,
    instance_endpoint,
)


@pytest.mark.parametrize("previous_first", (True, False))
def test_released_endpoint_and_current_launch_share_one_instance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, previous_first: bool
) -> None:
    """Route both launch orders through the first owner using the released wire name."""
    for label in ("USERNAME", "USER"):
        monkeypatch.setenv(label, "released-contract-user")
    for label in ("XDG_SESSION_ID", "WAYLAND_DISPLAY", "DISPLAY", "SESSIONNAME"):
        monkeypatch.setenv(label, "released-contract-session")
    root = os.path.normcase(str(tmp_path.expanduser().resolve()))
    payload = f"{root}\0released-contract-user\0released-contract-session"
    endpoint = instance_endpoint(
        hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
    )
    invocation = ApplicationInvocation.capture(
        ("fixture.sugar",), working_directory=tmp_path
    )
    owner = None
    duplicate = None
    received: list[ApplicationInvocation] = []

    def present(request: ApplicationInvocation) -> str:
        """Record the activation acknowledged by the first owner's visible surface."""
        received.append(request)
        return "fixture-main-shell"

    try:
        if previous_first:
            owner = ApplicationInstanceBroker(
                reservation=ApplicationInstanceReservation(
                    endpoint, (bind_instance_listener(endpoint),)
                ),
                child_token="fixture-token",
                accept_listener_invocations=True,
            )
        else:
            owner = ApplicationInstanceBroker.elect(
                install_root=tmp_path, invocation=invocation
            )
        assert owner is not None
        owner.bind_startup_presenter(present)
        if previous_first:
            duplicate = ApplicationInstanceBroker.elect(
                install_root=tmp_path, invocation=invocation
            )
            assert duplicate is None, (
                "Current launch admitted another owner beside the released endpoint"
            )
            temporary_claim = bind_instance_listener(
                instance_endpoint(instance_identity(tmp_path))
            )
            temporary_claim.close()
        else:
            forward_application_invocation(endpoint, invocation)
        assert received == [invocation]
    finally:
        if duplicate is not None:
            duplicate.close()
        if owner is not None:
            owner.close()
    replacement = ApplicationInstanceBroker.elect(
        install_root=tmp_path, invocation=invocation
    )
    assert replacement is not None
    replacement.close()

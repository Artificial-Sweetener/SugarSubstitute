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

"""Verify splash presentation handoff without transferring process ownership."""

from pathlib import Path
import json
from uuid import uuid4

import pytest

from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import ApplicationInvocation
from sugarsubstitute_shared.delegated_application_broker import (
    DelegatedApplicationBroker,
)
from sugarsubstitute_shared.launch_splash.client import SocketSplashSessionClient
from sugarsubstitute_shared.launch_splash.session import (
    create_splash_session_spec,
    splash_session_args,
)


def test_borrowed_splash_reuses_session_and_closes_through_original_owner(
    tmp_path: Path,
) -> None:
    """Consume handoff credentials and release through native IPC without owning a PID."""
    from launcher.sugarsubstitute_launcher.splash_transfer import (
        export_splash_session,
        take_borrowed_splash_session,
    )

    spec = create_splash_session_spec(port=12345)
    closed: list[bool] = []
    owner = ApplicationInstanceBroker.elect(
        install_root=tmp_path, invocation=ApplicationInvocation.capture(["launcher"])
    )
    assert owner is not None
    with owner:
        identity = owner.register_startup_resource(lambda: closed.append(True))
        delegate = DelegatedApplicationBroker(owner.child_environment({}))
        environment = export_splash_session(spec, resource_identity=identity)
        try:
            borrowed = take_borrowed_splash_session(
                environment, release=delegate.release_startup_resource
            )
            assert borrowed is not None
            assert environment == {}
            assert isinstance(borrowed.client, SocketSplashSessionClient)
            assert borrowed.client.spec == spec
            assert borrowed.app_arguments == tuple(splash_session_args(spec))
            assert not borrowed.cancellation_requested()
            borrowed.ensure_closed()
            borrowed.close()
            assert closed == [True]
            assert (
                take_borrowed_splash_session(
                    environment, release=delegate.release_startup_resource
                )
                is None
            )
        finally:
            delegate.close()
    assert closed == [True]


@pytest.mark.parametrize(
    "invalid_fields",
    [
        {"schema_version": 2},
        {"schema_version": True},
        {"resource_identity": "invalid"},
        {"arguments": [None]},
        {"arguments": []},
    ],
)
def test_invalid_splash_handoff_is_consumed_without_cleanup_authority(
    invalid_fields: dict[str, object],
) -> None:
    """Reject incomplete transfer data without releasing any owner's resource."""
    from launcher.sugarsubstitute_launcher.splash_transfer import (
        export_splash_session,
        take_borrowed_splash_session,
    )

    spec = create_splash_session_spec(port=12345)
    environment = export_splash_session(spec, resource_identity=uuid4().hex)
    key = next(iter(environment))
    payload = json.loads(environment[key])
    payload.update(invalid_fields)
    environment[key] = json.dumps(payload)
    released: list[str] = []
    with pytest.raises(ValueError):
        take_borrowed_splash_session(environment, release=released.append)
    assert environment == {}
    assert released == []

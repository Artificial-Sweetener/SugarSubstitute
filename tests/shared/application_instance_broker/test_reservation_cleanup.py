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

"""Prove failed multi-address admission releases every native reservation."""

from __future__ import annotations

import errno
from pathlib import Path
import threading

import pytest

from sugarsubstitute_shared import application_instance_election
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_election import (
    application_instance_endpoints,
)
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceEndpoint,
    ApplicationInvocation,
)
from sugarsubstitute_shared.application_instance_transport import (
    ApplicationInstanceListener,
    bind_instance_listener,
)


def test_failed_compatibility_bind_releases_primary_address(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Allow a fresh election after a later address fails native reservation."""
    endpoints = application_instance_endpoints(tmp_path)
    assert len(endpoints) == 2

    def fail_compatibility(
        endpoint: ApplicationInstanceEndpoint,
    ) -> ApplicationInstanceListener:
        """Inject one native bind failure after the canonical endpoint is acquired."""
        if endpoint == endpoints[1]:
            raise OSError(errno.EIO, "fixture compatibility bind failed")
        return bind_instance_listener(endpoint)

    with monkeypatch.context() as patch:
        patch.setattr(
            application_instance_election, "bind_instance_listener", fail_compatibility
        )
        with pytest.raises(OSError, match="fixture compatibility bind failed"):
            ApplicationInstanceBroker.elect(
                install_root=tmp_path, invocation=ApplicationInvocation.capture(())
            )
    replacement = ApplicationInstanceBroker.elect(
        install_root=tmp_path, invocation=ApplicationInvocation.capture(())
    )
    assert replacement is not None
    replacement.close()


def test_failed_listener_thread_start_releases_every_address(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stop started listeners and release authority when another listener cannot start."""
    original_start = threading.Thread.start
    started: list[threading.Thread] = []
    calls = 0

    def start_or_fail(thread: threading.Thread) -> None:
        """Fail the second broker accept thread at the runtime thread boundary."""
        nonlocal calls
        if thread.name == "application-instance-broker":
            calls += 1
            if calls == 2:
                raise RuntimeError("fixture accept thread unavailable")
            started.append(thread)
        original_start(thread)

    with monkeypatch.context() as patch:
        patch.setattr(threading.Thread, "start", start_or_fail)
        with pytest.raises(RuntimeError, match="fixture accept thread unavailable"):
            ApplicationInstanceBroker.elect(
                install_root=tmp_path, invocation=ApplicationInvocation.capture(())
            )
    assert started
    assert all(not thread.is_alive() for thread in started)
    replacement = ApplicationInstanceBroker.elect(
        install_root=tmp_path, invocation=ApplicationInvocation.capture(())
    )
    assert replacement is not None
    replacement.close()

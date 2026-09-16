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

"""Verify that delegated startup cleanup retains native owner authority."""

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest

from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInvocation,
    ApplicationInstanceBrokerError,
)
from sugarsubstitute_shared.delegated_application_broker import (
    DelegatedApplicationBroker,
)


def test_delegated_cleanup_is_exactly_once_and_cannot_close_replacement(
    tmp_path: Path,
) -> None:
    """Release through authenticated IPC without granting authority over later resources."""
    owner = ApplicationInstanceBroker.elect(
        install_root=tmp_path, invocation=ApplicationInvocation.capture(["launcher"])
    )
    assert owner is not None
    released: list[str] = []
    with owner:
        identity = owner.register_startup_resource(lambda: released.append("first"))
        delegate = DelegatedApplicationBroker(owner.child_environment({}))
        try:
            with ThreadPoolExecutor(max_workers=3) as requests:
                list(
                    requests.map(
                        lambda _: delegate.release_startup_resource(identity), range(3)
                    )
                )
            assert released == ["first"]
            replacement = owner.register_startup_resource(
                lambda: released.append("second")
            )
            with pytest.raises(ApplicationInstanceBrokerError):
                delegate.release_startup_resource(identity)
            assert released == ["first"]
            delegate.release_startup_resource(replacement)
            assert released == ["first", "second"]
        finally:
            delegate.close()
        owner.bind_startup_presenter(lambda _: "retained-owner")
        assert (
            ApplicationInstanceBroker.elect(
                install_root=tmp_path,
                invocation=ApplicationInvocation.capture(["launcher"]),
            )
            is None
        )


def test_failed_cleanup_can_be_retried_without_replacing_live_resource(
    tmp_path: Path,
) -> None:
    """Keep cleanup authority after failure and reject replacement until cleanup succeeds."""
    owner = ApplicationInstanceBroker.elect(
        install_root=tmp_path, invocation=ApplicationInvocation.capture(["launcher"])
    )
    assert owner is not None
    attempts: list[int] = []

    def cleanup() -> None:
        """Fail once at the external resource boundary, then complete cleanup."""
        attempts.append(1)
        if len(attempts) == 1:
            raise OSError("controlled cleanup failure")

    with owner:
        identity = owner.register_startup_resource(cleanup)
        with pytest.raises(RuntimeError, match="previous startup resource"):
            owner.register_startup_resource(lambda: None)
        delegate = DelegatedApplicationBroker(owner.child_environment({}))
        try:
            with pytest.raises(ApplicationInstanceBrokerError):
                delegate.release_startup_resource(identity)
            assert len(attempts) == 1
            delegate.release_startup_resource(identity)
            delegate.release_startup_resource(identity)
            assert len(attempts) == 2
        finally:
            delegate.close()
    assert len(attempts) == 2


def test_owner_shutdown_releases_resource_without_a_delegate_request(
    tmp_path: Path,
) -> None:
    """Clean up when the generation exits before it can return startup ownership."""
    owner = ApplicationInstanceBroker.elect(
        install_root=tmp_path, invocation=ApplicationInvocation.capture(["launcher"])
    )
    assert owner is not None
    released: list[bool] = []
    with owner:
        owner.register_startup_resource(lambda: released.append(True))
    owner.close()
    assert released == [True]
    with pytest.raises(RuntimeError, match="owner is closed"):
        owner.register_startup_resource(lambda: None)

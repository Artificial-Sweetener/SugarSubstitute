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

"""Keep native singleton authority stable across launch environment and desktop changes."""

from __future__ import annotations

from pathlib import Path

import pytest

from sugarsubstitute_shared.application_instance_identity import instance_identity


@pytest.mark.parametrize(
    "label",
    ["USERNAME", "USER", "SESSIONNAME", "XDG_SESSION_ID", "WAYLAND_DISPLAY", "DISPLAY"],
)
def test_owner_identity_does_not_follow_environment_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, label: str
) -> None:
    """Keep the same OS account and installation in one election namespace."""
    monkeypatch.setenv(label, "fixture-original")
    original = instance_identity(tmp_path)
    monkeypatch.setenv(label, "fixture-changed")
    assert instance_identity(tmp_path) == original
    assert instance_identity(tmp_path / ".") == original
    assert instance_identity(tmp_path / "different-installation") != original


@pytest.mark.platforms("windows")
def test_windows_path_spellings_share_one_owner(tmp_path: Path) -> None:
    """Keep case and extended-length spelling from creating duplicate owners."""
    from sugarsubstitute_shared.windows_long_paths import extended_length_path

    identity = instance_identity(tmp_path)
    assert instance_identity(Path(str(tmp_path).upper())) == identity
    assert instance_identity(Path(extended_length_path(tmp_path))) == identity


@pytest.mark.platforms("windows")
def test_kernel_account_identity_separates_owners(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Use the native account boundary even when launch labels remain identical."""
    from sugarsubstitute_shared import windows_process_security

    def first_account(pid: int | None) -> str:
        """Supply an account SID at the operating-system boundary."""
        assert pid is None
        return "S-1-5-21-1001"

    def second_account(pid: int | None) -> str:
        """Supply a different account without changing process environment."""
        assert pid is None
        return "S-1-5-21-1002"

    monkeypatch.setattr(windows_process_security, "process_user_sid", first_account)
    first = instance_identity(tmp_path)
    monkeypatch.setattr(windows_process_security, "process_user_sid", second_account)
    assert instance_identity(tmp_path) != first


@pytest.mark.platforms("windows")
def test_account_lookup_failure_cannot_create_an_alternative_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reject unverifiable authority rather than electing under an invented identity."""
    from sugarsubstitute_shared import windows_process_security

    def unavailable_account(pid: int | None) -> str:
        """Expose an operating-system identity failure to the election boundary."""
        raise OSError("fixture account lookup unavailable")

    monkeypatch.setattr(
        windows_process_security, "process_user_sid", unavailable_account
    )
    with pytest.raises(OSError, match="fixture account lookup unavailable"):
        instance_identity(tmp_path)


@pytest.mark.platforms("windows")
def test_changed_session_labels_forward_to_existing_native_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Route a changed launch environment through one real secured Windows pipe."""
    from sugarsubstitute_shared.application_instance_broker import (
        ApplicationInstanceBroker,
    )
    from sugarsubstitute_shared.application_instance_protocol import (
        ApplicationInvocation,
        RoutedApplicationInvocation,
    )
    from sugarsubstitute_shared.application_supervisor_client import (
        ApplicationSupervisorClient,
    )

    first = ApplicationInstanceBroker.elect(
        install_root=tmp_path, invocation=ApplicationInvocation.capture(())
    )
    assert first is not None
    client = None
    second = None
    received: list[ApplicationInvocation] = []
    try:
        client = ApplicationSupervisorClient.connect_from_environment(
            first.child_environment({})
        )
        assert client is not None
        connected = client

        def present(request: RoutedApplicationInvocation) -> None:
            """Acknowledge delivery without constructing a window or taking focus."""
            received.append(request.invocation)
            connected.complete_invocation(
                request.request_id, outcome="presented", surface="headless-fixture"
            )

        client.bind_invocation_handler(present)
        for label in (
            "USERNAME",
            "USER",
            "SESSIONNAME",
            "XDG_SESSION_ID",
            "WAYLAND_DISPLAY",
            "DISPLAY",
        ):
            monkeypatch.setenv(label, "fixture-changed")
        invocation = ApplicationInvocation.capture(("fixture-document.sugar",))
        second = ApplicationInstanceBroker.elect(
            install_root=tmp_path, invocation=invocation
        )
        assert second is None, "Environment changes admitted a second native owner"
        assert received == [invocation]
    finally:
        if second is not None:
            second.close()
        if client is not None:
            client.close()
        first.close()

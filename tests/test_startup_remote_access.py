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

"""Tests for the launch-scoped sticky remote-access decision."""

from __future__ import annotations

import errno
from email.message import Message
from urllib.error import HTTPError, URLError

import pytest

from sugarsubstitute_shared.startup_remote_access import (
    STARTUP_REMOTE_DEGRADED_ENV,
    StartupRemoteAccess,
    StartupConnectivityError,
    is_startup_connectivity_failure,
    startup_connectivity_error_from_output,
)


def test_remote_access_preserves_first_failure_for_the_launch() -> None:
    """Later outcomes must not replace or clear the first degradation."""

    remote_access = StartupRemoteAccess()

    remote_access.degrade(reason="manifest")
    remote_access.degrade(reason="nodepacks")

    assert remote_access.allows_remote_work is False
    assert remote_access.degradation_reason == "manifest"
    assert remote_access.child_environment({}) == {STARTUP_REMOTE_DEGRADED_ENV: "1"}


def test_available_launch_clears_inherited_degradation() -> None:
    """A fresh launcher decision must reset degradation from an older process."""

    remote_access = StartupRemoteAccess()

    assert remote_access.child_environment(
        {STARTUP_REMOTE_DEGRADED_ENV: "1", "PATH": "runtime"}
    ) == {"PATH": "runtime"}


@pytest.mark.parametrize(
    "error",
    [
        ConnectionError("connection refused"),
        TimeoutError("request timed out"),
        URLError("name resolution failed"),
        OSError(errno.ENETUNREACH, "network unreachable"),
        StartupConnectivityError("remote operation unavailable"),
    ],
)
def test_connectivity_classifier_accepts_only_remote_access_failures(
    error: BaseException,
) -> None:
    """Known transport failures must activate the launch fallback."""

    assert is_startup_connectivity_failure(error)


@pytest.mark.parametrize(
    "error",
    [
        UnicodeEncodeError("cp1252", "\u2588", 0, 1, "cannot encode"),
        OSError("local filesystem unavailable"),
        ValueError("invalid manifest"),
        HTTPError("https://example.invalid", 404, "not found", Message(), None),
    ],
)
def test_connectivity_classifier_rejects_local_and_protocol_failures(
    error: BaseException,
) -> None:
    """Local defects and valid HTTP responses must retain normal error semantics."""

    assert not is_startup_connectivity_failure(error)


def test_connectivity_classifier_follows_wrapped_transport_failure() -> None:
    """Infrastructure wrappers must not hide a transport failure from startup."""

    try:
        raise ConnectionError("offline")
    except ConnectionError as cause:
        wrapped = RuntimeError("repository update failed")
        wrapped.__cause__ = cause

    assert is_startup_connectivity_failure(wrapped)


def test_subprocess_output_classifier_requires_a_connectivity_marker() -> None:
    """Only recognizable network diagnostics may convert subprocess failure."""

    connectivity_error = startup_connectivity_error_from_output(
        "Retrying after NewConnectionError: getaddrinfo failed",
        operation="install requirements",
    )

    assert isinstance(connectivity_error, StartupConnectivityError)
    assert (
        startup_connectivity_error_from_output(
            "ERROR: No matching distribution found for imaginary-package",
            operation="install requirements",
        )
        is None
    )


@pytest.mark.parametrize(
    "output",
    [
        "fatal: unable to access repository: Could not resolve host: github.com",
        "failed to connect to github.com port 443 after 1000 ms",
        "Temporary failure resolving 'github.com'",
    ],
)
def test_subprocess_output_classifier_accepts_common_git_diagnostics(
    output: str,
) -> None:
    """Git transport diagnostics must activate the startup fallback."""

    assert (
        startup_connectivity_error_from_output(
            output,
            operation="update a repository",
        )
        is not None
    )

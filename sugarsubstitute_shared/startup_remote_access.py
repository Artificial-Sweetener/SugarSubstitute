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

"""Own the sticky remote-access decision for one application launch."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import errno
import ssl
from urllib.error import HTTPError, URLError


STARTUP_REMOTE_DEGRADED_ENV = "SUGARSUBSTITUTE_STARTUP_REMOTE_DEGRADED"

_CONNECTIVITY_ERRNOS = frozenset(
    value
    for name in (
        "EADDRNOTAVAIL",
        "ECONNABORTED",
        "ECONNREFUSED",
        "ECONNRESET",
        "EHOSTDOWN",
        "EHOSTUNREACH",
        "ENETDOWN",
        "ENETRESET",
        "ENETUNREACH",
        "ETIMEDOUT",
    )
    if (value := getattr(errno, name, None)) is not None
)
_CONNECTIVITY_WINERRORS = frozenset(
    {10050, 10051, 10052, 10053, 10054, 10060, 10061, 10065, 11001}
)
_CONNECTIVITY_EXCEPTION_IDENTITIES = frozenset(
    {
        ("httpx", "ConnectError"),
        ("httpx", "ConnectTimeout"),
        ("httpx", "NetworkError"),
        ("httpx", "ReadTimeout"),
        ("httpx", "TimeoutException"),
        ("httpx", "WriteTimeout"),
        ("requests.exceptions", "ConnectionError"),
        ("requests.exceptions", "ConnectTimeout"),
        ("requests.exceptions", "ReadTimeout"),
        ("requests.exceptions", "Timeout"),
        ("urllib3.exceptions", "ConnectTimeoutError"),
        ("urllib3.exceptions", "NameResolutionError"),
        ("urllib3.exceptions", "NewConnectionError"),
        ("urllib3.exceptions", "ReadTimeoutError"),
    }
)
_CONNECTIVITY_OUTPUT_MARKERS = (
    "cannot connect to proxy",
    "could not resolve host",
    "connection refused",
    "connection reset",
    "connection timed out",
    "connecttimeouterror",
    "failed to connect",
    "failed to establish a new connection",
    "getaddrinfo failed",
    "name or service not known",
    "name resolution",
    "nameresolutionerror",
    "network is unreachable",
    "newconnectionerror",
    "no route to host",
    "operation timed out",
    "proxyerror",
    "read timed out",
    "readtimeouterror",
    "temporary failure in name resolution",
    "temporary failure resolving",
)


class StartupConnectivityError(RuntimeError):
    """Report proven remote transport loss during automatic startup work."""


def is_startup_connectivity_failure(error: BaseException) -> bool:
    """Return whether an exception chain proves remote transport is unavailable."""

    current: BaseException | None = error
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if _is_connectivity_exception(current):
            return True
        current = current.__cause__ or current.__context__
    return False


def startup_connectivity_error_from_output(
    output: str,
    *,
    operation: str,
) -> StartupConnectivityError | None:
    """Convert explicit subprocess transport diagnostics into a typed failure."""

    normalized_output = " ".join(output.casefold().split())
    if not any(marker in normalized_output for marker in _CONNECTIVITY_OUTPUT_MARKERS):
        return None
    return StartupConnectivityError(
        f"Remote access became unavailable while attempting to {operation}."
    )


def _is_connectivity_exception(error: BaseException) -> bool:
    """Classify one exception without inferring connectivity from arbitrary text."""

    if isinstance(error, StartupConnectivityError):
        return True
    if isinstance(error, HTTPError):
        return False
    if isinstance(error, (ConnectionError, TimeoutError, URLError, ssl.SSLError)):
        return True
    if isinstance(error, OSError) and (
        error.errno in _CONNECTIVITY_ERRNOS
        or getattr(error, "winerror", None) in _CONNECTIVITY_WINERRORS
    ):
        return True
    error_type = type(error)
    return (
        error_type.__module__,
        error_type.__name__,
    ) in _CONNECTIVITY_EXCEPTION_IDENTITIES


@dataclass(slots=True)
class StartupRemoteAccess:
    """Track whether automatic remote work remains safe during one launch."""

    _degradation_reason: str | None = None

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> StartupRemoteAccess:
        """Restore the launcher's sticky degradation handoff."""

        if environment.get(STARTUP_REMOTE_DEGRADED_ENV) == "1":
            return cls(_degradation_reason="launcher_remote_work_failed")
        return cls()

    @property
    def allows_remote_work(self) -> bool:
        """Return whether another automatic remote operation may begin."""

        return self._degradation_reason is None

    @property
    def degradation_reason(self) -> str | None:
        """Return the first failure that fixed this launch to local fallbacks."""

        return self._degradation_reason

    def degrade(self, *, reason: str) -> None:
        """Latch the first remote failure for the remainder of this launch."""

        if self._degradation_reason is None:
            self._degradation_reason = reason

    def child_environment(self, environment: Mapping[str, str]) -> dict[str, str]:
        """Encode this launch decision into one isolated child environment."""

        child_environment = dict(environment)
        if self.allows_remote_work:
            child_environment.pop(STARTUP_REMOTE_DEGRADED_ENV, None)
        else:
            child_environment[STARTUP_REMOTE_DEGRADED_ENV] = "1"
        return child_environment


__all__ = [
    "STARTUP_REMOTE_DEGRADED_ENV",
    "StartupConnectivityError",
    "StartupRemoteAccess",
    "is_startup_connectivity_failure",
    "startup_connectivity_error_from_output",
]

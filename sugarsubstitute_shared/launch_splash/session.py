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

"""Represent launch-splash session connection details."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import secrets
import tempfile


SPLASH_ENDPOINT_ARG = "--splash-session-endpoint"
SPLASH_TOKEN_ARG = "--splash-session-token"
SPLASH_HOST_PID_ARG = "--splash-session-host-pid"
DEFAULT_SPLASH_HOST = "127.0.0.1"
MINIMUM_TOKEN_LENGTH = 24


@dataclass(frozen=True, slots=True)
class SplashSessionSpec:
    """Describe one local launch-splash IPC session."""

    host: str
    port: int
    token: str
    host_pid: int

    @property
    def endpoint(self) -> str:
        """Return the command-line endpoint representation."""

        return f"{self.host}:{self.port}"


def create_splash_session_spec(
    *,
    port: int,
    host: str = DEFAULT_SPLASH_HOST,
    token: str | None = None,
    host_pid: int | None = None,
) -> SplashSessionSpec:
    """Create a validated launch-splash session spec."""

    resolved_token = token if token is not None else secrets.token_urlsafe(32)
    resolved_host_pid = os.getpid() if host_pid is None else host_pid
    spec = SplashSessionSpec(
        host=host,
        port=port,
        token=resolved_token,
        host_pid=resolved_host_pid,
    )
    validate_splash_session_spec(spec)
    return spec


def validate_splash_session_spec(spec: SplashSessionSpec) -> None:
    """Reject malformed splash session connection details."""

    if spec.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("Splash session host must be local.")
    if not (0 < spec.port <= 65535):
        raise ValueError("Splash session port must be a valid TCP port.")
    if len(spec.token) < MINIMUM_TOKEN_LENGTH:
        raise ValueError("Splash session token is too short.")
    if spec.host_pid <= 0:
        raise ValueError("Splash session host PID must be positive.")


def splash_session_args(spec: SplashSessionSpec) -> list[str]:
    """Serialize a splash session spec into app launch arguments."""

    validate_splash_session_spec(spec)
    return [
        f"{SPLASH_ENDPOINT_ARG}={spec.endpoint}",
        f"{SPLASH_TOKEN_ARG}={spec.token}",
        f"{SPLASH_HOST_PID_ARG}={spec.host_pid}",
    ]


def splash_session_from_args(argv: list[str]) -> SplashSessionSpec | None:
    """Parse a splash session spec from command-line arguments when present."""

    values = _named_arg_values(argv)
    endpoint = values.get(SPLASH_ENDPOINT_ARG)
    token = values.get(SPLASH_TOKEN_ARG)
    host_pid = values.get(SPLASH_HOST_PID_ARG)
    if endpoint is None and token is None and host_pid is None:
        return None
    if endpoint is None or token is None or host_pid is None:
        raise ValueError("Splash session arguments must be supplied as a complete set.")
    host, port = _parse_endpoint(endpoint)
    try:
        parsed_host_pid = int(host_pid)
    except ValueError as error:
        raise ValueError("Splash session host PID must be an integer.") from error
    spec = SplashSessionSpec(
        host=host,
        port=port,
        token=token,
        host_pid=parsed_host_pid,
    )
    validate_splash_session_spec(spec)
    return spec


def splash_cancel_signal_path(spec: SplashSessionSpec) -> Path:
    """Return the local cancel signal path for one authenticated session."""

    validate_splash_session_spec(spec)
    token_digest = hashlib.sha256(spec.token.encode("utf-8")).hexdigest()[:32]
    return Path(tempfile.gettempdir()) / (
        f"sugarsubstitute-splash-cancel-{token_digest}.flag"
    )


def _named_arg_values(argv: list[str]) -> dict[str, str]:
    """Return supported `--name=value` splash session arguments."""

    values: dict[str, str] = {}
    for raw_argument in argv:
        if "=" not in raw_argument:
            continue
        name, value = raw_argument.split("=", 1)
        if name in {SPLASH_ENDPOINT_ARG, SPLASH_TOKEN_ARG, SPLASH_HOST_PID_ARG}:
            values[name] = value
    return values


def _parse_endpoint(endpoint: str) -> tuple[str, int]:
    """Parse a local host and port endpoint."""

    host, separator, raw_port = endpoint.rpartition(":")
    if not separator or not host:
        raise ValueError("Splash session endpoint must be host:port.")
    try:
        port = int(raw_port)
    except ValueError as error:
        raise ValueError("Splash session port must be an integer.") from error
    return host, port

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

"""Confirm splash disposal before revealing another top-level surface."""

from __future__ import annotations

from typing import Protocol

from substitute.shared.logging.logger import get_logger, log_error, log_exception

_LOGGER = get_logger("app.bootstrap.splash_surface_handoff")


class SplashCloseProtocol(Protocol):
    """Describe a splash whose close call confirms native disposal."""

    def close(self) -> object:
        """Close the splash or report an unconfirmed close."""


class SplashHandoffError(RuntimeError):
    """Prevent a second surface from appearing after unconfirmed disposal."""


def close_splash_before_reveal(
    splash: SplashCloseProtocol,
    *,
    replacement: str,
) -> None:
    """Fail closed when a splash could remain visible beside its replacement."""

    try:
        close_result = splash.close()
    except Exception:
        log_exception(
            _LOGGER,
            "Launch splash closure failed before surface reveal",
            replacement=replacement,
        )
        raise
    if close_result is False:
        log_error(
            _LOGGER,
            "Launch splash closure was not acknowledged before surface reveal",
            replacement=replacement,
        )
        raise SplashHandoffError(
            f"Launch splash closure was not confirmed before {replacement} reveal."
        )


__all__ = ["SplashCloseProtocol", "SplashHandoffError", "close_splash_before_reveal"]

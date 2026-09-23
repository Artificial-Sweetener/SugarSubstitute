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

"""Resolve immutable application launch context shared across process owners."""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum
from pathlib import Path


_LAUNCH_INTENT_PREFIX = "--launch-intent="


class ApplicationLaunchIntent(str, Enum):
    """Identify presentation policy for one application launch."""

    NORMAL = "normal"
    SETUP = "setup"


def application_launch_intent(argv: Sequence[str]) -> ApplicationLaunchIntent:
    """Return the explicit launch intent, defaulting compatible callers to normal."""

    for raw_argument in argv:
        if not raw_argument.startswith(_LAUNCH_INTENT_PREFIX):
            continue
        raw_intent = raw_argument[len(_LAUNCH_INTENT_PREFIX) :].strip()
        try:
            return ApplicationLaunchIntent(raw_intent)
        except ValueError as error:
            raise ValueError(
                f"Unsupported application launch intent: {raw_intent}"
            ) from error
    return ApplicationLaunchIntent.NORMAL


def application_launch_intent_argument(intent: ApplicationLaunchIntent) -> str:
    """Serialize one launch intent for a supervised process boundary."""

    return f"{_LAUNCH_INTENT_PREFIX}{intent.value}"


def explicit_application_launch_install_root(
    argv: Sequence[str],
) -> Path | None:
    """Resolve the explicit installation root carried by launch arguments."""

    prefix = "--install-root="
    for raw_argument in argv:
        if raw_argument.startswith(prefix):
            raw_path = raw_argument[len(prefix) :].strip()
            if raw_path:
                return Path(raw_path).expanduser().resolve()
    return None


def application_launch_install_root(
    argv: Sequence[str],
    *,
    app_root: Path,
) -> Path:
    """Resolve the installation root before application bootstrap starts."""

    return explicit_application_launch_install_root(argv) or app_root.resolve()


__all__ = [
    "ApplicationLaunchIntent",
    "application_launch_intent",
    "application_launch_intent_argument",
    "application_launch_install_root",
    "explicit_application_launch_install_root",
]

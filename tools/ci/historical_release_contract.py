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

"""Recreate the package-index view owned by one immutable historical release."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path


UV_EXCLUDE_NEWER_ENV = "UV_EXCLUDE_NEWER"
MANAGED_COMFY_OUTPUT_LOG_ENV = "SUGAR_SUBSTITUTE_STARTUP_HARNESS_COMFY_OUTPUT_LOG"
HISTORICAL_MANAGED_COMFY_OUTPUT_LOG_NAME = "historical-managed-comfy-startup.log"


class HistoricalReleaseContractError(ValueError):
    """Report historical metadata that cannot define a safe resolver cutoff."""


def historical_install_environment(
    environment: Mapping[str, str],
    *,
    published_at: str,
    install_root: Path,
) -> dict[str, str]:
    """Prepare publication-time resolution and durable managed-runtime evidence."""

    validated_published_at(published_at)
    historical_environment = dict(environment)
    historical_environment[UV_EXCLUDE_NEWER_ENV] = published_at
    historical_environment[MANAGED_COMFY_OUTPUT_LOG_ENV] = str(
        (install_root / HISTORICAL_MANAGED_COMFY_OUTPUT_LOG_NAME).resolve()
    )
    return historical_environment


def validated_published_at(value: object) -> str:
    """Return one timezone-qualified RFC 3339 publication timestamp."""

    if not isinstance(value, str) or not value:
        raise HistoricalReleaseContractError(
            "Historical release published_at is missing."
        )
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise HistoricalReleaseContractError(
            f"Historical release published_at is invalid: {value!r}."
        ) from error
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise HistoricalReleaseContractError(
            "Historical release published_at must include a timezone."
        )
    return value


__all__ = [
    "HISTORICAL_MANAGED_COMFY_OUTPUT_LOG_NAME",
    "HistoricalReleaseContractError",
    "MANAGED_COMFY_OUTPUT_LOG_ENV",
    "UV_EXCLUDE_NEWER_ENV",
    "historical_install_environment",
    "validated_published_at",
]

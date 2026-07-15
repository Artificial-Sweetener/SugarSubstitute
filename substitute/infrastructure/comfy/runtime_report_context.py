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

"""Fetch Comfy runtime facts for diagnostic error reports."""

from __future__ import annotations

from substitute.application.errors import RuntimeReportContext
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.runtime_info_client import fetch_comfy_runtime_info
from substitute.infrastructure.python_packages import (
    SUGARSUBSTITUTE_DISTRIBUTION_NAMES,
    installed_distribution_version,
)


def fetch_runtime_report_context(
    endpoint: ComfyEndpoint,
    *,
    timeout_seconds: float = 3.0,
) -> RuntimeReportContext:
    """Return report runtime context enriched with Comfy `/system_stats` data."""

    substitute_version = _substitute_version()
    runtime_info = fetch_comfy_runtime_info(
        endpoint,
        timeout_seconds=timeout_seconds,
    )
    if runtime_info is None:
        return RuntimeReportContext(substitute_version=substitute_version)

    return RuntimeReportContext(
        comfy_version=runtime_info.comfy_version,
        substitute_version=substitute_version,
        os_name=runtime_info.os_name,
        python_version=runtime_info.python_version,
        embedded_python=runtime_info.embedded_python,
        pytorch_version=runtime_info.pytorch_version,
        devices=runtime_info.devices,
        launch_args=runtime_info.launch_args,
    )


def _substitute_version() -> str:
    """Return the installed Substitute version or a source-checkout label."""

    return installed_distribution_version(
        SUGARSUBSTITUTE_DISTRIBUTION_NAMES,
        fallback="source checkout",
    )


__all__ = ["fetch_runtime_report_context"]

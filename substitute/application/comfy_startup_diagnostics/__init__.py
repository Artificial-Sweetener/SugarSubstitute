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

"""Expose Comfy startup diagnostic collection services."""

from substitute.application.comfy_startup_diagnostics.collector import (
    ComfyStartupDiagnosticsCollector,
)
from substitute.application.comfy_startup_diagnostics.enrichment import (
    StartupDiagnosticsMetadataEnricher,
)
from substitute.application.comfy_startup_diagnostics.summary import (
    recoverable_unignored_incidents,
    render_startup_diagnostics_report,
)
from substitute.application.comfy_startup_diagnostics.startup_failure_report_service import (
    build_startup_failure_report,
    build_startup_readiness_timeout_incident,
    build_startup_runtime_compatibility_incident,
)
from substitute.application.comfy_startup_diagnostics.titlebar_state import (
    StartupDiagnosticsTitlebarState,
    prepare_startup_diagnostics_titlebar_state,
)

__all__ = [
    "ComfyStartupDiagnosticsCollector",
    "StartupDiagnosticsMetadataEnricher",
    "StartupDiagnosticsTitlebarState",
    "build_startup_failure_report",
    "build_startup_readiness_timeout_incident",
    "build_startup_runtime_compatibility_incident",
    "prepare_startup_diagnostics_titlebar_state",
    "recoverable_unignored_incidents",
    "render_startup_diagnostics_report",
]

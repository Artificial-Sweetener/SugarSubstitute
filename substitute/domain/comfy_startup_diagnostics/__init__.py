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

"""Expose Comfy startup diagnostics domain models and helpers."""

from substitute.domain.comfy_startup_diagnostics.models import (
    ComfyStartupIncident,
    ComfyStartupIncidentKind,
    ComfyStartupIncidentSeverity,
    build_startup_incident_fingerprint,
    normalized_startup_incident_source,
)
from substitute.domain.comfy_startup_diagnostics.remediation import (
    StartupRemediation,
    StartupRemediationFacts,
    StartupTracebackLocation,
    build_startup_remediation,
    extract_missing_module_name,
    extract_relevant_traceback_location,
)
from substitute.domain.comfy_startup_diagnostics.repository_links import (
    ExtensionRepositoryLinks,
    normalize_repository_links,
    repository_links_from_github_id,
)

__all__ = [
    "ComfyStartupIncident",
    "ComfyStartupIncidentKind",
    "ComfyStartupIncidentSeverity",
    "ExtensionRepositoryLinks",
    "StartupRemediation",
    "StartupRemediationFacts",
    "StartupTracebackLocation",
    "build_startup_incident_fingerprint",
    "build_startup_remediation",
    "extract_missing_module_name",
    "extract_relevant_traceback_location",
    "normalize_repository_links",
    "normalized_startup_incident_source",
    "repository_links_from_github_id",
]

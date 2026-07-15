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

"""Prepare titlebar state for recoverable Comfy startup diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.comfy_startup_diagnostics.enrichment import (
    StartupDiagnosticsMetadataEnricher,
)
from substitute.application.comfy_startup_diagnostics.summary import (
    recoverable_unignored_incidents,
)
from substitute.application.ports.comfy_extension_metadata_provider import (
    ComfyExtensionMetadataProvider,
)
from substitute.domain.comfy_startup_diagnostics import (
    ComfyStartupIncident,
    ComfyStartupIncidentSeverity,
)


@dataclass(frozen=True)
class StartupDiagnosticsTitlebarState:
    """Describe startup diagnostics that should be exposed in shell chrome."""

    incidents: tuple[ComfyStartupIncident, ...]
    ignored_count: int
    transcript: tuple[str, ...]

    @property
    def total_count(self) -> int:
        """Return the number of visible unignored startup incidents."""

        return len(self.incidents)

    @property
    def error_count(self) -> int:
        """Return the number of visible startup incidents with error severity."""

        return _severity_count(self.incidents, ComfyStartupIncidentSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        """Return the number of visible startup incidents with warning severity."""

        return _severity_count(self.incidents, ComfyStartupIncidentSeverity.WARNING)

    @property
    def has_errors(self) -> bool:
        """Return whether the titlebar indicator should use error treatment."""

        return self.error_count > 0

    @property
    def fingerprint_set(self) -> frozenset[str]:
        """Return visible incident fingerprints for callout deduplication."""

        return frozenset(incident.fingerprint for incident in self.incidents)


def prepare_startup_diagnostics_titlebar_state(
    *,
    incidents: tuple[ComfyStartupIncident, ...],
    transcript: tuple[str, ...],
    ignored_fingerprints: frozenset[str],
    metadata_providers: tuple[ComfyExtensionMetadataProvider, ...] = (),
) -> StartupDiagnosticsTitlebarState | None:
    """Return titlebar diagnostics state when recoverable incidents remain."""

    enriched_incidents = StartupDiagnosticsMetadataEnricher(
        metadata_providers=metadata_providers,
    ).enrich(incidents)
    unignored_incidents = recoverable_unignored_incidents(
        enriched_incidents,
        ignored_fingerprints,
    )
    if not unignored_incidents:
        return None
    return StartupDiagnosticsTitlebarState(
        incidents=unignored_incidents,
        ignored_count=len(enriched_incidents) - len(unignored_incidents),
        transcript=transcript,
    )


def _severity_count(
    incidents: tuple[ComfyStartupIncident, ...],
    severity: ComfyStartupIncidentSeverity,
) -> int:
    """Return the number of incidents matching one severity."""

    return sum(1 for incident in incidents if incident.severity is severity)


__all__ = [
    "StartupDiagnosticsTitlebarState",
    "prepare_startup_diagnostics_titlebar_state",
]

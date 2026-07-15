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

"""Enrich startup diagnostics with installed extension metadata."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from substitute.application.ports.comfy_extension_metadata_provider import (
    ComfyExtensionMetadata,
    ComfyExtensionMetadataProvider,
)
from substitute.domain.comfy_startup_diagnostics import (
    ComfyStartupIncident,
    normalized_startup_incident_source,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("application.comfy_startup_diagnostics.enrichment")


class StartupDiagnosticsMetadataEnricher:
    """Attach extension repository metadata to startup incidents."""

    def __init__(
        self,
        *,
        metadata_providers: Iterable[ComfyExtensionMetadataProvider],
    ) -> None:
        """Store metadata providers in lookup priority order."""

        self._metadata_providers = tuple(metadata_providers)

    def enrich(
        self,
        incidents: tuple[ComfyStartupIncident, ...],
    ) -> tuple[ComfyStartupIncident, ...]:
        """Return incidents with repository metadata when available."""

        metadata = self._installed_metadata()
        if not metadata:
            return incidents
        return tuple(_enrich_incident(incident, metadata) for incident in incidents)

    def _installed_metadata(self) -> tuple[ComfyExtensionMetadata, ...]:
        """Return installed extension metadata from all providers."""

        installed: list[ComfyExtensionMetadata] = []
        for provider in self._metadata_providers:
            try:
                installed.extend(provider.installed_extensions().values())
            except Exception as error:
                log_warning(
                    _LOGGER,
                    "Failed to enrich startup diagnostics from extension metadata",
                    provider=type(provider).__name__,
                    error=repr(error),
                )
        return tuple(installed)


def _enrich_incident(
    incident: ComfyStartupIncident,
    metadata: tuple[ComfyExtensionMetadata, ...],
) -> ComfyStartupIncident:
    """Return one incident enriched with matching extension metadata."""

    matched = _matching_metadata(incident, metadata)
    if not matched:
        return incident
    values = dict(incident.values)
    values.setdefault("extension_label", incident.source or matched[0].key)
    _set_first(values, "extension_version", *(item.version for item in matched))
    _set_first(values, "cnr_id", *(item.cnr_id for item in matched))
    _set_first(values, "aux_id", *(item.aux_id for item in matched))
    _set_first(values, "repository_url", *(item.repository_url for item in matched))
    _set_first(values, "issues_url", *(item.issues_url for item in matched))
    _set_first(values, "repository_source", *(item.source for item in matched))
    if values == incident.values:
        return incident
    return replace(incident, values=values)


def _matching_metadata(
    incident: ComfyStartupIncident,
    metadata: tuple[ComfyExtensionMetadata, ...],
) -> tuple[ComfyExtensionMetadata, ...]:
    """Return metadata entries that identify the incident extension."""

    incident_keys = _incident_match_keys(incident)
    if not incident_keys:
        return ()
    matches = tuple(
        item
        for item in metadata
        if incident_keys.intersection(_metadata_match_keys(item))
    )
    return tuple(sorted(matches, key=_metadata_priority))


def _incident_match_keys(incident: ComfyStartupIncident) -> set[str]:
    """Return normalized lookup keys for one startup incident."""

    keys: set[str] = set()
    for value in (
        incident.source,
        normalized_startup_incident_source(incident.source),
        _string_value(incident.values.get("source")),
        _string_value(incident.values.get("extension_label")),
    ):
        if value:
            keys.add(value.casefold())
    return keys


def _metadata_match_keys(metadata: ComfyExtensionMetadata) -> set[str]:
    """Return normalized lookup keys for one extension metadata record."""

    keys = {
        value.casefold()
        for value in (metadata.key, metadata.cnr_id, metadata.aux_id)
        if value
    }
    if metadata.aux_id and "/" in metadata.aux_id:
        keys.add(metadata.aux_id.rsplit("/", maxsplit=1)[-1].casefold())
    return keys


def _metadata_priority(metadata: ComfyExtensionMetadata) -> tuple[int, int]:
    """Return sort priority favoring entries with richer link metadata."""

    return (
        0 if metadata.repository_url else 1,
        0 if metadata.version else 1,
    )


def _set_first(values: dict[str, object], key: str, *candidates: str | None) -> None:
    """Set one metadata value from the first non-empty candidate."""

    if key in values:
        return
    for candidate in candidates:
        if candidate:
            values[key] = candidate
            return


def _string_value(value: object) -> str | None:
    """Return a non-empty string metadata value."""

    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


__all__ = ["StartupDiagnosticsMetadataEnricher"]

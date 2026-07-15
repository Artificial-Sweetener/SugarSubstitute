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

"""Tests for enriching startup diagnostics with extension metadata."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.application.comfy_startup_diagnostics import (
    StartupDiagnosticsMetadataEnricher,
)
from substitute.application.ports.comfy_extension_metadata_provider import (
    ComfyExtensionMetadata,
)
from substitute.domain.comfy_startup_diagnostics import (
    ComfyStartupIncident,
    ComfyStartupIncidentKind,
    ComfyStartupIncidentSeverity,
)


class _Provider:
    """Metadata provider test double."""

    def __init__(self, metadata: Mapping[str, ComfyExtensionMetadata]) -> None:
        """Store metadata returned by the provider."""

        self._metadata = metadata

    def installed_extensions(self) -> Mapping[str, ComfyExtensionMetadata]:
        """Return configured extension metadata."""

        return self._metadata


class _FailingProvider:
    """Metadata provider that simulates lookup failure."""

    def installed_extensions(self) -> Mapping[str, ComfyExtensionMetadata]:
        """Raise a provider failure."""

        raise RuntimeError("metadata unavailable")


def test_enrichment_matches_incident_source_case_insensitively() -> None:
    """Incident source should match installed extension keys case-insensitively."""

    incident = _incident(source="ComfyUI-GGUF-FantasyTalking")
    enriched = StartupDiagnosticsMetadataEnricher(
        metadata_providers=(
            _Provider(
                {
                    "comfyui-gguf-fantasytalking": ComfyExtensionMetadata(
                        key="comfyui-gguf-fantasytalking",
                        version="48dd427",
                        cnr_id="fantasytalking",
                        aux_id="kael558/ComfyUI-GGUF-FantasyTalking",
                        repository_url=(
                            "https://github.com/kael558/ComfyUI-GGUF-FantasyTalking"
                        ),
                        issues_url=(
                            "https://github.com/kael558/ComfyUI-GGUF-FantasyTalking/issues"
                        ),
                        source="manager_installed_aux_id",
                    )
                }
            ),
        )
    ).enrich((incident,))[0]

    assert enriched.fingerprint == incident.fingerprint
    assert enriched.values["extension_version"] == "48dd427"
    assert enriched.values["cnr_id"] == "fantasytalking"
    assert enriched.values["aux_id"] == "kael558/ComfyUI-GGUF-FantasyTalking"
    assert (
        enriched.values["repository_url"]
        == "https://github.com/kael558/ComfyUI-GGUF-FantasyTalking"
    )
    assert (
        enriched.values["issues_url"]
        == "https://github.com/kael558/ComfyUI-GGUF-FantasyTalking/issues"
    )
    assert enriched.values["repository_source"] == "manager_installed_aux_id"


def test_enrichment_preserves_existing_values_and_prefers_link_metadata() -> None:
    """Existing incident values should remain while richer provider links are added."""

    incident = _incident(
        source="comfyui-impact-subpack",
        values={"location": "nodes.py:12", "missing_module": "einops"},
    )
    enriched = StartupDiagnosticsMetadataEnricher(
        metadata_providers=(
            _Provider(
                {
                    "comfyui-impact-subpack": ComfyExtensionMetadata(
                        key="comfyui-impact-subpack",
                        version="1.3.5",
                        cnr_id="comfyui-impact-subpack",
                    )
                }
            ),
            _Provider(
                {
                    "comfyui-impact-subpack": ComfyExtensionMetadata(
                        key="comfyui-impact-subpack",
                        repository_url=(
                            "https://github.com/ltdrdata/ComfyUI-Impact-Subpack"
                        ),
                        issues_url=(
                            "https://github.com/ltdrdata/ComfyUI-Impact-Subpack/issues"
                        ),
                        source="local_git_remote",
                    )
                }
            ),
        )
    ).enrich((incident,))[0]

    assert enriched.values["location"] == "nodes.py:12"
    assert enriched.values["missing_module"] == "einops"
    assert enriched.values["extension_version"] == "1.3.5"
    assert enriched.values["repository_url"] == (
        "https://github.com/ltdrdata/ComfyUI-Impact-Subpack"
    )
    assert enriched.values["repository_source"] == "local_git_remote"


def test_unmatched_incidents_are_returned_unchanged() -> None:
    """Incidents without matching metadata should keep identity and values."""

    incident = _incident(source="UnknownExtension")
    enriched = StartupDiagnosticsMetadataEnricher(
        metadata_providers=(_Provider({}),),
    ).enrich((incident,))[0]

    assert enriched is incident


def test_provider_failure_is_non_fatal() -> None:
    """Metadata provider failures should not prevent diagnostics display."""

    incident = _incident(source="BrokenNode")
    enriched = StartupDiagnosticsMetadataEnricher(
        metadata_providers=(_FailingProvider(),),
    ).enrich((incident,))

    assert enriched == (incident,)


def _incident(
    *,
    source: str,
    values: dict[str, object] | None = None,
) -> ComfyStartupIncident:
    """Return one deterministic startup incident."""

    return ComfyStartupIncident(
        kind=ComfyStartupIncidentKind.CUSTOM_NODE_IMPORT_FAILED,
        severity=ComfyStartupIncidentSeverity.ERROR,
        title="Extension failed to load",
        message="SyntaxError: broken",
        source=source,
        exception_type="SyntaxError",
        fingerprint=f"fingerprint-{source}",
        values=values or {},
    )

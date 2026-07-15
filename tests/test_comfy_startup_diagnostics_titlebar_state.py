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

"""Tests for titlebar state prepared from Comfy startup diagnostics."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.application.comfy_startup_diagnostics import (
    StartupDiagnosticsTitlebarState,
    prepare_startup_diagnostics_titlebar_state,
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
    """Metadata provider that simulates a lookup failure."""

    def installed_extensions(self) -> Mapping[str, ComfyExtensionMetadata]:
        """Raise a provider failure."""

        raise RuntimeError("metadata unavailable")


def test_titlebar_state_reports_counts_and_fingerprints() -> None:
    """Titlebar state should expose total, severity, and fingerprint facts."""

    state = StartupDiagnosticsTitlebarState(
        incidents=(
            _incident("error-a", ComfyStartupIncidentSeverity.ERROR),
            _incident("warning-a", ComfyStartupIncidentSeverity.WARNING),
        ),
        ignored_count=3,
        transcript=("line",),
    )

    assert state.total_count == 2
    assert state.error_count == 1
    assert state.warning_count == 1
    assert state.has_errors is True
    assert state.fingerprint_set == frozenset(
        {"fingerprint-error-a", "fingerprint-warning-a"}
    )
    assert state.ignored_count == 3
    assert state.transcript == ("line",)


def test_warning_only_titlebar_state_uses_warning_treatment() -> None:
    """Warning-only diagnostics should not request error badge treatment."""

    state = StartupDiagnosticsTitlebarState(
        incidents=(_incident("warning-a", ComfyStartupIncidentSeverity.WARNING),),
        ignored_count=0,
        transcript=(),
    )

    assert state.error_count == 0
    assert state.warning_count == 1
    assert state.has_errors is False


def test_prepare_titlebar_state_returns_none_when_all_recoverable_incidents_ignored() -> (
    None
):
    """Preparation should suppress the titlebar state when all incidents are ignored."""

    incident = _incident("ignored", ComfyStartupIncidentSeverity.ERROR)

    state = prepare_startup_diagnostics_titlebar_state(
        incidents=(incident,),
        transcript=(),
        ignored_fingerprints=frozenset({incident.fingerprint}),
    )

    assert state is None


def test_prepare_titlebar_state_filters_fatal_incidents() -> None:
    """Fatal incidents should stay out of recoverable titlebar diagnostics."""

    state = prepare_startup_diagnostics_titlebar_state(
        incidents=(
            _incident("fatal", ComfyStartupIncidentSeverity.FATAL),
            _incident("warning", ComfyStartupIncidentSeverity.WARNING),
        ),
        transcript=("startup",),
        ignored_fingerprints=frozenset(),
    )

    assert state is not None
    assert state.total_count == 1
    assert state.incidents[0].fingerprint == "fingerprint-warning"
    assert state.ignored_count == 1
    assert state.transcript == ("startup",)


def test_prepare_titlebar_state_preserves_enriched_repository_metadata() -> None:
    """Metadata enrichment should happen before titlebar state is returned."""

    state = prepare_startup_diagnostics_titlebar_state(
        incidents=(_incident("BrokenExtension", ComfyStartupIncidentSeverity.ERROR),),
        transcript=(),
        ignored_fingerprints=frozenset(),
        metadata_providers=(
            _Provider(
                {
                    "BrokenExtension": ComfyExtensionMetadata(
                        key="BrokenExtension",
                        version="123abc",
                        repository_url="https://github.com/example/BrokenExtension",
                        issues_url="https://github.com/example/BrokenExtension/issues",
                        source="manager_installed_aux_id",
                    )
                }
            ),
        ),
    )

    assert state is not None
    assert state.incidents[0].values["extension_version"] == "123abc"
    assert (
        state.incidents[0].values["repository_url"]
        == "https://github.com/example/BrokenExtension"
    )
    assert (
        state.incidents[0].values["issues_url"]
        == "https://github.com/example/BrokenExtension/issues"
    )


def test_prepare_titlebar_state_survives_metadata_provider_failure() -> None:
    """Metadata provider failures should not block titlebar diagnostics state."""

    incident = _incident("BrokenExtension", ComfyStartupIncidentSeverity.ERROR)

    state = prepare_startup_diagnostics_titlebar_state(
        incidents=(incident,),
        transcript=(),
        ignored_fingerprints=frozenset(),
        metadata_providers=(_FailingProvider(),),
    )

    assert state is not None
    assert state.incidents == (incident,)


def _incident(
    source: str,
    severity: ComfyStartupIncidentSeverity,
) -> ComfyStartupIncident:
    """Return one deterministic startup incident."""

    return ComfyStartupIncident(
        kind=ComfyStartupIncidentKind.PROCESS_EXITED_BEFORE_READY
        if severity is ComfyStartupIncidentSeverity.FATAL
        else ComfyStartupIncidentKind.CUSTOM_NODE_IMPORT_FAILED,
        severity=severity,
        title="Extension failed to load",
        message="startup issue",
        source=source,
        fingerprint=f"fingerprint-{source}",
    )

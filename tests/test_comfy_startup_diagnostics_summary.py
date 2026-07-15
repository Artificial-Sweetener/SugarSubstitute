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

"""Tests for rendering copyable Comfy startup diagnostics reports."""

from __future__ import annotations

from substitute.application.comfy_startup_diagnostics.summary import (
    render_startup_diagnostics_report,
)
from substitute.domain.comfy_startup_diagnostics import (
    ComfyStartupIncident,
    ComfyStartupIncidentKind,
    ComfyStartupIncidentSeverity,
)


def test_report_includes_contextual_remediation_fields() -> None:
    """Reports should include actionable structured facts when present."""

    report = render_startup_diagnostics_report(
        (
            ComfyStartupIncident(
                kind=ComfyStartupIncidentKind.CUSTOM_NODE_IMPORT_FAILED,
                severity=ComfyStartupIncidentSeverity.ERROR,
                title="Extension failed to load",
                message="ModuleNotFoundError: No module named 'einops'",
                source="DependencyNode",
                exception_type="ModuleNotFoundError",
                fingerprint="fingerprint-a",
                traceback=("Traceback (most recent call last):",),
                impact="ComfyUI is ready, but DependencyNode did not load.",
                cause="Missing Python dependency: einops.",
                remediation="Install or update the dependency in ComfyUI, then restart.",
                values={
                    "location": "nodes.py:12",
                    "missing_module": "einops",
                    "extension_version": "48dd427",
                    "repository_url": "https://github.com/example/DependencyNode",
                    "issues_url": "https://github.com/example/DependencyNode/issues",
                    "repository_source": "manager_installed_aux_id",
                },
            ),
        )
    )

    assert "Impact: ComfyUI is ready, but DependencyNode did not load." in report
    assert "Likely cause: Missing Python dependency: einops." in report
    assert "Location: nodes.py:12" in report
    assert "Missing module: einops" in report
    assert "Extension version: 48dd427" in report
    assert "Repository: https://github.com/example/DependencyNode" in report
    assert "Issues: https://github.com/example/DependencyNode/issues" in report
    assert "Metadata source: manager_installed_aux_id" in report
    assert "Suggested action: Install or update the dependency" in report
    assert "Traceback (most recent call last):" in report


def test_report_omits_empty_contextual_fields() -> None:
    """Reports should not render blank contextual labels."""

    report = render_startup_diagnostics_report(
        (
            ComfyStartupIncident(
                kind=ComfyStartupIncidentKind.STARTUP_WARNING,
                severity=ComfyStartupIncidentSeverity.WARNING,
                title="ComfyUI reported a startup warning",
                message="WARNING: optional package missing",
                fingerprint="fingerprint-b",
                log_excerpt=("WARNING: optional package missing",),
            ),
        )
    )

    assert "Impact:" not in report
    assert "Likely cause:" not in report
    assert "Location:" not in report
    assert "Missing module:" not in report
    assert "Repository:" not in report
    assert "Issues:" not in report
    assert "Extension version:" not in report
    assert "Log excerpt:" in report

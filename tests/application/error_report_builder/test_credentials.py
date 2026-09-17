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

"""Protect credentials at the copyable report boundary."""

from substitute.application.error_report_builder import ErrorReportBuilder
from substitute.application.errors import (
    RuntimeReportContext,
    SubstituteOperationContext,
    build_comfy_connection_error_report,
)


def test_startup_report_redacts_control_credentials() -> None:
    """Retain useful launch settings without exposing live control credentials."""
    arguments = (
        "main.py",
        "--splash-session-token=synthetic-inline-secret",
        "--api-key",
        "synthetic-split-secret",
        "--port=8188",
    )
    report = build_comfy_connection_error_report(
        title="Startup failed",
        message="The backend could not start.",
        stage="startup",
        context=SubstituteOperationContext(operation="startup"),
        runtime=RuntimeReportContext(launch_args=arguments),
    )

    rendered = ErrorReportBuilder().render(report)

    assert "synthetic-inline-secret" not in rendered
    assert "synthetic-split-secret" not in rendered
    assert "--splash-session-token=<redacted>" in rendered
    assert "--api-key <redacted>" in rendered
    assert "--port=8188" in rendered
    assert report.runtime.launch_args == arguments

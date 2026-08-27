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

"""Tests for Comfy startup diagnostic collection and fingerprinting."""

from __future__ import annotations

from sugarsubstitute_shared.localization import render_source_application_text

from substitute.application.comfy_startup_diagnostics import (
    ComfyStartupDiagnosticsCollector,
)
from substitute.domain.comfy_startup_diagnostics import (
    ComfyStartupIncidentKind,
    ComfyStartupIncidentSeverity,
    build_startup_incident_fingerprint,
    normalized_startup_incident_source,
)


def test_custom_node_traceback_and_import_failure_become_one_incident() -> None:
    """Collector should attach a Comfy custom-node traceback to the import failure."""

    collector = ComfyStartupDiagnosticsCollector()

    for line in (
        "Traceback (most recent call last):\n",
        '  File "E:\\ComfyUI\\nodes.py", line 2227, in load_custom_node\n',
        "    module_spec.loader.exec_module(module)\n",
        "SyntaxError: broken custom node\n",
        "Cannot import E:\\ComfyUI\\custom_nodes\\BrokenNode module for custom nodes: SyntaxError: broken custom node\n",
        "   0.0 seconds (IMPORT FAILED): E:\\ComfyUI\\custom_nodes\\BrokenNode\n",
    ):
        collector.append_output(line)

    incidents = collector.incidents()

    assert len(incidents) == 1
    incident = incidents[0]
    assert incident.kind is ComfyStartupIncidentKind.CUSTOM_NODE_IMPORT_FAILED
    assert incident.severity is ComfyStartupIncidentSeverity.ERROR
    assert incident.source == "BrokenNode"
    assert incident.exception_type == "SyntaxError"
    assert incident.traceback[0] == "Traceback (most recent call last):"
    assert "Cannot import" in incident.log_excerpt[-1]
    assert incident.impact is not None
    assert "ComfyUI is ready" in incident.impact


def test_ansi_prefixed_custom_node_import_failure_is_classified() -> None:
    """Collector should classify Comfy's colored logger import-failure records."""

    collector = ComfyStartupDiagnosticsCollector()

    for line in (
        "\x1b[1m\x1b[33m[WARNING]\x1b[0m Traceback (most recent call last):\n",
        '  File "E:\\ComfyUI\\nodes.py", line 2246, in load_custom_node\n',
        "ModuleNotFoundError: No module named 'timm.layers'\n",
        "\x1b[1m\x1b[33m[WARNING]\x1b[0m Cannot import "
        "E:\\ComfyUI\\custom_nodes\\comfyui-mmaudio module for custom nodes: "
        "No module named 'timm.layers'\n",
    ):
        collector.append_output(line)

    incident = collector.incidents()[0]

    assert incident.kind is ComfyStartupIncidentKind.CUSTOM_NODE_IMPORT_FAILED
    assert incident.severity is ComfyStartupIncidentSeverity.ERROR
    assert incident.source == "comfyui-mmaudio"
    assert incident.exception_type == "ModuleNotFoundError"
    assert incident.traceback[0] == "Traceback (most recent call last):"
    assert incident.values["missing_module"] == "timm.layers"


def test_import_failed_timing_row_without_prior_error_creates_incident() -> None:
    """A standalone Comfy import timing failure should still be actionable."""

    collector = ComfyStartupDiagnosticsCollector()

    collector.append_output(
        "   0.0 seconds (IMPORT FAILED): E:/ComfyUI/custom_nodes/BrokenNode\n"
    )

    incident = collector.incidents()[0]
    assert incident.kind is ComfyStartupIncidentKind.CUSTOM_NODE_IMPORT_FAILED
    assert incident.source == "BrokenNode"
    assert "import failure" in incident.message
    assert incident.remediation is not None
    assert (
        incident.remediation
        == "Update the extension first. If it still fails, report it to the maintainer."
    )


def test_ansi_prefixed_import_failed_timing_row_creates_incident() -> None:
    """Collector should classify colored Comfy import timing failure rows."""

    collector = ComfyStartupDiagnosticsCollector()

    collector.append_output(
        "\x1b[32m[INFO]\x1b[0m    0.1 seconds (IMPORT FAILED): "
        "E:\\ComfyUI\\custom_nodes\\ComfyUI_OmniSVG\n"
    )

    incident = collector.incidents()[0]

    assert incident.kind is ComfyStartupIncidentKind.CUSTOM_NODE_IMPORT_FAILED
    assert incident.source == "ComfyUI_OmniSVG"
    assert "import failure" in incident.message


def test_prestartup_failure_is_classified() -> None:
    """Custom-node prestartup failures should be separate from import failures."""

    collector = ComfyStartupDiagnosticsCollector()

    collector.append_output(
        "Failed to execute startup-script: E:\\ComfyUI\\custom_nodes\\BadPre\\prestartup_script.py / RuntimeError: no setup\n"
    )

    incident = collector.incidents()[0]
    assert incident.kind is ComfyStartupIncidentKind.CUSTOM_NODE_PRESTARTUP_FAILED
    assert incident.source == "BadPre"
    assert incident.exception_type == "RuntimeError"


def test_builtin_import_warning_and_failed_node_are_classified() -> None:
    """Comfy builtin/API node warnings should collect the following import rows."""

    collector = ComfyStartupDiagnosticsCollector()

    collector.append_output(
        "WARNING: some comfy_api_nodes/ nodes did not import correctly. This may be because they are missing some dependencies.\n"
    )
    collector.append_output("IMPORT FAILED: api_node_a\n")

    incidents = collector.incidents()

    assert [incident.kind for incident in incidents] == [
        ComfyStartupIncidentKind.BUILTIN_NODE_IMPORT_FAILED,
        ComfyStartupIncidentKind.BUILTIN_NODE_IMPORT_FAILED,
    ]
    assert incidents[0].source == "comfy_api_nodes"
    assert incidents[1].source == "api_node_a"


def test_generic_warning_is_classified() -> None:
    """Unmatched Comfy warning lines should become recoverable warning incidents."""

    collector = ComfyStartupDiagnosticsCollector()

    collector.append_output("WARNING: optional acceleration package missing\n")

    incident = collector.incidents()[0]
    assert incident.kind is ComfyStartupIncidentKind.STARTUP_WARNING
    assert incident.severity is ComfyStartupIncidentSeverity.WARNING
    assert incident.message == "WARNING: optional acceleration package missing"


def test_ansi_prefixed_generic_warning_is_classified() -> None:
    """Collector should keep unmatched colored Comfy warnings visible."""

    collector = ComfyStartupDiagnosticsCollector()

    collector.append_output(
        "\x1b[1m\x1b[33m[WARNING]\x1b[0m Optional startup warning\n"
    )

    incident = collector.incidents()[0]

    assert incident.kind is ComfyStartupIncidentKind.STARTUP_WARNING
    assert incident.severity is ComfyStartupIncidentSeverity.WARNING
    assert incident.message == "WARNING: Optional startup warning"


def test_sugarcubes_warning_line_is_classified_specifically() -> None:
    """SugarCubes startup warnings should not be reduced to generic warnings."""

    collector = ComfyStartupDiagnosticsCollector()

    collector.append_output(
        "WARNING: SugarCubes[base_cubes_sync_failed]: Base-Cubes sync failed: "
        "SugarCubes could not update Base-Cubes and is using the local checkout. "
        "(repoRef=Artificial-Sweetener/Base-Cubes; reason=ahead)\n"
    )

    incident = collector.incidents()[0]
    assert incident.kind is ComfyStartupIncidentKind.SUGARCUBES_MAINTENANCE_WARNING
    assert incident.severity is ComfyStartupIncidentSeverity.WARNING
    assert incident.title == "Base-Cubes sync failed"
    assert incident.source == "SugarCubes[base_cubes_sync_failed]"
    assert incident.values["diagnostic_code"] == "base_cubes_sync_failed"
    assert incident.impact is not None
    assert "ComfyUI can continue starting" in incident.impact


def test_sugarcubes_error_line_is_classified_specifically() -> None:
    """SugarCubes startup errors should stay nonfatal but visible as errors."""

    collector = ComfyStartupDiagnosticsCollector()

    collector.append_output(
        "ERROR: SugarCubes[sugarcubes_dependency_install_failed]: "
        "SugarCubes dependency install failed: SimpleSyrup could not be installed automatically. "
        "(nodeId=SimpleSyrup; reason=missing_comfy_cli)\n"
    )

    incident = collector.incidents()[0]
    assert incident.kind is ComfyStartupIncidentKind.SUGARCUBES_MAINTENANCE_FAILED
    assert incident.severity is ComfyStartupIncidentSeverity.ERROR
    assert incident.title == "SugarCubes dependency install failed"
    assert incident.values["diagnostic_code"] == (
        "sugarcubes_dependency_install_failed"
    )
    assert incident.remediation is not None
    assert "repair the listed" in incident.remediation


def test_traceback_alone_is_preserved_as_transcript_not_fatal() -> None:
    """Tracebacks should not be treated as fatal without process failure evidence."""

    collector = ComfyStartupDiagnosticsCollector()

    collector.append_output("Traceback (most recent call last):\n")
    collector.append_output("RuntimeError: still loading\n")

    assert collector.incidents() == ()
    assert collector.transcript() == (
        "Traceback (most recent call last):",
        "RuntimeError: still loading",
    )


def test_transcript_is_bounded() -> None:
    """Collector should keep a bounded startup transcript."""

    collector = ComfyStartupDiagnosticsCollector(max_transcript_records=3)

    for index in range(5):
        collector.append_output(f"line {index}\n")

    assert collector.transcript() == ("line 2", "line 3", "line 4")


def test_fingerprints_are_stable_across_path_separator_differences() -> None:
    """Equivalent Windows and POSIX-style custom-node paths should fingerprint alike."""

    windows_source = r"E:\ComfyUI\custom_nodes\BrokenNode"
    posix_source = "E:/ComfyUI/custom_nodes/BrokenNode"

    assert normalized_startup_incident_source(windows_source) == "BrokenNode"
    assert normalized_startup_incident_source(posix_source) == "BrokenNode"
    assert build_startup_incident_fingerprint(
        kind=ComfyStartupIncidentKind.CUSTOM_NODE_IMPORT_FAILED,
        source=windows_source,
        exception_type="SyntaxError",
        message="SyntaxError: broken custom node, line 42",
    ) == build_startup_incident_fingerprint(
        kind=ComfyStartupIncidentKind.CUSTOM_NODE_IMPORT_FAILED,
        source=posix_source,
        exception_type="SyntaxError",
        message="SyntaxError: broken custom node, line 7",
    )


def test_unicodeescape_custom_node_failure_gets_specific_remediation() -> None:
    """Unicode escape custom-node syntax errors should get specific guidance."""

    collector = ComfyStartupDiagnosticsCollector()

    for line in (
        "Traceback (most recent call last):\n",
        '  File "E:\\ComfyUI\\nodes.py", line 2227, in load_custom_node\n',
        '  File "E:\\ComfyUI\\custom_nodes\\ComfyUI-GGUF-FantasyTalking\\__init__.py", line 7, in <module>\n',
        "    from .nodes import NODE_CLASS_MAPPINGS\n",
        '  File "E:\\ComfyUI\\custom_nodes\\ComfyUI-GGUF-FantasyTalking\\nodes.py", line 608\n',
        '    """\n',
        "    ^^^^\n",
        "SyntaxError: (unicode error) 'unicodeescape' codec can't decode bytes in position 149-150: truncated \\UXXXXXXXX escape\n",
        "Cannot import E:\\ComfyUI\\custom_nodes\\ComfyUI-GGUF-FantasyTalking module for custom nodes: (unicode error) 'unicodeescape' codec can't decode bytes in position 149-150: truncated \\UXXXXXXXX escape (nodes.py, line 608)\n",
    ):
        collector.append_output(line)

    incident = collector.incidents()[0]

    assert incident.exception_type == "SyntaxError"
    assert incident.source == "ComfyUI-GGUF-FantasyTalking"
    assert incident.cause == "Invalid backslash escape in the extension's Python code."
    assert incident.remediation is not None
    assert (
        incident.remediation
        == "Update the extension first. If it still fails, report it to the maintainer."
    )
    assert not incident.remediation.startswith("Reinstall")
    assert incident.values["location"] == "nodes.py:608"


def test_module_not_found_custom_node_failure_gets_dependency_remediation() -> None:
    """Missing-module import failures should carry dependency facts."""

    collector = ComfyStartupDiagnosticsCollector()

    for line in (
        "Traceback (most recent call last):\n",
        '  File "E:\\ComfyUI\\custom_nodes\\DependencyNode\\__init__.py", line 1, in <module>\n',
        "    import einops\n",
        "ModuleNotFoundError: No module named 'einops'\n",
        "Cannot import E:\\ComfyUI\\custom_nodes\\DependencyNode module for custom nodes: ModuleNotFoundError: No module named 'einops'\n",
    ):
        collector.append_output(line)

    incident = collector.incidents()[0]

    assert incident.exception_type == "ModuleNotFoundError"
    assert incident.cause is not None
    assert render_source_application_text(incident.cause) == (
        "Missing Python dependency: einops."
    )
    assert incident.remediation is not None
    assert (
        incident.remediation
        == "Install or update the dependency in ComfyUI, then restart."
    )
    assert incident.values["missing_module"] == "einops"


def test_process_exit_before_ready_creates_fatal_incident() -> None:
    """Collector should build a fatal incident for pre-ready process exit."""

    collector = ComfyStartupDiagnosticsCollector()
    collector.append_output("Traceback (most recent call last):\n")
    collector.append_output("RuntimeError: launch failed\n")

    incident = collector.mark_process_exited_before_ready(
        pid=123,
        exit_code=1,
        host="127.0.0.1",
        port=8188,
        workspace="E:\\ComfyUI",
    )

    assert incident.kind is ComfyStartupIncidentKind.PROCESS_EXITED_BEFORE_READY
    assert incident.severity is ComfyStartupIncidentSeverity.FATAL
    assert incident.values["pid"] == 123
    assert incident.values["exit_code"] == 1
    assert "RuntimeError: launch failed" in incident.log_excerpt

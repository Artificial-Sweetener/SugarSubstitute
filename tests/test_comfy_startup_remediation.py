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

"""Tests for contextual Comfy startup remediation guidance."""

from __future__ import annotations

from substitute.domain.comfy_startup_diagnostics import (
    ComfyStartupIncidentKind,
    StartupRemediationFacts,
    build_startup_remediation,
    extract_missing_module_name,
    extract_relevant_traceback_location,
)

_UNICODE_ESCAPE_TRACEBACK = (
    "Traceback (most recent call last):",
    '  File "E:\\ComfyUI\\nodes.py", line 2227, in load_custom_node',
    "    module_spec.loader.exec_module(module)",
    '  File "E:\\ComfyUI\\custom_nodes\\ComfyUI-GGUF-FantasyTalking\\__init__.py", line 7, in <module>',
    "    from .nodes import NODE_CLASS_MAPPINGS",
    '  File "E:\\ComfyUI\\custom_nodes\\ComfyUI-GGUF-FantasyTalking\\nodes.py", line 608',
    '    """',
    "    ^^^^",
    "SyntaxError: (unicode error) 'unicodeescape' codec can't decode bytes in position 149-150: truncated \\UXXXXXXXX escape",
)


def test_unicodeescape_syntax_error_gets_backslash_specific_guidance() -> None:
    """Unicode escape syntax errors should explain invalid backslash escapes."""

    remediation = build_startup_remediation(
        StartupRemediationFacts(
            kind=ComfyStartupIncidentKind.CUSTOM_NODE_IMPORT_FAILED,
            source="ComfyUI-GGUF-FantasyTalking",
            exception_type="SyntaxError",
            message=(
                "(unicode error) 'unicodeescape' codec can't decode bytes in "
                "position 149-150: truncated \\UXXXXXXXX escape"
            ),
            traceback=_UNICODE_ESCAPE_TRACEBACK,
        )
    )

    assert remediation.impact is not None
    assert "ComfyUI is ready" in remediation.impact
    assert remediation.cause is not None
    assert (
        remediation.cause == "Invalid backslash escape in the extension's Python code."
    )
    assert remediation.suggested_action is not None
    assert (
        remediation.suggested_action
        == "Update the extension first. If it still fails, report it to the maintainer."
    )
    assert not remediation.suggested_action.startswith("Reinstall")


def test_generic_syntax_error_gets_source_parse_guidance() -> None:
    """Generic custom-node syntax errors should avoid dependency advice."""

    remediation = build_startup_remediation(
        StartupRemediationFacts(
            kind=ComfyStartupIncidentKind.CUSTOM_NODE_IMPORT_FAILED,
            source="BrokenNode",
            exception_type="SyntaxError",
            message="SyntaxError: invalid syntax",
        )
    )

    assert remediation.cause == "Python could not parse the extension's source code."
    assert remediation.suggested_action is not None
    assert "dependency" not in remediation.suggested_action.casefold()


def test_module_not_found_gets_dependency_guidance() -> None:
    """Missing modules should lead with dependency repair advice."""

    remediation = build_startup_remediation(
        StartupRemediationFacts(
            kind=ComfyStartupIncidentKind.CUSTOM_NODE_IMPORT_FAILED,
            source="DependencyNode",
            exception_type="ModuleNotFoundError",
            message="ModuleNotFoundError: No module named 'einops'",
        )
    )

    assert remediation.cause == "Missing Python dependency: einops."
    assert remediation.suggested_action is not None
    assert (
        remediation.suggested_action
        == "Install or update the dependency in ComfyUI, then restart."
    )
    assert (
        extract_missing_module_name("ModuleNotFoundError: No module named 'einops'")
        == "einops"
    )


def test_import_error_gets_dependency_or_api_guidance() -> None:
    """ImportError should identify dependency or API mismatch risk."""

    remediation = build_startup_remediation(
        StartupRemediationFacts(
            kind=ComfyStartupIncidentKind.CUSTOM_NODE_IMPORT_FAILED,
            source="ApiNode",
            exception_type="ImportError",
            message="ImportError: cannot import name 'Foo' from 'comfy'",
        )
    )

    assert remediation.cause is not None
    assert remediation.cause == "The extension may not match this ComfyUI version."
    assert remediation.suggested_action is not None
    assert (
        remediation.suggested_action
        == "Update the extension and its dependencies; it may not match this ComfyUI version."
    )


def test_native_load_error_gets_binary_dependency_guidance() -> None:
    """DLL and native extension failures should point to binary environment repair."""

    remediation = build_startup_remediation(
        StartupRemediationFacts(
            kind=ComfyStartupIncidentKind.CUSTOM_NODE_IMPORT_FAILED,
            source="NativeNode",
            exception_type="OSError",
            message="OSError: DLL load failed while importing cv2",
        )
    )

    assert remediation.cause == "A native dependency failed to load."
    assert remediation.suggested_action is not None
    assert "Python, PyTorch, CUDA, and Windows" in remediation.suggested_action


def test_unknown_custom_node_failure_gets_safe_fallback_guidance() -> None:
    """Unknown custom-node import failures should still produce actionable fallback."""

    remediation = build_startup_remediation(
        StartupRemediationFacts(
            kind=ComfyStartupIncidentKind.CUSTOM_NODE_IMPORT_FAILED,
            source=None,
            exception_type=None,
            message="unexpected custom node problem",
        )
    )

    assert remediation.impact is not None
    assert "this extension" in remediation.impact
    assert remediation.cause == "ComfyUI could not import this extension."
    assert remediation.suggested_action is not None
    assert (
        remediation.suggested_action
        == "Update the extension first. If it still fails, report it to the maintainer."
    )


def test_traceback_location_prefers_matching_custom_node_source() -> None:
    """Location extraction should prefer frames under the incident source folder."""

    location = extract_relevant_traceback_location(
        _UNICODE_ESCAPE_TRACEBACK,
        source="ComfyUI-GGUF-FantasyTalking",
    )

    assert location is not None
    assert location.file.endswith("ComfyUI-GGUF-FantasyTalking\\nodes.py")
    assert location.line == 608
    assert location.display == "nodes.py:608"


def test_traceback_location_handles_forward_slashes() -> None:
    """Location extraction should handle POSIX-style paths in tracebacks."""

    location = extract_relevant_traceback_location(
        (
            '  File "E:/ComfyUI/nodes.py", line 2227, in load_custom_node',
            '  File "E:/ComfyUI/custom_nodes/BrokenNode/nodes.py", line 12',
            "RuntimeError: broken",
        ),
        source="BrokenNode",
    )

    assert location is not None
    assert location.display == "nodes.py:12"


def test_traceback_location_returns_none_without_file_frames() -> None:
    """Tracebacks without parseable frames should not fabricate a location."""

    assert (
        extract_relevant_traceback_location(
            ("Traceback (most recent call last):",), source="BrokenNode"
        )
        is None
    )

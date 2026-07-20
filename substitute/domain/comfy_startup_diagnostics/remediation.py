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

"""Choose contextual user guidance for Comfy startup incidents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PureWindowsPath
import re

from sugarsubstitute_shared.localization import ApplicationText, app_text

from substitute.domain.comfy_startup_diagnostics.models import (
    ComfyStartupIncidentKind,
    normalized_startup_incident_source,
)

_TRACEBACK_FILE_PATTERN = re.compile(r'^\s*File "(?P<file>.+?)", line (?P<line>\d+)')
_NO_MODULE_PATTERN = re.compile(r"No module named ['\"](?P<module>[^'\"]+)['\"]")


@dataclass(frozen=True)
class StartupTracebackLocation:
    """Describe the most relevant Python traceback location for a startup issue."""

    file: str
    line: int | None
    display: str


@dataclass(frozen=True)
class StartupRemediationFacts:
    """Describe structured facts used to choose startup remediation text."""

    kind: ComfyStartupIncidentKind
    source: str | None
    exception_type: str | None
    message: ApplicationText
    traceback: tuple[str, ...] = ()
    location: str | None = None


@dataclass(frozen=True)
class StartupRemediation:
    """Describe user-facing impact and next steps for one startup incident."""

    impact: ApplicationText | None
    suggested_action: ApplicationText | None
    cause: ApplicationText | None = None


def build_startup_remediation(
    facts: StartupRemediationFacts,
) -> StartupRemediation:
    """Return contextual impact and remediation for one startup incident."""

    match facts.kind:
        case ComfyStartupIncidentKind.CUSTOM_NODE_IMPORT_FAILED:
            return _custom_node_import_remediation(facts)
        case ComfyStartupIncidentKind.CUSTOM_NODE_PRESTARTUP_FAILED:
            return StartupRemediation(
                impact=_extension_impact(facts.source),
                cause=app_text(
                    "The extension startup script failed before normal imports completed."
                ),
                suggested_action=_DEFAULT_EXTENSION_ACTION,
            )
        case ComfyStartupIncidentKind.BUILTIN_NODE_IMPORT_FAILED:
            return StartupRemediation(
                impact=app_text(
                    "Some built-in or API nodes may be unavailable in ComfyUI."
                ),
                cause=app_text(
                    "ComfyUI reported that one of its bundled node groups did not import correctly."
                ),
                suggested_action=app_text(
                    "Update ComfyUI dependencies and restart the application."
                ),
            )
        case ComfyStartupIncidentKind.PROCESS_EXITED_BEFORE_READY:
            return StartupRemediation(
                impact=app_text(
                    "ComfyUI did not become ready, so the application cannot continue startup."
                ),
                cause=app_text(
                    "The managed ComfyUI process exited before the readiness endpoint responded."
                ),
                suggested_action=app_text(
                    "Review the startup log and fix the last reported ComfyUI error."
                ),
            )
        case ComfyStartupIncidentKind.READINESS_TIMEOUT:
            return StartupRemediation(
                impact=app_text(
                    "ComfyUI did not become ready before the startup timeout."
                ),
                cause=app_text("The readiness endpoint did not respond in time."),
                suggested_action=app_text(
                    "Review the startup log for the slow or blocked startup step."
                ),
            )
        case ComfyStartupIncidentKind.SUGARCUBES_MAINTENANCE_WARNING:
            return StartupRemediation(
                impact=app_text(
                    "ComfyUI can continue starting, but some SugarCubes workflows "
                    "may need attention before they run correctly."
                ),
                cause=app_text(
                    "SugarCubes reported a recoverable startup maintenance issue."
                ),
                suggested_action=app_text(
                    "Review the SugarCubes diagnostic details and repair the listed "
                    "cube pack or dependency when convenient."
                ),
            )
        case ComfyStartupIncidentKind.SUGARCUBES_MAINTENANCE_FAILED:
            return StartupRemediation(
                impact=app_text(
                    "ComfyUI can continue starting, but SugarCubes cube features may "
                    "be degraded until this is repaired."
                ),
                cause=app_text("SugarCubes startup maintenance failed."),
                suggested_action=app_text(
                    "Review the SugarCubes diagnostic details and repair the listed "
                    "cube pack, dependency, or local checkout."
                ),
            )
        case _:
            return StartupRemediation(impact=None, cause=None, suggested_action=None)


def extract_relevant_traceback_location(
    traceback: tuple[str, ...],
    *,
    source: str | None,
) -> StartupTracebackLocation | None:
    """Return the best custom-node file/line location from a traceback."""

    frames = _traceback_frames(traceback)
    if not frames:
        return None
    normalized_source = normalized_startup_incident_source(source)
    if normalized_source is not None:
        for frame in reversed(frames):
            if _path_contains_custom_node_source(frame.file, normalized_source):
                return frame
    for frame in reversed(frames):
        if not _path_looks_like_comfy_core(frame.file):
            return frame
    return frames[-1]


def extract_missing_module_name(text: str) -> str | None:
    """Return the missing Python module named in an import error message."""

    match = _NO_MODULE_PATTERN.search(text)
    return match.group("module") if match is not None else None


def _custom_node_import_remediation(
    facts: StartupRemediationFacts,
) -> StartupRemediation:
    """Return remediation for an extension import failure."""

    message = _diagnostic_text(facts)
    exception_type = facts.exception_type or ""
    if exception_type == "SyntaxError" and _contains_unicode_escape_error(message):
        return StartupRemediation(
            impact=_extension_impact(facts.source),
            cause=app_text("Invalid backslash escape in the extension's Python code."),
            suggested_action=_DEFAULT_EXTENSION_ACTION,
        )
    if exception_type == "SyntaxError":
        return StartupRemediation(
            impact=_extension_impact(facts.source),
            cause=app_text("Python could not parse the extension's source code."),
            suggested_action=_DEFAULT_EXTENSION_ACTION,
        )
    if exception_type == "ModuleNotFoundError" or "no module named" in message:
        missing_module = extract_missing_module_name(
            "\n".join((facts.message, *facts.traceback))
        )
        return StartupRemediation(
            impact=_extension_impact(facts.source),
            cause=(
                app_text("Missing Python dependency: %1.", missing_module)
                if missing_module
                else app_text("The extension is missing a Python dependency.")
            ),
            suggested_action=app_text(
                "Install or update the dependency in ComfyUI, then restart."
            ),
        )
    if exception_type == "ImportError" or "cannot import name" in message:
        return StartupRemediation(
            impact=_extension_impact(facts.source),
            cause=app_text("The extension may not match this ComfyUI version."),
            suggested_action=app_text(
                "Update the extension and its dependencies; it may not match this ComfyUI version."
            ),
        )
    if exception_type == "OSError" or _contains_native_load_error(message):
        return StartupRemediation(
            impact=_extension_impact(facts.source),
            cause=app_text("A native dependency failed to load."),
            suggested_action=app_text(
                "Reinstall the failing native dependency for this Python, PyTorch, "
                "CUDA, and Windows setup."
            ),
        )
    if exception_type in {"AttributeError", "TypeError"}:
        return StartupRemediation(
            impact=_extension_impact(facts.source),
            cause=app_text("The extension may not match this ComfyUI version."),
            suggested_action=app_text(
                "Update the extension and its dependencies; it may not match this ComfyUI version."
            ),
        )
    return StartupRemediation(
        impact=_extension_impact(facts.source),
        cause=app_text("ComfyUI could not import this extension."),
        suggested_action=_DEFAULT_EXTENSION_ACTION,
    )


def _diagnostic_text(facts: StartupRemediationFacts) -> str:
    """Return normalized diagnostic text for policy matching."""

    return "\n".join((facts.message, *facts.traceback)).casefold()


def _contains_unicode_escape_error(message: str) -> bool:
    """Return whether diagnostic text describes a Python unicode escape error."""

    return (
        "unicodeescape" in message
        or "truncated \\u" in message
        or "unicode error" in message
    )


def _contains_native_load_error(message: str) -> bool:
    """Return whether diagnostic text describes a native extension load failure."""

    return (
        "dll load failed" in message
        or "could not find module" in message
        or "cannot open shared object file" in message
    )


_DEFAULT_EXTENSION_ACTION = app_text(
    "Update the extension first. If it still fails, report it to the maintainer."
)


def _extension_impact(source: str | None) -> ApplicationText:
    """Return a reusable impact statement for extension failures."""

    return app_text(
        "ComfyUI is ready, but %1 did not load. Workflows using this extension may fail or show missing nodes.",
        _source_label(source),
    )


def _source_label(source: str | None) -> str:
    """Return a readable extension label for guidance text."""

    return normalized_startup_incident_source(source) or "this extension"


def _traceback_frames(
    traceback: tuple[str, ...],
) -> tuple[StartupTracebackLocation, ...]:
    """Return parsed Python traceback file frames."""

    frames: list[StartupTracebackLocation] = []
    for line in traceback:
        match = _TRACEBACK_FILE_PATTERN.match(line)
        if match is None:
            continue
        path = match.group("file")
        line_number = int(match.group("line"))
        frames.append(
            StartupTracebackLocation(
                file=path,
                line=line_number,
                display=_display_location(path, line_number),
            )
        )
    return tuple(frames)


def _display_location(path: str, line: int | None) -> str:
    """Return a compact path display for one traceback location."""

    normalized = path.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    display_parts = parts[-1:]
    lowered_parts = [part.casefold() for part in parts]
    if "custom_nodes" in lowered_parts:
        index = lowered_parts.index("custom_nodes")
        if index + 2 < len(parts):
            display_parts = parts[index + 2 :]
        elif index + 1 < len(parts):
            display_parts = parts[index + 1 :]
    display = "/".join(display_parts) or PureWindowsPath(path).name or path
    return f"{display}:{line}" if line is not None else display


def _path_contains_custom_node_source(path: str, source: str) -> bool:
    """Return whether a traceback path belongs to one custom-node source."""

    normalized = path.replace("\\", "/").casefold()
    source_segment = f"/custom_nodes/{source.casefold()}/"
    source_file = f"/custom_nodes/{source.casefold()}.py"
    return source_segment in normalized or normalized.endswith(source_file)


def _path_looks_like_comfy_core(path: str) -> bool:
    """Return whether a traceback path appears to be ComfyUI core/import plumbing."""

    normalized = path.replace("\\", "/").casefold()
    return (
        normalized.endswith("/comfyui/nodes.py")
        or "importlib._bootstrap" in normalized
        or "<frozen importlib" in normalized
    )


__all__ = [
    "StartupRemediation",
    "StartupRemediationFacts",
    "StartupTracebackLocation",
    "build_startup_remediation",
    "extract_missing_module_name",
    "extract_relevant_traceback_location",
]

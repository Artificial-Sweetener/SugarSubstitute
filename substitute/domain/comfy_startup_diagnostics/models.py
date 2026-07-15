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

"""Model recoverable and fatal Comfy startup diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import re
from pathlib import PureWindowsPath


class ComfyStartupIncidentSeverity(Enum):
    """Classify startup incidents by user impact."""

    FATAL = "fatal"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ComfyStartupIncidentKind(Enum):
    """Classify known Comfy startup incident families."""

    PROCESS_EXITED_BEFORE_READY = "process_exited_before_ready"
    READINESS_TIMEOUT = "readiness_timeout"
    LAUNCH_EXCEPTION = "launch_exception"
    CUSTOM_NODE_IMPORT_FAILED = "custom_node_import_failed"
    CUSTOM_NODE_PRESTARTUP_FAILED = "custom_node_prestartup_failed"
    BUILTIN_NODE_IMPORT_FAILED = "builtin_node_import_failed"
    MISSING_DEPENDENCY = "missing_dependency"
    RUNTIME_COMPATIBILITY_FAILED = "runtime_compatibility_failed"
    SUGARCUBES_MAINTENANCE_WARNING = "sugarcubes_maintenance_warning"
    SUGARCUBES_MAINTENANCE_FAILED = "sugarcubes_maintenance_failed"
    STARTUP_WARNING = "startup_warning"
    UNCLASSIFIED_STARTUP_ERROR = "unclassified_startup_error"


@dataclass(frozen=True)
class ComfyStartupIncident:
    """Describe one actionable Comfy startup diagnostic incident."""

    kind: ComfyStartupIncidentKind
    severity: ComfyStartupIncidentSeverity
    title: str
    message: str
    source: str | None = None
    exception_type: str | None = None
    fingerprint: str = ""
    log_excerpt: tuple[str, ...] = ()
    traceback: tuple[str, ...] = ()
    impact: str | None = None
    cause: str | None = None
    remediation: str | None = None
    values: dict[str, object] = field(default_factory=dict)


def build_startup_incident_fingerprint(
    *,
    kind: ComfyStartupIncidentKind,
    source: str | None,
    exception_type: str | None,
    message: str,
) -> str:
    """Return a stable key for one repeatable startup incident."""

    material = "|".join(
        (
            kind.value,
            normalized_startup_incident_source(source) or "",
            _normalized_fingerprint_segment(exception_type or ""),
            _normalized_fingerprint_segment(message),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def normalized_startup_incident_source(source: str | None) -> str | None:
    """Return a stable source label from a Comfy path or free-form source."""

    if source is None:
        return None
    stripped = source.strip().strip('"')
    if not stripped:
        return None
    normalized = stripped.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    lowered_parts = [part.lower() for part in parts]
    if "custom_nodes" in lowered_parts:
        index = lowered_parts.index("custom_nodes")
        if index + 1 < len(parts):
            return _strip_python_suffix(parts[index + 1])
    return _strip_python_suffix(PureWindowsPath(stripped).name)


def _normalized_fingerprint_segment(value: str) -> str:
    """Normalize volatile spacing and path separators inside fingerprint material."""

    without_line_numbers = re.sub(r", line \d+", "", value, flags=re.IGNORECASE)
    without_positions = re.sub(r"position \d+-\d+", "position", without_line_numbers)
    normalized_paths = without_positions.replace("\\", "/")
    return " ".join(normalized_paths.casefold().split())


def _strip_python_suffix(value: str) -> str:
    """Return a source label without a Python file suffix when present."""

    return value[:-3] if value.endswith(".py") else value


__all__ = [
    "ComfyStartupIncident",
    "ComfyStartupIncidentKind",
    "ComfyStartupIncidentSeverity",
    "build_startup_incident_fingerprint",
    "normalized_startup_incident_source",
]

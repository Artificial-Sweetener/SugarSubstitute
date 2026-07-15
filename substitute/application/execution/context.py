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

"""Describe safe diagnostic context for application execution tasks."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass
import re

SafeFieldValue = Hashable | None

_WINDOWS_ABSOLUTE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_POSIX_ABSOLUTE_PATH = re.compile(r"^/(?:Users|home|var|tmp|etc|mnt|srv)/")
_TRACEBACK_MARKERS = ("Traceback (most recent call last)", '\n  File "')
SAFE_EXECUTION_FIELD_NAMES = frozenset(
    {
        "alias",
        "batch_count",
        "cache_generation",
        "cache_key",
        "cancelled",
        "catalog_revision",
        "class_name",
        "client_id",
        "completed_count",
        "cube_id",
        "cube_version",
        "display_name",
        "domain",
        "drop_reason",
        "endpoint",
        "error_type",
        "feature_profile_id",
        "file_name",
        "generation",
        "host",
        "job_id",
        "kind",
        "lane",
        "node_class",
        "node_id",
        "operation",
        "operation_key",
        "owner_id",
        "page_id",
        "pending_count",
        "port",
        "queued_age_ms",
        "reason",
        "request_id",
        "route_key",
        "run_duration_ms",
        "scope_id",
        "scene_key",
        "source_key",
        "source_length",
        "status",
        "storage_key",
        "target_id",
        "trace_id",
        "workflow_id",
    }
)


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Carry sanitized task context that can safely enter logs and traces."""

    operation: str
    reason: str
    lane: str
    scope_id: str | None = None
    owner_id: str | None = None
    safe_fields: tuple[tuple[str, SafeFieldValue], ...] = ()

    def __post_init__(self) -> None:
        """Validate labels and safe fields before task work trusts them."""

        _require_non_blank(self.operation, field_name="operation")
        _require_non_blank(self.reason, field_name="reason")
        _require_non_blank(self.lane, field_name="lane")
        _require_optional_non_blank(self.scope_id, field_name="scope_id")
        _require_optional_non_blank(self.owner_id, field_name="owner_id")
        for field_name, value in self.safe_fields:
            _validate_safe_field(field_name, value)

    def field_value(self, field_name: str) -> SafeFieldValue:
        """Return one safe field value when it exists."""

        _require_non_blank(field_name, field_name="field_name")
        for candidate, value in self.safe_fields:
            if candidate == field_name:
                return value
        return None


def _validate_safe_field(field_name: str, value: SafeFieldValue) -> None:
    """Reject unsafe diagnostic field names and values."""

    _require_non_blank(field_name, field_name="safe_fields field name")
    normalized_name = field_name.strip().lower()
    if normalized_name not in SAFE_EXECUTION_FIELD_NAMES:
        raise ValueError(f"{field_name} is not an approved execution safe field.")
    if isinstance(value, str):
        _validate_safe_string_value(field_name, value)


def _validate_safe_string_value(field_name: str, value: str) -> None:
    """Reject string values containing local paths or raw tracebacks."""

    if any(marker in value for marker in _TRACEBACK_MARKERS):
        raise ValueError(f"{field_name} must not contain raw traceback text.")
    if _WINDOWS_ABSOLUTE_PATH.search(value) or _POSIX_ABSOLUTE_PATH.search(value):
        raise ValueError(f"{field_name} must not contain a full local path.")


def _require_optional_non_blank(value: str | None, *, field_name: str) -> None:
    """Reject blank optional labels when a label is supplied."""

    if value is not None:
        _require_non_blank(value, field_name=field_name)


def _require_non_blank(value: str, *, field_name: str) -> None:
    """Reject blank task context labels."""

    if not value.strip():
        raise ValueError(f"{field_name} must not be blank.")


__all__ = [
    "ExecutionContext",
    "SAFE_EXECUTION_FIELD_NAMES",
    "SafeFieldValue",
]

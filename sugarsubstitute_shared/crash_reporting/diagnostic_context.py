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

"""Define typed, source-attributed product and system crash diagnostics."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from typing import Self


@dataclass(frozen=True, slots=True)
class DiagnosticValue:
    """Carry one diagnostic value or an explicit collection failure."""

    value: str | None
    source: str
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        """Require nonempty provenance and exactly one value outcome."""

        if not self.source.strip():
            raise ValueError("Diagnostic value source cannot be empty.")
        has_value = self.value is not None and bool(self.value.strip())
        has_reason = self.unavailable_reason is not None and bool(
            self.unavailable_reason.strip()
        )
        if has_value == has_reason:
            raise ValueError(
                "Diagnostic value requires either a value or an unavailable reason."
            )

    @classmethod
    def available(cls, value: object, *, source: str) -> Self:
        """Create one successfully collected diagnostic value."""

        text = str(value).strip()
        if not text:
            return cls.unavailable("source returned an empty value", source=source)
        return cls(value=text, source=source)

    @classmethod
    def unavailable(cls, reason: str, *, source: str) -> Self:
        """Create one explicit diagnostic collection failure."""

        normalized = reason.strip()
        if not normalized:
            raise ValueError("Diagnostic unavailable reason cannot be empty.")
        return cls(value=None, source=source, unavailable_reason=normalized)

    @property
    def display_value(self) -> str:
        """Return copyable text that never hides a missing diagnostic."""

        if self.value is not None:
            return f"{self.value} [source: {self.source}]"
        return f"unavailable ({self.unavailable_reason}) [source: {self.source}]"

    def to_json(self) -> dict[str, str | None]:
        """Return the stable serialized diagnostic value."""

        return {
            "value": self.value,
            "source": self.source,
            "unavailable_reason": self.unavailable_reason,
        }

    @classmethod
    def from_json(cls, payload: object) -> Self:
        """Parse one strict serialized diagnostic value."""

        if not isinstance(payload, Mapping):
            raise ValueError("Diagnostic value must be an object.")
        value = payload.get("value")
        source = payload.get("source")
        unavailable_reason = payload.get("unavailable_reason")
        if value is not None and not isinstance(value, str):
            raise ValueError("Diagnostic value content is invalid.")
        if not isinstance(source, str):
            raise ValueError("Diagnostic value source is invalid.")
        if unavailable_reason is not None and not isinstance(unavailable_reason, str):
            raise ValueError("Diagnostic unavailable reason is invalid.")
        return cls(
            value=value,
            source=source,
            unavailable_reason=unavailable_reason,
        )


@dataclass(frozen=True, slots=True)
class CrashDiagnosticContext:
    """Describe mandatory product, runtime, and basic system crash identity."""

    substitute_version: DiagnosticValue
    substitute_release_version: DiagnosticValue
    supervising_launcher_version: DiagnosticValue
    installed_launcher_version: DiagnosticValue
    comfyui_version: DiagnosticValue
    comfyui_commit: DiagnosticValue
    operating_system: DiagnosticValue
    system_architecture: DiagnosticValue
    python_version: DiagnosticValue
    python_architecture: DiagnosticValue
    processor: DiagnosticValue
    logical_processor_count: DiagnosticValue
    physical_memory: DiagnosticValue
    gpu: DiagnosticValue
    readiness_schema: DiagnosticValue

    def to_json(self) -> dict[str, object]:
        """Return every required diagnostic field in declaration order."""

        return {
            field.name: getattr(self, field.name).to_json() for field in fields(self)
        }

    @classmethod
    def from_json(cls, payload: object) -> Self:
        """Parse a complete diagnostic context without accepting silent gaps."""

        if not isinstance(payload, Mapping):
            raise ValueError("Crash diagnostic context must be an object.")
        expected = {field.name for field in fields(cls)}
        if set(payload) != expected:
            raise ValueError("Crash diagnostic context fields are incomplete.")
        return cls(
            **{name: DiagnosticValue.from_json(payload[name]) for name in expected}
        )

    @classmethod
    def unavailable_legacy(cls) -> Self:
        """Represent a legacy incident that predates complete diagnostics."""

        missing = DiagnosticValue.unavailable(
            "not recorded by this incident schema", source="legacy_incident"
        )
        return cls(**{field.name: missing for field in fields(cls)})


__all__ = ["CrashDiagnosticContext", "DiagnosticValue"]

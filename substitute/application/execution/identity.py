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

"""Define reusable identity values for execution freshness checks."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass

IdentityPartValue = Hashable | None


@dataclass(frozen=True, slots=True)
class TaskIdentity:
    """Carry stable task identity fields used for stale-result rejection."""

    request_id: int
    domain: str
    parts: tuple[tuple[str, IdentityPartValue], ...] = ()
    cancellation_generation: int = 0

    def __post_init__(self) -> None:
        """Reject ambiguous identity values before scheduling work."""

        _require_non_negative(self.request_id, field_name="request_id")
        _require_non_blank(self.domain, field_name="domain")
        _require_non_negative(
            self.cancellation_generation,
            field_name="cancellation_generation",
        )
        seen_names: set[str] = set()
        for field_name, _value in self.parts:
            _require_non_blank(field_name, field_name="parts field name")
            if field_name in seen_names:
                raise ValueError(f"{field_name} appears more than once in parts.")
            seen_names.add(field_name)

    def field_value(self, field_name: str) -> IdentityPartValue:
        """Return one identity field value by name."""

        _require_non_blank(field_name, field_name="field_name")
        if field_name == "request_id":
            return self.request_id
        if field_name == "domain":
            return self.domain
        if field_name == "cancellation_generation":
            return self.cancellation_generation
        for candidate, value in self.parts:
            if candidate == field_name:
                return value
        return None

    def with_cancellation_generation(self, generation: int) -> "TaskIdentity":
        """Return this identity tied to one cancellation generation."""

        _require_non_negative(generation, field_name="generation")
        return TaskIdentity(
            request_id=self.request_id,
            domain=self.domain,
            parts=self.parts,
            cancellation_generation=generation,
        )


def _require_non_negative(value: int, *, field_name: str) -> None:
    """Reject negative identity counters."""

    if value < 0:
        raise ValueError(f"{field_name} must be non-negative.")


def _require_non_blank(value: str, *, field_name: str) -> None:
    """Reject blank identity labels."""

    if not value.strip():
        raise ValueError(f"{field_name} must not be blank.")


__all__ = [
    "IdentityPartValue",
    "TaskIdentity",
]

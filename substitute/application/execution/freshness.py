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

"""Validate execution result identity before visible publication."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from .identity import IdentityPartValue, TaskIdentity

DropReason = Literal[
    "fresh",
    "missing_identity",
    "identity_mismatch",
    "cancelled",
    "scope_closed",
    "receiver_destroyed",
]


@dataclass(frozen=True, slots=True)
class FreshnessRequirement:
    """List identity fields that must match before publication."""

    required_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        """Reject an empty freshness requirement."""

        if not self.required_fields:
            raise ValueError("required_fields must not be empty.")
        for field_name in self.required_fields:
            if not field_name.strip():
                raise ValueError("required field names must not be blank.")


@dataclass(frozen=True, slots=True)
class FreshnessMismatch:
    """Describe one identity field that failed freshness validation."""

    field_name: str
    expected: IdentityPartValue
    actual: IdentityPartValue


@dataclass(frozen=True, slots=True)
class FreshnessDecision:
    """Describe whether an execution result can still be published."""

    is_fresh: bool
    drop_reason: DropReason
    mismatches: tuple[FreshnessMismatch, ...] = ()


class StaleResultGuard:
    """Centralize stale-result validation for execution outcomes."""

    def validate(
        self,
        *,
        result_identity: TaskIdentity,
        current_identity: TaskIdentity,
        required_fields: Iterable[str] | FreshnessRequirement,
    ) -> FreshnessDecision:
        """Return whether result identity still matches current owner state."""

        requirement = _coerce_requirement(required_fields)
        missing: list[FreshnessMismatch] = []
        mismatches: list[FreshnessMismatch] = []
        for field_name in requirement.required_fields:
            expected = current_identity.field_value(field_name)
            actual = result_identity.field_value(field_name)
            mismatch = FreshnessMismatch(
                field_name=field_name,
                expected=expected,
                actual=actual,
            )
            if expected is None or actual is None:
                missing.append(mismatch)
            elif expected != actual:
                mismatches.append(mismatch)

        if missing:
            return FreshnessDecision(
                is_fresh=False,
                drop_reason="missing_identity",
                mismatches=tuple(missing),
            )
        if mismatches:
            return FreshnessDecision(
                is_fresh=False,
                drop_reason="identity_mismatch",
                mismatches=tuple(mismatches),
            )
        return FreshnessDecision(is_fresh=True, drop_reason="fresh")

    @staticmethod
    def cancelled() -> FreshnessDecision:
        """Return a freshness decision for a cancelled task."""

        return FreshnessDecision(is_fresh=False, drop_reason="cancelled")

    @staticmethod
    def scope_closed() -> FreshnessDecision:
        """Return a freshness decision for a closed owner scope."""

        return FreshnessDecision(is_fresh=False, drop_reason="scope_closed")

    @staticmethod
    def receiver_destroyed() -> FreshnessDecision:
        """Return a freshness decision for a destroyed receiver."""

        return FreshnessDecision(is_fresh=False, drop_reason="receiver_destroyed")


def _coerce_requirement(
    required_fields: Iterable[str] | FreshnessRequirement,
) -> FreshnessRequirement:
    """Convert field iterables to a validated freshness requirement."""

    if isinstance(required_fields, FreshnessRequirement):
        return required_fields
    return FreshnessRequirement(tuple(required_fields))


__all__ = [
    "DropReason",
    "FreshnessDecision",
    "FreshnessMismatch",
    "FreshnessRequirement",
    "StaleResultGuard",
]

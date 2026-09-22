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

"""Identify why the launcher expected or initiated process termination."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum


class SupervisedTerminationReason(Enum):
    """Classify supervisor-known causes separately from unexplained exits."""

    UNKNOWN = "unknown"
    USER_CANCELLATION = "user_cancellation"
    READINESS_FAILURE = "readiness_failure"
    UPDATE_READINESS_FAILURE = "update_readiness_failure"
    UPDATE_ACTIVATION_FAILURE = "update_activation_failure"
    GENERATION_READINESS_FAILURE = "generation_readiness_failure"


@dataclass(frozen=True, slots=True)
class SupervisedTermination:
    """Carry one trusted supervisor classification and redacted diagnostic detail."""

    reason: SupervisedTerminationReason = SupervisedTerminationReason.UNKNOWN
    detail: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    @property
    def is_user_cancellation(self) -> bool:
        """Return whether the user explicitly cancelled this run."""

        return self.reason is SupervisedTerminationReason.USER_CANCELLATION

    @property
    def is_startup_failure(self) -> bool:
        """Return whether the launcher stopped a run after a known startup failure."""

        return self.reason in {
            SupervisedTerminationReason.READINESS_FAILURE,
            SupervisedTerminationReason.UPDATE_READINESS_FAILURE,
            SupervisedTerminationReason.UPDATE_ACTIVATION_FAILURE,
            SupervisedTerminationReason.GENERATION_READINESS_FAILURE,
        }


__all__ = ["SupervisedTermination", "SupervisedTerminationReason"]

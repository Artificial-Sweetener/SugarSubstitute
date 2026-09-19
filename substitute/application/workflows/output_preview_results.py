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

"""Describe preview-registry acceptance and final-lane closure outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from substitute.application.workflows.output_preview_registry import (
        OutputPreviewLane,
        OutputPreviewLaneKey,
        OutputPreviewRejectionReason,
    )


@dataclass(frozen=True, slots=True)
class OutputPreviewAcceptance:
    """Return the complete result of accepting or rejecting one preview event."""

    accepted: bool
    lanes: tuple[OutputPreviewLane, ...] = ()
    created_preview_ids: tuple[UUID, ...] = ()
    retired_preview_ids: tuple[UUID, ...] = ()
    rejection_reason: OutputPreviewRejectionReason | None = None

    @classmethod
    def rejected(
        cls,
        reason: OutputPreviewRejectionReason,
        *,
        retired_preview_ids: tuple[UUID, ...] = (),
    ) -> OutputPreviewAcceptance:
        """Return a rejected preview result with any retired stale identities."""

        return cls(
            accepted=False,
            retired_preview_ids=retired_preview_ids,
            rejection_reason=reason,
        )


@dataclass(frozen=True, slots=True)
class OutputPreviewCloseResult:
    """Describe preview lanes closed by a matching final output."""

    closed_preview_ids: tuple[UUID, ...]
    completed_keys: tuple[OutputPreviewLaneKey, ...]

    @property
    def closed(self) -> bool:
        """Return whether any preview lane was closed."""

        return bool(self.closed_preview_ids)


__all__ = ["OutputPreviewAcceptance", "OutputPreviewCloseResult"]

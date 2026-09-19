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

"""Copy release bytes while publishing observations independently of asset trust."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import BinaryIO, Protocol

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TransferProgress:
    """Describe copied bytes without implying asset validation or installation readiness."""

    completed_bytes: int
    total_bytes: int | None


class TransferSource(Protocol):
    """Expose the binary read boundary shared by files and HTTPS responses."""

    def read(self, size: int, /) -> bytes:
        """Read a bounded block, returning empty bytes at end of stream."""


class ObservedAssetTransfer:
    """Own transfer counting and isolate presentation failures from release copying."""

    def __init__(
        self,
        observer: Callable[[TransferProgress], None] | None = None,
    ) -> None:
        """Retain the optional observer for this download adapter."""
        self._observer = observer

    def copy(
        self,
        source: TransferSource,
        destination: BinaryIO,
        *,
        total_bytes: int | None,
    ) -> None:
        """Copy bounded blocks and report actual writes before asset promotion."""
        completed = 0
        self._report(TransferProgress(completed, total_bytes))
        while block := source.read(1024 * 1024):
            destination.write(block)
            completed += len(block)
            self._report(TransferProgress(completed, total_bytes))

    def _report(self, progress: TransferProgress) -> None:
        """Disable a failed observer while retaining actionable exception context."""
        if self._observer is None:
            return
        try:
            self._observer(progress)
        except Exception:
            _LOGGER.exception(
                "Asset transfer observer failed; continuing the download.",
                extra={
                    "completed_bytes": progress.completed_bytes,
                    "total_bytes": progress.total_bytes,
                },
            )
            self._observer = None

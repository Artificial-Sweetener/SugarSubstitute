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

"""Retain the complete onboarding setup transcript outside bounded UI memory."""

from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import TextIO

from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.onboarding.setup_transcript")
_TRANSCRIPT_NAME = "onboarding-setup.log"


class OnboardingSetupTranscript:
    """Append and flush setup output to the installation diagnostics directory."""

    def __init__(self, stream: TextIO, path: Path) -> None:
        """Own one line-buffered transcript stream and its public path."""

        self._stream: TextIO | None = stream
        self._path = path
        self._lock = Lock()

    @classmethod
    def open(cls, logs_dir: Path) -> OnboardingSetupTranscript | None:
        """Create the durable transcript or return None after a safe failure."""

        path = logs_dir.resolve() / _TRANSCRIPT_NAME
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            stream = path.open("a", encoding="utf-8", buffering=1)
        except OSError as error:
            log_warning(
                _LOGGER,
                "Could not open the onboarding setup transcript",
                error_type=type(error).__name__,
            )
            return None
        return cls(stream, path)

    @property
    def path(self) -> Path:
        """Return the retained transcript path."""

        return self._path

    def append(self, line: str) -> None:
        """Append and flush one setup line without disrupting setup on I/O failure."""

        normalized = line.rstrip("\r\n")
        if not normalized:
            return
        with self._lock:
            stream = self._stream
            if stream is None:
                return
            try:
                stream.write(normalized + "\n")
                stream.flush()
            except OSError as error:
                self._stream = None
                try:
                    stream.close()
                except OSError:
                    pass
                log_warning(
                    _LOGGER,
                    "Stopped writing the onboarding setup transcript",
                    error_type=type(error).__name__,
                )

    def close(self) -> None:
        """Flush and close the transcript stream idempotently."""

        with self._lock:
            stream, self._stream = self._stream, None
            if stream is None:
                return
            try:
                stream.close()
            except OSError as error:
                log_warning(
                    _LOGGER,
                    "Could not close the onboarding setup transcript cleanly",
                    error_type=type(error).__name__,
                )


__all__ = ["OnboardingSetupTranscript"]

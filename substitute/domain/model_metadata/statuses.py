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

"""Define status values for model metadata refresh workflows."""

from __future__ import annotations

from enum import Enum


class FingerprintStatus(str, Enum):
    """Describe backend SHA256 evidence availability for one model file."""

    READY = "ready"
    MISSING = "missing"
    STALE = "stale"
    FAILED = "failed"


class JobStatus(str, Enum):
    """Describe Substitute BackEnd fingerprint job status values."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class ModelDownloadStatus(str, Enum):
    """Describe Substitute BackEnd model download job status values."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BackendHashLookupStatus(str, Enum):
    """Describe local backend model lookup by SHA256."""

    COMPLETE = "complete"
    NOT_FOUND = "not-found"
    HASHING_REQUIRED = "hashing-required"
    HASHING_RUNNING = "hashing-running"
    UNAVAILABLE = "unavailable"


class CivitaiLookupStatus(str, Enum):
    """Describe the outcome of looking up a model version on CivitAI."""

    FOUND = "found"
    NOT_FOUND = "not-found"
    UNAVAILABLE = "unavailable"
    INVALID_RESPONSE = "invalid-response"


class ThumbnailSelectionStatus(str, Enum):
    """Describe whether a default CivitAI thumbnail was selected."""

    SELECTED = "selected"
    NO_SFW_IMAGE = "no-sfw-image"


__all__ = [
    "BackendHashLookupStatus",
    "CivitaiLookupStatus",
    "FingerprintStatus",
    "JobStatus",
    "ModelDownloadStatus",
    "ThumbnailSelectionStatus",
]

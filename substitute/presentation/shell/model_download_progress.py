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

"""Project verified model download jobs into workflow-neutral progress copy."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationText, app_text

from substitute.application.model_metadata import (
    BackendModelDownloadJob,
    ModelDownloadStatus,
)
from substitute.application.recipes import RecipeModelResolutionRequired


def model_download_message(job: BackendModelDownloadJob) -> ApplicationText:
    """Return user-facing workflow overlay copy for one download job."""

    if job.status is ModelDownloadStatus.QUEUED:
        return app_text("Preparing the download.")
    if job.status is ModelDownloadStatus.RUNNING:
        return job.detail or app_text("Starting the model download.")
    if job.status is ModelDownloadStatus.COMPLETE:
        return app_text("The model has finished downloading.")
    if job.status is ModelDownloadStatus.CANCELLED:
        return app_text("Cancelling the model download.")
    if job.status is ModelDownloadStatus.FAILED:
        return app_text("The model download failed.")
    return app_text("Downloading...")


def model_download_label(
    required: RecipeModelResolutionRequired,
) -> ApplicationText:
    """Return the best aggregate label for exact missing model candidates."""

    unique = {
        (reference.kind, reference.sha256.upper()) for reference in required.references
    }
    if len(unique) > 1:
        return app_text("Models")
    for reference in required.references:
        candidate = reference.candidate
        if candidate is None:
            continue
        model_name = candidate.model_name.strip()
        version_name = candidate.version_name.strip()
        if (
            model_name
            and version_name
            and version_name.casefold() not in {model_name.casefold(), "base"}
        ):
            return f"{model_name} - {version_name}"
        if model_name:
            return model_name
        if candidate.name.strip():
            return candidate.name.strip()
    return app_text("model")


def model_download_detail(job: BackendModelDownloadJob) -> ApplicationText:
    """Return concise byte progress for one verified download."""

    if job.status is ModelDownloadStatus.QUEUED:
        return app_text("Waiting for the download to start...")
    if job.status is ModelDownloadStatus.COMPLETE:
        return app_text("Loading")
    if job.status is ModelDownloadStatus.CANCELLED:
        return app_text("Cancelling download...")
    if job.status is ModelDownloadStatus.FAILED:
        return job.error or app_text("Download failed.")
    if job.bytes_downloaded is None or not job.bytes_total:
        return job.detail or app_text("Downloading...")
    return app_text(
        "%1 of %2",
        _format_download_bytes(job.bytes_downloaded),
        _format_download_bytes(job.bytes_total),
    )


def model_download_progress(job: BackendModelDownloadJob) -> int | None:
    """Return determinate progress in per-mille units when available."""

    if job.status is ModelDownloadStatus.COMPLETE:
        return 1000
    if job.bytes_downloaded is None or not job.bytes_total:
        return None
    return int(1000 * job.bytes_downloaded / max(1, job.bytes_total))


def _format_download_bytes(value: int) -> str:
    """Return a compact byte count for progress presentation."""

    amount = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if amount < 1024.0 or unit == "GB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024.0
    return f"{amount:.1f} GB"


__all__ = [
    "model_download_detail",
    "model_download_label",
    "model_download_message",
    "model_download_progress",
]

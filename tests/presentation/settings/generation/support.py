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

"""Provide focused fakes and builders for generation Settings tests."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QAbstractButton, QApplication

from substitute.application.generation import (
    GenerationPreviewPreferenceService,
    OutputPreferenceService,
)
from substitute.domain.generation import (
    GenerationPreviewPreferences,
    OutputPreferences,
    TaesdPreviewAssetStatus,
    default_generation_preview_preferences,
)
from substitute.presentation.settings.generation_page import GenerationSettingsPage
from substitute.presentation.settings.settings_async import SettingsAsyncTaskRunner
from tests.support.execution import ImmediateTaskSubmitter

_APPLICATION_OWNER: QApplication | None = None


class MemoryPreviewPreferenceRepository:
    """Store generation preview preferences in memory."""

    def __init__(self) -> None:
        """Initialize the repository with default preferences."""

        self.preferences = default_generation_preview_preferences()

    def load(self) -> GenerationPreviewPreferences:
        """Return current preferences."""

        return self.preferences

    def save(self, preferences: GenerationPreviewPreferences) -> None:
        """Persist preferences in memory."""

        self.preferences = preferences


class RecordingPreviewBackend:
    """Return ready TAESD state while recording asset preparation."""

    def __init__(self) -> None:
        """Initialize empty call recording."""

        self.ensure_calls = 0

    def get_taesd_status(self) -> TaesdPreviewAssetStatus:
        """Return a ready TAESD status."""

        return ready_taesd_status()

    def ensure_taesd_assets(self) -> TaesdPreviewAssetStatus:
        """Record asset preparation and return ready state."""

        self.ensure_calls += 1
        return ready_taesd_status()


class MemoryOutputPreferenceRepository:
    """Store output organization preferences in memory."""

    def __init__(self) -> None:
        """Initialize the repository with default preferences."""

        self.preferences = OutputPreferences()

    def load(self) -> OutputPreferences:
        """Return current preferences."""

        return self.preferences

    def save(self, preferences: OutputPreferences) -> None:
        """Persist preferences in memory."""

        self.preferences = preferences


def immediate_task_runner(
    parent: QObject,
    *,
    owner_id: str,
) -> SettingsAsyncTaskRunner:
    """Create a runner whose work and result delivery finish inline."""

    return SettingsAsyncTaskRunner(
        parent,
        submitter=ImmediateTaskSubmitter(),
        owner_id=owner_id,
    )


def build_preview_page(
    repository: MemoryPreviewPreferenceRepository,
    backend: RecordingPreviewBackend | None = None,
) -> GenerationSettingsPage:
    """Build a generation page around preview preference test owners."""

    application()
    return GenerationSettingsPage(
        preference_service=GenerationPreviewPreferenceService(repository, backend),
        task_runner_factory=immediate_task_runner,
    )


def build_output_page(
    *,
    default_output_root: Path,
    output_repository: MemoryOutputPreferenceRepository | None = None,
) -> GenerationSettingsPage:
    """Build a generation page with isolated output preference state."""

    application()
    repository = output_repository or MemoryOutputPreferenceRepository()
    return GenerationSettingsPage(
        preference_service=GenerationPreviewPreferenceService(
            MemoryPreviewPreferenceRepository()
        ),
        output_preference_service=OutputPreferenceService(
            repository,
            default_output_root=default_output_root,
        ),
        task_runner_factory=immediate_task_runner,
    )


def application() -> QApplication:
    """Return the process QApplication or create it for a worker."""

    global _APPLICATION_OWNER  # noqa: PLW0603

    app = QApplication.instance()
    if isinstance(app, QApplication):
        _APPLICATION_OWNER = app
        return app
    _APPLICATION_OWNER = QApplication([])
    return _APPLICATION_OWNER


def button_named(page: GenerationSettingsPage, text: str) -> QAbstractButton:
    """Return the uniquely named visible action below a generation page."""

    matches = tuple(
        button
        for button in page.findChildren(QAbstractButton)
        if button.text().strip() == text
    )
    if len(matches) != 1:
        raise AssertionError(f"Expected one {text!r} button, found {len(matches)}.")
    return matches[0]


def ready_taesd_status() -> TaesdPreviewAssetStatus:
    """Return a minimal ready TAESD status."""

    return TaesdPreviewAssetStatus(
        schema_version=1,
        ready=True,
        installed_count=4,
        missing_count=0,
        downloads_attempted=True,
        assets=(),
        destination_root="E:\\ComfyUI\\models\\vae_approx",
    )

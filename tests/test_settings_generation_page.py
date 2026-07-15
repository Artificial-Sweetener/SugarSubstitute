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

"""Widget contract tests for generation Settings page."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QAbstractButton, QApplication, QLabel, QWidget

from substitute.application.generation import (
    GenerationPreviewPreferenceService,
    OutputOrganizationPreferenceService,
)
from substitute.domain.generation import GenerationPreviewPreferences
from substitute.domain.generation import (
    GenerationPreviewMethod,
    OutputOrganizationPreferences,
    TaesdPreviewAssetStatus,
    default_generation_preview_preferences,
)
from substitute.presentation.settings.settings_card import SettingsCard
from substitute.presentation.settings.generation_page import GenerationSettingsPage
from substitute.presentation.settings.settings_async import SettingsAsyncTaskRunner
from substitute.presentation.settings.settings_workspace_panel import (
    SettingsPageDescriptor,
    SettingsWorkspacePanel,
)
from tests.execution_testing import ImmediateTaskSubmitter

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "settings Qt contract tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


class _MemoryRepository:
    """Store generation preview preferences in memory."""

    def __init__(self) -> None:
        """Initialize with default preferences."""

        self.preferences = default_generation_preview_preferences()

    def load(self) -> GenerationPreviewPreferences:
        """Return current preferences."""

        return self.preferences

    def save(self, preferences: GenerationPreviewPreferences) -> None:
        """Persist preferences in memory."""

        self.preferences = preferences


class _Backend:
    """Record TAESD ensure calls."""

    def __init__(self) -> None:
        """Initialize call recording."""

        self.ensure_calls = 0

    def get_taesd_status(self) -> TaesdPreviewAssetStatus | None:
        """Return a ready status."""

        return _ready_status()

    def ensure_taesd_assets(self) -> TaesdPreviewAssetStatus | None:
        """Record ensure calls and return a ready status."""

        self.ensure_calls += 1
        return _ready_status()


class _OutputRepository:
    """Store output organization preferences in memory."""

    def __init__(self) -> None:
        """Initialize with default preferences."""

        self.preferences = OutputOrganizationPreferences()

    def load(self) -> OutputOrganizationPreferences:
        """Return current preferences."""

        return self.preferences

    def save(self, preferences: OutputOrganizationPreferences) -> None:
        """Persist preferences in memory."""

        self.preferences = preferences


def _task_runner_factory(
    parent: QObject,
    *,
    owner_id: str,
) -> SettingsAsyncTaskRunner:
    """Create an immediate Settings task runner for widget tests."""

    return SettingsAsyncTaskRunner(
        parent,
        submitter=ImmediateTaskSubmitter(),
        owner_id=owner_id,
    )


def test_generation_page_loads_default_preview_preferences() -> None:
    """Generation page should default to enabled latent RGB previews."""

    app = _app()
    repository = _MemoryRepository()
    page = GenerationSettingsPage(
        preference_service=GenerationPreviewPreferenceService(repository),
        task_runner_factory=_task_runner_factory,
    )

    app.processEvents()

    assert page.is_generation_preview_enabled() is True
    assert page.selected_preview_method() == GenerationPreviewMethod.LATENT2RGB.value


def test_generation_page_toggle_persists_enabled_state() -> None:
    """Generation preview toggle should persist through the preference service."""

    app = _app()
    repository = _MemoryRepository()
    page = GenerationSettingsPage(
        preference_service=GenerationPreviewPreferenceService(repository),
        task_runner_factory=_task_runner_factory,
    )

    page.set_generation_preview_enabled(False)
    _wait_for_generation_page_idle(page)
    app.processEvents()

    assert repository.preferences.enabled is False
    assert page.preview_type_combo.isEnabled() is False


def test_generation_page_selecting_taesd_triggers_backend_ensure() -> None:
    """Selecting TAESD should prepare backend preview assets."""

    app = _app()
    repository = _MemoryRepository()
    backend = _Backend()
    page = GenerationSettingsPage(
        preference_service=GenerationPreviewPreferenceService(repository, backend),
        task_runner_factory=_task_runner_factory,
    )

    page.set_preview_method(GenerationPreviewMethod.TAESD.value)
    _wait_for_generation_page_idle(page)
    app.processEvents()

    assert repository.preferences.method is GenerationPreviewMethod.TAESD
    assert backend.ensure_calls == 1
    assert page.status_text() == "TAESD preview files are installed."
    assert page.preview_type_row_widget is not None
    assert (
        page.preview_type_row_widget.description_label.text()
        == "Choose the ComfyUI latent preview method sent with new prompts."
    )


def test_generation_page_output_settings_preview_and_save() -> None:
    """Output organization controls should preview and autosave preferences."""

    app = _app()
    preview_repository = _MemoryRepository()
    output_repository = _OutputRepository()
    page = GenerationSettingsPage(
        preference_service=GenerationPreviewPreferenceService(preview_repository),
        output_organization_service=OutputOrganizationPreferenceService(
            output_repository,
            default_output_root=Path("E:/projects"),
        ),
        task_runner_factory=_task_runner_factory,
    )

    page.set_output_root_text("D:/Images")
    page.set_output_path_pattern("{workflow}\\{date}\\{run}_{source}_{width}x{height}")
    app.processEvents()

    assert page.output_preview_text().endswith(
        "D:\\Images\\My Workflow\\2026-05-01\\007_main_output_1024x1024.png"
    )

    page.output_path_pattern_edit.editingFinished.emit()
    app.processEvents()

    assert output_repository.preferences.output_root == Path("D:/Images")
    assert (
        output_repository.preferences.path_pattern
        == "{workflow}\\{date}\\{run}_{source}_{width}x{height}"
    )


def test_generation_page_output_root_shows_default_path_without_persisting_it() -> None:
    """Default output root should be visible while preferences keep default semantics."""

    app = _app()
    output_repository = _OutputRepository()
    page = GenerationSettingsPage(
        preference_service=GenerationPreviewPreferenceService(_MemoryRepository()),
        output_organization_service=OutputOrganizationPreferenceService(
            output_repository,
            default_output_root=Path("E:/projects"),
        ),
        task_runner_factory=_task_runner_factory,
    )
    app.processEvents()

    assert Path(page.output_root_edit.text()) == Path("E:/projects")

    page.output_root_edit.editingFinished.emit()
    app.processEvents()

    assert output_repository.preferences.output_root is None
    assert Path(page.output_root_edit.text()) == Path("E:/projects")


def test_generation_page_output_settings_preview_renders_seed_token() -> None:
    """Output preview should use the deterministic example seed value."""

    app = _app()
    page = GenerationSettingsPage(
        preference_service=GenerationPreviewPreferenceService(_MemoryRepository()),
        output_organization_service=OutputOrganizationPreferenceService(
            _OutputRepository(),
            default_output_root=Path("E:/projects"),
        ),
        task_runner_factory=_task_runner_factory,
    )

    page.set_output_path_pattern("{workflow}\\{seed}_{source}")
    app.processEvents()

    assert page.output_preview_text().endswith(
        "E:\\projects\\My Workflow\\123456789_main_output.png"
    )


def test_generation_page_output_settings_reject_invalid_token() -> None:
    """Invalid output pattern autosaves should not overwrite saved preferences."""

    app = _app()
    output_repository = _OutputRepository()
    page = GenerationSettingsPage(
        preference_service=GenerationPreviewPreferenceService(_MemoryRepository()),
        output_organization_service=OutputOrganizationPreferenceService(
            output_repository,
            default_output_root=Path("E:/projects"),
        ),
        task_runner_factory=_task_runner_factory,
    )

    page.set_output_path_pattern("{node_id}")
    page.output_path_pattern_edit.editingFinished.emit()
    app.processEvents()

    assert "Unknown output path token" in page.output_preview_text()
    assert (
        output_repository.preferences.path_pattern
        == "{date}\\{run}_{cube#}_{workflow}_{source}"
    )


def test_generation_page_output_settings_are_minimal() -> None:
    """Output settings should not expose separate token or apply/reset controls."""

    app = _app()
    page = GenerationSettingsPage(
        preference_service=GenerationPreviewPreferenceService(_MemoryRepository()),
        output_organization_service=OutputOrganizationPreferenceService(
            _OutputRepository(),
            default_output_root=Path("E:/projects"),
        ),
        task_runner_factory=_task_runner_factory,
    )
    app.processEvents()

    labels = _label_texts(page)
    buttons = _button_texts(page)

    assert "Output folder" in labels
    assert "Output pattern" in labels
    assert "Output preview" in labels
    assert "Output tokens" not in labels
    assert "Apply" not in buttons
    assert "Reset" not in buttons
    assert "Insert" not in buttons


def test_generation_page_output_rows_do_not_clip_at_narrow_width() -> None:
    """Output organization rows should wrap without overflowing their cards."""

    app = _app()
    page = GenerationSettingsPage(
        preference_service=GenerationPreviewPreferenceService(_MemoryRepository()),
        output_organization_service=OutputOrganizationPreferenceService(
            _OutputRepository(),
            default_output_root=Path("E:/projects"),
        ),
        task_runner_factory=_task_runner_factory,
    )
    panel = SettingsWorkspacePanel()
    panel.resize(360, 620)
    panel.set_pages(
        (
            SettingsPageDescriptor(
                "generation",
                "Generation",
                "Preview",
                None,
                page,
            ),
        )
    )
    panel.show()
    app.processEvents()

    output_cards = {
        card.title_label.text(): card for card in page.findChildren(SettingsCard)
    }

    for title in ("Output folder", "Output pattern", "Output preview"):
        card = output_cards[title]
        assert card.layout_mode() in {"wrapped", "wrapped_no_icon"}
        assert card.trailing_widget is not None
        assert card.trailing_widget.width() <= card.width()

    panel.close()


def test_generation_page_output_fields_keep_preferred_width_when_wide() -> None:
    """Output fields should keep their comfortable width when space permits."""

    app = _app()
    page = GenerationSettingsPage(
        preference_service=GenerationPreviewPreferenceService(_MemoryRepository()),
        output_organization_service=OutputOrganizationPreferenceService(
            _OutputRepository(),
            default_output_root=Path("E:/projects"),
        ),
        task_runner_factory=_task_runner_factory,
    )
    panel = SettingsWorkspacePanel()
    panel.resize(1500, 620)
    panel.set_pages(
        (
            SettingsPageDescriptor(
                "generation",
                "Generation",
                "Preview",
                None,
                page,
            ),
        )
    )
    panel.show()
    app.processEvents()

    assert page.output_root_edit.width() == 420
    assert page.output_path_pattern_edit.width() == 360
    assert page.output_preview_edit.width() == 420

    panel.close()


def test_generation_page_output_root_autosaves_and_default_clears_root() -> None:
    """Output root edits should autosave and Default should restore default semantics."""

    app = _app()
    output_repository = _OutputRepository()
    page = GenerationSettingsPage(
        preference_service=GenerationPreviewPreferenceService(_MemoryRepository()),
        output_organization_service=OutputOrganizationPreferenceService(
            output_repository,
            default_output_root=Path("E:/projects"),
        ),
        task_runner_factory=_task_runner_factory,
    )

    page.set_output_root_text("D:/Images")
    page.output_root_edit.editingFinished.emit()
    app.processEvents()

    assert output_repository.preferences.output_root == Path("D:/Images")
    assert Path(page.output_root_edit.text()) == Path("D:/Images")

    page._clear_output_root()
    app.processEvents()

    assert output_repository.preferences.output_root is None
    assert Path(page.output_root_edit.text()) == Path("E:/projects")


def test_generation_page_output_pattern_token_autocomplete_filters_and_inserts() -> (
    None
):
    """Typing a token fragment should offer output tokens and insert the selected one."""

    app = _app()
    page = GenerationSettingsPage(
        preference_service=GenerationPreviewPreferenceService(_MemoryRepository()),
        output_organization_service=OutputOrganizationPreferenceService(
            _OutputRepository(),
            default_output_root=Path("E:/projects"),
        ),
        task_runner_factory=_task_runner_factory,
    )
    page.show()
    app.processEvents()

    page.output_path_pattern_edit.setFocus()
    page.set_output_path_pattern("{workflow}\\{da")
    page.output_path_pattern_edit.setCursorPosition(len("{workflow}\\{da"))
    assert page.output_token_autocomplete is not None
    page.output_token_autocomplete.refresh()
    app.processEvents()

    assert page.output_token_autocomplete.is_visible() is True
    assert page.output_token_autocomplete.visible_tokens() == ("{date}", "{day}")

    accepted = page.output_token_autocomplete.accept_current()
    app.processEvents()

    assert accepted is True
    assert page.output_path_pattern_edit.text() == "{workflow}\\{date}"
    page.close()


def test_generation_page_output_pattern_token_autocomplete_inserts_seed() -> None:
    """Typing a seed token fragment should offer and insert the seed token."""

    app = _app()
    page = GenerationSettingsPage(
        preference_service=GenerationPreviewPreferenceService(_MemoryRepository()),
        output_organization_service=OutputOrganizationPreferenceService(
            _OutputRepository(),
            default_output_root=Path("E:/projects"),
        ),
        task_runner_factory=_task_runner_factory,
    )
    page.show()
    app.processEvents()

    page.output_path_pattern_edit.setFocus()
    page.set_output_path_pattern("{see")
    page.output_path_pattern_edit.setCursorPosition(len("{see"))
    assert page.output_token_autocomplete is not None
    page.output_token_autocomplete.refresh()
    app.processEvents()

    assert page.output_token_autocomplete.is_visible() is True
    assert page.output_token_autocomplete.visible_tokens() == ("{seed}",)

    accepted = page.output_token_autocomplete.accept_current()
    app.processEvents()

    assert accepted is True
    assert page.output_path_pattern_edit.text() == "{seed}"
    page.close()


def _label_texts(widget: QWidget) -> tuple[str, ...]:
    """Return non-empty label texts below a widget."""

    return tuple(
        text for label in widget.findChildren(QLabel) if (text := label.text().strip())
    )


def _button_texts(widget: QWidget) -> tuple[str, ...]:
    """Return non-empty button texts below a widget."""

    return tuple(
        text
        for button in widget.findChildren(QAbstractButton)
        if (text := button.text().strip())
    )


def _ready_status() -> TaesdPreviewAssetStatus:
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


def _app() -> QApplication:
    """Return the existing QApplication or create one for widget tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def _wait_for_generation_page_idle(
    page: GenerationSettingsPage,
    timeout_seconds: float = 5.0,
) -> None:
    """Pump Qt events in tests until generation settings saves settle."""

    app = _app()
    deadline = time.perf_counter() + timeout_seconds
    while page.has_pending_work() and time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.005)
    app.processEvents()

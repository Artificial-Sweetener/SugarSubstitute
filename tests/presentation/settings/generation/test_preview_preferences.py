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

"""Verify generation preview preference presentation and persistence."""

from __future__ import annotations

from substitute.domain.generation import GenerationPreviewMethod
from tests.presentation.settings.generation.support import (
    MemoryPreviewPreferenceRepository,
    RecordingPreviewBackend,
    build_preview_page,
)
from tests.support.qt.lifecycle import destroy_qt_object


def test_generation_page_loads_default_preview_preferences() -> None:
    """Generation page should default to enabled latent RGB previews."""

    repository = MemoryPreviewPreferenceRepository()
    page = build_preview_page(repository)

    assert page.is_generation_preview_enabled() is True
    assert page.selected_preview_method() == GenerationPreviewMethod.LATENT2RGB.value
    destroy_qt_object(page)


def test_generation_page_toggle_persists_enabled_state() -> None:
    """Generation preview toggle should persist through its owner service."""

    repository = MemoryPreviewPreferenceRepository()
    page = build_preview_page(repository)

    page.set_generation_preview_enabled(False)

    assert page.has_pending_work() is False
    assert repository.preferences.enabled is False
    assert page.preview_type_combo.isEnabled() is False
    destroy_qt_object(page)


def test_generation_page_selecting_taesd_triggers_backend_ensure() -> None:
    """Selecting TAESD should prepare backend preview assets."""

    repository = MemoryPreviewPreferenceRepository()
    backend = RecordingPreviewBackend()
    page = build_preview_page(repository, backend)

    page.set_preview_method(GenerationPreviewMethod.TAESD.value)

    assert page.has_pending_work() is False
    assert repository.preferences.method is GenerationPreviewMethod.TAESD
    assert backend.ensure_calls == 1
    assert page.status_text() == "TAESD preview files are installed."
    assert page.preview_type_row_widget is not None
    assert (
        page.preview_type_row_widget.description_label.text()
        == "Choose the ComfyUI latent preview method sent with new prompts."
    )
    destroy_qt_object(page)

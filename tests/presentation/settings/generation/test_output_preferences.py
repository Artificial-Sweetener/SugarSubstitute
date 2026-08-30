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

"""Verify generation output preference presentation and persistence."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QAbstractButton, QLabel

from tests.presentation.settings.generation.support import (
    MemoryOutputPreferenceRepository,
    application,
    build_output_page,
    button_named,
)


def test_generation_page_output_settings_preview_and_save(tmp_path: Path) -> None:
    """Output controls should preview and autosave preferences."""

    app = application()
    default_root = tmp_path / "default-output"
    custom_root = tmp_path / "custom-output"
    repository = MemoryOutputPreferenceRepository()
    page = build_output_page(
        default_output_root=default_root,
        output_repository=repository,
    )

    page.set_output_root_text(str(custom_root))
    page.set_output_path_pattern("{workflow}\\{date}\\{run}_{source}_{width}x{height}")
    app.processEvents()

    assert page.output_preview_text() == str(
        custom_root / "My Workflow" / "2026-05-01" / "007_main_output_1024x1024.png"
    )

    page.output_path_pattern_edit.editingFinished.emit()

    assert repository.preferences.organization.output_root == custom_root
    assert (
        repository.preferences.organization.path_pattern
        == "{workflow}\\{date}\\{run}_{source}_{width}x{height}"
    )
    page.close()


def test_generation_page_shows_default_root_without_persisting_it(
    tmp_path: Path,
) -> None:
    """Default root should remain a visible derived preference."""

    default_root = tmp_path / "default-output"
    repository = MemoryOutputPreferenceRepository()
    page = build_output_page(
        default_output_root=default_root,
        output_repository=repository,
    )

    assert Path(page.output_root_edit.text()) == default_root

    page.output_root_edit.editingFinished.emit()

    assert repository.preferences.organization.output_root is None
    assert Path(page.output_root_edit.text()) == default_root
    page.close()


def test_generation_page_output_preview_renders_seed_token(tmp_path: Path) -> None:
    """Output preview should use the deterministic example seed value."""

    default_root = tmp_path / "default-output"
    page = build_output_page(default_output_root=default_root)

    page.set_output_path_pattern("{workflow}\\{seed}_{source}")

    assert page.output_preview_text() == str(
        default_root / "My Workflow" / "123456789_main_output.png"
    )
    page.close()


def test_generation_page_rejects_invalid_output_token(tmp_path: Path) -> None:
    """Invalid output patterns should not overwrite saved preferences."""

    repository = MemoryOutputPreferenceRepository()
    page = build_output_page(
        default_output_root=tmp_path / "default-output",
        output_repository=repository,
    )

    page.set_output_path_pattern("{node_id}")
    page.output_path_pattern_edit.editingFinished.emit()

    assert "Unknown output path token" in page.output_preview_text()
    assert (
        repository.preferences.organization.path_pattern
        == "{date}\\{run}_{cube#}_{workflow}_{source}"
    )
    page.close()


def test_generation_page_output_settings_are_minimal(tmp_path: Path) -> None:
    """Output settings should expose only directly actionable controls."""

    page = build_output_page(default_output_root=tmp_path / "default-output")
    labels = tuple(
        text for label in page.findChildren(QLabel) if (text := label.text().strip())
    )
    buttons = tuple(
        text
        for button in page.findChildren(QAbstractButton)
        if (text := button.text().strip())
    )

    assert "Output folder" in labels
    assert "Output pattern" in labels
    assert "Output preview" in labels
    assert "Output tokens" not in labels
    assert "Apply" not in buttons
    assert "Reset" not in buttons
    assert "Insert" not in buttons
    page.close()


def test_generation_page_output_root_autosaves_and_default_clears_root(
    tmp_path: Path,
) -> None:
    """Default action should restore derived output-root semantics."""

    default_root = tmp_path / "default-output"
    custom_root = tmp_path / "custom-output"
    repository = MemoryOutputPreferenceRepository()
    page = build_output_page(
        default_output_root=default_root,
        output_repository=repository,
    )

    page.set_output_root_text(str(custom_root))
    page.output_root_edit.editingFinished.emit()

    assert repository.preferences.organization.output_root == custom_root
    assert Path(page.output_root_edit.text()) == custom_root

    button_named(page, "Default").click()

    assert repository.preferences.organization.output_root is None
    assert Path(page.output_root_edit.text()) == default_root
    page.close()

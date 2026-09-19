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

"""Verify immutable paired application/runtime selection and rollback."""

from __future__ import annotations

from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.application_release_selection import (
    ApplicationReleaseSelection,
    LEGACY_RELEASE_GENERATION,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout


_GENERATION = "a" * 32


def _prepare_complete_release(selection: ApplicationReleaseSelection) -> Path:
    """Prepare one generation with its paired application and runtime roots."""

    root = selection.prepare(generation=_GENERATION, version="0.23.0")
    (root / "app").mkdir()
    (root / "app" / "main.py").write_text("candidate", encoding="utf-8")
    (root / "runtime").mkdir()
    (root / "runtime" / "python.exe").write_text("runtime", encoding="utf-8")
    return root


def test_first_generation_activates_atomically_over_legacy_layout(
    tmp_path: Path,
) -> None:
    """Keep the untouched legacy layout as the first rollback target."""

    install_root = tmp_path / "installation"
    (install_root / "app").mkdir(parents=True)
    (install_root / "runtime").mkdir()
    selection = ApplicationReleaseSelection(install_root)
    prepared = _prepare_complete_release(selection)

    selected = selection.activate(generation=_GENERATION)

    assert selected.current == _GENERATION
    assert selected.previous == LEGACY_RELEASE_GENERATION
    assert not prepared.exists()
    assert selection.active_root() == selection.generation_root(_GENERATION)
    layout = InstallLayout.from_root(install_root)
    assert layout.app_dir == selection.generation_root(_GENERATION) / "app"
    assert layout.runtime_dir == selection.generation_root(_GENERATION) / "runtime"


def test_failed_generation_rolls_back_and_is_quarantined(tmp_path: Path) -> None:
    """Restore the prior pointer without deleting either authoritative data root."""

    install_root = tmp_path / "installation"
    legacy_app = install_root / "app"
    legacy_app.mkdir(parents=True)
    (legacy_app / "main.py").write_text("legacy", encoding="utf-8")
    (install_root / "runtime").mkdir()
    selection = ApplicationReleaseSelection(install_root)
    _prepare_complete_release(selection)
    selection.activate(generation=_GENERATION)

    restored = selection.rollback(generation=_GENERATION)

    assert restored.current == LEGACY_RELEASE_GENERATION
    assert selection.active_root() == install_root
    assert (install_root / "app" / "main.py").read_text(encoding="utf-8") == ("legacy")
    record = (selection.generation_root(_GENERATION) / "release.json").read_text(
        encoding="utf-8"
    )
    assert '"status": "rejected"' in record


def test_selection_rejects_incomplete_or_redirected_generation(tmp_path: Path) -> None:
    """Fail closed before an incomplete generation can become active."""

    selection = ApplicationReleaseSelection(tmp_path / "installation")
    selection.prepare(generation=_GENERATION, version="0.23.0")

    with pytest.raises(ValueError, match="incomplete"):
        selection.activate(generation=_GENERATION)
    with pytest.raises(ValueError, match="identity"):
        selection.generation_root("../outside")

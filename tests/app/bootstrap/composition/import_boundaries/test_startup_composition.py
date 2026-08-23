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

"""Test startup composition import boundaries."""

from __future__ import annotations

import textwrap


from .support import (
    COMPOSITION_SOURCE,
    run_isolated_import_probe,
    top_level_imported_module_names as _top_level_imported_module_names,
)


def test_startup_composition_uses_direct_danbooru_service_imports() -> None:
    """Dependency composition should not pay the Danbooru package facade cost."""

    imported_modules = _top_level_imported_module_names(COMPOSITION_SOURCE)
    source = COMPOSITION_SOURCE.read_text(encoding="utf-8")

    assert "substitute.application.danbooru" not in imported_modules
    assert "from substitute.application.danbooru import" not in source
    assert "substitute.application.danbooru.image_preview_service" in source


def test_startup_composition_import_does_not_load_qfluentwidgets() -> None:
    """Startup composition import should not load Fluent widgets before UI build."""

    code = textwrap.dedent(
        """
        import importlib
        import json
        import sys

        importlib.import_module("substitute.app.bootstrap.composition")
        loaded = any(
            name == "qfluentwidgets" or name.startswith("qfluentwidgets.")
            for name in sys.modules
        )
        print(json.dumps(loaded))
        """
    )

    completed = run_isolated_import_probe(code)

    assert completed.stdout.strip() == "false"


def test_startup_composition_imports_no_onboarding_ui_at_module_load() -> None:
    """Ready-route composition imports should not pay onboarding UI costs."""

    forbidden = {
        "substitute.app.bootstrap.installation_context",
        "substitute.app.bootstrap.onboarding_execution",
        "substitute.application.onboarding",
        "substitute.presentation.onboarding",
    }

    assert forbidden.isdisjoint(_top_level_imported_module_names(COMPOSITION_SOURCE))


def test_startup_composition_uses_direct_generation_service_imports() -> None:
    """Dependency composition should not pay the generation package facade cost."""

    imported_modules = _top_level_imported_module_names(COMPOSITION_SOURCE)
    source = COMPOSITION_SOURCE.read_text(encoding="utf-8")

    assert "substitute.application.generation" not in imported_modules
    assert "from substitute.application.generation import" not in source
    assert "substitute.application.generation.generation_service" in source

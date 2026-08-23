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

"""Test shell and UI import deferral boundaries."""

from __future__ import annotations

import textwrap


from .support import (
    run_isolated_import_probe,
)


def test_main_window_composition_import_keeps_canvas_view_deferred() -> None:
    """Main-window composition imports should not load concrete canvas widgets."""

    code = textwrap.dedent(
        """
        import importlib
        import json
        import sys

        importlib.import_module("substitute.presentation.shell.main_window_composition")
        forbidden = {
            "cv2",
            "substitute.presentation.canvas.factory",
            "substitute.presentation.canvas.input.input_canvas_view",
            "substitute.presentation.canvas.output.output_canvas_view",
        }
        loaded = sorted(name for name in sys.modules if name in forbidden)
        print(json.dumps(loaded))
        """
    )

    completed = run_isolated_import_probe(code)

    assert completed.stdout.strip() == "[]"


def test_model_metadata_action_scheduler_import_keeps_menu_ui_deferred() -> None:
    """The action scheduler should not import the context-menu UI stack."""

    code = textwrap.dedent(
        """
        import json
        import sys

        from substitute.presentation.shell.model_metadata_context_action_handler import (
            ModelMetadataContextActionScheduler,
        )

        prefixes = (
            "PySide6",
            "qfluentwidgets",
            "scipy",
            "substitute.presentation.widgets.model_metadata_context_menu",
        )
        loaded = sorted(
            name
            for name in sys.modules
            if any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes)
        )
        print(json.dumps([ModelMetadataContextActionScheduler.__name__, loaded]))
        """
    )

    completed = run_isolated_import_probe(code)

    assert completed.stdout.strip() == '["ModelMetadataContextActionScheduler", []]'


def test_cube_icon_factory_import_keeps_fluent_theme_deferred() -> None:
    """Constructing the icon factory should not import Fluent theme helpers."""

    code = textwrap.dedent(
        """
        import json
        import sys

        from substitute.presentation.resources.cube_icon_factory import CubeIconFactory

        factory = CubeIconFactory()
        loaded = sorted(
            name
            for name in sys.modules
            if name == "qfluentwidgets" or name.startswith("qfluentwidgets.")
        )
        print(json.dumps([factory.__class__.__name__, loaded]))
        """
    )

    completed = run_isolated_import_probe(code)

    assert completed.stdout.strip() == '["CubeIconFactory", []]'


def test_wildcard_management_opener_import_keeps_modal_stack_deferred() -> None:
    """The wildcard opener export should not import the prompt-editor modal."""

    code = textwrap.dedent(
        """
        import json
        import sys

        from substitute.presentation.managed_text_assets import WildcardManagementOpener

        prefixes = (
            "PySide6",
            "qfluentwidgets",
            "scipy",
            "substitute.presentation.editor.prompt_editor",
            "substitute.presentation.managed_text_assets.managed_text_asset_modal",
            "substitute.presentation.managed_text_assets.wildcard_management_modal",
        )
        loaded = sorted(
            name
            for name in sys.modules
            if any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes)
        )
        print(json.dumps([WildcardManagementOpener.__name__, loaded]))
        """
    )

    completed = run_isolated_import_probe(code)

    assert completed.stdout.strip() == '["WildcardManagementOpener", []]'


def test_main_window_dependencies_import_keeps_ui_and_network_modules_deferred() -> (
    None
):
    """The dependency dataclass import should not force UI or network stacks."""

    code = textwrap.dedent(
        """
        import importlib
        import json
        import sys

        importlib.import_module("substitute.presentation.shell.main_window_dependencies")
        prefixes = ("PySide6", "qfluentwidgets", "requests", "scipy")
        loaded = sorted(
            name
            for name in sys.modules
            if any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes)
        )
        print(json.dumps(loaded))
        """
    )

    completed = run_isolated_import_probe(code)

    assert completed.stdout.strip() == "[]"

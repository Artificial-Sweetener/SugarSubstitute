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

"""Test editor-panel mask-picker refresh contracts."""

from __future__ import annotations

import importlib
import logging
from types import ModuleType, SimpleNamespace

from _pytest.logging import LogCaptureFixture


class _MaskPickerDouble:
    """Record metadata and refreshes for one mask-picker widget."""

    def __init__(self, metadata: dict[str, object]) -> None:
        """Store picker metadata."""

        self._metadata = metadata
        self.mask_paths: list[str] = []
        self.refresh_paths: list[str] = []

    def property(self, name: str) -> object | None:
        """Return Qt-style metadata."""

        if name == "input_metadata":
            return self._metadata
        return None

    def set_mask_path(self, path: str) -> None:
        """Record one mask path update."""

        self.mask_paths.append(path)

    def refresh_mask_path(self, path: str) -> None:
        """Record one autosave refresh."""

        self.refresh_paths.append(path)


def _panel_module() -> ModuleType:
    """Return the production editor-panel module."""

    return importlib.import_module("substitute.presentation.editor.panel.view")


def test_refresh_mask_picker_updates_matching_picker() -> None:
    """Editor panel should refresh the picker matching cube alias and node name."""

    module = _panel_module()
    matching = _MaskPickerDouble(
        {
            "cube_alias": "Inpaint",
            "node_name": "load_image_as_mask",
            "key": "image",
        }
    )
    other = _MaskPickerDouble(
        {
            "cube_alias": "Other",
            "node_name": "load_image_as_mask",
            "key": "image",
        }
    )
    panel = SimpleNamespace(findChildren=lambda _type: [other, matching])

    module.EditorPanel.refresh_mask_picker(
        panel,
        "Inpaint",
        "load_image_as_mask",
        "E:/masks/current.png",
    )

    assert other.refresh_paths == []
    assert matching.refresh_paths == ["E:/masks/current.png"]


def test_refresh_mask_picker_logs_when_no_picker_matches(
    caplog: LogCaptureFixture,
) -> None:
    """Missing mask picker matches should be observable."""

    module = _panel_module()
    picker = _MaskPickerDouble(
        {
            "node_name": "load_image_as_mask",
            "key": "image",
        }
    )
    panel = SimpleNamespace(findChildren=lambda _type: [picker])

    with caplog.at_level(
        logging.WARNING,
        logger="sugarsubstitute.presentation.editor.panel.view",
    ):
        module.EditorPanel.refresh_mask_picker(
            panel,
            "Inpaint",
            "load_image_as_mask",
            "E:/masks/current.png",
        )

    assert picker.mask_paths == []
    assert "no matching picker was found" in caplog.text
    assert "cube_alias=Inpaint" in caplog.text
    assert "inspected_count=1" in caplog.text

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

"""Test card-wrapper ownership through the EditorPanel façade."""

from __future__ import annotations

import importlib
from types import ModuleType, SimpleNamespace


def _panel_module() -> ModuleType:
    """Return the production editor-panel module."""

    return importlib.import_module("substitute.presentation.editor.panel.view")


def test_card_wrapper_cleanup_ignores_stale_wrapper() -> None:
    """Destroyed stale wrappers must not remove a newer registry owner."""

    panel_module = _panel_module()
    panel = SimpleNamespace(card_wrappers={})
    first_wrapper = object()
    current_wrapper = object()

    panel_module.EditorPanel.register_card_wrapper(
        panel,
        "Cube",
        "vae_override",
        first_wrapper,
    )
    panel_module.EditorPanel.register_card_wrapper(
        panel,
        "Cube",
        "vae_override",
        current_wrapper,
    )
    panel_module.EditorPanel.remove_card_wrapper_if_current(
        panel,
        "Cube",
        "vae_override",
        first_wrapper,
    )

    assert panel.card_wrappers[("Cube", "vae_override")] is current_wrapper

    panel_module.EditorPanel.remove_card_wrapper_if_current(
        panel,
        "Cube",
        "vae_override",
        current_wrapper,
    )

    assert ("Cube", "vae_override") not in panel.card_wrappers


def test_card_wrapper_cleanup_ignores_unknown_key() -> None:
    """Removing a non-current wrapper should not affect unrelated entries."""

    panel_module = _panel_module()
    wrapper = object()
    panel = SimpleNamespace(card_wrappers={("Other", "node"): wrapper})

    panel_module.EditorPanel.remove_card_wrapper_if_current(
        panel,
        "Cube",
        "vae_override",
        object(),
    )

    assert panel.card_wrappers == {("Other", "node"): wrapper}

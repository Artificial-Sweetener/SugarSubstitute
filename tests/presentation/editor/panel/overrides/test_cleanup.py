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

"""Verify override-manager teardown owns every mounted toolbar control."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.application.overrides import PinnedOverrideService
from substitute.presentation.editor.panel.overrides_controller import (
    GlobalOverridesManager,
)

from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
)


def test_overrides_manager_dispose_removes_widgets_and_state() -> None:
    """Dispose every label and control while clearing manager state."""

    class DummyLabel:
        """Record deferred disposal for one toolbar object."""

        def __init__(self, name: str) -> None:
            self.name = name
            self.deleted = False

        def deleteLater(self) -> None:
            """Record the manager's Qt-compatible disposal request."""

            self.deleted = True

    class DummyWidget(DummyLabel):
        """Represent one toolbar control paired with a label."""

    class DummyLayout:
        """Record controls removed from the toolbar layout."""

        def __init__(self) -> None:
            self.removed: list[object] = []

        def removeWidget(self, widget: object) -> None:
            """Record one removed toolbar object."""

            self.removed.append(widget)

        def indexOf(self, widget: object) -> int:  # pragma: no cover
            """Report that no toolbar object is mounted."""

            del widget
            return -1

        def insertWidget(self, index: int, widget: object) -> None:  # pragma: no cover
            """Accept the manager layout protocol outside this test path."""

            del index, widget

    class DummyMW:
        """Expose the toolbar layout required by the manager."""

        def __init__(self) -> None:
            self.menu_bar_layout = DummyLayout()

    mw = DummyMW()
    mgr = GlobalOverridesManager(
        mw,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )

    # Pre-populate with two override controls and corresponding state
    l1, w1 = DummyLabel("seed_label"), DummyWidget("seed_widget")
    l2, w2 = DummyLabel("sampler_label"), DummyWidget("sampler_widget")
    mgr._global_override_controls = {
        "seed": (l1, w1),
        "sampler_name": (l2, w2),
    }
    mgr._global_overrides = {
        "seed": {"value": 42, "mode": "global"},
        "sampler_name": {"value": "Euler", "mode": "global"},
    }

    # Act
    mgr.dispose()

    # Assert: controls cleared and state reset
    assert mgr._global_override_controls == {}
    assert mgr._global_overrides == {}

    # Assert: layout removal was called for all widgets and labels
    removed_names = {getattr(w, "name", None) for w in mw.menu_bar_layout.removed}
    assert removed_names == {
        "seed_label",
        "seed_widget",
        "sampler_label",
        "sampler_widget",
    }

    # Assert: deleteLater invoked on all
    assert l1.deleted and w1.deleted and l2.deleted and w2.deleted

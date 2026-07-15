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

from __future__ import annotations

import sys
import types
from types import SimpleNamespace

from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
)


def test_overrides_manager_dispose_removes_widgets_and_state(monkeypatch) -> None:
    class DummyLabel:
        def __init__(self, name):
            self.name = name
            self.deleted = False

        def deleteLater(self):
            self.deleted = True

    class DummyWidget(DummyLabel):
        pass

    class DummyLayout:
        def __init__(self):
            self.removed = []

        def removeWidget(self, w):
            self.removed.append(w)

        # Some code paths call indexOf/insertWidget; not used here but present elsewhere
        def indexOf(self, w):  # pragma: no cover - not exercised in this test
            return -1

        def insertWidget(self, i, w):  # pragma: no cover - not exercised in this test
            pass

    class DummyMW:
        def __init__(self):
            self.menu_bar_layout = DummyLayout()

    sys.modules.pop("substitute.presentation.editor.panel.overrides_controller", None)
    qfw = types.ModuleType("qfluentwidgets")
    qfw.CaptionLabel = DummyLabel
    monkeypatch.setitem(sys.modules, "qfluentwidgets", qfw)
    qtgui = types.ModuleType("PySide6.QtGui")
    qtgui.QAction = type("QAction", (), {})
    monkeypatch.setitem(sys.modules, "PySide6.QtGui", qtgui)
    field_pipeline_stub = types.ModuleType(
        "substitute.presentation.editor.panel.factories.field_pipeline"
    )
    field_pipeline_stub.LAYOUT_HANDLED = object()
    field_pipeline_stub.build_widget_for_field_spec = lambda **_kwargs: None
    monkeypatch.setitem(
        sys.modules,
        "substitute.presentation.editor.panel.factories.field_pipeline",
        field_pipeline_stub,
    )
    choice_factory_stub = types.ModuleType(
        "substitute.presentation.editor.panel.factories.choice_factory"
    )
    choice_factory_stub.resolve_choice_options_for_field = lambda **_kwargs: ()
    monkeypatch.setitem(
        sys.modules,
        "substitute.presentation.editor.panel.factories.choice_factory",
        choice_factory_stub,
    )
    field_state_stub = types.ModuleType(
        "substitute.presentation.editor.panel.field_state_controller"
    )
    field_state_stub.EditorPanelFieldStateController = type(
        "EditorPanelFieldStateController",
        (),
        {
            "__init__": lambda self, *_args, **_kwargs: None,
            "bind_node_widget_state": lambda self, *_args, **_kwargs: None,
        },
    )
    monkeypatch.setitem(
        sys.modules,
        "substitute.presentation.editor.panel.field_state_controller",
        field_state_stub,
    )
    model_choice_stub = types.ModuleType(
        "substitute.presentation.editor.panel.model_choice_snapshot_controller"
    )
    model_choice_stub.PanelModelChoiceSnapshotController = type(
        "PanelModelChoiceSnapshotController",
        (),
        {},
    )
    monkeypatch.setitem(
        sys.modules,
        "substitute.presentation.editor.panel.model_choice_snapshot_controller",
        model_choice_stub,
    )
    from substitute.presentation.editor.panel.overrides_controller import (
        GlobalOverridesManager,
    )

    mw = DummyMW()
    mgr = GlobalOverridesManager(
        mw,
        pinned_override_service=SimpleNamespace(),
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

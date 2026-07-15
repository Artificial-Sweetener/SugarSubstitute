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

"""Focused tests for editor-panel field synchronization ownership."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable, cast

from _pytest.monkeypatch import MonkeyPatch

from substitute.domain.generation.seed_control import SeedControlState, SeedMode
import substitute.presentation.editor.panel.field_sync_controller as field_sync_mod
import substitute.presentation.editor.panel.field_state_controller as field_state_mod
from substitute.presentation.editor.panel.field_sync_controller import (
    EditorPanelFieldSyncController,
    EditorPanelFieldSyncHost,
)
from substitute.presentation.editor.panel.field_state_controller import (
    EditorPanelFieldStateController,
    EditorPanelFieldStateHost,
)


class _PromptEditorDouble:
    """Prompt-editor double that records source replacement calls."""

    def __init__(self, metadata: dict[str, str], text: str) -> None:
        """Initialize metadata and visible source text."""

        self._metadata = metadata
        self._text = text
        self.baseline_replacements: list[str] = []
        self.plain_text_replacements: list[str] = []

    def property(self, name: str) -> object:
        """Return one dynamic property."""

        if name == "input_metadata":
            return self._metadata
        return None

    def toPlainText(self) -> str:
        """Return the current visible source text."""

        return self._text

    def replaceBaselineSourceText(self, text: str) -> None:
        """Record a baseline-safe source replacement."""

        self.baseline_replacements.append(text)
        self._text = text

    def setPlainText(self, text: str) -> None:
        """Record fallback plain-text replacement."""

        self.plain_text_replacements.append(text)
        self._text = text


class _CubeWidgetDouble:
    """Cube widget double that returns scripted prompt-editor children."""

    def __init__(self, prompt_editors: list[_PromptEditorDouble]) -> None:
        """Store child prompt editors."""

        self._prompt_editors = prompt_editors

    def findChildren(self, cls: type[object]) -> list[_PromptEditorDouble]:
        """Return prompt editors only for the requested class."""

        if cls is _PromptEditorDouble:
            return self._prompt_editors
        return []


class _Widget:
    """Widget double with mutable visibility."""

    def __init__(
        self,
        *,
        properties: dict[str, object] | None = None,
        parent: object | None = None,
    ) -> None:
        """Initialize visible state."""

        self.visible = True
        self._properties = dict(properties or {})
        self._parent = parent

    def setVisible(self, visible: bool) -> None:
        """Record visibility."""

        self.visible = visible

    def isVisible(self) -> bool:
        """Return current visibility."""

        return self.visible

    def property(self, name: str) -> object:
        """Return one Qt-style property."""

        return self._properties.get(name)

    def parentWidget(self) -> object | None:
        """Return the assigned parent widget."""

        return self._parent


class _SignalDouble:
    """Minimal signal double for field-state binding tests."""

    def __init__(self) -> None:
        """Initialize connected callbacks."""

        self._callbacks: list[Callable[..., object]] = []

    def connect(self, callback: Callable[..., object]) -> None:
        """Store one callback."""

        self._callbacks.append(callback)

    def emit(self, *args: object) -> None:
        """Invoke stored callbacks."""

        for callback in list(self._callbacks):
            callback(*args)


class _SeedBoxDouble:
    """SeedBox test double with value and mode signals."""

    def __init__(self, metadata: dict[str, object]) -> None:
        """Initialize seed value, mode, and metadata."""

        self._metadata = metadata
        self._value = 0
        self._mode = "random"
        self.valueChanged = _SignalDouble()
        self.modeChanged = _SignalDouble()

    def property(self, name: str) -> object:
        """Return one Qt-style property."""

        if name == "input_metadata":
            return self._metadata
        return None

    def value(self) -> int:
        """Return current seed value."""

        return self._value

    def setValue(self, value: object) -> None:  # noqa: N802
        """Set current seed value and emit when changed."""

        next_value = int(cast(Any, value))
        if self._value == next_value:
            return
        self._value = next_value
        self.valueChanged.emit(next_value)

    def mode(self) -> str:
        """Return current seed mode."""

        return self._mode

    def setMode(self, mode: str) -> None:  # noqa: N802
        """Set current seed mode and emit when changed."""

        if self._mode == mode:
            return
        self._mode = mode
        self.modeChanged.emit(mode)


class _CubeParent:
    """Cube-section parent double that records height refresh requests."""

    def __init__(self) -> None:
        """Initialize refresh counter."""

        self.height_refreshes = 0

    def defer_update_cube_height(self) -> None:
        """Record a deferred cube-height refresh."""

        self.height_refreshes += 1


def test_sync_prompt_editor_values_from_buffers_restores_all_cubes(
    monkeypatch: MonkeyPatch,
) -> None:
    """Full prompt sync should restore every prompt widget and refresh diagnostics."""

    monkeypatch.setattr(field_state_mod, "PromptEditor", _PromptEditorDouble)
    first_prompt = _PromptEditorDouble(
        {"cube_alias": "A", "node_name": "prompt", "key": "text"},
        "stale",
    )
    second_prompt = _PromptEditorDouble(
        {"cube_alias": "B", "node_name": "prompt", "key": "text"},
        "unchanged",
    )
    scene_refreshes: list[str] = []
    host = SimpleNamespace(
        _cube_states={
            "A": SimpleNamespace(
                buffer={"nodes": {"prompt": {"inputs": {"text": "fresh"}}}}
            ),
            "B": SimpleNamespace(
                buffer={"nodes": {"prompt": {"inputs": {"text": "unchanged"}}}}
            ),
        },
        cube_widgets={
            "A": _CubeWidgetDouble([first_prompt]),
            "B": _CubeWidgetDouble([second_prompt]),
        },
        refresh_prompt_scene_diagnostics=lambda: scene_refreshes.append("refresh"),
    )

    EditorPanelFieldStateController(
        cast(EditorPanelFieldStateHost, host)
    ).sync_prompt_editor_values_from_buffers()

    assert first_prompt.toPlainText() == "fresh"
    assert first_prompt.baseline_replacements == ["fresh"]
    assert second_prompt.baseline_replacements == []
    assert scene_refreshes == ["refresh"]


def test_sync_prompt_editor_values_for_cube_scans_only_target_cube(
    monkeypatch: MonkeyPatch,
) -> None:
    """Cube-scoped prompt sync should avoid mutating unrelated cube widgets."""

    monkeypatch.setattr(field_state_mod, "PromptEditor", _PromptEditorDouble)
    target_prompt = _PromptEditorDouble(
        {"cube_alias": "A", "node_name": "prompt", "key": "text"},
        "old",
    )
    unrelated_prompt = _PromptEditorDouble(
        {"cube_alias": "B", "node_name": "prompt", "key": "text"},
        "unchanged",
    )
    host = SimpleNamespace(
        _cube_states={
            "A": SimpleNamespace(
                buffer={"nodes": {"prompt": {"inputs": {"text": "new"}}}}
            ),
            "B": SimpleNamespace(
                buffer={"nodes": {"prompt": {"inputs": {"text": "other"}}}}
            ),
        },
        cube_widgets={
            "A": _CubeWidgetDouble([target_prompt]),
            "B": _CubeWidgetDouble([unrelated_prompt]),
        },
    )

    EditorPanelFieldStateController(
        cast(EditorPanelFieldStateHost, host)
    ).sync_prompt_editor_values_for_cube("A")

    assert target_prompt.toPlainText() == "new"
    assert unrelated_prompt.toPlainText() == "unchanged"


def test_wire_seedbox_state_restores_and_persists_seed_mode(
    monkeypatch: MonkeyPatch,
) -> None:
    """SeedBox mode should round-trip through cube field control state."""

    monkeypatch.setattr(field_state_mod, "SeedBox", _SeedBoxDouble)
    seedbox = _SeedBoxDouble(
        {"cube_alias": "CubeA", "node_name": "KSampler", "key": "seed"}
    )
    cube_state = SimpleNamespace(
        buffer={"nodes": {"KSampler": {"inputs": {"seed": 123}}}},
        dirty=False,
        field_control_states={"KSampler": {"seed": SeedControlState(SeedMode.FIXED)}},
    )

    EditorPanelFieldStateController().bind_node_widget_state(seedbox, cube_state, {})

    assert seedbox.value() == 123
    assert seedbox.mode() == "fixed"

    seedbox.setMode("random")

    assert cube_state.field_control_states["KSampler"]["seed"].mode == SeedMode.RANDOM
    assert cube_state.dirty is True


def test_set_search_field_match_keys_reapplies_current_hidden_fields() -> None:
    """Field-search state should hide non-matches without changing policy hidden keys."""

    matching_key = ("CubeA", "KSampler", "sampler_name")
    hidden_key = ("CubeA", "KSampler", "seed")
    non_matching_key = ("CubeA", "KSampler", "cfg")
    matching_row = _Widget()
    hidden_row = _Widget()
    non_matching_row = _Widget()
    host = SimpleNamespace(
        _hidden_field_keys={hidden_key},
        _search_field_match_keys=None,
        _field_search_active=False,
        row_widgets={
            matching_key: (_Widget(), matching_row),
            hidden_key: (_Widget(), hidden_row),
            non_matching_key: (_Widget(), non_matching_row),
        },
        col_widgets={},
        card_wrappers={},
    )

    EditorPanelFieldSyncController(
        cast(EditorPanelFieldSyncHost, host)
    ).set_search_field_match_keys({matching_key}, active=True)

    assert host._hidden_field_keys == {hidden_key}
    assert host._search_field_match_keys == {matching_key}
    assert host._field_search_active is True
    assert matching_row.visible is True
    assert hidden_row.visible is False
    assert non_matching_row.visible is False


def test_apply_hidden_field_keys_hides_empty_cards_and_refreshes_height(
    monkeypatch: MonkeyPatch,
) -> None:
    """Card visibility should reflect hidden/search state and refresh on change."""

    reconciled: list[dict[object, object]] = []
    monkeypatch.setattr(
        field_sync_mod,
        "reconcile_node_card_body_separators",
        lambda rows: reconciled.append(dict(rows)),
    )
    cube_parent = _CubeParent()
    visible_key = ("CubeA", "NodeA", "visible")
    hidden_key = ("CubeA", "NodeA", "hidden")
    visible_row = _Widget()
    hidden_row = _Widget()
    card = _Widget(
        properties={"base_card_visible": True},
        parent=cube_parent,
    )
    host = SimpleNamespace(
        _hidden_field_keys=set(),
        _search_field_match_keys={visible_key},
        _field_search_active=True,
        row_widgets={
            visible_key: (_Widget(), visible_row),
            hidden_key: (_Widget(), hidden_row),
        },
        col_widgets={},
        card_wrappers={("CubeA", "NodeA"): card},
    )

    controller = EditorPanelFieldSyncController(cast(EditorPanelFieldSyncHost, host))
    controller.apply_hidden_field_keys({hidden_key})
    controller.set_search_field_match_keys(set(), active=True)

    assert visible_row.visible is False
    assert hidden_row.visible is False
    assert card.visible is False
    assert cube_parent.height_refreshes == 1
    assert reconciled


def test_apply_hidden_field_keys_updates_grouped_column_dividers() -> None:
    """Grouped column dividers should hide when only one column remains visible."""

    first_key = ("CubeA", "NodeA", "first")
    second_key = ("CubeA", "NodeA", "second")
    first_divider = _Widget(properties={"vertical_divider_for_field": first_key})
    second_divider = _Widget(properties={"vertical_divider_for_field": second_key})

    class _Layout:
        """Layout double exposing divider widgets."""

        def __init__(self, widgets: list[_Widget]) -> None:
            """Store ordered divider widgets."""

            self._widgets = widgets

        def count(self) -> int:
            """Return widget count."""

            return len(self._widgets)

        def itemAt(self, index: int) -> object:  # noqa: N802
            """Return a layout item for one widget."""

            return SimpleNamespace(widget=lambda: self._widgets[index])

    parent = SimpleNamespace(layout=lambda: _Layout([first_divider, second_divider]))
    row_container = _Widget()
    first_col = _Widget(properties={"field_key": first_key}, parent=parent)
    second_col = _Widget(properties={"field_key": second_key}, parent=parent)
    horizontal_divider = _Widget()
    host = SimpleNamespace(
        _hidden_field_keys=set(),
        _search_field_match_keys=None,
        _field_search_active=False,
        row_widgets={first_key: (horizontal_divider, _Widget())},
        col_widgets={
            first_key: (row_container, first_col, object()),
            second_key: (row_container, second_col, object()),
        },
        card_wrappers={},
    )

    EditorPanelFieldSyncController(
        cast(EditorPanelFieldSyncHost, host)
    ).apply_hidden_field_keys({second_key})

    assert first_col.visible is True
    assert second_col.visible is False
    assert row_container.visible is True
    assert first_divider.visible is False
    assert second_divider.visible is False
    assert horizontal_divider.visible is True

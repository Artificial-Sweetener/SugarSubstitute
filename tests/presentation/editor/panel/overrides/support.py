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

"""Additional presentation contracts for the pinned override toolbar manager."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    FieldBehavior,
    OverrideBehavior,
    OverridePinPolicy,
    ResolvedFieldSpec,
)
from substitute.presentation.editor.panel import overrides_controller
from substitute.presentation.widgets import tooltips


class _Signal:
    """Minimal signal stub for widget wiring tests."""

    def __init__(self) -> None:
        self._callbacks: list[Callable[..., None]] = []

    def connect(self, callback: Callable[..., None]) -> None:
        """Store connected callback."""

        self._callbacks.append(callback)

    def emit(self, *args: object) -> None:
        """Invoke stored callbacks."""

        for callback in list(self._callbacks):
            callback(*args)


class _DummyAction:
    """Minimal checked QAction stand-in."""

    def __init__(self, data: dict[str, object], checked: bool) -> None:
        self._data = data
        self._checked = checked

    def data(self) -> dict[str, object]:
        """Return action payload."""

        return self._data

    def isChecked(self) -> bool:
        """Return check state."""

        return self._checked


def _policy_name(policy: object) -> str:
    """Return a stable lower-case name for real or stub Qt size policies."""

    name = getattr(policy, "name", None)
    return str(name if name is not None else policy).lower()


class _DummyLabel:
    """Simple label stub tracked by the toolbar layout."""

    def __init__(self, name: str, parent: object | None = None) -> None:
        self.name = name
        self.deleted = False
        self.visible = False
        self.tooltip = ""
        self.filters: list[object] = []
        self.size_policy: tuple[object, object] | None = None

    def setContentsMargins(self, *_args: object, **_kwargs: object) -> None:
        """Ignore label margin updates."""

    def setSizePolicy(self, horizontal: object, vertical: object) -> None:
        """Record toolbar label sizing policy."""

        self.size_policy = (_policy_name(horizontal), _policy_name(vertical))

    def setToolTip(self, tooltip: str) -> None:
        """Record owner tooltip text."""

        self.tooltip = tooltip

    def toolTip(self) -> str:
        """Return owner tooltip text."""

        return self.tooltip

    def installEventFilter(self, tooltip_filter: object) -> None:
        """Record installed tooltip filters."""

        self.filters.append(tooltip_filter)

    def deleteLater(self) -> None:
        """Record disposal."""

        self.deleted = True

    def hide(self) -> None:
        """Record hidden state."""

        self.visible = False

    def show(self) -> None:
        """Record visible state."""

        self.visible = True


class _DummyWidget:
    """Toolbar widget stub with one configurable signal surface."""

    def __init__(self, name: str, signal_name: str = "valueChanged") -> None:
        self.name = name
        self.deleted = False
        self.visible = False
        self.fixed_width: int | None = None
        self.fixed_height: int | None = None
        self.maximum_width: int | None = None
        self.size_policy: tuple[object, object] | None = None
        self.stylesheet: str | None = None
        self.filters: list[object] = []
        setattr(self, signal_name, _Signal())

    def setFixedWidth(self, width: int) -> None:
        """Record fixed width constraints."""

        self.fixed_width = width

    def setFixedHeight(self, height: int) -> None:
        """Record fixed height constraints."""

        self.fixed_height = height

    def setMaximumWidth(self, width: int) -> None:
        """Record maximum width constraints."""

        self.maximum_width = width

    def setSizePolicy(self, horizontal: object, vertical: object) -> None:
        """Record toolbar sizing policy."""

        self.size_policy = (_policy_name(horizontal), _policy_name(vertical))

    def setStyleSheet(self, stylesheet: str) -> None:
        """Record stylesheet constraints."""

        self.stylesheet = stylesheet

    def installEventFilter(self, tooltip_filter: object) -> None:
        """Record installed tooltip filters."""

        self.filters.append(tooltip_filter)

    def deleteLater(self) -> None:
        """Record disposal."""

        self.deleted = True

    def hide(self) -> None:
        """Record hidden state."""

        self.visible = False

    def show(self) -> None:
        """Record visible state."""

        self.visible = True


class _DummyLayout:
    """Minimal menu-bar layout stub used by the manager."""

    def __init__(self) -> None:
        self.widgets: list[object] = []
        self.removed: list[object] = []

    def indexOf(self, widget: object) -> int:
        """Return existing widget index or `-1` when absent."""

        try:
            return self.widgets.index(widget)
        except ValueError:
            return -1

    def insertWidget(self, index: int, widget: object) -> None:
        """Insert one widget into layout order."""

        self.widgets.insert(index, widget)

    def removeWidget(self, widget: object) -> None:
        """Record and remove one widget from layout order."""

        self.removed.append(widget)
        if widget in self.widgets:
            self.widgets.remove(widget)


class _RestartToolbarButton:
    """Record restart toolbar spacing refresh requests."""

    def __init__(self) -> None:
        self.refresh_calls = 0

    def refresh_toolbar_spacing(self) -> None:
        """Record one spacing reconciliation request."""

        self.refresh_calls += 1


class _SnapshotSource:
    """Mutable behavior-snapshot source for toolbar rebuild tests."""

    def __init__(self, snapshot: EditorBehaviorSnapshot) -> None:
        self.snapshot = snapshot

    def current_behavior_snapshot(self) -> EditorBehaviorSnapshot:
        """Return the active behavior snapshot."""

        return self.snapshot


def _install_toolbar_view_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    build_widget_callback: Callable[..., object],
    choice_options_callback: Callable[..., object] | None = None,
) -> None:
    """Replace only the manager's imported presentation collaborators."""

    monkeypatch.setattr(overrides_controller, "CaptionLabel", _DummyLabel)
    monkeypatch.setattr(
        overrides_controller,
        "build_widget_for_field_spec",
        build_widget_callback,
    )
    monkeypatch.setattr(
        overrides_controller,
        "resolve_choice_options_for_field",
        choice_options_callback
        if choice_options_callback is not None
        else lambda **_kwargs: (),
    )

    def _bind_fluent_tooltip(
        owner: Any,
        text: str,
        *widgets: Any,
        **_kwargs: object,
    ) -> None:
        """Record tooltip binding without importing Qt tooltip filters."""

        if hasattr(owner, "setToolTip"):
            owner.setToolTip(text)
        tooltip_filter = object()
        seen: set[int] = set()
        for widget in (owner, *widgets):
            if id(widget) in seen:
                continue
            seen.add(id(widget))
            if hasattr(widget, "installEventFilter"):
                widget.installEventFilter(tooltip_filter)

    monkeypatch.setattr(tooltips, "bind_fluent_tooltip", _bind_fluent_tooltip)
    monkeypatch.setattr(
        tooltips,
        "tooltip_from_field_meta",
        lambda meta: meta.get("tooltip", "") if isinstance(meta, dict) else "",
    )


def _field_spec(
    *,
    override_key: str,
    field_key: str,
    value: object,
    order: int,
    pin_policy: OverridePinPolicy = OverridePinPolicy.DEFAULT_PINNED,
    field_type: str = "STRING",
    field_info: list[object] | None = None,
    meta_info: dict[str, object] | None = None,
) -> ResolvedFieldSpec:
    """Build one representative field spec for toolbar manager tests."""

    return ResolvedFieldSpec(
        cube_alias="A",
        node_name="ksampler",
        class_type="KSampler",
        field_key=field_key,
        field_type=field_type,
        constraints={},
        meta_info=dict(meta_info or {}),
        field_info=field_info,
        value=value,
        field_behavior=FieldBehavior(
            field_key=field_key,
            override_behavior=OverrideBehavior(
                override_key=override_key,
                pin_policy=pin_policy,
                toolbar_order=order,
            ),
        ),
    )


def _snapshot(*specs: ResolvedFieldSpec) -> EditorBehaviorSnapshot:
    """Build one snapshot with the provided toolbar candidate specs."""

    return EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={
            "A": {
                "ksampler": {spec.field_key: spec for spec in specs},
            }
        },
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )

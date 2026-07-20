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

"""Provide a seed-entry widget with fixed/random modes and large integer support."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import (
    app_text,
    set_localized_tooltip,
    translate_application_text,
)

from typing import TYPE_CHECKING, Any, Protocol, cast

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QKeyEvent, QWheelEvent
from PySide6.QtWidgets import QSizePolicy, QWidget

from substitute.presentation.widgets.wheel_permission import wheel_event_is_allowed

if TYPE_CHECKING:
    LineEdit = Any
    RoundMenu = Any
    SplitToolButton = Any
    from substitute.presentation.widgets.menu_model import MenuItem, MenuModel
    from substitute.presentation.widgets.qfluent_menu_renderer import (
        QFluentMenuRenderer,
    )

    def setFont(_widget: object, _font_size: int = 14, _weight: int = 50) -> None: ...

    class _FifProtocol(Protocol):
        """Describe the icon members SeedBox uses from FluentIcon."""

        PIN: object
        UNPIN: object

    class Action:
        """Describe the Action constructor used by SeedBox."""

        def __init__(
            self,
            _icon: object,
            _text: str,
            _parent: object = None,
            *,
            triggered: object | None = None,
        ) -> None: ...

    FIF: _FifProtocol
else:
    try:
        from qfluentwidgets import Action
        from qfluentwidgets import FluentIcon as FIF
        from qfluentwidgets import LineEdit
        from qfluentwidgets import RoundMenu
        from substitute.presentation.widgets.menu_buttons import ToggleSplitToolButton
    except ImportError:  # pragma: no cover - runtime fallback only
        from PySide6 import QtWidgets

        _QtLineEdit = getattr(QtWidgets, "QLineEdit", None)
        _QtMenu = getattr(QtWidgets, "QMenu", None)
        _QtToolButton = getattr(QtWidgets, "QToolButton", None)

        class _FallbackLineEdit(QWidget):
            """Provide minimal line-edit behavior when widget toolkits are unavailable."""

            def __init__(self, *_args: object, **_kwargs: object) -> None:
                """Initialize text state and Qt-like signals used by SeedBox."""

                super().__init__()
                self._text = ""
                self.textChanged = Signal(object)

            def setText(self, text: str) -> None:
                """Store text and emit the textChanged signal."""

                self._text = text
                self.textChanged.emit(text)

            def text(self) -> str:
                """Return the current text payload."""

                return self._text

            def setMinimumWidth(self, _width: int) -> None:
                """Accept minimum-width configuration without side effects."""

            def setTextMargins(
                self,
                _left: int,
                _top: int,
                _right: int,
                _bottom: int,
            ) -> None:
                """Accept text-margin configuration without side effects."""

            def blockSignals(self, _blocked: bool) -> None:
                """Accept signal-blocking calls without side effects."""

            def keyPressEvent(self, _event: object) -> None:
                """Accept forwarded key events without side effects."""

        class _FallbackMenu(QWidget):
            """Provide minimal action-menu behavior when qfluentwidgets is unavailable."""

            def __init__(self, *_args: object, **_kwargs: object) -> None:
                """Initialize empty action collection."""

                super().__init__()
                self._actions: list[object] = []

            def addAction(self, action: object) -> None:
                """Record appended action objects."""

                self._actions.append(action)

        class _FallbackSplitToolButton(QWidget):
            """Provide minimal split-button behavior when qfluentwidgets is unavailable."""

            def __init__(self, _icon: object = None, *_args: object) -> None:
                """Capture icon state and provide child parts for sizing hooks."""

                super().__init__()
                self.button = QWidget(self)
                self.dropButton = QWidget(self)
                self._icon = _icon
                self._flyout = None
                self.clicked = Signal()

            def setFlyout(self, flyout: object) -> None:
                """Store attached flyout menu payload."""

                self._flyout = flyout

            def setToolTip(self, _text: str) -> None:
                """Accept tooltip configuration without side effects."""

            def setEnabled(self, _enabled: bool) -> None:
                """Accept enabled-state configuration without side effects."""

            def setIcon(self, icon: object) -> None:
                """Store the current icon payload."""

                self._icon = icon

        LineEdit = _QtLineEdit or _FallbackLineEdit
        RoundMenu = _QtMenu or _FallbackMenu
        SplitToolButton = _QtToolButton or _FallbackSplitToolButton

        class _FallbackIcons:
            """Provide minimal icon placeholders when qfluentwidgets is unavailable."""

            PIN = object()
            UNPIN = object()

        class Action:  # type: ignore[no-redef]
            """Provide minimal Action-compatible fallback used by setup code."""

            def __init__(
                self,
                _icon: object,
                _text: str,
                _parent: object = None,
                *,
                triggered: object | None = None,
            ) -> None:
                self.triggered = triggered

        FIF = _FallbackIcons()

        def setFont(_widget: object, _font_size: int = 14, _weight: int = 50) -> None:
            """Provide no-op font helper when qfluentwidgets is unavailable."""

    else:
        try:
            from qfluentwidgets.common.font import setFont  # type: ignore[import-untyped]
        except ImportError:  # pragma: no cover - runtime fallback only

            def setFont(
                _widget: object, _font_size: int = 14, _weight: int = 50
            ) -> None:
                """Provide no-op font helper when qfluentwidgets font helpers are unavailable."""

        else:
            try:
                from substitute.presentation.widgets.menu_model import (
                    MenuItem,
                    MenuModel,
                )
                from substitute.presentation.widgets.qfluent_menu_renderer import (
                    QFluentMenuRenderer,
                )
            except ImportError:
                pass

        SplitToolButton = ToggleSplitToolButton


SEED_CONTROL_HEIGHT = 33
SEED_PREFERRED_WIDTH = 192
SEED_SHRINKABLE_MINIMUM_WIDTH = 60


def _app_seed_icon(member_name: str, fallback_icon: object) -> object:
    """Return an app-owned seed icon when the icon layer is available."""

    try:
        from substitute.presentation.resources.app_icon import AppIcon
    except (AttributeError, ImportError):  # pragma: no cover - fallback import path
        return fallback_icon
    return getattr(AppIcon, member_name, fallback_icon)


_RANDOM_SEED_ICON = _app_seed_icon("GAME_DIE_HIGH_CONTRAST", FIF.UNPIN)
_FIXED_SEED_ICON = _app_seed_icon("LOCKED_HIGH_CONTRAST", FIF.PIN)


def _qt_constant(attr_name: str, fallback: int) -> int:
    """Resolve Qt constants across enum styles and basic test doubles."""

    enum_owner = getattr(Qt, "Key", Qt)
    enum_value = getattr(enum_owner, attr_name, None)
    if enum_value is None:
        enum_value = getattr(Qt, attr_name, None)
    if enum_value is None:
        return fallback
    try:
        return int(enum_value)
    except TypeError:
        return fallback


def _fixed_policy() -> QSizePolicy.Policy:
    """Resolve fixed policy enum across Qt versions and stub doubles."""

    enum_owner = getattr(QSizePolicy, "Policy", None)
    if enum_owner is not None:
        fixed_policy = getattr(enum_owner, "Fixed", None)
        if fixed_policy is not None:
            return cast(QSizePolicy.Policy, fixed_policy)

    fallback_policy = getattr(QSizePolicy, "Fixed", None)
    if fallback_policy is None:
        return QSizePolicy.Policy.Preferred
    return cast(QSizePolicy.Policy, fallback_policy)


def _maximum_policy() -> QSizePolicy.Policy:
    """Resolve maximum policy enum across Qt versions and stub doubles."""

    enum_owner = getattr(QSizePolicy, "Policy", None)
    if enum_owner is not None:
        maximum_policy = getattr(enum_owner, "Maximum", None)
        if maximum_policy is not None:
            return cast(QSizePolicy.Policy, maximum_policy)

    fallback_policy = getattr(QSizePolicy, "Maximum", None)
    if fallback_policy is None:
        return QSizePolicy.Policy.Preferred
    return cast(QSizePolicy.Policy, fallback_policy)


def _set_strong_focus_policy(widget: object) -> None:
    """Disable focus-by-wheel when Qt focus policy APIs are available."""

    set_focus_policy = getattr(widget, "setFocusPolicy", None)
    if not callable(set_focus_policy):
        return
    focus_policy = getattr(getattr(Qt, "FocusPolicy", None), "StrongFocus", None)
    if focus_policy is not None and callable(set_focus_policy):
        set_focus_policy(focus_policy)


def _seed_mode_menu(
    parent: QWidget,
    *,
    random_callback: object,
    fixed_callback: object,
) -> tuple[object, object, object]:
    """Return the seed mode menu and its two executable actions."""

    try:
        menu = QFluentMenuRenderer(parent=parent).render(
            MenuModel(
                entries=(
                    MenuItem(
                        "seed.randomize",
                        app_text("Randomize"),
                        callback=cast(Any, random_callback),
                        icon=_RANDOM_SEED_ICON,
                    ),
                    MenuItem(
                        "seed.use_current",
                        app_text("Use Current"),
                        callback=cast(Any, fixed_callback),
                        icon=_FIXED_SEED_ICON,
                    ),
                )
            )
        )
    except NameError:
        pass
    else:
        return (
            menu,
            _rendered_seed_action(menu, "seed.randomize"),
            _rendered_seed_action(menu, "seed.use_current"),
        )

    menu = cast(Any, RoundMenu(parent=parent))
    random_action = Action(
        _RANDOM_SEED_ICON,
        translate_application_text("Randomize"),
        parent,
        triggered=random_callback,
    )
    fixed_action = Action(
        _FIXED_SEED_ICON,
        translate_application_text("Use Current"),
        parent,
        triggered=fixed_callback,
    )
    menu.addAction(random_action)
    menu.addAction(fixed_action)
    return menu, random_action, fixed_action


def _rendered_seed_action(menu: object, action_id: str) -> object:
    """Return one renderer-created seed action by stable id."""

    menu_actions = getattr(menu, "menuActions", None)
    if callable(menu_actions):
        for action in menu_actions():
            action_property = getattr(action, "property", None)
            if (
                callable(action_property)
                and action_property("menuActionId") == action_id
            ):
                return action
    raise RuntimeError(f"Seed mode menu action was not rendered: {action_id}")


class SeedBox(QWidget):
    """Render and manage seed values with fixed/random mode controls."""

    valueChanged = Signal(object)
    modeChanged = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        minimum: int | None = None,
        maximum: int | None = None,
        step: int = 1,
        allow_negative: bool = True,
    ) -> None:
        """Initialize line-edit and split-button controls for seed entry."""

        super().__init__(parent)
        _set_strong_focus_policy(self)
        self._minimum: int | None = minimum
        self._maximum: int | None = maximum
        self._step = max(1, int(step or 1))
        self._allow_negative = allow_negative
        self._mode = "random"
        self._last_value: int | None = None

        self.line_edit = cast(Any, LineEdit(self))
        _set_strong_focus_policy(self.line_edit)
        self.line_edit.setText("0")
        self.line_edit.setFixedHeight(SEED_CONTROL_HEIGHT)
        setFont(self.line_edit, 14)
        self.line_edit.textChanged.connect(self._on_text_changed)
        self._on_text_changed(self.line_edit.text())

        self.menu, self.random_action, self.fixed_action = _seed_mode_menu(
            self,
            random_callback=self._set_random_mode,
            fixed_callback=self._set_fixed_mode,
        )

        self.split_button = cast(Any, SplitToolButton(_RANDOM_SEED_ICON, self))
        if hasattr(self.split_button, "setFlyout"):
            self.split_button.setFlyout(self.menu)
        set_localized_tooltip(self.split_button, "Seed options")
        self.split_button.setEnabled(True)
        self._connect_primary_button()

        main_width = 40
        arrow_width = 18
        split_total = main_width + arrow_width
        self._set_part_width(self.split_button, "button", main_width)
        self._set_part_width(self.split_button, "dropButton", arrow_width)
        self.split_button.setFixedWidth(split_total)

        desired_height = self.line_edit.height()
        self.split_button.setFixedHeight(desired_height)
        self._set_part_height(self.split_button, "button", desired_height)
        self._set_part_height(self.split_button, "dropButton", desired_height)

        icon_part_width = 28
        arrow_part_width = 18
        split_button_total = icon_part_width + arrow_part_width
        self._configure_button_part(self.split_button, "button", icon_part_width)
        self._configure_button_part(self.split_button, "dropButton", arrow_part_width)
        self.split_button.setFixedWidth(split_button_total)
        self.split_button.setMinimumWidth(split_button_total)
        self.split_button.setMaximumWidth(split_button_total)

        total_width = SEED_PREFERRED_WIDTH
        self.line_edit.move(0, 0)
        self.resize(total_width, self.line_edit.height())
        self.restore_size_contract()
        self.split_button.raise_()

    def restore_size_contract(self) -> None:
        """Reassert SeedBox-owned sizing after a surrounding surface reuses it."""

        set_size_policy = getattr(self, "setSizePolicy", None)
        if callable(set_size_policy):
            set_size_policy(_maximum_policy(), _fixed_policy())
        self.setFixedHeight(SEED_CONTROL_HEIGHT)
        self.line_edit.setFixedHeight(SEED_CONTROL_HEIGHT)
        self.split_button.setFixedHeight(SEED_CONTROL_HEIGHT)
        self._set_part_height(self.split_button, "button", SEED_CONTROL_HEIGHT)
        self._set_part_height(self.split_button, "dropButton", SEED_CONTROL_HEIGHT)
        self._sync_child_geometry()
        update_geometry = getattr(self, "updateGeometry", None)
        if callable(update_geometry):
            update_geometry()

    def _connect_primary_button(self) -> None:
        """Connect the split-button primary click to fixed/random toggling."""

        primary_button = getattr(self.split_button, "button", self.split_button)
        clicked_signal = getattr(primary_button, "clicked", None)
        if clicked_signal is not None and hasattr(clicked_signal, "connect"):
            clicked_signal.connect(self._toggle_mode)

    @staticmethod
    def _set_part_width(split_button: object, part_name: str, width: int) -> None:
        """Set width for split-button parts when the part exists."""

        part = getattr(split_button, part_name, None)
        if part is not None and hasattr(part, "setFixedWidth"):
            part.setFixedWidth(width)

    @staticmethod
    def _set_part_height(split_button: object, part_name: str, height: int) -> None:
        """Set height for split-button parts when the part exists."""

        part = getattr(split_button, part_name, None)
        if part is not None and hasattr(part, "setFixedHeight"):
            part.setFixedHeight(height)

    @staticmethod
    def _configure_button_part(
        split_button: object, part_name: str, width: int
    ) -> None:
        """Apply fixed sizing policies to split-button child parts."""

        part = getattr(split_button, part_name, None)
        if part is None:
            return
        if hasattr(part, "setFixedWidth"):
            part.setFixedWidth(width)
        if hasattr(part, "setMinimumWidth"):
            part.setMinimumWidth(width)
        if hasattr(part, "setMaximumWidth"):
            part.setMaximumWidth(width)
        if hasattr(part, "setSizePolicy"):
            fixed_policy = _fixed_policy()
            part.setSizePolicy(fixed_policy, fixed_policy)

    def _position_split_button(self) -> None:
        """Place split-button at the right edge of line edit."""

        x_pos = max(0, self.line_edit.width() - self.split_button.width())
        self.split_button.move(x_pos, 0)

    def _sync_child_geometry(self, width: int | None = None) -> None:
        """Resize child controls to the width assigned by the parent layout."""

        effective_width = self.width() if width is None else max(0, int(width))
        self.line_edit.setFixedWidth(effective_width)
        self._position_split_button()
        right_margin = min(self.split_button.width() - 8, max(0, effective_width - 8))
        self.line_edit.setTextMargins(0, 0, right_margin, 0)

    def sizeHint(self) -> QSize:
        """Return combo-like preferred geometry without forcing a fixed width."""

        return QSize(SEED_PREFERRED_WIDTH, self.line_edit.height())

    def minimumSizeHint(self) -> QSize:
        """Return a compact minimum that lets constrained rows elide seed text."""

        return QSize(SEED_SHRINKABLE_MINIMUM_WIDTH, self.height())

    def resizeEvent(self, event: object) -> None:
        """Keep overlay layout synchronized when widget width changes."""

        self._sync_child_geometry()
        if hasattr(event, "accept"):
            event.accept()

    def setMode(self, mode: str) -> None:
        """Switch seed mode between `fixed` and `random`."""

        normalized = mode.strip().lower()
        if normalized not in {"fixed", "random"}:
            raise ValueError("mode must be 'fixed' or 'random'")
        if normalized == self._mode:
            return
        if normalized == "random":
            self._set_random_mode()
            return
        self._set_fixed_mode()

    def mode(self) -> str:
        """Return current seed mode."""

        return self._mode

    def setValue(self, value: int) -> None:
        """Set seed value using integer coercion and configured bounds."""

        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = self._minimum if self._minimum is not None else 0
        clamped = self._clamp(parsed)
        previous = self.value()
        self.line_edit.setText(str(clamped))
        if previous != clamped:
            self.valueChanged.emit(clamped)

    def value(self) -> int:
        """Return current integer value, defaulting to lower bound when invalid."""

        try:
            return int(self.line_edit.text())
        except (TypeError, ValueError):
            return self._minimum if self._minimum is not None else 0

    def setMinimum(self, value: int | None) -> None:
        """Set minimum clamp value."""

        self._minimum = int(value) if value is not None else None
        self._on_text_changed(self.line_edit.text())

    def setMaximum(self, value: int | None) -> None:
        """Set maximum clamp value."""

        self._maximum = int(value) if value is not None else None
        self._on_text_changed(self.line_edit.text())

    def setRange(self, minimum: int | None, maximum: int | None) -> None:
        """Set both minimum and maximum bounds."""

        self.setMinimum(minimum)
        self.setMaximum(maximum)

    def setSingleStep(self, value: int) -> None:
        """Set keyboard and wheel increment size."""

        self._step = max(1, int(value or 1))

    def setAllowNegative(self, allow_negative: bool) -> None:
        """Allow or disallow negative textual values."""

        self._allow_negative = allow_negative
        self._on_text_changed(self.line_edit.text())

    def minimum(self) -> int | None:
        """Return minimum clamp value."""

        return self._minimum

    def maximum(self) -> int | None:
        """Return maximum clamp value."""

        return self._maximum

    def singleStep(self) -> int:
        """Return current increment step."""

        return self._step

    def _set_random_mode(self) -> None:
        """Set random mode and show the random seed icon."""

        self._mode = "random"
        self._set_mode_icon(_RANDOM_SEED_ICON)
        self.modeChanged.emit("random")

    def _set_fixed_mode(self) -> None:
        """Set fixed mode and show the fixed seed icon."""

        self._mode = "fixed"
        self._set_mode_icon(_FIXED_SEED_ICON)
        self.modeChanged.emit("fixed")

    def _set_mode_icon(self, icon: object) -> None:
        """Apply mode icon when split-button supports icon updates."""

        if hasattr(self.split_button, "setIcon"):
            self.split_button.setIcon(icon)

    def _toggle_mode(self) -> None:
        """Toggle between random and fixed modes."""

        if self._mode == "random":
            self._set_fixed_mode()
            return
        self._set_random_mode()

    def _clamp(self, value: int) -> int:
        """Clamp value against configured optional bounds."""

        if self._minimum is not None and value < self._minimum:
            return self._minimum
        if self._maximum is not None and value > self._maximum:
            return self._maximum
        return int(value)

    def _on_text_changed(self, text: str) -> None:
        """Sanitize text, clamp numeric value, and emit change deltas."""

        filtered = self._filter_numeric(text)
        if text != filtered:
            self.line_edit.blockSignals(True)
            self.line_edit.setText(filtered)
            self.line_edit.blockSignals(False)

        try:
            value = int(filtered)
        except (TypeError, ValueError):
            value = self._minimum if self._minimum is not None else 0
        clamped = self._clamp(value)
        if str(clamped) != filtered:
            self.line_edit.blockSignals(True)
            self.line_edit.setText(str(clamped))
            self.line_edit.blockSignals(False)

        if self._last_value == clamped:
            return
        self._last_value = clamped
        self.valueChanged.emit(clamped)

    def _filter_numeric(self, text: str) -> str:
        """Keep optional minus and digits, preserving empty semantics."""

        stripped = text.strip()
        if not stripped:
            if self._minimum is not None and self._minimum >= 0:
                return "0"
            return ""
        if self._allow_negative:
            if stripped.startswith("-"):
                return "-" + "".join(
                    character for character in stripped[1:] if character.isdigit()
                )
            return "".join(character for character in stripped if character.isdigit())
        return "".join(character for character in stripped if character.isdigit())

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Step seed value for Up/Down keys and forward others to line edit."""

        key_up = _qt_constant("Key_Up", 16777235)
        key_down = _qt_constant("Key_Down", 16777237)
        key_code = int(event.key())
        if key_code in {key_up, key_down}:
            try:
                current_value = int(self.line_edit.text())
            except (TypeError, ValueError):
                current_value = self._minimum if self._minimum is not None else 0
            delta = self._step if key_code == key_up else -self._step
            self.setValue(self._clamp(current_value + delta))
            event.accept()
            return
        self.line_edit.keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Step seed value from mouse-wheel delta and clamp to bounds."""

        if not wheel_event_is_allowed(self, event):
            event.ignore()
            return
        delta = int(event.angleDelta().y())
        try:
            current_value = int(self.line_edit.text())
        except (TypeError, ValueError):
            current_value = self._minimum if self._minimum is not None else 0
        if delta > 0:
            current_value += self._step
        elif delta < 0:
            current_value -= self._step
        self.setValue(self._clamp(current_value))
        event.accept()


__all__ = ["SeedBox"]

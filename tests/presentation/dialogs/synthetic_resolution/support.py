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

"""Verify synthetic canvas resolution dialog interaction and defaults."""

from __future__ import annotations

from typing import Protocol, cast

from PySide6.QtWidgets import QApplication


from substitute.application.workflows.synthetic_canvas_resolution_role_service import (
    SyntheticCanvasResolutionRole,
)
from substitute.domain.workflow import (
    CanvasDimensionAuthority,
    CanvasDimensions,
)
from substitute.presentation.dialogs.synthetic_canvas_resolution_dialog import (
    SyntheticCanvasResolutionDialog,
)
from substitute.presentation.editor.panel.dimension_presets import (
    DimensionPresetCatalog,
    DimensionPresetItem,
    DimensionPresetSection,
)


class _PresetSource:
    """Provide deterministic shared presets to dialog tests."""

    def __init__(self) -> None:
        """Initialize prepared state and save calls."""

        self.prepare_reasons: list[str] = []
        self.saved_global: list[tuple[int, int]] = []
        self.saved_model: list[tuple[int, int]] = []
        self.catalog = DimensionPresetCatalog(
            sections=(
                DimensionPresetSection(
                    title="Global",
                    presets=(DimensionPresetItem("Portrait", 832, 1216),),
                ),
            ),
            model_save_label="Illustrious",
        )

    def prepare_dimension_preset_catalog(self, *, reason: str) -> None:
        """Record preparation."""

        self.prepare_reasons.append(reason)

    def current_dimension_preset_catalog(self) -> DimensionPresetCatalog:
        """Return the deterministic catalog."""

        return self.catalog

    def save_current_dimensions_globally(self, width: int, height: int) -> None:
        """Record a global save."""

        self.saved_global.append((width, height))

    def save_current_dimensions_for_model(self, width: int, height: int) -> None:
        """Record a model save."""

        self.saved_model.append((width, height))


class _MenuLike(Protocol):
    """Describe the QFluent menu surface inspected by hierarchy tests."""

    _subMenus: list[_MenuLike]
    _actions: list[_ActionLike]

    def title(self) -> str:
        """Return the visible submenu title."""


class _ActionLike(Protocol):
    """Describe one enabled action exposed by the shared preset menu."""

    def isEnabled(self) -> bool:  # noqa: N802
        """Return whether the action can be triggered."""

    def text(self) -> str:
        """Return the visible action label."""

    def trigger(self) -> None:
        """Invoke the action callback."""


def _app() -> QApplication:
    """Return the process QApplication."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _activate_hidden_dialog_layout(
    dialog: SyntheticCanvasResolutionDialog,
) -> None:
    """Resolve nested widget geometry without showing a native window."""

    dialog.widget.ensurePolished()
    dialog.widget.resize(dialog.widget.sizeHint())
    for widget in (
        dialog.widget,
        dialog.form,
        dialog.form.scope_options,
    ):
        layout = widget.layout()
        if layout is not None:
            layout.activate()
    dialog.form.anchor_options.resize(dialog.form.scope_options.size())
    anchor_layout = dialog.form.anchor_options.layout()
    if anchor_layout is not None:
        anchor_layout.activate()
    _app().processEvents()


def _submenu(menu: object, title: str) -> _MenuLike:
    """Return one rendered QFluent submenu by its visible title."""

    submenus = getattr(menu, "_subMenus", ())
    return cast(
        _MenuLike,
        next(submenu for submenu in submenus if submenu.title() == title),
    )


def _enabled_action(menu: object, text: str) -> _ActionLike:
    """Return one enabled rendered action by its visible text."""

    actions = getattr(menu, "_actions", ())
    return cast(
        _ActionLike,
        next(
            action for action in actions if action.isEnabled() and action.text() == text
        ),
    )


def _role() -> SyntheticCanvasResolutionRole:
    """Build one representative Prompt by Region authority role."""

    return SyntheticCanvasResolutionRole(
        section_key="Prompt by Region",
        surface_key="@synthetic/role",
        authority=CanvasDimensionAuthority(
            dimensions=CanvasDimensions(960, 1344),
            node_names=("spatial root",),
            field_pairs=(("width", "height"),),
            convergence_node_names=("sampler",),
            structural_fingerprint="structure",
            dimension_fingerprint="dimensions",
        ),
    )

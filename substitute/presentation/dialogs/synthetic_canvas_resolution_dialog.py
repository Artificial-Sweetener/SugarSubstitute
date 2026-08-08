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

"""Collect a guarded synthetic Input-canvas resolution change request."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget
from qfluentwidgets import IndeterminateProgressBar  # type: ignore[import-untyped]

from sugarsubstitute_shared.presentation.localization import (
    app_text,
    set_localized_text,
)
from substitute.application.node_behavior import DimensionFieldPair
from substitute.application.workflows.synthetic_canvas_resolution_role_service import (
    SyntheticCanvasResolutionRole,
)
from substitute.domain.workflow import (
    SyntheticCanvasAnchor,
    SyntheticCanvasResizeRequest,
    SyntheticCanvasResizeScope,
)
from substitute.presentation.dialogs.full_window_modal import FullWindowModalBase
from substitute.presentation.dialogs.synthetic_canvas_resolution_form import (
    SyntheticCanvasResolutionForm,
)
from substitute.presentation.editor.panel.dimension_presets import (
    DimensionPresetCatalogSource,
)
from substitute.presentation.editor.panel.menus.dimension_row_actions import (
    DimensionRowBinding,
    build_dimension_context_menu,
)
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedCaptionLabel,
    LocalizedSubtitleLabel,
)

_DIALOG_WIDTH = 560
_CONTENT_SPACING = 16


class SyntheticCanvasResolutionDialog(FullWindowModalBase):
    """Present one complete, guarded synthetic canvas resize decision."""

    resizeRequested = Signal(object)
    cancellationRequested = Signal()

    def __init__(
        self,
        *,
        role: SyntheticCanvasResolutionRole,
        preset_source: DimensionPresetCatalogSource | None,
        parent: QWidget | None,
    ) -> None:
        """Build the dialog around one immutable graph-authority snapshot."""

        super().__init__(parent)
        self._role = role
        self._preset_source = preset_source
        self._busy = False
        self._allow_terminal_close = False
        self.widget.setFixedWidth(_DIALOG_WIDTH)
        self.viewLayout.setSpacing(_CONTENT_SPACING)
        self.viewLayout.setContentsMargins(24, 24, 24, 20)
        set_localized_text(self.yesButton, "Resize canvas")
        set_localized_text(self.cancelButton, "Cancel")

        self._build_header()
        self.form = SyntheticCanvasResolutionForm(
            current_dimensions=role.authority.dimensions,
            parent=self.widget,
        )
        self._dimension_binding = DimensionRowBinding(
            pair=DimensionFieldPair(
                stem="",
                width_key="width",
                height_key="height",
            ),
            width_widget=self.form.width_spin,
            height_widget=self.form.height_spin,
            width_column=self.form.width_spin,
            height_column=self.form.height_spin,
        )
        self.viewLayout.addWidget(self.form)
        self._build_status()

        self.form.stateChanged.connect(self._sync_apply_enabled)
        self.form.scopeChanged.connect(self._on_scope_changed)
        self.form.preset_menu_button.clicked.connect(self._rebuild_preset_menu)
        self._prepare_preset_menu(reason="resolution_dialog_opened")
        self._on_scope_changed(self.form.selected_scope())
        self._sync_apply_enabled()

    @property
    def role(self) -> SyntheticCanvasResolutionRole:
        """Return the authority snapshot captured when the dialog opened."""

        return self._role

    def resize_request(self) -> SyntheticCanvasResizeRequest:
        """Return the current validated dialog request."""

        return SyntheticCanvasResizeRequest(
            dimensions=self.form.dimensions(),
            scope=self.form.selected_scope(),
            anchor=self.form.selected_anchor(),
            resampling_mode=self.form.resampling_mode(),
        )

    def selected_anchor(self) -> SyntheticCanvasAnchor:
        """Return the selected anchor through the form's semantic owner."""

        return self.form.selected_anchor()

    def validate(self) -> bool:
        """Publish valid intent while keeping the modal open for async work."""

        if self._busy or not self._dimensions_changed():
            return False
        request = self.resize_request()
        self.set_busy(True)
        self.resizeRequested.emit(request)
        return False

    def set_busy(self, busy: bool) -> None:
        """Block edits while a canvas transaction is in flight."""

        self._busy = busy
        self.form.set_editing_enabled(not busy)
        self.progress_bar.setVisible(busy)
        self.cancelButton.setEnabled(True)
        self._sync_preset_menu_availability()
        self._sync_apply_enabled()

    def show_error(self, message: str) -> None:
        """Return to editable state and show one actionable localized error."""

        self.set_busy(False)
        self.error_label.setText(message)
        self.error_label.show()

    def finish_successfully(self) -> None:
        """Close after canvas and graph owners commit successfully."""

        self._allow_terminal_close = True
        self.accept()

    def finish_cancelled(self) -> None:
        """Close after an in-flight CuteCanvas request reaches cancellation."""

        self._allow_terminal_close = True
        self.reject()

    def reject(self) -> None:
        """Request cancellation without removing the blocking wash early."""

        if self._busy and not self._allow_terminal_close:
            self.cancellationRequested.emit()
            self.cancelButton.setEnabled(False)
            return
        super().reject()

    def _build_header(self) -> None:
        """Build concise title and graph-authority explanation."""

        self.viewLayout.addWidget(
            LocalizedSubtitleLabel(app_text("Change canvas resolution"), self.widget)
        )
        description = LocalizedBodyLabel(
            app_text(
                "Choose how the Input canvas and its regional masks should fit the new size."
            ),
            self.widget,
        )
        description.setWordWrap(True)
        self.viewLayout.addWidget(description)

    def _build_status(self) -> None:
        """Build inline validation/error and asynchronous progress feedback."""

        self.error_label = LocalizedCaptionLabel(
            app_text("Unable to resize canvas"), self.widget
        )
        self.error_label.setObjectName("SyntheticResolutionError")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        self.progress_bar = IndeterminateProgressBar(self.widget)
        self.progress_bar.hide()
        self.viewLayout.addWidget(self.error_label)
        self.viewLayout.addWidget(self.progress_bar)

    def _prepare_preset_menu(self, *, reason: str) -> None:
        """Prepare preset data before rendering the existing dimension menu."""

        source = self._preset_source
        if source is not None:
            source.prepare_dimension_preset_catalog(reason=reason)
        self._rebuild_preset_menu()

    def _rebuild_preset_menu(self) -> None:
        """Attach the existing dimension-row menu to the modal trigger unchanged."""

        menu = build_dimension_context_menu(
            source_widget=self.form.preset_menu_button,
            binding=self._dimension_binding,
            anchor_side=None,
            dimension_preset_source=self._preset_source,
            include_swap=False,
        )
        self.form.set_preset_menu(menu)
        self._preset_menu = menu
        self._sync_preset_menu_availability()

    def _sync_preset_menu_availability(self) -> None:
        """Restore preset-menu availability after busy transitions."""

        self.form.set_preset_menu_enabled(not self._busy)

    def _on_scope_changed(self, scope: SyntheticCanvasResizeScope) -> None:
        """Update the terminal action label for the selected operation."""

        if scope is SyntheticCanvasResizeScope.CANVAS_ONLY:
            set_localized_text(self.yesButton, "Resize canvas")
        else:
            set_localized_text(self.yesButton, "Scale canvas and masks")

    def _sync_apply_enabled(self) -> None:
        """Enable applying only for a valid, changed, idle target size."""

        self.yesButton.setEnabled(not self._busy and self._dimensions_changed())

    def _dimensions_changed(self) -> bool:
        """Return whether the target size differs from the authority snapshot."""

        return self.form.dimensions() != self._role.authority.dimensions


__all__ = ["SyntheticCanvasResolutionDialog"]

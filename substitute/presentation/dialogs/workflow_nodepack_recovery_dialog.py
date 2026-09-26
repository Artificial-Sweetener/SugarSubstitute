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

"""Present missing workflow nodepacks as an explicit non-blocking review."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import FluentIcon  # type: ignore[import-untyped]

from sugarsubstitute_shared.presentation.localization import app_text

from substitute.application.comfy_nodepacks.workflow_dependency_resolution import (
    WorkflowNodepackInstallCandidate,
    WorkflowNodepackSourceKind,
)
from substitute.application.comfy_nodepacks.workflow_nodepack_recovery_plan import (
    WorkflowNodepackRecoveryPlan,
)
from substitute.presentation.dialogs.full_window_modal import FullWindowModalBase
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedCaptionLabel,
    LocalizedPrimaryPushButton,
    LocalizedPushButton,
    LocalizedSubtitleLabel,
)
from substitute.presentation.shell.chrome_style import (
    connect_theme_refresh,
    winui_card_border_color,
    winui_card_fill_color,
)

_DIALOG_WIDTH = 700
_DIALOG_MINIMUM_HEIGHT = 420
_ACTION_BUTTON_HEIGHT = 34


class WorkflowNodepackRecoveryDialog(FullWindowModalBase):
    """Review package matches and unresolved classes before acquisition."""

    def __init__(
        self,
        plan: WorkflowNodepackRecoveryPlan,
        *,
        parent: object | None = None,
    ) -> None:
        """Build a deterministic review from one authoritative recovery plan."""

        super().__init__(parent)
        self._plan = plan
        self._install_selected = False
        self._rows: list[QFrame] = []
        self.setClosableOnMaskClicked(False)
        self.setModal(True)
        self.hideYesButton()
        self.hideCancelButton()
        self.widget.setMinimumSize(_DIALOG_WIDTH, _DIALOG_MINIMUM_HEIGHT)
        self.widget.setMaximumWidth(_DIALOG_WIDTH)
        self._build_header()
        self._build_review()
        self._build_actions()
        self._apply_theme()
        connect_theme_refresh(self, self._apply_theme)

    @property
    def install_selected(self) -> bool:
        """Return whether the user explicitly approved all shown candidates."""

        return self._install_selected

    @property
    def candidates(self) -> tuple[WorkflowNodepackInstallCandidate, ...]:
        """Return the exact packages represented by the install action."""

        return self._plan.resolution.candidates

    def _build_header(self) -> None:
        """Create the review title and install guidance."""

        header = QWidget(self.widget)
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(
            LocalizedSubtitleLabel(
                app_text("Custom nodes required by this workflow"),
                header,
            )
        )
        guidance = LocalizedBodyLabel(
            app_text(
                "Review the custom node packages matched to missing workflow nodes before installing them."
            ),
            header,
        )
        guidance.setWordWrap(True)
        layout.addWidget(guidance)
        self.viewLayout.addWidget(header)

    def _build_review(self) -> None:
        """Create a scrollable list of matched packages and unresolved classes."""

        scroll = QScrollArea(self.widget)
        scroll.setObjectName("WorkflowNodepackRecoveryScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea#WorkflowNodepackRecoveryScroll { background: transparent; }"
            "QScrollArea#WorkflowNodepackRecoveryScroll > QWidget > QWidget {"
            " background: transparent; }"
        )
        host = QWidget(scroll)
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for candidate in self._plan.resolution.candidates:
            layout.addWidget(self._candidate_row(candidate, host))
        unresolved_classes = tuple(
            sorted(
                {
                    unresolved.node.class_type
                    for unresolved in self._plan.resolution.unresolved
                }
            )
        )
        if unresolved_classes:
            unresolved = LocalizedBodyLabel(
                app_text(
                    "No trusted package match was found for: %1",
                    ", ".join(unresolved_classes),
                ),
                host,
            )
            unresolved.setObjectName("WorkflowNodepackUnresolvedClasses")
            unresolved.setWordWrap(True)
            layout.addWidget(unresolved)
        layout.addStretch(1)
        scroll.setWidget(host)
        self.viewLayout.addWidget(scroll, 1)

    def _candidate_row(
        self,
        candidate: WorkflowNodepackInstallCandidate,
        parent: QWidget,
    ) -> QFrame:
        """Build one package row with exact classes and acquisition authority."""

        row = QFrame(parent)
        row.setObjectName("WorkflowNodepackCandidateRow")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(3)
        name = LocalizedBodyLabel(candidate.nodepack.display_name, row)
        name.setObjectName("WorkflowNodepackCandidateName")
        layout.addWidget(name)
        classes = LocalizedCaptionLabel(
            app_text("Provides: %1", ", ".join(candidate.class_types)),
            row,
        )
        classes.setWordWrap(True)
        layout.addWidget(classes)
        source_label = (
            app_text("Source: Comfy Registry")
            if candidate.nodepack.source_kind is WorkflowNodepackSourceKind.REGISTRY
            else app_text("Source: ComfyUI-Manager catalog")
        )
        layout.addWidget(LocalizedCaptionLabel(source_label, row))
        if candidate.nodepack.version is not None:
            version_label = (
                app_text("Version: %1", candidate.nodepack.version)
                if candidate.nodepack.source_kind is WorkflowNodepackSourceKind.REGISTRY
                else app_text("Revision: %1", candidate.nodepack.version)
            )
            version = LocalizedCaptionLabel(version_label, row)
            version.setWordWrap(True)
            layout.addWidget(version)
        self._rows.append(row)
        return row

    def _build_actions(self) -> None:
        """Create stable cancellation and explicit aggregate install actions."""

        self.buttonGroup.show()
        self.buttonGroup.setFixedHeight(70)
        _clear_layout(self.buttonLayout)
        self.buttonLayout.setContentsMargins(24, 17, 24, 17)
        self.buttonLayout.setSpacing(12)
        self.buttonLayout.addStretch(1)
        self.cancel_action = LocalizedPushButton(app_text("Cancel"), self.buttonGroup)
        self.cancel_action.setFixedHeight(_ACTION_BUTTON_HEIGHT)
        self.cancel_action.clicked.connect(self.reject)
        self.buttonLayout.addWidget(self.cancel_action)
        self.install_action = LocalizedPrimaryPushButton(
            app_text(
                "Install %1 custom node packages",
                len(self._plan.resolution.candidates),
            ),
            self.buttonGroup,
        )
        self.install_action.setObjectName("WorkflowNodepackInstallAction")
        self.install_action.setIcon(FluentIcon.DOWNLOAD)
        self.install_action.setFixedHeight(_ACTION_BUTTON_HEIGHT)
        self.install_action.setEnabled(bool(self._plan.resolution.candidates))
        self.install_action.clicked.connect(self._accept_install)
        self.buttonLayout.addWidget(self.install_action)

    def _accept_install(self) -> None:
        """Accept only when the review contains at least one install candidate."""

        if not self.install_action.isEnabled():
            return
        self._install_selected = True
        QDialog.accept(self)

    def _apply_theme(self) -> None:
        """Refresh candidate cards from the application theme tokens."""

        fill = _rgba_string(winui_card_fill_color())
        border = _rgba_string(winui_card_border_color())
        style = (
            "QFrame#WorkflowNodepackCandidateRow {"
            f"background: {fill};"
            f"border: 1px solid {border};"
            "border-radius: 8px;"
            "}"
        )
        for row in self._rows:
            row.setStyleSheet(style)


class WorkflowNodepackRecoveryPresenter:
    """Own non-blocking review dialogs until their Qt completion signal fires."""

    def __init__(
        self,
        *,
        parent: object | None,
        dialog_factory: Callable[..., WorkflowNodepackRecoveryDialog] | None = None,
    ) -> None:
        """Store the modal owner and optional deterministic dialog factory."""

        self._parent = parent
        self._dialog_factory = dialog_factory or WorkflowNodepackRecoveryDialog
        self._active: set[WorkflowNodepackRecoveryDialog] = set()

    def present(
        self,
        plan: WorkflowNodepackRecoveryPlan,
        approved: Callable[[tuple[WorkflowNodepackInstallCandidate, ...]], None],
        cancelled: Callable[[], None],
    ) -> None:
        """Open one review without entering a nested Qt event loop."""

        dialog = self._dialog_factory(plan, parent=self._parent)
        self._active.add(dialog)

        def finished(result: int) -> None:
            """Dispatch the explicit selection and release dialog ownership."""

            self._active.discard(dialog)
            try:
                if (
                    result == int(QDialog.DialogCode.Accepted)
                    and dialog.install_selected
                ):
                    approved(dialog.candidates)
                else:
                    cancelled()
            finally:
                dialog.deleteLater()

        dialog.finished.connect(finished)
        dialog.open()

    def close(self) -> None:
        """Reject and release every active review during shell teardown."""

        for dialog in tuple(self._active):
            dialog.reject()


def _clear_layout(layout: QLayout) -> None:
    """Remove default qfluent footer widgets before custom action placement."""

    while layout.count():
        item = layout.takeAt(0)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)


def _rgba_string(color: tuple[int, int, int, int]) -> str:
    """Return one Qt stylesheet RGBA value."""

    red, green, blue, alpha = color
    return f"rgba({red}, {green}, {blue}, {alpha})"


__all__ = [
    "WorkflowNodepackRecoveryDialog",
    "WorkflowNodepackRecoveryPresenter",
]

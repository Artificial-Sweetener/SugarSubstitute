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

"""Present repair stages and recovery actions using the shared Fluent controls."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QAbstractAnimation, QPropertyAnimation, Signal
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    CaptionLabel,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    SubtitleLabel,
)

from launcher.sugarsubstitute_launcher.localized_text import launcher_text
from sugarsubstitute_shared.presentation.installer_surface import expose_native_material


class RepairProgressView(QWidget):
    """Keep repair status primary and diagnostics available on request."""

    primary_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build a stage view whose progress advances only when its owner reports work."""
        super().__init__(parent)
        expose_native_material(self)
        self._title = cast(
            QLabel, SubtitleLabel(launcher_text("Repairing SugarSubstitute"), self)
        )
        self._description = cast(
            QLabel,
            BodyLabel(launcher_text("Repair keeps your files and models."), self),
        )
        self._description.setWordWrap(True)
        self._stage = cast(QLabel, BodyLabel(self))
        self._stage.setObjectName("RepairStage")
        self._stage.setWordWrap(True)
        self._step = cast(QLabel, CaptionLabel(self))
        self._bar = cast(QProgressBar, ProgressBar(self))
        self._bar.setObjectName("RepairProgress")
        self._bar.setRange(0, 100)
        self._bar.setFixedHeight(6)
        self._bar.setValue(0)
        self._opacity = QGraphicsOpacityEffect(self._bar)
        self._opacity.setOpacity(1.0)
        self._bar.setGraphicsEffect(self._opacity)
        self._pulse = QPropertyAnimation(self._opacity, b"opacity", self)
        self._pulse.setDuration(450)
        self._pulse.setStartValue(1.0)
        self._pulse.setKeyValueAt(0.5, 0.55)
        self._pulse.setEndValue(1.0)
        self._details_button = cast(
            QPushButton, PushButton(launcher_text("Details"), self)
        )
        self._details_button.setObjectName("RepairDetailsToggle")
        self._details_button.setCheckable(True)
        self._details = QPlainTextEdit(self)
        self._details.setReadOnly(True)
        self._details.setMinimumHeight(150)
        self._details.hide()
        self._details_button.toggled.connect(self._details.setVisible)
        self._primary = cast(QPushButton, PrimaryPushButton(self))
        self._primary.setObjectName("RepairPrimaryAction")
        self._primary.clicked.connect(self.primary_requested)
        self._primary.hide()
        self._close = cast(
            QPushButton, PushButton(launcher_text("Close when finished"), self)
        )
        self._close.clicked.connect(self.close_requested)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(18)
        layout.addWidget(self._title)
        layout.addWidget(self._description)
        layout.addSpacing(16)
        stage_row = QHBoxLayout()
        stage_row.addWidget(self._stage, 1)
        stage_row.addWidget(self._step)
        layout.addLayout(stage_row)
        layout.addWidget(self._bar)
        layout.addWidget(self._details)
        layout.addStretch(1)
        actions = QHBoxLayout()
        actions.addWidget(self._details_button)
        actions.addStretch(1)
        actions.addWidget(self._close)
        actions.addWidget(self._primary)
        layout.addLayout(actions)

    def set_stage(self, title: str, *, completed: int, total: int) -> None:
        """Render completed work without manufacturing elapsed-time progress."""
        if total <= 0 or completed < 0 or completed >= total:
            raise ValueError(
                "Active repair progress requires an unfinished valid step."
            )
        self._stage.setText(title)
        self._step.setText(launcher_text("Step %1 of %2", completed + 1, total))
        self._bar.setValue(round(100 * completed / total))

    def begin_attempt(self) -> None:
        """Reset terminal actions before the controller starts a fresh repair attempt."""
        self._title.setText(launcher_text("Repairing SugarSubstitute"))
        self._description.setText(launcher_text("Repair keeps your files and models."))
        self._stage.setText(launcher_text("Checking repair files"))
        self._step.clear()
        self._bar.setValue(0)
        self._primary.hide()
        self._close.setText(launcher_text("Close when finished"))
        self._close.setEnabled(True)
        self._details.clear()

    def pulse_activity(self) -> None:
        """Pulse the Fluent bar when the producer reports real activity."""
        if self._pulse.state() is not QAbstractAnimation.State.Running:
            self._pulse.start()

    def set_details(self, details: str) -> None:
        """Update optional diagnostics without opening or moving the details pane."""
        self._details.setPlainText(details)

    def set_close_pending(self) -> None:
        """Acknowledge deferred close while keeping ongoing repair visible."""
        self._description.setText(
            launcher_text("This window will close when repair finishes.")
        )
        self._close.setEnabled(False)

    def show_result(self, *, succeeded: bool, details: str = "") -> None:
        """Present an explicit next action after execution reaches a terminal state."""
        self._pulse.stop()
        self._opacity.setOpacity(1.0)
        self._stage.clear()
        self._step.clear()
        self._close.setText(launcher_text("Close"))
        self._close.setEnabled(True)
        self._primary.show()
        if succeeded:
            self._bar.setValue(100)
            self._title.setText(launcher_text("Repair complete"))
            self._description.setText(
                launcher_text("SugarSubstitute is ready to open.")
            )
            self._primary.setText(launcher_text("Open SugarSubstitute"))
        else:
            self._title.setText(launcher_text("Repair needs attention"))
            self._description.setText(
                launcher_text("Review the details, then try the repair again.")
            )
            self._primary.setText(launcher_text("Try again"))
        self.set_details(details)

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

"""Present the live setup transcript without reflowing installer progress."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QWidget

from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.terminal import (
    TerminalOutputStream,
    TerminalOutputView,
)
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedCaptionLabel,
    LocalizedPushButton,
)
from sugarsubstitute_shared.presentation.localization import set_localized_window_title


class SetupLogDialog(QDialog):
    """Show a bounded, copyable live setup log in a dedicated window."""

    def __init__(
        self,
        *,
        stream: TerminalOutputStream,
        parent: QWidget,
    ) -> None:
        """Build the stable transcript surface and bind its process-lifetime stream."""

        super().__init__(parent)
        self.setObjectName("OnboardingSetupLogDialog")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        set_localized_window_title(self, "Setup log")
        self.resize(860, 520)
        self.setMinimumSize(680, 400)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        title = LocalizedBodyLabel(app_text("Setup log"), self)
        title.setObjectName("OnboardingDialogTitle")
        layout.addWidget(title)
        description = LocalizedCaptionLabel(
            app_text("Technical setup details update here while the installer works."),
            self,
        )
        description.setObjectName("OnboardingInfoDescription")
        description.setWordWrap(True)
        layout.addWidget(description)
        self.output_view = TerminalOutputView(self, min_height=320, max_height=1200)
        self.output_view.set_stream(stream)
        layout.addWidget(self.output_view, 1)
        actions = QHBoxLayout()
        actions.addStretch(1)
        close_button = LocalizedPushButton(app_text("Close"), self)
        close_button.clicked.connect(self.close)
        actions.addWidget(close_button)
        layout.addLayout(actions)

    def present(self) -> None:
        """Show and focus the existing live transcript surface."""

        host_window = self.parentWidget()
        if host_window is not None:
            root = host_window.window().findChild(QWidget, "OnboardingRoot")
            if root is not None:
                self.setFont(root.font())
                self.setStyleSheet(root.styleSheet())
        self.show()
        self.raise_()
        self.activateWindow()


__all__ = ["SetupLogDialog"]

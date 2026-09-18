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

"""Own splash feedback composition and its deferred Fluent enrichment."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget
from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)
from sugarsubstitute_shared.presentation.terminal.output_style import (
    TerminalOutputAppearance,
)
from sugarsubstitute_shared.presentation.terminal.output_view import TerminalOutputView

if TYPE_CHECKING:
    from sugarsubstitute_shared.launch_splash.activity import SplashActivity
    from sugarsubstitute_shared.launch_splash.progress import SplashProgress
    from substitute.presentation.shell.splash_activity_presenter import (
        SplashActivityPresenter,
    )
    from substitute.presentation.shell.splash_progress_panel import SplashProgressPanel


class SplashFeedback(QWidget):
    """Compose diagnostics, operation activity and completion under one lifetime."""

    detailsVisibilityChanged = Signal(bool)

    def __init__(
        self,
        *,
        parent: QWidget,
        dark_theme: bool,
        accent_color: str,
        activity_clock: Callable[[], float],
    ) -> None:
        """Prepare lightweight diagnostics before the first native splash frame."""
        super().__init__(parent)
        self._clock = activity_clock
        self._panel: SplashProgressPanel | None = None
        self._presenter: SplashActivityPresenter | None = None
        self._stream = TerminalOutputStream(max_lines=2000)
        self._terminal = TerminalOutputView(
            self,
            appearance=TerminalOutputAppearance.from_color(
                dark_theme=dark_theme, accent_color=accent_color
            ),
            use_qfluent_chrome=False,
            observe_qfluent_theme=False,
        )
        self._terminal.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._terminal.set_stream(self._stream)
        self.log_view = self._terminal.log_view
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.addWidget(self._terminal)
        self._terminal.hide()

    def enrich(self) -> None:
        """Mount Fluent controls once the window permits heavier presentation imports."""
        if self._panel is not None:
            return
        from substitute.presentation.shell.splash_activity_presenter import (
            SplashActivityPresenter,
        )
        from substitute.presentation.shell.splash_progress_panel import (
            SplashProgressPanel,
        )

        self._layout.removeWidget(self._terminal)
        self._panel = SplashProgressPanel(details=self._terminal, parent=self)
        self._layout.addWidget(self._panel)
        self._panel.detailsVisibilityChanged.connect(self.detailsVisibilityChanged)
        self._presenter = SplashActivityPresenter(
            stream=self._stream, parent=self, clock=self._clock
        )
        self._presenter.textChanged.connect(self._panel.set_activity_status)

    def append_log(self, line: str) -> None:
        """Retain output while operation feedback remains independent of log volume."""
        if not line:
            return
        self._stream.append_line(line)
        if self._panel is not None:
            from substitute.application.comfy_startup_status import (
                describe_comfy_startup_output,
            )
            from sugarsubstitute_shared.presentation.localization import (
                render_application_text,
            )

            self._panel.record_activity()
            status = describe_comfy_startup_output(line)
            if status is not None:
                assert self._presenter is not None
                self._presenter.set_detail(render_application_text(status))
        if self._presenter is not None:
            self._presenter.restore_after_log(line)

    def set_progress(self, progress: SplashProgress, *, status: str) -> None:
        """Forward producer-owned units into the mounted completion panel."""
        self.enrich()
        assert self._panel is not None
        assert self._presenter is not None
        self._presenter.clear_detail()
        self._panel.set_progress(progress, status=status)

    def start_activity(self, activity: SplashActivity) -> None:
        """Start the operation presenter shared by status and diagnostics."""
        self.enrich()
        assert self._presenter is not None
        self._presenter.start(activity)

    def clear_activity(self) -> None:
        """Remove operation feedback while retaining completion and durable output."""
        if self._presenter is not None:
            self._presenter.clear()

    def show_failure(self, message: str) -> None:
        """End operation feedback and expose the terminal failure with diagnostics."""
        self.enrich()
        assert self._panel is not None
        assert self._presenter is not None
        self._presenter.clear()
        self._presenter.shutdown()
        self.append_log(message)
        self._panel.show_failure(message)

    def shutdown(self) -> None:
        """Stop owned activity callbacks when the containing window closes."""
        if self._presenter is not None:
            self._presenter.shutdown()

    @property
    def details_visible(self) -> bool:
        """Expose the panel's authoritative disclosure state to the window layout."""
        return self._panel is not None and self._panel.details_visible

    def set_details_visible(self, visible: bool) -> None:
        """Delegate titlebar disclosure to the diagnostics panel."""
        self.enrich()
        assert self._panel is not None
        self._panel.set_details_visible(visible)

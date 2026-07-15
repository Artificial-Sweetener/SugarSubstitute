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

"""Open ComfyUI Settings in an embedded Qt web surface."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from json import dumps
from re import escape
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import QRect, Qt, QTimer, QUrl, QSize
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QWidget

try:
    from qfluentwidgets.common.style_sheet import themeColor  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - lightweight test stubs

    def themeColor() -> QColor:
        """Return a stable fallback accent for lightweight imports."""

        return QColor(_DEFAULT_COMFY_SETTINGS_ACCENT_COLOR)


from substitute.domain.onboarding import ComfyEndpoint
from substitute.shared.logging.logger import get_logger, log_info, log_warning

if TYPE_CHECKING:
    from PySide6.QtGui import QResizeEvent
    from PySide6.QtWebEngineCore import QWebEngineScript

_qt_webengine_core: Any
_qt_webengine_widgets: Any
try:
    _qt_webengine_core = import_module("PySide6.QtWebEngineCore")
    _qt_webengine_widgets = import_module("PySide6.QtWebEngineWidgets")

    WEBENGINE_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on optional Qt installation.
    _qt_webengine_core = None
    _qt_webengine_widgets = None
    WEBENGINE_AVAILABLE = False

_LOGGER = get_logger("presentation.shell.comfy_settings_webview")
COMFY_SETTINGS_DIALOG_OBJECT_NAME = "ComfySettingsWebViewDialog"
COMFY_SETTINGS_VIEW_OBJECT_NAME = "ComfySettingsWebEngineView"
COMFY_SETTINGS_LOADING_OBJECT_NAME = "ComfySettingsLoadingOverlay"
_COMFY_FRONTEND_DIALOG_MODULE_PREFIX = "dialogService-"
_LOADING_OVERLAY_RELEASE_DELAY_MS = 2200
_DEFAULT_COMFY_SETTINGS_ACCENT_COLOR = "#E91E63"


@dataclass(frozen=True)
class ComfySettingsAccentPalette:
    """Provide scoped CSS colors derived from the active Substitute accent."""

    primary: str
    hover: str
    active: str
    soft_background: str
    soft_foreground: str
    contrast: str


def comfy_settings_accent_palette(
    accent_color: QColor | None = None,
) -> ComfySettingsAccentPalette:
    """Return Comfy Settings color tokens derived from one application accent."""

    accent = QColor(themeColor()) if accent_color is None else QColor(accent_color)
    if not accent.isValid():
        accent = QColor(_DEFAULT_COMFY_SETTINGS_ACCENT_COLOR)
    accent.setAlpha(255)
    foreground_mix_target = (
        QColor("#000000") if _relative_luminance(accent) > 0.72 else QColor("#FFFFFF")
    )
    return ComfySettingsAccentPalette(
        primary=_hex_color(accent),
        hover=_hex_color(_mix_color(accent, QColor("#FFFFFF"), 0.22)),
        active=_hex_color(_mix_color(accent, QColor("#FFFFFF"), 0.38)),
        soft_background=_rgba_color(accent, 0.18),
        soft_foreground=_hex_color(_mix_color(accent, foreground_mix_target, 0.46)),
        contrast="#18181B" if _relative_luminance(accent) > 0.48 else "#FFFFFF",
    )


def _hex_color(color: QColor) -> str:
    """Return one opaque CSS hex color string."""

    normalized = QColor(color)
    normalized.setAlpha(255)
    return normalized.name().upper()


def _rgba_color(color: QColor, alpha: float) -> str:
    """Return one CSS rgba color string with a stable decimal alpha."""

    normalized_alpha = max(0.0, min(1.0, alpha))
    return (
        f"rgba({color.red()}, {color.green()}, {color.blue()}, {normalized_alpha:.2f})"
    )


def _mix_color(color: QColor, target: QColor, amount: float) -> QColor:
    """Blend one QColor toward another for dark-theme UI accents."""

    normalized_amount = max(0.0, min(1.0, amount))
    return QColor(
        round(color.red() + ((target.red() - color.red()) * normalized_amount)),
        round(color.green() + ((target.green() - color.green()) * normalized_amount)),
        round(color.blue() + ((target.blue() - color.blue()) * normalized_amount)),
    )


def _relative_luminance(color: QColor) -> float:
    """Return the WCAG relative luminance for one opaque color."""

    def channel_luminance(channel: int) -> float:
        """Return the linearized luminance contribution for one RGB channel."""

        normalized: float = float(channel) / 255.0
        if normalized <= 0.03928:
            return normalized / 12.92
        return float(((normalized + 0.055) / 1.055) ** 2.4)

    return (
        (0.2126 * channel_luminance(color.red()))
        + (0.7152 * channel_luminance(color.green()))
        + (0.0722 * channel_luminance(color.blue()))
    )


@dataclass(frozen=True)
class ComfySettingsWebViewRequest:
    """Describe one ComfyUI Settings webview load request."""

    endpoint: ComfyEndpoint

    def url(self) -> str:
        """Return the ComfyUI frontend URL used by the settings webview."""

        return f"http://{self.endpoint.host}:{self.endpoint.port}/"


class ComfySettingsWebViewDialog(QDialog):
    """Host ComfyUI Settings after Comfy completes normal frontend startup."""

    def __init__(
        self,
        request: ComfySettingsWebViewRequest,
        parent: QWidget | None = None,
    ) -> None:
        """Create and load a ComfyUI browser dialog focused on Settings."""

        if not WEBENGINE_AVAILABLE:
            raise RuntimeError("Qt WebEngine is not available in this environment.")
        super().__init__(None)
        assert _qt_webengine_core is not None
        assert _qt_webengine_widgets is not None
        self._anchor = parent
        self.setObjectName(COMFY_SETTINGS_DIALOG_OBJECT_NAME)
        self.setWindowTitle("ComfyUI Settings")
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.resize(QSize(1040, 760))
        self._request = request
        self._profile = _qt_webengine_core.QWebEngineProfile(self)
        self._install_scripts()
        self._view = _qt_webengine_widgets.QWebEngineView(self)
        self._view.setObjectName(COMFY_SETTINGS_VIEW_OBJECT_NAME)
        self._page = _qt_webengine_core.QWebEnginePage(self._profile, self._view)
        self._view.setPage(self._page)
        self._loading_overlay = QLabel("Loading ComfyUI Settings...", self)
        self._loading_overlay.setObjectName(COMFY_SETTINGS_LOADING_OBJECT_NAME)
        self._loading_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_overlay.setStyleSheet(
            """
            QLabel#ComfySettingsLoadingOverlay {
                background: #202020;
                color: #f4f4f5;
                font-size: 16px;
                font-weight: 600;
            }
            """
        )
        self._build_layout()
        self._view.loadFinished.connect(self._schedule_loading_overlay_release)
        self._view.load(QUrl(request.url()))
        self._position_over_anchor()
        log_info(
            _LOGGER,
            "Opened ComfyUI Settings webview with normal Comfy frontend startup",
            host=request.endpoint.host,
            port=request.endpoint.port,
        )

    def _install_scripts(self) -> None:
        """Inject post-startup dialog focus CSS and settings bootstrap script."""

        self._profile.scripts().insert(
            _webengine_script(
                "SugarSubstituteComfySettingsFocusCss",
                build_comfy_settings_dialog_focus_script(),
                _qt_webengine_core.QWebEngineScript.InjectionPoint.DocumentCreation,
            )
        )
        self._profile.scripts().insert(
            _webengine_script(
                "SugarSubstituteComfySettingsBootstrap",
                build_comfy_settings_bootstrap_script(),
                _qt_webengine_core.QWebEngineScript.InjectionPoint.DocumentReady,
            )
        )

    def _build_layout(self) -> None:
        """Place the WebEngine view and loading overlay in the dialog."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._view)
        self._position_loading_overlay()
        self._loading_overlay.show()
        self._loading_overlay.raise_()

    def resizeEvent(self, event: "QResizeEvent") -> None:
        """Keep the loading overlay aligned with the embedded browser."""

        super().resizeEvent(event)
        if hasattr(self, "_loading_overlay"):
            self._position_loading_overlay()

    def _position_loading_overlay(self) -> None:
        """Cover the browser with the startup mask while Comfy initializes."""

        self._loading_overlay.setGeometry(self.rect())

    def _schedule_loading_overlay_release(self, loaded: bool) -> None:
        """Hide the startup mask after Comfy has time to open Settings."""

        if not loaded:
            self._loading_overlay.setText("ComfyUI did not finish loading.")
            return
        QTimer.singleShot(_LOADING_OVERLAY_RELEASE_DELAY_MS, self._hide_loading_overlay)

    def _hide_loading_overlay(self) -> None:
        """Reveal the webview once the settings bootstrap has had a chance to run."""

        self._loading_overlay.hide()

    def _position_over_anchor(self) -> None:
        """Center the top-level WebEngine window over the main application window."""

        if self._anchor is None:
            return
        anchor_window = self._anchor.window()
        if anchor_window is None:
            return
        self.setGeometry(comfy_settings_window_geometry(anchor_window.frameGeometry()))


def open_comfy_settings_webview(
    *,
    endpoint: ComfyEndpoint,
    parent: QWidget | None,
) -> ComfySettingsWebViewDialog:
    """Open a non-modal ComfyUI Settings webview for one endpoint."""

    dialog = ComfySettingsWebViewDialog(
        ComfySettingsWebViewRequest(endpoint=endpoint),
        parent=parent,
    )
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    return dialog


def comfy_settings_window_geometry(anchor_frame: QRect) -> QRect:
    """Return a centered WebEngine window geometry for one anchor frame."""

    width = max(720, min(anchor_frame.width() - 60, 1180))
    height = max(520, min(anchor_frame.height() - 90, 820))
    geometry = QRect(0, 0, width, height)
    geometry.moveCenter(anchor_frame.center())
    return geometry


def build_comfy_settings_dialog_focus_script(
    *,
    accent_palette: ComfySettingsAccentPalette | None = None,
) -> str:
    """Return JavaScript that isolates Settings after Comfy opens the dialog."""

    palette = (
        accent_palette
        if accent_palette is not None
        else comfy_settings_accent_palette()
    )
    css = r"""
html,
body {
  overflow: hidden !important;
}

body.sugar-comfy-settings-dialog-opened {
  background: #111 !important;
}

body.sugar-comfy-settings-dialog-opened .sugar-comfy-settings-dialog-mask {
  align-items: stretch !important;
  background: #111 !important;
  backdrop-filter: none !important;
  justify-content: stretch !important;
  padding: 0 !important;
  z-index: 2147483001 !important;
}

body.sugar-comfy-settings-dialog-opened .sugar-comfy-settings-dialog-frame {
  border-radius: 0 !important;
  height: 100vh !important;
  margin: 0 !important;
  max-height: none !important;
  max-width: none !important;
  width: 100vw !important;
  z-index: 2147483002 !important;
}

body.sugar-comfy-settings-dialog-opened .sugar-comfy-settings-dialog-content {
  height: 100% !important;
  margin: 0 !important;
  max-height: none !important;
  overflow: hidden !important;
  padding: 0 !important;
  width: 100% !important;
}

body.sugar-comfy-settings-dialog-opened .sugar-comfy-settings-dialog {
  --sugar-comfy-settings-accent: __SUGAR_COMFY_SETTINGS_ACCENT__;
  --sugar-comfy-settings-accent-hover: __SUGAR_COMFY_SETTINGS_ACCENT_HOVER__;
  --sugar-comfy-settings-accent-active: __SUGAR_COMFY_SETTINGS_ACCENT_ACTIVE__;
  --sugar-comfy-settings-accent-soft: __SUGAR_COMFY_SETTINGS_ACCENT_SOFT__;
  --sugar-comfy-settings-accent-foreground: __SUGAR_COMFY_SETTINGS_ACCENT_FOREGROUND__;
  --sugar-comfy-settings-accent-contrast: __SUGAR_COMFY_SETTINGS_ACCENT_CONTRAST__;
  --p-primary-color: var(--sugar-comfy-settings-accent) !important;
  --p-primary-hover-color: var(--sugar-comfy-settings-accent-hover) !important;
  --p-primary-active-color: var(--sugar-comfy-settings-accent-active) !important;
  --p-primary-contrast-color: var(--sugar-comfy-settings-accent-contrast) !important;
  --p-primary-300: var(--sugar-comfy-settings-accent-foreground) !important;
  --p-primary-400: var(--sugar-comfy-settings-accent-hover) !important;
  --p-primary-500: var(--sugar-comfy-settings-accent) !important;
  --p-primary-600: var(--sugar-comfy-settings-accent) !important;
  --p-blue-300: var(--sugar-comfy-settings-accent-foreground) !important;
  --p-blue-400: var(--sugar-comfy-settings-accent-hover) !important;
  --p-blue-500: var(--sugar-comfy-settings-accent) !important;
  --p-blue-600: var(--sugar-comfy-settings-accent) !important;
  --p-button-primary-background: var(--sugar-comfy-settings-accent) !important;
  --p-button-primary-border-color: var(--sugar-comfy-settings-accent) !important;
  --p-button-primary-color: var(--sugar-comfy-settings-accent-contrast) !important;
  --p-button-primary-focus-ring-color: var(--sugar-comfy-settings-accent) !important;
  --p-button-primary-hover-background: var(--sugar-comfy-settings-accent-hover) !important;
  --p-button-primary-hover-border-color: var(--sugar-comfy-settings-accent-hover) !important;
  --p-button-primary-hover-color: var(--sugar-comfy-settings-accent-contrast) !important;
  --p-button-primary-active-background: var(--sugar-comfy-settings-accent-active) !important;
  --p-button-primary-active-border-color: var(--sugar-comfy-settings-accent-active) !important;
  --p-button-primary-active-color: var(--sugar-comfy-settings-accent-contrast) !important;
  --p-button-outlined-primary-color: var(--sugar-comfy-settings-accent-foreground) !important;
  --p-button-outlined-primary-border-color: var(--sugar-comfy-settings-accent) !important;
  --p-button-outlined-primary-hover-background: var(--sugar-comfy-settings-accent-soft) !important;
  --p-button-text-primary-color: var(--sugar-comfy-settings-accent-foreground) !important;
  --p-button-text-primary-hover-background: var(--sugar-comfy-settings-accent-soft) !important;
  --p-tag-primary-background: var(--sugar-comfy-settings-accent-soft) !important;
  --p-tag-primary-color: var(--sugar-comfy-settings-accent-foreground) !important;
  --p-radiobutton-checked-background: var(--sugar-comfy-settings-accent) !important;
  --p-radiobutton-checked-border-color: var(--sugar-comfy-settings-accent) !important;
  --p-radiobutton-checked-focus-border-color: var(--sugar-comfy-settings-accent) !important;
  --p-radiobutton-checked-hover-background: var(--sugar-comfy-settings-accent-hover) !important;
  --p-radiobutton-checked-hover-border-color: var(--sugar-comfy-settings-accent-hover) !important;
  --p-radiobutton-focus-ring-color: var(--sugar-comfy-settings-accent) !important;
  --p-radiobutton-icon-checked-color: var(--sugar-comfy-settings-accent-contrast) !important;
  --p-radiobutton-icon-checked-hover-color: var(--sugar-comfy-settings-accent-contrast) !important;
  --p-toggleswitch-checked-background: var(--sugar-comfy-settings-accent) !important;
  --p-toggleswitch-checked-hover-background: var(--sugar-comfy-settings-accent-hover) !important;
  --p-toggleswitch-focus-ring-color: var(--sugar-comfy-settings-accent) !important;
  --p-toggleswitch-handle-checked-color: var(--sugar-comfy-settings-accent) !important;
  --p-toggleswitch-handle-checked-hover-color: var(--sugar-comfy-settings-accent-hover) !important;
  --p-slider-range-background: var(--sugar-comfy-settings-accent) !important;
  --p-slider-handle-focus-ring-color: var(--sugar-comfy-settings-accent) !important;
  border-radius: 0 !important;
  height: 100% !important;
  max-height: none !important;
  max-width: none !important;
  position: relative !important;
  width: 100% !important;
  z-index: 2147483003 !important;
}

body.sugar-comfy-settings-dialog-opened
  .sugar-comfy-settings-dialog
  .p-tag.p-component {
  background-color: var(--sugar-comfy-settings-accent-soft) !important;
  border-color: var(--sugar-comfy-settings-accent-foreground) !important;
  color: var(--sugar-comfy-settings-accent-foreground) !important;
}

body.sugar-comfy-settings-dialog-opened
  .sugar-comfy-settings-dialog
  .p-tag.p-component
  svg,
body.sugar-comfy-settings-dialog-opened
  .sugar-comfy-settings-dialog
  .p-tag.p-component
  path {
  color: currentColor !important;
  fill: currentColor !important;
}

body.sugar-comfy-settings-dialog-opened
  .sugar-comfy-settings-dialog
  .p-radiobutton.p-radiobutton-checked
  .p-radiobutton-box {
  background-color: var(--sugar-comfy-settings-accent) !important;
  border-color: var(--sugar-comfy-settings-accent) !important;
  transition: none !important;
}

body.sugar-comfy-settings-dialog-opened
  .sugar-comfy-settings-dialog
  .p-radiobutton.p-radiobutton-checked:not(.p-disabled):hover
  .p-radiobutton-box {
  background-color: var(--sugar-comfy-settings-accent-hover) !important;
  border-color: var(--sugar-comfy-settings-accent-hover) !important;
}

body.sugar-comfy-settings-dialog-opened
  .sugar-comfy-settings-dialog
  .p-radiobutton.p-radiobutton-checked
  .p-radiobutton-icon {
  background-color: var(--sugar-comfy-settings-accent-contrast) !important;
  transition: none !important;
}

body.sugar-comfy-settings-dialog-opened
  .sugar-comfy-settings-dialog
  .p-toggleswitch.p-toggleswitch-checked
  .p-toggleswitch-slider {
  background-color: var(--sugar-comfy-settings-accent) !important;
}

body.sugar-comfy-settings-dialog-opened
  .sugar-comfy-settings-dialog
  .p-toggleswitch.p-toggleswitch-checked:not(.p-disabled):hover
  .p-toggleswitch-slider {
  background-color: var(--sugar-comfy-settings-accent-hover) !important;
}

body.sugar-comfy-settings-dialog-opened
  .sugar-comfy-settings-dialog
  .p-toggleswitch.p-toggleswitch-checked
  .p-toggleswitch-handle {
  color: var(--sugar-comfy-settings-accent) !important;
}

body.sugar-comfy-settings-dialog-opened
  .sugar-comfy-settings-dialog
  .p-slider
  .p-slider-range {
  background-color: var(--sugar-comfy-settings-accent) !important;
}

body.sugar-comfy-settings-dialog-opened
  .sugar-comfy-settings-dialog
  [data-component-id="LeftPanelHeader"] {
  display: none !important;
}

body.sugar-comfy-settings-dialog-opened .sugar-comfy-settings-hidden-header {
  display: none !important;
}

body.sugar-comfy-settings-dialog-opened .sugar-comfy-settings-hidden-close {
  display: none !important;
}

body.sugar-comfy-settings-dialog-opened .sugar-comfy-settings-dialog,
body.sugar-comfy-settings-dialog-opened .sugar-comfy-settings-dialog * {
  pointer-events: auto !important;
}
"""
    css = css.replace("__SUGAR_COMFY_SETTINGS_ACCENT__", palette.primary)
    css = css.replace("__SUGAR_COMFY_SETTINGS_ACCENT_HOVER__", palette.hover)
    css = css.replace("__SUGAR_COMFY_SETTINGS_ACCENT_ACTIVE__", palette.active)
    css = css.replace("__SUGAR_COMFY_SETTINGS_ACCENT_SOFT__", palette.soft_background)
    css = css.replace(
        "__SUGAR_COMFY_SETTINGS_ACCENT_FOREGROUND__",
        palette.soft_foreground,
    )
    css = css.replace("__SUGAR_COMFY_SETTINGS_ACCENT_CONTRAST__", palette.contrast)
    escaped_css = css.replace("\\", "\\\\").replace("`", "\\`")
    return f"""
(() => {{
  const style = document.createElement("style");
  style.id = "sugar-substitute-comfy-settings-shell-style";
  style.textContent = `{escaped_css}`;
  document.documentElement.appendChild(style);
}})();
"""


def build_comfy_settings_bootstrap_script(
    *,
    dialog_module_prefix: str = _COMFY_FRONTEND_DIALOG_MODULE_PREFIX,
    default_panel: str = "root/Comfy",
    default_setting_id: str = "Comfy.VueNodes.Enabled",
    accent_palette: ComfySettingsAccentPalette | None = None,
    retry_count: int = 80,
    retry_delay_ms: int = 125,
) -> str:
    """Return JavaScript that opens ComfyUI's own Settings dialog."""

    escaped_prefix = escape(dialog_module_prefix)
    target_panel = dumps(default_panel)
    target_setting_id = dumps(default_setting_id)
    palette = (
        accent_palette
        if accent_palette is not None
        else comfy_settings_accent_palette()
    )
    accent_tokens = dumps(
        {
            "--sugar-comfy-settings-accent": palette.primary,
            "--sugar-comfy-settings-accent-hover": palette.hover,
            "--sugar-comfy-settings-accent-active": palette.active,
            "--sugar-comfy-settings-accent-soft": palette.soft_background,
            "--sugar-comfy-settings-accent-foreground": palette.soft_foreground,
            "--sugar-comfy-settings-accent-contrast": palette.contrast,
            "--p-primary-color": palette.primary,
            "--p-primary-hover-color": palette.hover,
            "--p-primary-active-color": palette.active,
            "--p-primary-contrast-color": palette.contrast,
            "--p-primary-300": palette.soft_foreground,
            "--p-primary-400": palette.hover,
            "--p-primary-500": palette.primary,
            "--p-primary-600": palette.primary,
            "--p-blue-300": palette.soft_foreground,
            "--p-blue-400": palette.hover,
            "--p-blue-500": palette.primary,
            "--p-blue-600": palette.primary,
            "--p-button-primary-background": palette.primary,
            "--p-button-primary-border-color": palette.primary,
            "--p-button-primary-color": palette.contrast,
            "--p-button-primary-focus-ring-color": palette.primary,
            "--p-button-primary-hover-background": palette.hover,
            "--p-button-primary-hover-border-color": palette.hover,
            "--p-button-primary-hover-color": palette.contrast,
            "--p-button-primary-active-background": palette.active,
            "--p-button-primary-active-border-color": palette.active,
            "--p-button-primary-active-color": palette.contrast,
            "--p-button-outlined-primary-color": palette.soft_foreground,
            "--p-button-outlined-primary-border-color": palette.primary,
            "--p-button-outlined-primary-hover-background": palette.soft_background,
            "--p-button-text-primary-color": palette.soft_foreground,
            "--p-button-text-primary-hover-background": palette.soft_background,
            "--p-tag-primary-background": palette.soft_background,
            "--p-tag-primary-color": palette.soft_foreground,
            "--p-radiobutton-checked-background": palette.primary,
            "--p-radiobutton-checked-border-color": palette.primary,
            "--p-radiobutton-checked-focus-border-color": palette.primary,
            "--p-radiobutton-checked-hover-background": palette.hover,
            "--p-radiobutton-checked-hover-border-color": palette.hover,
            "--p-radiobutton-focus-ring-color": palette.primary,
            "--p-radiobutton-icon-checked-color": palette.contrast,
            "--p-radiobutton-icon-checked-hover-color": palette.contrast,
            "--p-toggleswitch-checked-background": palette.primary,
            "--p-toggleswitch-checked-hover-background": palette.hover,
            "--p-toggleswitch-focus-ring-color": palette.primary,
            "--p-toggleswitch-handle-checked-color": palette.primary,
            "--p-toggleswitch-handle-checked-hover-color": palette.hover,
            "--p-slider-range-background": palette.primary,
            "--p-slider-handle-focus-ring-color": palette.primary,
        }
    )
    return f"""
(() => {{
  if (window.__sugarSubstituteComfySettingsBootstrapStarted) {{
    return;
  }}
  window.__sugarSubstituteComfySettingsBootstrapStarted = true;

  const retryCount = {retry_count};
  const retryDelayMs = {retry_delay_ms};
  const dialogModulePattern = /{escaped_prefix}[^"'<>\\s]+\\.js/;
  const targetPanel = {target_panel};
  const targetSettingId = {target_setting_id};
  const accentTokens = {accent_tokens};

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  const findDialogModuleUrl = () => {{
    const candidates = [
      ...document.querySelectorAll('link[href*="{dialog_module_prefix}"]'),
      ...document.querySelectorAll('script[src*="{dialog_module_prefix}"]')
    ];
    for (const candidate of candidates) {{
      const url = candidate.href || candidate.src;
      if (url) {{
        return new URL(url, window.location.href).href;
      }}
    }}
    for (const link of document.querySelectorAll('link[rel="modulepreload"]')) {{
      const href = link.href || "";
      if (dialogModulePattern.test(href)) {{
        return new URL(href, window.location.href).href;
      }}
    }}
    return null;
  }};

  const resolveSettingsDialogExport = async (moduleUrl) => {{
    const response = await fetch(moduleUrl, {{ cache: "force-cache" }});
    const moduleText = await response.text();
    const match = moduleText.match(/useSettingsDialog as ([A-Za-z_$][\\w$]*)/);
    const exportName = match ? match[1] : "useSettingsDialog";
    const module = await import(moduleUrl);
    const useSettingsDialog = module[exportName] || module.useSettingsDialog;
    if (typeof useSettingsDialog !== "function") {{
      throw new Error("ComfyUI Settings dialog export was not found.");
    }}
    return useSettingsDialog;
  }};

  const findSettingsDialog = () => {{
    const settingsRoot = document.querySelector('[data-testid="settings-dialog"]');
    if (!settingsRoot) {{
      return null;
    }}
    const frame = settingsRoot.closest('.p-dialog, [role="dialog"]');
    const content = settingsRoot.closest('.p-dialog-content, [data-pc-section="content"]');
    const mask = settingsRoot.closest('.p-dialog-mask');
    return {{ settingsRoot, frame, content, mask }};
  }};

  const hideSettingsCloseControls = (settingsRoot, frame) => {{
    const candidates = [
      ...settingsRoot.querySelectorAll('button'),
      ...(frame ? frame.querySelectorAll('button') : [])
    ];
    const seen = new Set();
    const closeControls = candidates.filter((button) => {{
      if (seen.has(button)) {{
        return false;
      }}
      seen.add(button);
      const label = button.getAttribute("aria-label") || "";
      const title = button.getAttribute("title") || "";
      return /close/i.test(label)
        || /close/i.test(title)
        || button.classList.contains("p-dialog-close-button")
        || button.dataset.pcName === "pcclosebutton"
        || Boolean(button.querySelector(".pi-times"));
    }});
    const selectors = [
      '.p-dialog-header-close',
      '.p-dialog-close-button',
      '[data-pc-section="closebutton"]'
    ];
    for (const control of [
      ...closeControls,
      ...settingsRoot.querySelectorAll(selectors.join(',')),
      ...(frame ? frame.querySelectorAll(selectors.join(',')) : [])
    ]) {{
      const closeHeader = control.closest("header");
      if (closeHeader && settingsRoot.contains(closeHeader)) {{
        closeHeader.classList.add("sugar-comfy-settings-hidden-header");
        closeHeader.style.setProperty("display", "none", "important");
      }}
      control.setAttribute("aria-hidden", "true");
      control.setAttribute("tabindex", "-1");
      control.classList.add("sugar-comfy-settings-hidden-close");
      control.style.setProperty("display", "none", "important");
    }}
  }};

  const hideSettingsReservedHeaders = (settingsRoot) => {{
    const headerSelectors = [
      '[data-component-id="LeftPanelHeader"]',
      'header.flex.h-18.w-full.shrink-0.items-center-safe.gap-2.pr-3.pl-6'
    ];
    for (const header of settingsRoot.querySelectorAll(headerSelectors.join(","))) {{
      header.classList.add("sugar-comfy-settings-hidden-header");
      header.style.setProperty("display", "none", "important");
    }}
  }};

  const alignSettingsSearchWithContent = (settingsRoot) => {{
    const searchInput = settingsRoot.querySelector('input[placeholder*="Search Settings"]');
    const searchWrapper = searchInput?.closest("div.px-3");
    const contentHeading = [...settingsRoot.querySelectorAll("main h1, main h2, main h3, main [role='heading']")]
      .find((element) => {{
        const style = window.getComputedStyle(element);
        return style.display !== "none" && style.visibility !== "hidden";
      }});
    if (!searchWrapper || !contentHeading) {{
      return;
    }}
    if (!searchWrapper.dataset.sugarBasePaddingTop) {{
      searchWrapper.dataset.sugarBasePaddingTop =
        window.getComputedStyle(searchWrapper).paddingTop;
      searchWrapper.dataset.sugarBaseMarginTop =
        window.getComputedStyle(searchWrapper).marginTop;
    }}
    const basePaddingTop = Number.parseFloat(
      searchWrapper.dataset.sugarBasePaddingTop || "0"
    ) || 0;
    const baseMarginTop = Number.parseFloat(
      searchWrapper.dataset.sugarBaseMarginTop || "0"
    ) || 0;
    searchWrapper.style.setProperty("padding-top", `${{basePaddingTop}}px`, "important");
    searchWrapper.style.setProperty("margin-top", `${{baseMarginTop}}px`, "important");
    const searchTop = searchInput.getBoundingClientRect().top;
    const contentTop = contentHeading.getBoundingClientRect().top;
    const offset = Math.round(contentTop - searchTop);
    if (offset >= 0) {{
      searchWrapper.style.setProperty(
        "padding-top",
        `${{basePaddingTop + offset}}px`,
        "important"
      );
      searchWrapper.style.setProperty("margin-top", `${{baseMarginTop}}px`, "important");
      return;
    }}
    searchWrapper.style.setProperty("padding-top", `${{basePaddingTop}}px`, "important");
    searchWrapper.style.setProperty(
      "margin-top",
      `${{baseMarginTop + offset}}px`,
      "important"
    );
  }};

  const applySettingsAccent = (settingsRoot) => {{
    for (const [name, value] of Object.entries(accentTokens)) {{
      settingsRoot.style.setProperty(name, value, "important");
    }}
    for (const tag of settingsRoot.querySelectorAll(".p-tag.p-component")) {{
      tag.style.setProperty("background-color", accentTokens["--sugar-comfy-settings-accent-soft"], "important");
      tag.style.setProperty("border-color", accentTokens["--sugar-comfy-settings-accent-foreground"], "important");
      tag.style.setProperty("color", accentTokens["--sugar-comfy-settings-accent-foreground"], "important");
      for (const iconPart of tag.querySelectorAll("svg, path")) {{
        iconPart.style.setProperty("color", "currentColor", "important");
        iconPart.style.setProperty("fill", "currentColor", "important");
      }}
    }}
    for (const radioBox of settingsRoot.querySelectorAll(".p-radiobutton.p-radiobutton-checked .p-radiobutton-box")) {{
      radioBox.style.setProperty("transition", "none", "important");
      radioBox.style.setProperty("background-color", accentTokens["--sugar-comfy-settings-accent"], "important");
      radioBox.style.setProperty("border-color", accentTokens["--sugar-comfy-settings-accent"], "important");
    }}
    for (const radioIcon of settingsRoot.querySelectorAll(".p-radiobutton.p-radiobutton-checked .p-radiobutton-icon")) {{
      radioIcon.style.setProperty("transition", "none", "important");
      radioIcon.style.setProperty("background-color", accentTokens["--sugar-comfy-settings-accent-contrast"], "important");
    }}
    for (const radio of settingsRoot.querySelectorAll(".p-radiobutton.p-radiobutton-checked")) {{
      radio.style.setProperty("--p-radiobutton-checked-background", accentTokens["--sugar-comfy-settings-accent"], "important");
      radio.style.setProperty("--p-radiobutton-checked-border-color", accentTokens["--sugar-comfy-settings-accent"], "important");
      radio.style.setProperty("--p-radiobutton-icon-checked-color", accentTokens["--sugar-comfy-settings-accent-contrast"], "important");
    }}
    for (const slider of settingsRoot.querySelectorAll(".p-toggleswitch.p-toggleswitch-checked .p-toggleswitch-slider")) {{
      slider.style.setProperty("background-color", accentTokens["--sugar-comfy-settings-accent"], "important");
    }}
    for (const handle of settingsRoot.querySelectorAll(".p-toggleswitch.p-toggleswitch-checked .p-toggleswitch-handle")) {{
      handle.style.setProperty("color", accentTokens["--sugar-comfy-settings-accent"], "important");
      handle.style.setProperty("border-color", accentTokens["--sugar-comfy-settings-accent"], "important");
    }}
    for (const range of settingsRoot.querySelectorAll(".p-slider .p-slider-range")) {{
      range.style.setProperty("background-color", accentTokens["--sugar-comfy-settings-accent"], "important");
    }}
  }};

  const applySettingsFocus = (dialog) => {{
    document.body.classList.add("sugar-comfy-settings-dialog-opened");
    dialog.settingsRoot.classList.add("sugar-comfy-settings-dialog");
    dialog.frame?.classList.add("sugar-comfy-settings-dialog-frame");
    dialog.content?.classList.add("sugar-comfy-settings-dialog-content");
    dialog.mask?.classList.add("sugar-comfy-settings-dialog-mask");
    dialog.mask?.style.setProperty("background", "#111", "important");
    dialog.mask?.style.setProperty("backdrop-filter", "none", "important");
    dialog.mask?.style.setProperty("z-index", "2147483001", "important");
    dialog.mask?.style.setProperty("align-items", "stretch", "important");
    dialog.mask?.style.setProperty("justify-content", "stretch", "important");
    dialog.mask?.style.setProperty("padding", "0", "important");
    dialog.frame?.style.setProperty("z-index", "2147483002", "important");
    dialog.frame?.style.setProperty("width", "100vw", "important");
    dialog.frame?.style.setProperty("height", "100vh", "important");
    dialog.frame?.style.setProperty("max-width", "none", "important");
    dialog.frame?.style.setProperty("max-height", "none", "important");
    dialog.frame?.style.setProperty("margin", "0", "important");
    dialog.frame?.style.setProperty("border-radius", "0", "important");
    dialog.content?.style.setProperty("width", "100%", "important");
    dialog.content?.style.setProperty("height", "100%", "important");
    dialog.content?.style.setProperty("padding", "0", "important");
    dialog.content?.style.setProperty("margin", "0", "important");
    dialog.content?.style.setProperty("overflow", "hidden", "important");
    dialog.settingsRoot.style.setProperty("width", "100%", "important");
    dialog.settingsRoot.style.setProperty("height", "100%", "important");
    dialog.settingsRoot.style.setProperty("max-width", "none", "important");
    dialog.settingsRoot.style.setProperty("max-height", "none", "important");
    dialog.settingsRoot.style.setProperty("border-radius", "0", "important");
    applySettingsAccent(dialog.settingsRoot);
    hideSettingsReservedHeaders(dialog.settingsRoot);
    alignSettingsSearchWithContent(dialog.settingsRoot);
    hideSettingsCloseControls(dialog.settingsRoot, dialog.frame);
    window.requestAnimationFrame(() => {{
      alignSettingsSearchWithContent(dialog.settingsRoot);
    }});
    window.__sugarSubstituteComfySettingsObserver?.disconnect?.();
    window.__sugarSubstituteComfySettingsObserver = new MutationObserver(() => {{
      applySettingsAccent(dialog.settingsRoot);
      hideSettingsReservedHeaders(dialog.settingsRoot);
      alignSettingsSearchWithContent(dialog.settingsRoot);
      hideSettingsCloseControls(dialog.settingsRoot, dialog.frame);
    }});
    window.__sugarSubstituteComfySettingsObserver.observe(dialog.frame || dialog.settingsRoot, {{
      childList: true,
      subtree: true,
    }});
  }};

  const selectTargetSettingsCategory = (settingsRoot) => {{
    const directNavItem = settingsRoot.querySelector(`[data-nav-id="${{targetPanel}}"]`);
    const navItems = [...settingsRoot.querySelectorAll("nav button, nav [data-nav-id]")];
    const matchingButton = navItems.find((button) =>
      button.textContent.trim() === "Comfy"
    );
    const target = directNavItem || matchingButton;
    if (!target) {{
      return false;
    }}
    target.scrollIntoView({{ block: "center" }});
    target.click();
    return true;
  }};

  const waitForTargetSettingsContent = async (settingsRoot) => {{
    for (let attempt = 0; attempt < retryCount; attempt += 1) {{
      if (settingsRoot.querySelector(`#${{CSS.escape(targetSettingId)}}`)) {{
        return true;
      }}
      selectTargetSettingsCategory(settingsRoot);
      await sleep(retryDelayMs);
    }}
    return false;
  }};

  const focusSettingsDialog = async () => {{
    let dialog = null;
    for (let attempt = 0; attempt < retryCount && !dialog; attempt += 1) {{
      dialog = findSettingsDialog();
      if (!dialog) {{
        await sleep(retryDelayMs);
      }}
    }}
    if (!dialog) {{
      throw new Error("ComfyUI Settings dialog DOM was not found.");
    }}
    applySettingsFocus(dialog);
    if (selectTargetSettingsCategory(dialog.settingsRoot)) {{
      window.requestAnimationFrame(() => {{
        alignSettingsSearchWithContent(dialog.settingsRoot);
      }});
    }}
    await waitForTargetSettingsContent(dialog.settingsRoot);
  }};

  const openSettingsDialog = async () => {{
    let moduleUrl = null;
    for (let attempt = 0; attempt < retryCount && !moduleUrl; attempt += 1) {{
      moduleUrl = findDialogModuleUrl();
      if (!moduleUrl) {{
        await sleep(retryDelayMs);
      }}
    }}
    if (!moduleUrl) {{
      throw new Error("ComfyUI dialog service module was not found.");
    }}
    const useSettingsDialog = await resolveSettingsDialogExport(moduleUrl);
    for (let attempt = 0; attempt < retryCount; attempt += 1) {{
      try {{
        useSettingsDialog().show(undefined, targetSettingId);
        await focusSettingsDialog();
        return;
      }} catch (error) {{
        if (attempt === retryCount - 1) {{
          throw error;
        }}
        await sleep(retryDelayMs);
      }}
    }}
  }};

  openSettingsDialog().catch((error) => {{
    console.error("[SugarSubstitute] Failed to open ComfyUI Settings", error);
    document.body.classList.add("sugar-comfy-settings-open-failed");
  }});
}})();
"""


def _webengine_script(
    name: str,
    source_code: str,
    injection_point: object,
) -> "QWebEngineScript":
    """Create one WebEngine user script for the settings-only shell."""

    if _qt_webengine_core is None:
        raise RuntimeError("Qt WebEngine script support is not available.")
    script = _qt_webengine_core.QWebEngineScript()
    script.setName(name)
    script.setSourceCode(source_code)
    script.setInjectionPoint(cast("QWebEngineScript.InjectionPoint", injection_point))
    script.setRunsOnSubFrames(False)
    script.setWorldId(_qt_webengine_core.QWebEngineScript.ScriptWorldId.MainWorld)
    return cast("QWebEngineScript", script)


def log_webengine_unavailable() -> None:
    """Record that the ComfyUI Settings webview cannot be opened."""

    log_warning(
        _LOGGER,
        "Qt WebEngine is unavailable; ComfyUI Settings webview cannot open",
    )


__all__ = [
    "COMFY_SETTINGS_DIALOG_OBJECT_NAME",
    "COMFY_SETTINGS_LOADING_OBJECT_NAME",
    "COMFY_SETTINGS_VIEW_OBJECT_NAME",
    "ComfySettingsAccentPalette",
    "ComfySettingsWebViewDialog",
    "ComfySettingsWebViewRequest",
    "WEBENGINE_AVAILABLE",
    "build_comfy_settings_bootstrap_script",
    "build_comfy_settings_dialog_focus_script",
    "comfy_settings_accent_palette",
    "comfy_settings_window_geometry",
    "log_webengine_unavailable",
    "open_comfy_settings_webview",
]

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

"""Build startup runtime objects before route-specific shell orchestration."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import Any, Protocol

from substitute.app.bootstrap.startup_trace import trace_mark, trace_span
from substitute.domain.onboarding import InstallationContext
from substitute.shared.qfluentwidgets_banner import (
    suppress_qfluentwidgets_import_banner,
)


class StartupPhaseTimer(Protocol):
    """Describe the startup timing surface needed by runtime bootstrap."""

    def phase(self, name: str) -> AbstractContextManager[None]:
        """Return a timing context manager for one startup phase."""


@dataclass(slots=True)
class StartupThemeConfiguration:
    """Apply and cache the process theme configuration when requested."""

    appearance_runtime: Any
    startup_timer: StartupPhaseTimer
    configure_theme_callback: Callable[[Any], Any]
    _resolved_appearance: Any | None = field(default=None, init=False)

    def configure(self) -> Any:
        """Return the resolved appearance after applying the theme once."""

        if self._resolved_appearance is not None:
            return self._resolved_appearance
        with suppress_qfluentwidgets_import_banner():
            with self.startup_timer.phase("startup.configure_theme"):
                with trace_span("startup.configure_theme"):
                    self._resolved_appearance = self.configure_theme_callback(
                        self.appearance_runtime
                    )
        trace_mark(
            "startup.theme.configured",
            theme_mode=self._resolved_appearance.effective_theme_mode.value,
            backdrop_mode=self._resolved_appearance.effective_backdrop_mode,
        )
        return self._resolved_appearance

    @property
    def resolved_appearance(self) -> Any | None:
        """Return the cached resolved appearance when theme has run."""

        return self._resolved_appearance


@dataclass(frozen=True, slots=True)
class StartupRuntimeBootstrap:
    """Return startup runtime objects needed by the remaining bootstrap flow."""

    app: Any
    appearance_runtime: Any
    theme_configuration: StartupThemeConfiguration
    comfy_output_stream: Any
    runtime_services: Any

    @property
    def resolved_appearance(self) -> Any | None:
        """Return the resolved appearance if theme configuration has run."""

        return self.theme_configuration.resolved_appearance

    def configure_theme(self) -> Any:
        """Apply and return the process theme through the owned theme runtime."""

        return self.theme_configuration.configure()


def build_startup_runtime_bootstrap(
    *,
    cli_args: Sequence[str],
    installation_context: InstallationContext,
    startup_timer: StartupPhaseTimer,
    create_application: Callable[[Sequence[str]], Any],
    build_appearance_runtime: Callable[[InstallationContext], Any],
    configure_theme: Callable[[Any], Any],
    build_application_runtime_services: Callable[..., Any],
    output_stream_factory: Callable[[], Any] | None = None,
    configure_theme_immediately: bool = True,
) -> StartupRuntimeBootstrap:
    """Create the Qt app, appearance runtime, output stream, and runtime services."""

    with startup_timer.phase("startup.create_application"):
        with trace_span("startup.create_application"):
            app = create_application(cli_args)
    trace_mark("startup.application.created", app_type=type(app).__name__)
    with startup_timer.phase("startup.build_appearance_runtime"):
        with trace_span("startup.build_appearance_runtime"):
            appearance_runtime = build_appearance_runtime(installation_context)
    theme_configuration = StartupThemeConfiguration(
        appearance_runtime=appearance_runtime,
        startup_timer=startup_timer,
        configure_theme_callback=configure_theme,
    )
    if configure_theme_immediately:
        theme_configuration.configure()
    if output_stream_factory is None:
        from sugarsubstitute_shared.presentation.terminal.output_stream import (
            TerminalOutputStream,
        )

        output_stream_factory = TerminalOutputStream
    comfy_output_stream = output_stream_factory()
    with trace_span("startup.runtime_services.build"):
        runtime_services = build_application_runtime_services(
            context=installation_context,
            comfy_output_stream=comfy_output_stream,
            appearance_runtime=appearance_runtime,
        )
    trace_mark("startup.runtime_services.built")
    return StartupRuntimeBootstrap(
        app=app,
        appearance_runtime=appearance_runtime,
        theme_configuration=theme_configuration,
        comfy_output_stream=comfy_output_stream,
        runtime_services=runtime_services,
    )


__all__ = [
    "StartupRuntimeBootstrap",
    "StartupPhaseTimer",
    "StartupThemeConfiguration",
    "build_startup_runtime_bootstrap",
]

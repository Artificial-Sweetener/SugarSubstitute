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

"""Run a selected launcher under the durable baseline ownership session."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import ExitStack
import logging
import os
from pathlib import Path
import sys
from typing import Protocol

from launcher.sugarsubstitute_launcher.startup_splash_session import (
    StartupSplashSession,
)

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_broker_session import (
    ApplicationBrokerSession,
    DELEGATED_LAUNCHER_ENV,
)
from sugarsubstitute_shared.launcher_update.bundle_paths import LauncherBundlePaths
from sugarsubstitute_shared.launcher_update.bundle_selection import (
    LauncherBundleSelection,
    SelectedLauncherBundle,
)
from sugarsubstitute_shared.launcher_update.targets import (
    launcher_bundle_target_for_key,
)

_LOGGER = logging.getLogger(__name__)


class GenerationSupervisor(Protocol):
    """Own a selected process family through its terminal user action."""

    def supervise(
        self,
        *,
        layout: InstallLayout,
        command: Sequence[str],
        environment: Mapping[str, str],
    ) -> int:
        """Wait for the selected process and return its terminal status."""


def dispatch_selected_launcher(
    *,
    layout: InstallLayout,
    broker: ApplicationBrokerSession,
    arguments: Sequence[str],
    supervisor: GenerationSupervisor | None = None,
    on_baseline_fallback: Callable[[], None] | None = None,
    splash_session: StartupSplashSession | None = None,
    register_startup_resource: Callable[[Callable[[], None]], str] | None = None,
) -> int | None:
    """Dispatch from the installed baseline or continue it after failed startup.

    None keeps the elected owner running the baseline. An integer completes this
    invocation. Closing the selected launcher never releases the baseline lease;
    the caller owns that lifetime throughout supervision and fallback.
    """
    if not bool(getattr(sys, "frozen", False)):
        return None
    if Path(sys.executable).resolve() != layout.executable_path.resolve():
        return None
    if not LauncherBundlePaths(layout.root).selection.exists():
        return None
    target = launcher_bundle_target_for_key(layout.target.key)
    selection = LauncherBundleSelection(layout.root, target)
    try:
        candidate = selection.resolve()
    except (OSError, ValueError):
        _LOGGER.exception("Launcher selection unavailable; continuing baseline startup")
        return None
    if candidate.generation is None:
        return None
    from sugarsubstitute_shared.launcher_update.delegation_contract import (
        supports_launcher_delegation,
    )

    if not supports_launcher_delegation(candidate.root, target):
        _reject_generation(selection, candidate)
        _LOGGER.warning(
            "Selected launcher cannot share ownership; continuing baseline | generation=%s",
            candidate.generation,
        )
        return None
    from launcher.sugarsubstitute_launcher.generation_supervision import (
        GenerationStartupError,
        LauncherGenerationSupervisor,
    )

    if supervisor is None:
        supervisor = LauncherGenerationSupervisor(
            cancellation_requested=(
                splash_session.cancellation_requested
                if splash_session is not None
                else None
            )
        )
    command = [str(candidate.root / target.executable_relative_path), *arguments]
    if not any(
        arg == "--install-root" or arg.startswith("--install-root=")
        for arg in arguments
    ):
        command.append(f"--install-root={layout.root}")
    environment = broker.child_environment(os.environ)
    environment[DELEGATED_LAUNCHER_ENV] = "1"
    try:
        with ExitStack() as startup:
            if splash_session is not None:
                if register_startup_resource is None:
                    raise ValueError("Splash handoff requires its creating supervisor.")
                from launcher.sugarsubstitute_launcher.delegated_startup_presentation import (
                    DelegatedStartupPresentation,
                )

                environment.update(
                    startup.enter_context(
                        DelegatedStartupPresentation(
                            broker=broker,
                            splash=splash_session,
                            register_resource=register_startup_resource,
                        )
                    )
                )
            result = supervisor.supervise(
                layout=layout, command=command, environment=environment
            )
    except GenerationStartupError:
        _LOGGER.exception(
            "Selected launcher could not start; continuing baseline | generation=%s",
            candidate.generation,
        )
        result = None
    restart_requested = broker.consume_restart_request()
    if result == 0 and not restart_requested:
        return 0
    _reject_generation(selection, candidate)
    if result is None or restart_requested:
        if on_baseline_fallback is not None:
            on_baseline_fallback()
        return None
    return result


def _reject_generation(
    selection: LauncherBundleSelection, candidate: SelectedLauncherBundle
) -> None:
    """Retain a usable baseline even if the rejection record cannot be persisted."""
    try:
        selection.reject(candidate)
    except (OSError, ValueError):
        _LOGGER.exception(
            "Failed launcher generation could not be retired | generation=%s",
            candidate.generation,
        )

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

"""Drive installed onboarding code off-screen and report event-loop health."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import sys
import time
from typing import TypeVar, cast


_HEARTBEAT_INTERVAL_MS = 50
_HEARTBEAT_REPORT_INTERVAL_SECONDS = 2.0
_MAX_RESPONSIVE_GAP_SECONDS = 1.0
_INTERACTION_PROBE_INTERVAL_MS = 2_000
_MAX_INTERACTION_PROBE_SECONDS = 0.5
_POLL_INTERVAL_MS = 25
_WIDGET_T = TypeVar("_WIDGET_T")


@dataclass(frozen=True, slots=True)
class InstalledSetupResult:
    """Describe one completed real onboarding run."""

    success: bool
    duration_seconds: float
    heartbeat_count: int
    maximum_heartbeat_gap_seconds: float
    interaction_probe_count: int
    maximum_interaction_probe_seconds: float
    final_page: str
    final_status: str
    launch_command: tuple[str, ...]
    handoff_verified: bool


class SetupHarnessFailure(RuntimeError):
    """Report a failed or unresponsive installed onboarding run."""


def main(argv: list[str] | None = None) -> int:
    """Load installed source, drive onboarding, and write one result file."""

    args = _parse_args(sys.argv[1:] if argv is None else argv)
    app_root = args.install_root / "app"
    if not (app_root / "main.py").is_file():
        raise SetupHarnessFailure(f"Installed app payload is missing: {app_root}")
    sys.path.insert(0, str(app_root))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("SUBSTITUTE_DISABLE_APP_USER_MODEL_ID", "1")
    print("HARNESS_CHILD_STARTED", flush=True)

    try:
        result = _run_installed_onboarding(
            install_root=args.install_root,
            provisioning_timeout_seconds=args.provisioning_timeout_seconds,
        )
    except BaseException as error:
        args.result_path.parent.mkdir(parents=True, exist_ok=True)
        args.result_path.write_text(
            json.dumps(
                {
                    "success": False,
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(
            f"HARNESS_CHILD_FAILED type={type(error).__name__} details={error}",
            flush=True,
        )
        raise

    args.result_path.parent.mkdir(parents=True, exist_ok=True)
    args.result_path.write_text(
        json.dumps(asdict(result), indent=2),
        encoding="utf-8",
    )
    print(
        "HARNESS_CHILD_COMPLETED "
        f"duration={result.duration_seconds:.3f} "
        f"max_gap={result.maximum_heartbeat_gap_seconds:.3f}",
        flush=True,
    )
    return 0


def _run_installed_onboarding(
    *,
    install_root: Path,
    provisioning_timeout_seconds: float,
) -> InstalledSetupResult:
    """Drive the production onboarding window through managed-local setup."""

    from PySide6.QtCore import QObject, QTimer, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QWidget
    from qfluentwidgets import LineEdit, RadioButton  # type: ignore[import-untyped]

    from substitute.app.bootstrap import composition
    from substitute.app.bootstrap.app_layout import resolve_app_layout
    from substitute.app.bootstrap.installation_context import (
        build_onboarding_service_bundle,
        create_default_installation_context,
    )
    from substitute.app.bootstrap.startup_route_flow import run_startup_route_flow
    from substitute.presentation.onboarding import OnboardingWindow
    from substitute.presentation.widgets.spin_box import SpinBox

    class EventLoopHeartbeat(QObject):
        """Measure and report main-thread scheduling gaps during provisioning."""

        def __init__(self) -> None:
            """Start a precise recurring Qt heartbeat."""

            super().__init__()
            self.count = 0
            self.maximum_gap_seconds = 0.0
            self._last_tick = time.monotonic()
            self._last_report = self._last_tick
            self._timer = QTimer(self)
            self._timer.setTimerType(Qt.TimerType.PreciseTimer)
            self._timer.setInterval(_HEARTBEAT_INTERVAL_MS)
            self._timer.timeout.connect(self._tick)
            self._timer.start()

        def _tick(self) -> None:
            """Record one scheduling gap and emit a watchdog-visible pulse."""

            now = time.monotonic()
            gap = now - self._last_tick
            self._last_tick = now
            self.count += 1
            self.maximum_gap_seconds = max(self.maximum_gap_seconds, gap)
            if now - self._last_report >= _HEARTBEAT_REPORT_INTERVAL_SECONDS:
                self._last_report = now
                print(
                    "HARNESS_HEARTBEAT "
                    f"count={self.count} max_gap={self.maximum_gap_seconds:.3f}",
                    flush=True,
                )

    class UiInteractionProbe(QObject):
        """Exercise geometry and paint work while provisioning remains active."""

        def __init__(self, target: QWidget) -> None:
            """Start periodic move and full-window paint probes."""

            super().__init__()
            self._target = target
            self.count = 0
            self.maximum_duration_seconds = 0.0
            self.failure: str | None = None
            self._timer = QTimer(self)
            self._timer.setTimerType(Qt.TimerType.PreciseTimer)
            self._timer.setInterval(_INTERACTION_PROBE_INTERVAL_MS)
            self._timer.timeout.connect(self._probe)
            self._timer.start()

        def _probe(self) -> None:
            """Move, repaint, and capture the production window once."""

            started_at = time.monotonic()
            try:
                original_position = self._target.pos()
                self._target.move(original_position.x() + 1, original_position.y())
                self._target.move(original_position)
                self._target.repaint()
                captured = self._target.grab()
                if captured.isNull():
                    self.failure = "Production onboarding paint capture was null."
            except (AttributeError, RuntimeError) as error:
                self.failure = f"Production onboarding interaction failed: {error}"
            duration = time.monotonic() - started_at
            self.count += 1
            self.maximum_duration_seconds = max(
                self.maximum_duration_seconds,
                duration,
            )

    started_at = time.monotonic()
    application = composition.create_application(
        ["sugarsubstitute-source-setup-harness", f"--install-root={install_root}"]
    )
    bundle = build_onboarding_service_bundle(install_root)
    assessment = bundle.readiness_service.assess()
    context = create_default_installation_context(install_root)
    handoff_commands: list[tuple[str, ...]] = []
    quit_requests: list[bool] = []

    def start_ready_app_process(command: Sequence[str]) -> bool:
        """Record the production Qt handoff without starting another GUI process."""

        handoff_commands.append(tuple(command))
        return True

    def reject_ready_shell_fallback(_context: object) -> None:
        """Fail when the successful process handoff unexpectedly falls back."""

        raise SetupHarnessFailure("Ready-app process handoff used the shell fallback.")

    route_result = run_startup_route_flow(
        readiness_assessment=assessment,
        no_comfy=False,
        installation_context=context,
        initial_workspace=None,
        initial_shell_placement=None,
        entrypoint_path=resolve_app_layout(install_root).entrypoint_path,
        initial_geometry=None,
        splash=None,
        show_onboarding_window=composition.show_onboarding_window,
        show_repair_window=composition.show_repair_window,
        start_ready_app_process=start_ready_app_process,
        launch_ready_shell=reject_ready_shell_fallback,
        quit_app=lambda: quit_requests.append(True),
    )
    window = route_result.onboarding_window
    if not isinstance(window, OnboardingWindow):
        raise SetupHarnessFailure("Production composition returned the wrong window.")
    heartbeat = EventLoopHeartbeat()
    interaction_probe = UiInteractionProbe(window)
    application.processEvents()

    def widget(widget_type: type[_WIDGET_T], object_name: str) -> _WIDGET_T:
        """Return one production widget by its stable automation name."""

        found = window.findChild(widget_type, object_name)
        if found is None:
            raise SetupHarnessFailure(f"Onboarding widget is missing: {object_name}")
        return cast(_WIDGET_T, found)

    def process_events(milliseconds: int = _POLL_INTERVAL_MS) -> None:
        """Advance the real Qt event loop for one bounded interval."""

        application.processEvents()
        QTest.qWait(milliseconds)
        application.processEvents()

    def current_page() -> str:
        """Return the active production onboarding page name."""

        current = window.page_stack.currentWidget()
        return current.objectName() if current is not None else ""

    def click(object_name: str) -> None:
        """Click one real onboarding control."""

        control = widget(QWidget, object_name)
        QTest.mouseClick(control, Qt.MouseButton.LeftButton)
        process_events(100)

    def wait_for_page(object_name: str, timeout_seconds: float = 5.0) -> None:
        """Wait for one deterministic page transition."""

        _wait_until(
            predicate=lambda: current_page() == object_name,
            timeout_seconds=timeout_seconds,
            description=f"page {object_name}",
            process_events=process_events,
        )

    install_edit = widget(LineEdit, "OnboardingInstallRootEdit")
    if install_edit.text().casefold() != str(install_root).casefold():
        raise SetupHarnessFailure(
            "Installed onboarding did not retain its locked installation root."
        )
    if current_page() == "OnboardingInstallRootPage":
        click("OnboardingPrimaryButton")
        wait_for_page("OnboardingTargetModePage")
    elif current_page() != "OnboardingTargetModePage":
        raise SetupHarnessFailure(
            f"Installed onboarding opened on an unexpected page: {current_page()}"
        )

    managed_radio = widget(
        RadioButton,
        "OnboardingTargetCardRadio_managed_local",
    )
    QTest.mouseClick(managed_radio, Qt.MouseButton.LeftButton)
    process_events(100)
    click("OnboardingPrimaryButton")
    wait_for_page("OnboardingManagedLocalPage")

    widget(LineEdit, "OnboardingManagedHostEdit").setText("127.0.0.1")
    widget(SpinBox, "OnboardingManagedPortSpinBox").setValue(8188)
    widget(LineEdit, "OnboardingManagedWorkspaceEdit").setText(
        str(install_root / "comfyui")
    )
    process_events()
    click("OnboardingPrimaryButton")
    wait_for_page("OnboardingFolderSetupPage")

    widget(LineEdit, "OnboardingManagedModelRootEdit").setText(
        str(install_root / "models")
    )
    widget(LineEdit, "OnboardingOutputRootEdit").setText(str(install_root / "output"))
    process_events()
    click("OnboardingPrimaryButton")
    wait_for_page("OnboardingIntegrationsPage")
    click("OnboardingPrimaryButton")
    wait_for_page("OnboardingProvisioningPage")

    last_progress = ""

    def provisioning_finished() -> bool:
        """Report progress changes while waiting for the terminal action."""

        nonlocal last_progress
        progress = " | ".join(
            (
                window.provisioning_page.status_label.text(),
                window.provisioning_page.detail_label.text(),
                window.primary_button.text(),
            )
        )
        if progress != last_progress:
            last_progress = progress
            print(f"HARNESS_PROGRESS {progress}", flush=True)
        return window.primary_button.text() in {"Review setup", "Try again"}

    _wait_until(
        predicate=provisioning_finished,
        timeout_seconds=provisioning_timeout_seconds,
        description="managed provisioning terminal state",
        process_events=process_events,
    )
    if window.primary_button.text() != "Review setup":
        raise SetupHarnessFailure(
            "Managed provisioning failed: "
            f"{window.provisioning_page.status_label.text()} | "
            f"{window.provisioning_page.detail_label.text()}"
        )
    if heartbeat.maximum_gap_seconds > _MAX_RESPONSIVE_GAP_SECONDS:
        raise SetupHarnessFailure(
            "Qt event loop became unresponsive during provisioning: "
            f"maximum gap was {heartbeat.maximum_gap_seconds:.3f} seconds."
        )
    if interaction_probe.failure is not None:
        raise SetupHarnessFailure(interaction_probe.failure)
    if interaction_probe.maximum_duration_seconds > _MAX_INTERACTION_PROBE_SECONDS:
        raise SetupHarnessFailure(
            "Production onboarding move/paint work became slow during provisioning: "
            f"maximum probe was {interaction_probe.maximum_duration_seconds:.3f} "
            "seconds."
        )

    click("OnboardingPrimaryButton")
    wait_for_page("OnboardingCompletionPage")
    controller = window._controller
    completion = controller.completion
    if completion is None:
        raise SetupHarnessFailure("Onboarding reached completion without a result.")
    launch_command = tuple(completion.launch_command)
    if window.primary_button.text() != "Open Substitute":
        raise SetupHarnessFailure(
            "Completion did not expose the ready-app handoff action: "
            f"{window.primary_button.text()}"
        )
    click("OnboardingPrimaryButton")
    if handoff_commands != [launch_command]:
        raise SetupHarnessFailure(
            "Completion did not submit its launch command through the production "
            f"route: expected={launch_command!r} actual={handoff_commands!r}"
        )
    if quit_requests != [True]:
        raise SetupHarnessFailure(
            "Completion did not request shutdown after a successful handoff."
        )
    if window.isVisible():
        raise SetupHarnessFailure("Completion window remained visible after handoff.")

    result = InstalledSetupResult(
        success=True,
        duration_seconds=time.monotonic() - started_at,
        heartbeat_count=heartbeat.count,
        maximum_heartbeat_gap_seconds=heartbeat.maximum_gap_seconds,
        interaction_probe_count=interaction_probe.count,
        maximum_interaction_probe_seconds=(interaction_probe.maximum_duration_seconds),
        final_page=current_page(),
        final_status=window.provisioning_page.status_label.text(),
        launch_command=launch_command,
        handoff_verified=True,
    )
    return result


def _wait_until(
    *,
    predicate: object,
    timeout_seconds: float,
    description: str,
    process_events: object,
) -> None:
    """Wait for a UI predicate while continuously advancing Qt events."""

    from collections.abc import Callable

    typed_predicate = cast(Callable[[], bool], predicate)
    typed_process_events = cast(Callable[[], None], process_events)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        typed_process_events()
        if typed_predicate():
            return
    raise SetupHarnessFailure(f"Timed out waiting for {description}.")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse installed-runtime child arguments."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--install-root", required=True, type=Path)
    parser.add_argument("--result-path", required=True, type=Path)
    parser.add_argument(
        "--provisioning-timeout-seconds",
        type=float,
        default=7_200.0,
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())

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

"""Own the Qt application lifetime for the supervised setup surface."""

from __future__ import annotations

import sys
from typing import cast

from launcher.sugarsubstitute_launcher.cli import LauncherArguments
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.startup_plan import LauncherStartupPlan
from sugarsubstitute_shared.application_broker_session import ApplicationBrokerSession


def run_launcher_window(
    *,
    args: LauncherArguments,
    startup_plan: LauncherStartupPlan,
    broker: ApplicationBrokerSession | None,
) -> int:
    """Show setup or repair UI after installed launch routing is complete."""

    from PySide6.QtWidgets import QApplication

    from launcher.sugarsubstitute_launcher.ui.main_window import LauncherMainWindow

    from sugarsubstitute_shared.qt_application_instance_control import (
        start_application_instance_control,
        stop_application_instance_control,
    )

    from launcher.sugarsubstitute_launcher.application.installation.composition import (
        build_installation_workflow,
    )
    from launcher.sugarsubstitute_launcher.localization import (
        build_launcher_localization_runtime,
    )
    from launcher.sugarsubstitute_launcher.process import (
        start_installed_launcher_handoff,
    )
    from launcher.sugarsubstitute_launcher.release_source_routing import (
        initial_install_release_source,
    )

    application = QApplication.instance()
    owns_application = application is None
    if application is None:
        application = QApplication(sys.argv[:1])
    application = cast(QApplication, application)
    localization_runtime = build_launcher_localization_runtime(
        application,
        layout=startup_plan.layout,
        locale_override=args.locale_override,
    )
    instance_control = start_application_instance_control()
    resume_runtime = startup_plan.runtime_setup_pending and not args.repair

    def admit_installation(layout: InstallLayout) -> bool:
        """Require the supervising process before writing a selected folder."""
        if instance_control is None:
            raise RuntimeError(
                "Installation requires an active application supervisor."
            )
        return instance_control.claim_installation(layout.root)

    try:
        window = LauncherMainWindow(
            initial_layout=startup_plan.layout,
            continue_install=args.continue_install and not resume_runtime,
            repair=args.repair,
            update_check_enabled=not args.no_update_check,
            initial_release_source=initial_install_release_source(args.manifest_url),
            workflow_factory=lambda output_callback, progress_observer, activity_callback, cancellation: (
                build_installation_workflow(
                    output_callback=output_callback,
                    progress_observer=progress_observer,
                    activity_callback=activity_callback,
                    cancellation=cancellation,
                    admit_installation=admit_installation,
                    process_starter=start_installed_launcher_handoff,
                )
            ),
            localization_manager=localization_runtime.manager,
            handoff_geometry=args.handoff_geometry,
        )
        if resume_runtime:
            from PySide6.QtCore import QTimer
            from launcher.sugarsubstitute_launcher.installed_runtime_setup import (
                pending_runtime_application,
            )

            window.accept_installed_application(
                pending_runtime_application(startup_plan.layout)
            )
            QTimer.singleShot(0, window, window.start_runtime_setup)
        if owns_application:
            window.handoff_completed.connect(application.quit)
        presenter = None
        if broker is not None:
            from launcher.sugarsubstitute_launcher.ui.instance_presentation import (
                LauncherInstancePresenter,
            )

            presenter = LauncherInstancePresenter(window)
            broker.bind_startup_presenter(presenter.present)
        from sugarsubstitute_shared.application_readiness import (
            ApplicationReadinessSurface,
        )
        from sugarsubstitute_shared.qt_surface_readiness import (
            schedule_surface_readiness_receipt,
        )

        schedule_surface_readiness_receipt(
            surface=ApplicationReadinessSurface.LAUNCHER_WINDOW,
            window=window,
        )
        window.show()
        from launcher.sugarsubstitute_launcher.ui.installer_qualification import (
            schedule_installer_qualification,
        )

        schedule_installer_qualification(window)
        if owns_application:
            return int(application.exec())
        return 0
    finally:
        if instance_control is not None:
            stop_application_instance_control()
        if broker is not None:
            broker.bind_startup_presenter(None)
            broker.close()

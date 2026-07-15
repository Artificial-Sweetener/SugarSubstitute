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

"""Create concrete managed-ready startup port bundles."""

from __future__ import annotations

from substitute.app.bootstrap.managed_target_activation import (
    activate_target,
    managed_startup_fatal_incident,
)
from substitute.app.bootstrap.runtime_compatibility import (
    create_endpoint_backend_compatibility_checker,
)
from substitute.app.bootstrap.startup_diagnostics_request import (
    request_startup_diagnostics_titlebar_update,
)
from substitute.app.bootstrap.startup_diagnostics_resources import (
    create_startup_diagnostics_collector,
    create_startup_diagnostics_ignore_repository,
)
from substitute.app.bootstrap.startup_model_metadata_bridge import (
    create_model_metadata_update_bridge,
)
from substitute.app.bootstrap.startup_ports import StartupManagedReadyFactoryPorts
from substitute.app.bootstrap.startup_signal_bridges import (
    create_managed_compatibility_recovery_bridge,
)
from substitute.application.comfy_startup_diagnostics import (
    build_startup_failure_report,
    build_startup_readiness_timeout_incident,
    build_startup_runtime_compatibility_incident,
)
from substitute.presentation.errors.startup_failure_presenter import (
    present_startup_failure_report,
)


def create_startup_managed_ready_factory_ports() -> StartupManagedReadyFactoryPorts:
    """Create concrete factories and adapters for managed-ready startup."""

    return StartupManagedReadyFactoryPorts(
        create_startup_diagnostics_collector=create_startup_diagnostics_collector,
        create_startup_diagnostics_ignore_repository=(
            create_startup_diagnostics_ignore_repository
        ),
        create_runtime_compatibility_checker=(
            create_endpoint_backend_compatibility_checker
        ),
        create_managed_compatibility_recovery_bridge=(
            create_managed_compatibility_recovery_bridge
        ),
        create_model_metadata_update_bridge=create_model_metadata_update_bridge,
        request_startup_diagnostics_titlebar_update=(
            request_startup_diagnostics_titlebar_update
        ),
        activate_target=activate_target,
        managed_startup_fatal_incident=managed_startup_fatal_incident,
        present_startup_failure_report=present_startup_failure_report,
        build_startup_failure_report=build_startup_failure_report,
        build_startup_readiness_timeout_incident=(
            build_startup_readiness_timeout_incident
        ),
        build_startup_runtime_compatibility_incident=(
            build_startup_runtime_compatibility_incident
        ),
    )


__all__ = ["create_startup_managed_ready_factory_ports"]

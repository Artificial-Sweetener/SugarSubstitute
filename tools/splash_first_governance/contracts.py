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

"""Own reviewed startup boundaries and their lightweight dependency policy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SplashFirstContract:
    """Describe one executable function and its reviewed splash boundary."""

    relative_path: Path
    function_name: str
    boundary_call: str
    allowed_module_import_roots: frozenset[str]
    allowed_pre_boundary_imports: frozenset[str]
    allowed_pre_boundary_calls: frozenset[str]
    allowed_module_dispatch_calls: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class SplashDependencyContract:
    """Protect one module in the transitive pre-paint dependency closure."""

    relative_path: Path
    forbidden_import_prefixes: frozenset[str]
    function_name: str | None = None
    boundary_call: str | None = None


def repository_contracts() -> tuple[SplashFirstContract, ...]:
    """Return the authoritative executable startup contracts."""

    stdlib_roots = frozenset(
        {
            "__future__",
            "collections",
            "logging",
            "os",
            "pathlib",
            "sys",
            "time",
            "typing",
        }
    )
    return (
        SplashFirstContract(
            relative_path=Path("main.py"),
            function_name="main",
            boundary_call="start_early_launch_splash",
            allowed_module_import_roots=stdlib_roots,
            allowed_pre_boundary_imports=frozenset(
                {
                    "substitute.app.bootstrap.early_launch_splash",
                    "sugarsubstitute_shared.localization",
                }
            ),
            allowed_pre_boundary_calls=frozenset(
                {
                    "Path",
                    "Path.resolve",
                    "_install_crash_runtime",
                    "resolve",
                    "resolve_early_startup_locale",
                    "start_early_launch_splash",
                    "system_ui_languages",
                    "time.perf_counter",
                }
            ),
            allowed_module_dispatch_calls=frozenset({"_run_entrypoint"}),
        ),
        SplashFirstContract(
            relative_path=Path("launcher/sugarsubstitute_launcher/app.py"),
            function_name="main",
            boundary_call="start_launcher_splash_session",
            allowed_module_import_roots=stdlib_roots,
            allowed_pre_boundary_imports=frozenset(
                {
                    "launcher.sugarsubstitute_launcher.application_launch",
                    "launcher.sugarsubstitute_launcher.application_startup_contract",
                    "launcher.sugarsubstitute_launcher.application_election_recovery",
                    "launcher.sugarsubstitute_launcher.cli",
                    "launcher.sugarsubstitute_launcher.crash_routing",
                    "launcher.sugarsubstitute_launcher.launcher_ui_supervision",
                    "launcher.sugarsubstitute_launcher.logging_setup",
                    "launcher.sugarsubstitute_launcher.runtime_paths",
                    "launcher.sugarsubstitute_launcher.splash_session",
                    "launcher.sugarsubstitute_launcher.startup_plan",
                    "launcher.sugarsubstitute_launcher.supervisor_handoff_wait",
                    "sugarsubstitute_shared.supervisor_handoff",
                    "sugarsubstitute_shared.application_broker_session",
                    "sugarsubstitute_shared.delegated_application_broker",
                    "launcher.sugarsubstitute_launcher.splash_transfer",
                }
            ),
            allowed_pre_boundary_calls=frozenset(
                {
                    "Path",
                    "Path.cwd",
                    "ApplicationElectionRecovery",
                    "election_recovery.run",
                    "_frozen_invocation_path",
                    "_frozen_support_path",
                    "_native_frozen_executable_path",
                    "elect_application",
                    "os.environ.pop",
                    "DelegatedApplicationBroker",
                    "take_borrowed_splash_session",
                    "configure_launcher_logging",
                    "frozen_invocation_path",
                    "frozen_support_path",
                    "native_frozen_executable_path",
                    "parse_launcher_args",
                    "resolve_startup_candidate",
                    "route_explicit_crash_operation",
                    "should_attempt_installed_app_launch",
                    "splash_session.close",
                    "start_launcher_splash_session",
                    "supervisor_handoff_present",
                    "tuple",
                    "wait_for_outgoing_supervisor",
                }
            ),
        ),
    )


def repository_dependency_contracts() -> tuple[SplashDependencyContract, ...]:
    """Return the reviewed modules that form the splash pre-paint closure."""

    forbidden = frozenset(
        {
            "cutecanvas",
            "numpy",
            "psutil",
            "qpane",
            "qfluentwidgets",
            "scipy",
            "torch",
            "substitute.app.bootstrap.splash_process",
            "substitute.presentation.shell.window_frame",
        }
    )
    contracts = [
        SplashDependencyContract(Path(path), forbidden)
        for path in (
            "launcher/sugarsubstitute_launcher/runtime_policy.py",
            "launcher/sugarsubstitute_launcher/splash_session.py",
            "substitute/app/bootstrap/application_catalogs.py",
            "substitute/app/bootstrap/splash_arguments.py",
            "substitute/app/bootstrap/splash_localization.py",
            "substitute/presentation/shell/splash_window.py",
            "substitute/presentation/shell/window_effects.py",
            "sugarsubstitute_shared/supervisor_handoff.py",
        )
    ]
    # Delegated startup borrows the already-visible baseline surface. Only bounded
    # owner authentication and session parsing belong before its own splash call.
    contracts.extend(
        SplashDependencyContract(
            Path(path),
            forbidden
            | {
                "launcher.sugarsubstitute_launcher.generation_dispatch",
                "sugarsubstitute_shared.launcher_update.bundle_selection",
            },
        )
        for path in (
            "sugarsubstitute_shared/application_broker_session.py",
            "sugarsubstitute_shared/delegated_application_broker.py",
            "launcher/sugarsubstitute_launcher/splash_transfer.py",
            "launcher/sugarsubstitute_launcher/startup_splash_session.py",
        )
    )
    contracts.append(
        SplashDependencyContract(
            Path("launcher/sugarsubstitute_launcher/supervisor_handoff_wait.py"),
            forbidden
            | {
                "sugarsubstitute_shared.process_identity",
                "sugarsubstitute_shared.supervisor_handoff",
            },
            function_name="wait_for_outgoing_supervisor",
            boundary_call="start_launcher_splash_session",
        )
    )
    contracts.append(
        SplashDependencyContract(
            Path("substitute/app/bootstrap/shared_splash_host.py"),
            forbidden
            | {
                "sugarsubstitute_shared.launch_splash.server",
                "sugarsubstitute_shared.launch_splash.session",
            },
            function_name="main",
            boundary_call="splash.show",
        )
    )
    return tuple(contracts)

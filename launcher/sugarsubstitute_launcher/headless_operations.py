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

"""Own launcher operations that intentionally construct no GUI state."""

from __future__ import annotations

import logging

from launcher.sugarsubstitute_launcher.cli import LauncherArguments


def verify_release_connectivity(args: LauncherArguments) -> int:
    """Run the explicit headless release-connectivity operation."""

    from launcher.sugarsubstitute_launcher.connectivity import (
        ReleaseConnectivityVerifier,
    )
    from launcher.sugarsubstitute_launcher.release_source_routing import (
        explicit_release_source,
    )

    ReleaseConnectivityVerifier().verify(
        release_source=explicit_release_source(args.manifest_url)
    )
    return 0


def run_headless_install(args: LauncherArguments) -> int:
    """Install launcher and app payload without constructing GUI state."""

    if args.install_root is None:
        raise ValueError("Headless installation requires an explicit install root.")
    from launcher.sugarsubstitute_launcher.application.installation.composition import (
        build_installation_workflow,
    )
    from launcher.sugarsubstitute_launcher.headless_install import (
        HeadlessInstallService,
    )
    from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
    from launcher.sugarsubstitute_launcher.localization import (
        seed_headless_locale_preference,
    )
    from launcher.sugarsubstitute_launcher.logging_setup import (
        configure_launcher_logging,
    )
    from launcher.sugarsubstitute_launcher.release_source_routing import (
        initial_install_release_source,
    )

    layout = InstallLayout.from_root(args.install_root)
    configure_launcher_logging(layout=layout)
    logger = logging.getLogger(__name__)
    HeadlessInstallService(
        workflow=build_installation_workflow(output_callback=logger.info)
    ).install(
        install_root=layout.root,
        release_source=initial_install_release_source(args.manifest_url),
    )
    seed_headless_locale_preference(
        layout,
        locale_override=args.locale_override,
    )
    return 0


__all__ = ["run_headless_install", "verify_release_connectivity"]

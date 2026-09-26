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

"""Install exact core nodepack releases from targeted Registry descriptors."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from urllib.error import HTTPError, URLError

from substitute.application.comfy_nodepacks.core_nodepack_reconciliation_plan import (
    RegistryInstallOutcome,
)
from substitute.domain.comfy_manager import ComfyManagerRuntime
from substitute.infrastructure.comfy.comfy_registry_release_client import (
    ComfyRegistryReleaseClient,
    RegistryReleaseUnavailableError,
)
from substitute.infrastructure.comfy.nodepack_manifest import CoreComfyNodepack
from substitute.infrastructure.comfy.nodepack_operation_timing import (
    measure_nodepack_operation,
)
from substitute.infrastructure.comfy.nodepack_reconciliation_logger import LogCallback
from substitute.infrastructure.comfy.pinned_nodepack_source import (
    TrustedNodepackArchiveInstaller,
)
from substitute.shared.logging.logger import get_logger, log_info, log_warning
from sugarsubstitute_shared.startup_remote_access import (
    is_startup_connectivity_failure,
)

_LOGGER = get_logger("infrastructure.comfy.nodepack_registry_installer")


@dataclass(frozen=True, slots=True)
class RegistryInstallResult:
    """Return a classified targeted Registry acquisition outcome."""

    outcome: RegistryInstallOutcome
    output: tuple[str, ...]


class ComfyNodepackRegistryInstaller:
    """Install exact Registry archives without enumerating the global catalog."""

    def __init__(
        self,
        *,
        release_client: ComfyRegistryReleaseClient | None = None,
        archive_installer: TrustedNodepackArchiveInstaller | None = None,
    ) -> None:
        """Compose targeted metadata resolution with transactional installation."""

        self._release_client = release_client or ComfyRegistryReleaseClient()
        self._archive_installer = archive_installer or TrustedNodepackArchiveInstaller()

    def install_exact(
        self,
        *,
        manager_runtime: ComfyManagerRuntime,
        nodepack: CoreComfyNodepack,
        on_log: LogCallback | None,
        env: Mapping[str, str] | None,
    ) -> RegistryInstallResult:
        """Resolve and install one exact release without a full Registry reload."""

        self._emit(
            on_log,
            (
                f"[ComfyNodepacks] Asking Comfy Registry for "
                f"{nodepack.registry_id}@{nodepack.required_version}."
            ),
        )
        try:
            with measure_nodepack_operation(
                operation="registry_install_exact",
                nodepack_id=nodepack.nodepack_id.value,
                on_log=on_log,
            ):
                release = self._release_client.resolve_exact(nodepack)
                self._archive_installer.install_registry_release(
                    target_path=manager_runtime.workspace / nodepack.expected_folder,
                    nodepack=nodepack,
                    archive_url=release.archive_url,
                    on_log=on_log,
                    env=env,
                )
        except RegistryReleaseUnavailableError as error:
            return RegistryInstallResult(
                RegistryInstallOutcome.VERSION_UNAVAILABLE,
                (str(error),),
            )
        except (HTTPError, URLError, TimeoutError) as error:
            return self._failed_result(
                nodepack=nodepack,
                error=error,
                outcome=RegistryInstallOutcome.REGISTRY_UNREACHABLE,
            )
        except OSError as error:
            outcome = (
                RegistryInstallOutcome.REGISTRY_UNREACHABLE
                if is_startup_connectivity_failure(error)
                else RegistryInstallOutcome.FAILED
            )
            return self._failed_result(
                nodepack=nodepack,
                error=error,
                outcome=outcome,
            )
        except (RuntimeError, ValueError) as error:
            return self._failed_result(
                nodepack=nodepack,
                error=error,
                outcome=RegistryInstallOutcome.FAILED,
            )
        return RegistryInstallResult(RegistryInstallOutcome.INSTALLED, ())

    @staticmethod
    def _failed_result(
        *,
        nodepack: CoreComfyNodepack,
        error: BaseException,
        outcome: RegistryInstallOutcome,
    ) -> RegistryInstallResult:
        """Record bounded failure identity without exposing remote URL details."""

        reason = type(error).__name__
        log_warning(
            _LOGGER,
            "Comfy Registry exact install failed",
            nodepack=nodepack.registry_id,
            required_version=nodepack.required_version,
            outcome=outcome.value,
            reason_type=reason,
        )
        return RegistryInstallResult(outcome, (reason,))

    @staticmethod
    def _emit(callback: LogCallback | None, message: str) -> None:
        """Emit Registry activity to structured and setup logs."""

        log_info(_LOGGER, message)
        if callback is not None:
            callback(message)


__all__ = ["ComfyNodepackRegistryInstaller", "RegistryInstallResult"]

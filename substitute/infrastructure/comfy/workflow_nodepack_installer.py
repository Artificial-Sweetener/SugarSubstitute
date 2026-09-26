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

"""Install explicitly approved workflow nodepacks through trusted sources."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
import re
import tempfile
from urllib.error import HTTPError, URLError

from substitute.application.comfy_nodepacks.workflow_dependency_resolution import (
    WorkflowNodepackInstallCandidate,
    WorkflowNodepackSourceKind,
)
from substitute.infrastructure.comfy.comfy_registry_release_client import (
    ComfyRegistryReleaseClient,
    RegistryReleaseUnavailableError,
)
from substitute.infrastructure.comfy.nodepack_python_dependencies import (
    install_nodepack_python_dependencies,
    install_nodepack_requirements,
)
from substitute.infrastructure.comfy.pinned_nodepack_source import (
    RegistryArchiveIdentity,
    TrustedNodepackArchiveInstaller,
)
from substitute.infrastructure.comfy.trusted_nodepack_installer import (
    install_trusted_nodepack_repository,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_exception,
    log_info,
)

_LOGGER = get_logger("infrastructure.comfy.workflow_nodepack_installer")
_SAFE_FOLDER_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_GIT_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


class WorkflowNodepackInstallStatus(StrEnum):
    """Classify one approved package installation result."""

    INSTALLED = "installed"
    VERSION_UNAVAILABLE = "version_unavailable"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class WorkflowNodepackInstallItemResult:
    """Describe one package result without exposing sensitive remote details."""

    package_id: str
    version: str | None
    source_kind: WorkflowNodepackSourceKind
    status: WorkflowNodepackInstallStatus
    reason_type: str | None = None


@dataclass(frozen=True, slots=True)
class WorkflowNodepackInstallResult:
    """Carry deterministic results for an approved workflow package batch."""

    items: tuple[WorkflowNodepackInstallItemResult, ...]

    @property
    def installed_package_ids(self) -> tuple[str, ...]:
        """Return packages whose source and Python dependencies were installed."""

        return tuple(
            item.package_id
            for item in self.items
            if item.status is WorkflowNodepackInstallStatus.INSTALLED
        )

    @property
    def failed(self) -> bool:
        """Return whether any approved package failed to install completely."""

        return any(
            item.status is not WorkflowNodepackInstallStatus.INSTALLED
            for item in self.items
        )


class WorkflowNodepackInstaller:
    """Acquire approved sources and their declared Python dependencies."""

    def __init__(
        self,
        *,
        release_client: ComfyRegistryReleaseClient | None = None,
        archive_installer: TrustedNodepackArchiveInstaller | None = None,
    ) -> None:
        """Compose exact Registry lookup and trusted source acquisition."""

        self._release_client = release_client or ComfyRegistryReleaseClient()
        self._archive_installer = archive_installer or TrustedNodepackArchiveInstaller()

    def install(
        self,
        candidates: Sequence[WorkflowNodepackInstallCandidate],
        *,
        workspace: Path,
        python_executable: Path,
        env: Mapping[str, str] | None = None,
    ) -> WorkflowNodepackInstallResult:
        """Install each approved package independently and retain partial outcomes."""

        items = tuple(
            self._install_one(
                candidate,
                workspace=workspace,
                python_executable=python_executable,
                env=env,
            )
            for candidate in candidates
        )
        return WorkflowNodepackInstallResult(items=items)

    def _install_one(
        self,
        candidate: WorkflowNodepackInstallCandidate,
        *,
        workspace: Path,
        python_executable: Path,
        env: Mapping[str, str] | None,
    ) -> WorkflowNodepackInstallItemResult:
        """Install one candidate while classifying expected acquisition failures."""

        nodepack = candidate.nodepack
        version = nodepack.version
        try:
            folder_name = _nodepack_folder_name(candidate)
            target = workspace / "custom_nodes" / folder_name
            if target.exists():
                raise RuntimeError(
                    "Refusing to replace an existing arbitrary workflow nodepack."
                )
            custom_nodes = target.parent
            custom_nodes.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix=".substitute-workflow-nodepack-",
                dir=custom_nodes,
            ) as temporary_directory:
                staged = Path(temporary_directory) / folder_name
                if nodepack.source_kind is WorkflowNodepackSourceKind.REGISTRY:
                    self._stage_registry(candidate, target=staged, env=env)
                elif nodepack.source_kind is WorkflowNodepackSourceKind.GIT_REPOSITORY:
                    self._stage_git(candidate, target=staged)
                else:
                    raise ValueError("Unsupported workflow nodepack source kind.")
                _install_dependencies(
                    target=staged,
                    display_name=nodepack.display_name,
                    python_executable=python_executable,
                    env=env,
                )
                staged.rename(target)
        except RegistryReleaseUnavailableError as error:
            return self._failure(
                candidate,
                version=version,
                status=WorkflowNodepackInstallStatus.VERSION_UNAVAILABLE,
                error=error,
            )
        except (
            HTTPError,
            OSError,
            RuntimeError,
            TimeoutError,
            URLError,
            ValueError,
        ) as error:
            return self._failure(
                candidate,
                version=version,
                status=WorkflowNodepackInstallStatus.FAILED,
                error=error,
            )
        log_info(
            _LOGGER,
            "Installed approved workflow nodepack",
            package_id=nodepack.identifier,
            version=version or "unresolved",
            source_kind=nodepack.source_kind.value,
            affected_node_classes=",".join(candidate.class_types),
        )
        return WorkflowNodepackInstallItemResult(
            package_id=nodepack.identifier,
            version=version,
            source_kind=nodepack.source_kind,
            status=WorkflowNodepackInstallStatus.INSTALLED,
        )

    def _stage_registry(
        self,
        candidate: WorkflowNodepackInstallCandidate,
        *,
        target: Path,
        env: Mapping[str, str] | None,
    ) -> None:
        """Materialize one exact Registry release in an isolated staging path."""

        nodepack = candidate.nodepack
        if nodepack.version is None:
            raise ValueError("Comfy Registry nodepack has no installable version.")
        release = self._release_client.resolve_exact(
            registry_id=nodepack.identifier,
            version=nodepack.version,
        )
        self._archive_installer.install_workflow_registry_release(
            target_path=target,
            identity=RegistryArchiveIdentity(
                registry_id=nodepack.identifier,
                display_name=nodepack.display_name,
                version=nodepack.version,
            ),
            archive_url=release.archive_url,
            on_log=None,
            env=env,
        )

    @staticmethod
    def _stage_git(
        candidate: WorkflowNodepackInstallCandidate,
        *,
        target: Path,
    ) -> None:
        """Clone one catalog-confirmed repository into an isolated staging path."""

        nodepack = candidate.nodepack
        if nodepack.repository_url is None:
            raise ValueError("Git workflow nodepack has no repository URL.")
        if nodepack.version is None or not _GIT_COMMIT_PATTERN.fullmatch(
            nodepack.version
        ):
            raise ValueError("Git workflow nodepack has no exact commit revision.")
        install_trusted_nodepack_repository(
            repository_url=nodepack.repository_url,
            revision=nodepack.version,
            target_path=target,
            display_name=nodepack.display_name,
        )

    @staticmethod
    def _failure(
        candidate: WorkflowNodepackInstallCandidate,
        *,
        version: str | None,
        status: WorkflowNodepackInstallStatus,
        error: BaseException,
    ) -> WorkflowNodepackInstallItemResult:
        """Log one bounded failure and return its stable classification."""

        log_exception(
            _LOGGER,
            "Approved workflow nodepack installation failed",
            error=error,
            package_id=candidate.nodepack.identifier,
            version=version or "unresolved",
            source_kind=candidate.nodepack.source_kind.value,
            affected_node_classes=",".join(candidate.class_types),
            status=status.value,
        )
        return WorkflowNodepackInstallItemResult(
            package_id=candidate.nodepack.identifier,
            version=version,
            source_kind=candidate.nodepack.source_kind,
            status=status,
            reason_type=type(error).__name__,
        )


def _nodepack_folder_name(candidate: WorkflowNodepackInstallCandidate) -> str:
    """Derive and validate the approved package's custom-node directory name."""

    nodepack = candidate.nodepack
    if nodepack.source_kind is WorkflowNodepackSourceKind.REGISTRY:
        return _validated_folder_name(nodepack.identifier)
    if nodepack.source_kind is WorkflowNodepackSourceKind.GIT_REPOSITORY:
        repository_url = nodepack.repository_url
        if repository_url is None:
            raise ValueError("Git workflow nodepack has no repository URL.")
        return _validated_folder_name(
            repository_url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
        )
    raise ValueError("Unsupported workflow nodepack source kind.")


def _validated_folder_name(value: str) -> str:
    """Return a portable single-segment custom-node folder name."""

    normalized = value.strip()
    stem = normalized.split(".", 1)[0].upper()
    if (
        not _SAFE_FOLDER_PATTERN.fullmatch(normalized)
        or normalized.endswith(".")
        or stem in _WINDOWS_RESERVED_NAMES
    ):
        raise ValueError("Workflow nodepack does not have a safe folder name.")
    return normalized


def _install_dependencies(
    *,
    target: Path,
    display_name: str,
    python_executable: Path,
    env: Mapping[str, str] | None,
) -> None:
    """Install one staged nodepack's authoritative Python dependency manifest."""

    if (target / "requirements.txt").is_file():
        install_nodepack_requirements(
            python_executable=python_executable,
            nodepack_root=target,
            display_name=display_name,
            env=env,
        )
    elif (target / "pyproject.toml").is_file():
        install_nodepack_python_dependencies(
            python_executable=python_executable,
            nodepack_root=target,
            display_name=display_name,
            env=env,
        )


__all__ = [
    "WorkflowNodepackInstallItemResult",
    "WorkflowNodepackInstallResult",
    "WorkflowNodepackInstallStatus",
    "WorkflowNodepackInstaller",
]

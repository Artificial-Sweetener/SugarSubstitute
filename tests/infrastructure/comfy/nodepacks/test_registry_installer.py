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

"""Tests for targeted exact-version Comfy Registry nodepack installation."""

from __future__ import annotations

from pathlib import Path
from typing import cast
from urllib.error import URLError

import pytest

from substitute.application.comfy_nodepacks.core_nodepack_reconciliation_plan import (
    RegistryInstallOutcome,
)
from substitute.domain.comfy_manager import ComfyManagerKind, ComfyManagerRuntime
from substitute.infrastructure.comfy.comfy_registry_release_client import (
    ComfyRegistryRelease,
    ComfyRegistryReleaseClient,
    RegistryReleaseUnavailableError,
)
from substitute.infrastructure.comfy.nodepack_manifest import CORE_COMFY_NODEPACKS
from substitute.infrastructure.comfy.nodepack_registry_installer import (
    ComfyNodepackRegistryInstaller,
)
from substitute.infrastructure.comfy.pinned_nodepack_source import (
    TrustedNodepackArchiveInstaller,
)


class _ReleaseClient:
    """Return or raise one deterministic Registry resolution result."""

    def __init__(self, result: ComfyRegistryRelease | BaseException) -> None:
        """Store the result and initialize observed manifests."""

        self.result = result
        self.calls: list[tuple[str, str]] = []

    def resolve_exact(
        self,
        *,
        registry_id: str,
        version: str,
    ) -> ComfyRegistryRelease:
        """Return the configured release or raise its configured failure."""

        self.calls.append((registry_id, version))
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


class _ArchiveInstaller:
    """Record one transactional Registry archive installation."""

    def __init__(self, error: RuntimeError | None = None) -> None:
        """Initialize observed arguments and an optional transaction failure."""

        self.calls: list[dict[str, object]] = []
        self.error = error

    def install_registry_release(self, **kwargs: object) -> None:
        """Record the exact trusted archive installation request."""

        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error


def test_installs_targeted_exact_release_without_manager_catalog_reload(
    tmp_path: Path,
) -> None:
    """Resolve one exact descriptor and install it into the canonical folder."""

    nodepack = CORE_COMFY_NODEPACKS[0]
    release = ComfyRegistryRelease(
        node_id=nodepack.registry_id,
        version=nodepack.required_version,
        archive_url="https://cdn.comfy.org/publisher/node/version/node.zip",
    )
    client = _ReleaseClient(release)
    archive_installer = _ArchiveInstaller()
    logs: list[str] = []
    runtime = _runtime(tmp_path, tmp_path / "python.exe")

    result = ComfyNodepackRegistryInstaller(
        release_client=cast(ComfyRegistryReleaseClient, client),
        archive_installer=cast(TrustedNodepackArchiveInstaller, archive_installer),
    ).install_exact(
        manager_runtime=runtime,
        nodepack=nodepack,
        on_log=logs.append,
        env={"TEMP": str(tmp_path / "temp")},
    )

    assert result.outcome is RegistryInstallOutcome.INSTALLED
    assert client.calls == [(nodepack.registry_id, nodepack.required_version)]
    assert archive_installer.calls == [
        {
            "target_path": tmp_path / nodepack.expected_folder,
            "nodepack": nodepack,
            "archive_url": release.archive_url,
            "on_log": logs.append,
            "env": {"TEMP": str(tmp_path / "temp")},
        }
    ]
    assert logs[0] == (
        f"[ComfyNodepacks] Asking Comfy Registry for "
        f"{nodepack.registry_id}@{nodepack.required_version}."
    )
    assert logs[-1].startswith(
        "[ComfyNodepacks][Timing] operation=registry_install_exact "
        f"nodepack={nodepack.nodepack_id.value} outcome=completed elapsed_ms="
    )


@pytest.mark.parametrize(
    ("error", "expected"),
    (
        (
            RegistryReleaseUnavailableError("release unavailable"),
            RegistryInstallOutcome.VERSION_UNAVAILABLE,
        ),
        (URLError("offline"), RegistryInstallOutcome.REGISTRY_UNREACHABLE),
        (RuntimeError("invalid descriptor"), RegistryInstallOutcome.FAILED),
    ),
)
def test_classifies_targeted_registry_failures_for_safe_fallback(
    tmp_path: Path,
    error: BaseException,
    expected: RegistryInstallOutcome,
) -> None:
    """Keep GitHub fallback policy deterministic for targeted acquisition failures."""

    client = _ReleaseClient(error)
    archive_installer = _ArchiveInstaller()

    result = ComfyNodepackRegistryInstaller(
        release_client=cast(ComfyRegistryReleaseClient, client),
        archive_installer=cast(TrustedNodepackArchiveInstaller, archive_installer),
    ).install_exact(
        manager_runtime=_runtime(tmp_path, tmp_path / "python.exe"),
        nodepack=CORE_COMFY_NODEPACKS[0],
        on_log=None,
        env=None,
    )

    assert result.outcome is expected
    assert archive_installer.calls == []


def test_archive_validation_failure_is_durable_without_remote_url(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Record bounded failure identity while keeping descriptor URLs out of logs."""

    nodepack = CORE_COMFY_NODEPACKS[0]
    release = ComfyRegistryRelease(
        node_id=nodepack.registry_id,
        version=nodepack.required_version,
        archive_url="https://cdn.comfy.org/private-token/node.zip",
    )
    archive_installer = _ArchiveInstaller(
        RuntimeError("archive source identity mismatch")
    )

    result = ComfyNodepackRegistryInstaller(
        release_client=cast(ComfyRegistryReleaseClient, _ReleaseClient(release)),
        archive_installer=cast(TrustedNodepackArchiveInstaller, archive_installer),
    ).install_exact(
        manager_runtime=_runtime(tmp_path, tmp_path / "python.exe"),
        nodepack=nodepack,
        on_log=None,
        env=None,
    )

    assert result.outcome is RegistryInstallOutcome.FAILED
    assert "reason_type=RuntimeError" in caplog.text
    assert release.archive_url not in caplog.text


def _runtime(workspace: Path, python: Path) -> ComfyManagerRuntime:
    """Build one validated integrated Manager runtime fixture."""

    return ComfyManagerRuntime(
        kind=ComfyManagerKind.INTEGRATED,
        workspace=workspace,
        python_executable=python,
        version="4.2.2",
    )

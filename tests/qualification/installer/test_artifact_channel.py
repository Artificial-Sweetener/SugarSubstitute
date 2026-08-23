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

"""Qualify trusted local candidate artifacts and cache boundaries."""

from __future__ import annotations

import json
from pathlib import Path
import ssl
import sys
import urllib.request

import pytest

from sugarsubstitute_shared.installer_qualification import (
    InstallerQualificationPlan,
)
from sugarsubstitute_shared.tls import EXTRA_CA_FILE_ENV, SystemTrustTlsContext
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError
from tools.ci.installer_ui_qualification import (
    prepare_qualification_evidence,
)
from tools.ci.local_release_server import LocalReleaseServer
from tools.ci.standalone_artifact_cache import (
    qualification_standalone_artifact_cache,
    standalone_cache_diagnostic_path,
)


def test_local_candidate_channel_uses_trusted_https_and_exact_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Temporary non-release assets should use the launcher's real HTTPS path."""

    release_root = tmp_path / "candidate"
    release_root.mkdir()
    (release_root / "manifest.json").write_text(
        '{"asset":"https://localhost.invalid/asset.zip","version":"9999.0.1"}\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    with LocalReleaseServer(
        release_root=release_root,
        certificate_root=Path("certificate"),
    ) as server:
        monkeypatch.setenv(EXTRA_CA_FILE_ENV, str(server.trust_bundle_path))
        context = SystemTrustTlsContext.create()
        with urllib.request.urlopen(
            server.manifest_url,
            timeout=5.0,
            context=context,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        legacy_context = ssl.create_default_context(
            cafile=str(server.trust_bundle_path)
        )
        with urllib.request.urlopen(
            server.manifest_url,
            timeout=5.0,
            context=legacy_context,
        ) as response:
            assert response.status == 200

        assert server.manifest_url == f"{server.base_url}/manifest.json"
        assert payload == {
            "asset": f"{server.base_url}/asset.zip",
            "version": "9999.0.1",
        }
        assert server.certificate_path.is_absolute()
        assert server.trust_bundle_path.is_absolute()
        requests = [
            json.loads(line)
            for line in server.request_log_path.read_text(encoding="utf-8").splitlines()
        ]
        assert [request["path"] for request in requests] == [
            "/manifest.json",
            "/manifest.json",
        ]
        assert (
            server.trust_bundle_path.read_text(encoding="ascii").count(
                "-----BEGIN CERTIFICATE-----"
            )
            > 1
        )


def test_qualification_evidence_is_absolute_across_process_working_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every process handoff should resolve evidence against the same location."""

    monkeypatch.chdir(tmp_path)

    evidence = prepare_qualification_evidence(
        install_root=Path("installed"),
        expected_version="1.2.3",
        endpoint_port=8188,
        phase="clean",
    )
    plan = InstallerQualificationPlan.from_environment(evidence.environment)

    assert plan is not None
    assert plan.install_root == (tmp_path / "installed").resolve()
    assert plan.event_log_path == evidence.event_log_path
    assert evidence.readiness_path.is_absolute()
    assert evidence.trace_path.is_absolute()
    assert evidence.event_log_path.is_absolute()
    assert plan.target_mode == "managed_local"
    assert plan.managed_workspace_path == (tmp_path / "installed" / "comfyui")
    assert plan.managed_model_root == (tmp_path / "installed" / "qualified-models")
    assert plan.force_cpu_mode is (sys.platform != "darwin")
    assert evidence.environment[
        "SUGAR_SUBSTITUTE_STARTUP_HARNESS_COMFY_OUTPUT_LOG"
    ] == str((tmp_path / "installed" / "managed-comfy-startup.log").resolve())


def test_clean_qualification_exchanges_only_complete_standalone_artifacts(
    tmp_path: Path,
) -> None:
    """Cached downloads should enter and leave the otherwise-clean install root."""

    install_root = tmp_path / "installed"
    external_cache = tmp_path / "ci-cache"
    cached_artifact = external_cache / "release" / "win-cpu" / "artifact.7z.001"
    cached_artifact.parent.mkdir(parents=True)
    cached_artifact.write_bytes(b"cached")
    (cached_artifact.parent / "artifact.7z.001.part").write_bytes(b"partial")

    with qualification_standalone_artifact_cache(
        install_root=install_root,
        external_cache_root=external_cache,
        timeout_seconds=5.0,
    ) as stage:
        assert stage is not None
        installed_artifact = (
            install_root
            / ".sugarsubstitute-cache"
            / "standalone"
            / "release"
            / "win-cpu"
            / "artifact.7z.001"
        )
        assert not installed_artifact.exists()
        ready_path = install_root / "launcher" / "config.json"
        ready_path.parent.mkdir(parents=True)
        ready_path.write_text("{}", encoding="utf-8")
        stage.wait_for_completion()
        stage.require_success()
        assert installed_artifact.read_bytes() == b"cached"
        assert not installed_artifact.with_name("artifact.7z.001.part").exists()
        installed_artifact.unlink()
        installed_artifact.write_bytes(b"verified replacement")

    assert cached_artifact.read_bytes() == b"verified replacement"
    assert (cached_artifact.parent / "artifact.7z.001.part").read_bytes() == b"partial"
    receipt = json.loads(
        standalone_cache_diagnostic_path(install_root).read_text(encoding="utf-8")
    )
    assert receipt["state"] == "staged_after_install_layout"
    assert receipt["ready_path_present"] is True
    assert receipt["source"]["total_bytes"] == len(b"cached")
    assert receipt["destination"]["total_bytes"] == len(b"cached")


def test_clean_qualification_rejects_cache_inside_install_root(tmp_path: Path) -> None:
    """The acceleration cache must not weaken clean-root isolation."""

    install_root = tmp_path / "installed"

    with pytest.raises(InstallerLifecycleError, match="outside the clean install"):
        with qualification_standalone_artifact_cache(
            install_root=install_root,
            external_cache_root=install_root / "cache",
            timeout_seconds=5.0,
        ):
            pass


def test_qualification_evidence_preserves_focused_timeout(tmp_path: Path) -> None:
    """Focused diagnostics should carry their exact total chain timeout."""

    evidence = prepare_qualification_evidence(
        install_root=tmp_path / "installed",
        expected_version="1.2.3",
        endpoint_port=8188,
        phase="clean",
        timeout_seconds=900.0,
    )

    assert evidence.plan.timeout_seconds == 900.0

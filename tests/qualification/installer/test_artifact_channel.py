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
from tools.ci.installer_ui_qualification import (
    prepare_qualification_evidence,
)
from tools.ci.local_release_server import LocalReleaseServer


def _write_release_channel(release_root: Path) -> tuple[dict[str, str], str]:
    """Write one production-addressed candidate channel with exact local bytes."""

    release_root.mkdir()
    asset_names = {
        "app": "SugarSubstitute-app-v9999.0.1.zip",
        "launcher": "SugarSubstitute-installer-payload-windows-x64-v9999.0.1.zip",
        "installer": "SugarSubstitute-9999.0.1-Windows-x64.exe",
    }
    for name in asset_names.values():
        (release_root / name).write_bytes(f"exact bytes for {name}".encode())
    public_root = (
        "https://github.com/Artificial-Sweetener/SugarSubstitute/"
        "releases/download/v9999.0.1"
    )

    def asset(name: str) -> dict[str, str | int]:
        """Describe one staged asset through its future production URL."""

        path = release_root / name
        return {
            "filename": name,
            "url": f"{public_root}/{name}",
            "sha256": "a" * 64,
            "size_bytes": path.stat().st_size,
        }

    source_manifest = (
        json.dumps(
            {
                "schema_version": 2,
                "channel": "stable",
                "version": "9999.0.1",
                "minimum_launcher_version": "0.1.0",
                "release_metadata": {"publication": "pending"},
                "app": asset(asset_names["app"]),
                "launchers": {"windows_x64": asset(asset_names["launcher"])},
                "installers": {"windows_x64_exe": asset(asset_names["installer"])},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    (release_root / "manifest.json").write_text(source_manifest, encoding="utf-8")
    return asset_names, source_manifest


def test_local_candidate_channel_uses_trusted_https_and_exact_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Temporary non-release assets should use the launcher's real HTTPS path."""

    release_root = tmp_path / "candidate"
    asset_names, source_manifest = _write_release_channel(release_root)
    manifest_path = release_root / "manifest.json"
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
        with urllib.request.urlopen(
            payload["app"]["url"],
            timeout=5.0,
            context=legacy_context,
        ) as response:
            assert response.read() == (release_root / asset_names["app"]).read_bytes()

        assert server.manifest_url == f"{server.base_url}/manifest.json"
        assert payload["version"] == "9999.0.1"
        assert payload["release_metadata"] == {"publication": "pending"}
        assert payload["app"]["url"] == f"{server.base_url}/{asset_names['app']}"
        assert payload["launchers"]["windows_x64"]["url"] == (
            f"{server.base_url}/{asset_names['launcher']}"
        )
        assert payload["installers"]["windows_x64_exe"]["url"] == (
            f"{server.base_url}/{asset_names['installer']}"
        )
        assert manifest_path.read_text(encoding="utf-8") == source_manifest
        assert server.certificate_path.is_absolute()
        assert server.trust_bundle_path.is_absolute()
        assert (
            server.trust_bundle_path.read_text(encoding="ascii").count(
                "-----BEGIN CERTIFICATE-----"
            )
            > 1
        )
        server.require_completed_requests(
            (
                "/manifest.json",
                "/manifest.json",
                f"/{asset_names['app']}",
            ),
            timeout_seconds=5.0,
        )

    requests = [
        json.loads(line)
        for line in server.request_log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [(request["event"], request["path"]) for request in requests] == [
        ("request.started", "/manifest.json"),
        ("request.completed", "/manifest.json"),
        ("request.started", "/manifest.json"),
        ("request.completed", "/manifest.json"),
        ("request.started", f"/{asset_names['app']}"),
        ("request.completed", f"/{asset_names['app']}"),
    ]
    assert all(
        request["duration_ns"] >= 0
        for request in requests
        if request["event"] == "request.completed"
    )


def test_local_candidate_channels_use_independent_dynamic_ports(tmp_path: Path) -> None:
    """Concurrent qualification owners must never contend for a fixed port."""

    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    _write_release_channel(first_root)
    _write_release_channel(second_root)

    with LocalReleaseServer(
        release_root=first_root,
        certificate_root=tmp_path / "first-certificate",
    ) as first_server:
        with LocalReleaseServer(
            release_root=second_root,
            certificate_root=tmp_path / "second-certificate",
        ) as second_server:
            assert first_server.base_url != second_server.base_url
            assert first_server.manifest_url.endswith("/manifest.json")
            assert second_server.manifest_url.endswith("/manifest.json")


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

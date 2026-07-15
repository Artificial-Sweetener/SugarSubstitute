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

"""Run a private HTTPS proof of the launcher app-update flow."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import ssl
import subprocess
import sys
import threading
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Self

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout  # noqa: E402
from launcher.sugarsubstitute_launcher.runtime import RuntimeProvisioningResult  # noqa: E402
from launcher.sugarsubstitute_launcher.runtime_reconciliation import (  # noqa: E402
    RuntimeReconciliationProgress,
)

DEFAULT_HARNESS_ROOT = REPO_ROOT.parent / "SugarSubstitute-update-harness"
OPENSSL_CONFIG_NAME = "localhost-openssl.cnf"
CERT_NAME = "localhost-cert.pem"
KEY_NAME = "localhost-key.pem"
OLD_VERSION = "0.4.0"
NEW_VERSION = "0.4.1"


class HttpsUpdateHarnessError(RuntimeError):
    """Raised when the HTTPS update proof cannot complete."""


@dataclass(frozen=True, slots=True)
class HttpsUpdateHarnessResult:
    """Describe one completed HTTPS update proof."""

    harness_root: Path
    install_root: Path
    manifest_url: str
    asset_url: str
    request_paths: tuple[str, ...]
    installed_version: str


class RecordingRuntimeReconciler:
    """Record runtime reconciliation without running uv in the harness."""

    def __init__(self) -> None:
        """Create an empty reconciliation log."""

        self.layouts: list[InstallLayout] = []

    def reconcile(
        self,
        *,
        layout: InstallLayout,
        progress: RuntimeReconciliationProgress,
    ) -> RuntimeProvisioningResult:
        """Record one reconciliation call and return a lightweight marker."""

        _ = progress
        self.layouts.append(layout)
        return RuntimeProvisioningResult(
            python_executable=layout.runtime_python,
            requirements_path=layout.app_dir / "requirements.txt",
        )


class RecordingProgress:
    """Record launcher update progress messages."""

    def __init__(self) -> None:
        """Create an empty progress log."""

        self.lines: list[str] = []

    def append_log(self, line: str) -> None:
        """Record one progress line."""

        self.lines.append(line)


class RecordingHttpsServer:
    """Serve one directory over HTTPS and record request paths."""

    def __init__(self, *, root: Path, cert_path: Path, key_path: Path) -> None:
        """Create a stopped local HTTPS server."""

        self._root = root
        self._request_paths: list[str] = []
        handler = self._handler_class()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=cert_path, keyfile=key_path)
        self._server.socket = context.wrap_socket(
            self._server.socket,
            server_side=True,
        )
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        """Return the HTTPS origin URL for this server."""

        return f"https://localhost:{self._server.server_port}"

    @property
    def request_paths(self) -> tuple[str, ...]:
        """Return all served request paths."""

        return tuple(self._request_paths)

    def __enter__(self) -> Self:
        """Start serving requests."""

        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="sugarsubstitute-https-update-harness",
            daemon=True,
        )
        self._thread.start()
        return self

    def __exit__(self, *_args: object) -> None:
        """Stop serving requests."""

        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _handler_class(self) -> type[SimpleHTTPRequestHandler]:
        """Create a handler bound to this server root and request log."""

        root = self._root
        request_paths = self._request_paths

        class _Handler(SimpleHTTPRequestHandler):
            """Serve files from the harness release directory."""

            def __init__(self, *args: Any, **kwargs: Any) -> None:
                """Initialize the handler with the release directory."""

                super().__init__(*args, directory=str(root), **kwargs)

            def do_GET(self) -> None:
                """Record and serve one GET request."""

                request_paths.append(self.path)
                super().do_GET()

            def log_message(self, _format: str, *_args: object) -> None:
                """Suppress standard HTTP request logging."""

        return _Handler


def run_https_update_harness(
    *,
    harness_root: Path = DEFAULT_HARNESS_ROOT,
    keep_artifacts: bool = False,
) -> HttpsUpdateHarnessResult:
    """Run the private HTTPS update flow proof."""

    from launcher.sugarsubstitute_launcher.config import LauncherConfig
    from launcher.sugarsubstitute_launcher.config import ReleaseSourceConfig
    from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
    from launcher.sugarsubstitute_launcher.payload import AppPayloadInstaller
    from launcher.sugarsubstitute_launcher.release_sources import (
        release_source_from_config,
    )
    from launcher.sugarsubstitute_launcher.update_orchestrator import (
        LauncherUpdateOrchestrator,
    )
    from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState

    resolved_root = harness_root.expanduser().resolve()
    _prepare_harness_root(resolved_root)
    install_root = resolved_root / "install" / "SugarSubstitute"
    release_root = resolved_root / "release"
    cert_root = resolved_root / "cert"
    release_root.mkdir(parents=True, exist_ok=True)
    cert_root.mkdir(parents=True, exist_ok=True)

    layout = InstallLayout.from_root(install_root)
    _write_installed_app(layout.app_dir, OLD_VERSION)
    LauncherUpdateState(installed_app_version=OLD_VERSION).save(layout.state_path)

    app_zip = _write_app_payload_zip(release_root, NEW_VERSION)
    cert_path, key_path = _create_localhost_certificate(cert_root)
    previous_ssl_cert_file = os.environ.get("SSL_CERT_FILE")
    os.environ["SSL_CERT_FILE"] = str(cert_path)
    try:
        with RecordingHttpsServer(
            root=release_root,
            cert_path=cert_path,
            key_path=key_path,
        ) as server:
            asset_url = f"{server.base_url}/{app_zip.name}"
            manifest_url = f"{server.base_url}/manifest.json"
            _write_manifest(
                release_root / "manifest.json",
                version=NEW_VERSION,
                app_zip=app_zip,
                app_url=asset_url,
            )
            config = LauncherConfig.from_layout(
                layout=layout,
                release_source=ReleaseSourceConfig(
                    kind="github_release_manifest",
                    manifest_url=manifest_url,
                ),
            )
            runtime_reconciler = RecordingRuntimeReconciler()
            progress = RecordingProgress()
            result = LauncherUpdateOrchestrator(
                payload_installer=AppPayloadInstaller(),
                runtime_reconciler=runtime_reconciler,
                now=_fixed_now,
            ).run(
                layout=layout,
                config=config,
                release_source=release_source_from_config(config.release_source),
                no_update_check=False,
                progress=progress,
            )
            _assert_update_result(
                result=result,
                layout=layout,
                runtime_reconciler=runtime_reconciler,
                progress=progress,
                request_paths=server.request_paths,
            )
            return HttpsUpdateHarnessResult(
                harness_root=resolved_root,
                install_root=install_root,
                manifest_url=manifest_url,
                asset_url=asset_url,
                request_paths=server.request_paths,
                installed_version=LauncherUpdateState.load(
                    layout.state_path
                ).installed_app_version
                or "",
            )
    finally:
        if previous_ssl_cert_file is None:
            os.environ.pop("SSL_CERT_FILE", None)
        else:
            os.environ["SSL_CERT_FILE"] = previous_ssl_cert_file
        if not keep_artifacts:
            shutil.rmtree(resolved_root, ignore_errors=True)


def _prepare_harness_root(harness_root: Path) -> None:
    """Create a clean harness root after validating the target path."""

    if harness_root.anchor == str(harness_root):
        raise HttpsUpdateHarnessError(f"Refusing to clean root path: {harness_root}")
    if harness_root.name != DEFAULT_HARNESS_ROOT.name:
        raise HttpsUpdateHarnessError(
            f"Harness root must be named {DEFAULT_HARNESS_ROOT.name}: {harness_root}"
        )
    if harness_root.exists():
        shutil.rmtree(harness_root)
    harness_root.mkdir(parents=True)


def _write_installed_app(app_dir: Path, version: str) -> None:
    """Write a minimal existing app payload."""

    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "main.py").write_text(f"print('old {version}')\n", encoding="utf-8")
    (app_dir / "requirements.txt").write_text("PySide6\n", encoding="utf-8")
    (app_dir / "sitecustomize.py").write_text("# old\n", encoding="utf-8")
    (app_dir / "substitute").mkdir()
    (app_dir / "substitute" / "__init__.py").write_text(
        '"""Old payload."""\n',
        encoding="utf-8",
    )
    (app_dir / "third_party").mkdir()
    (app_dir / "third_party" / "manifest.toml").write_text(
        "[[component]]\n",
        encoding="utf-8",
    )


def _write_app_payload_zip(release_root: Path, version: str) -> Path:
    """Write a minimal new app payload zip."""

    app_zip = release_root / f"SugarSubstitute-app-v{version}.zip"
    with zipfile.ZipFile(app_zip, "w") as archive:
        archive.writestr("main.py", f"print('new {version}')\n")
        archive.writestr("requirements.txt", "PySide6\n")
        archive.writestr("sitecustomize.py", "# new\n")
        archive.writestr("substitute/__init__.py", '"""New payload."""\n')
        archive.writestr("third_party/manifest.toml", "[[component]]\n")
    return app_zip


def _write_manifest(
    manifest_path: Path,
    *,
    version: str,
    app_zip: Path,
    app_url: str,
) -> None:
    """Write the HTTPS release manifest served by the harness."""

    manifest = {
        "schema_version": 1,
        "channel": "stable",
        "version": version,
        "minimum_launcher_version": "0.1.0",
        "app": {
            "filename": app_zip.name,
            "url": app_url,
            "sha256": _sha256(app_zip),
            "size_bytes": app_zip.stat().st_size,
        },
        "launchers": {},
        "installers": {},
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _create_localhost_certificate(cert_root: Path) -> tuple[Path, Path]:
    """Create a self-signed localhost certificate trusted by this process."""

    config_path = cert_root / OPENSSL_CONFIG_NAME
    cert_path = cert_root / CERT_NAME
    key_path = cert_root / KEY_NAME
    config_path.write_text(
        "\n".join(
            [
                "[req]",
                "distinguished_name = dn",
                "x509_extensions = v3_req",
                "prompt = no",
                "[dn]",
                "CN = localhost",
                "[v3_req]",
                "basicConstraints = critical, CA:TRUE",
                "keyUsage = critical, digitalSignature, keyEncipherment, keyCertSign",
                "extendedKeyUsage = serverAuth",
                "subjectAltName = @alt_names",
                "[alt_names]",
                "DNS.1 = localhost",
                "IP.1 = 127.0.0.1",
                "",
            ]
        ),
        encoding="utf-8",
    )
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-keyout",
            str(key_path),
            "-out",
            str(cert_path),
            "-config",
            str(config_path),
            "-sha256",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return cert_path, key_path


def _assert_update_result(
    *,
    result: object,
    layout: object,
    runtime_reconciler: RecordingRuntimeReconciler,
    progress: RecordingProgress,
    request_paths: tuple[str, ...],
) -> None:
    """Validate that the real update flow completed."""

    from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
    from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState

    if not isinstance(layout, InstallLayout):
        raise HttpsUpdateHarnessError("Harness received invalid layout.")
    if not bool(getattr(result, "checked_manifest", False)):
        raise HttpsUpdateHarnessError("Update did not check the manifest.")
    if not bool(getattr(result, "installed_update", False)):
        raise HttpsUpdateHarnessError(f"Update did not install: {result!r}")
    state = LauncherUpdateState.load(layout.state_path)
    if state.installed_app_version != NEW_VERSION:
        raise HttpsUpdateHarnessError(f"Unexpected state version: {state}")
    if not runtime_reconciler.layouts:
        raise HttpsUpdateHarnessError("Runtime reconciliation did not run.")
    if "/manifest.json" not in request_paths:
        raise HttpsUpdateHarnessError(f"Manifest was not requested: {request_paths}")
    expected_zip = f"/SugarSubstitute-app-v{NEW_VERSION}.zip"
    if expected_zip not in request_paths:
        raise HttpsUpdateHarnessError(f"App payload was not requested: {request_paths}")
    main_text = (layout.app_dir / "main.py").read_text(encoding="utf-8")
    if f"new {NEW_VERSION}" not in main_text:
        raise HttpsUpdateHarnessError("Installed app payload was not promoted.")
    previous_text = (layout.root / "app_previous" / "main.py").read_text(
        encoding="utf-8"
    )
    if f"old {OLD_VERSION}" not in previous_text:
        raise HttpsUpdateHarnessError("Previous payload was not preserved.")
    expected_progress = [
        "Checking for SugarSubstitute updates.",
        f"Installing SugarSubstitute {NEW_VERSION}.",
        "Preparing SugarSubstitute runtime.",
        f"Installed SugarSubstitute {NEW_VERSION}.",
    ]
    if progress.lines != expected_progress:
        raise HttpsUpdateHarnessError(f"Unexpected progress lines: {progress.lines}")


def _fixed_now() -> datetime:
    """Return a deterministic harness timestamp."""

    return datetime(2026, 7, 7, 12, tzinfo=UTC)


def _sha256(path: Path) -> str:
    """Return the SHA256 digest for one file."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line HTTPS update harness."""

    args = _parse_args(argv if argv is not None else sys.argv[1:])
    result = run_https_update_harness(
        harness_root=args.harness_root,
        keep_artifacts=args.keep_artifacts,
    )
    print("HTTPS update harness passed.")
    print(f"manifest_url={result.manifest_url}")
    print(f"asset_url={result.asset_url}")
    print(f"installed_version={result.installed_version}")
    print(f"requests={','.join(result.request_paths)}")
    if args.keep_artifacts:
        print(f"harness_root={result.harness_root}")
        print(f"install_root={result.install_root}")
    return 0


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse command-line options."""

    parser = argparse.ArgumentParser(
        description="Run a headless private HTTPS launcher update proof.",
    )
    parser.add_argument(
        "--harness-root",
        type=Path,
        default=DEFAULT_HARNESS_ROOT,
        help="Disposable harness folder. Must be named SugarSubstitute-update-harness.",
    )
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Keep the disposable release/install folders for inspection.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())

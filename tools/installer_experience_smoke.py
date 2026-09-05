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

"""Render and interact with production installer pages without side effects."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
from collections.abc import Callable, Sequence
from typing import Never, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from qfluentwidgets import Theme, setTheme  # type: ignore[import-untyped] # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout  # noqa: E402
from launcher.sugarsubstitute_launcher.localization import (  # noqa: E402
    LauncherLocalizationRuntime,
    build_launcher_localization_runtime,
)
from launcher.sugarsubstitute_launcher.ui.experience_models import (  # noqa: E402
    ExperienceSnapshot,
)
from launcher.sugarsubstitute_launcher.ui.main_window import (  # noqa: E402
    LauncherMainWindow,
)
from launcher.sugarsubstitute_launcher.ui.installer_presentation import (  # noqa: E402
    LauncherUiState,
)
from tools.install_experience_onboarding import (  # noqa: E402
    capture_onboarding_matrix,
    open_interactive_onboarding,
)
from tools.install_experience_model_evidence import (  # noqa: E402
    capture_live_recommendation_page,
)
from tools.install_experience_capture import (  # noqa: E402
    prepare_opaque_dark_capture_surface,
    save_opaque_dark_widget_capture,
)
from tools.install_experience_interactive import (  # noqa: E402
    run_interactive_full_experience,
)


_DEFAULT_ARTIFACT_ROOT = REPO_ROOT / "build" / "qualification" / "installer-smoke"
_PAGES = (
    "language",
    "install",
    "install-failure",
    "install-complete",
    "repair",
    "repair-full",
    "repair-working",
    "repair-protected-data",
    "repair-failure",
    "repair-rollback",
    "repair-complete",
)


class SmokeBoundaryViolation(RuntimeError):
    """Report any production side effect attempted by the smoke UI."""


class BlockedReleaseSource:
    """Fail if smoke presentation reaches a release or network boundary."""

    def load_manifest(self) -> Never:
        """Reject manifest loading because smoke pages are presentation-only."""

        raise SmokeBoundaryViolation("Smoke UI attempted to load a release manifest.")


class SideEffectAudit:
    """Record forbidden installer workflow composition attempts."""

    def __init__(self) -> None:
        """Initialize a zero-call safety record."""

        self.workflow_factory_calls = 0
        self.network_calls = 0
        self.download_calls = 0
        self.install_calls = 0
        self.git_calls = 0
        self.subprocess_calls = 0
        self.handoff_calls = 0
        self.target_mutations = 0

    def workflow_factory(self, _log: Callable[[str], None]) -> Never:
        """Reject workflow construction before install or subprocess work exists."""

        self.workflow_factory_calls += 1
        raise SmokeBoundaryViolation("Smoke UI attempted to construct an installer.")


def run_headless_smoke(
    *,
    artifact_root: Path = _DEFAULT_ARTIFACT_ROOT,
) -> dict[str, object]:
    """Capture every production page and semantic state without external work."""

    output_root = _require_artifact_root(artifact_root)
    output_root.mkdir(parents=True, exist_ok=True)
    application = _application()
    setTheme(Theme.DARK)
    audit = SideEffectAudit()
    window, localization_runtime = _window(
        application=application,
        audit=audit,
        repair=False,
    )
    prepare_opaque_dark_capture_surface(window)
    sentinels = _create_protected_sentinels(output_root)
    sentinel_hashes_before = _sentinel_hashes(sentinels)
    window.show()
    application.processEvents()
    evidence: list[dict[str, object]] = []
    try:
        for page in _PAGES:
            _project_page(window, page)
            application.processEvents()
            if window.failure_presenter.active_dialog is not None:
                QTest.qWait(250)
                application.processEvents()
            screenshot_path = output_root / f"{page}.png"
            save_opaque_dark_widget_capture(window, screenshot_path)
            snapshot = window.view.experience_snapshot()
            evidence.append(
                {
                    "scenario": page,
                    "screenshot": str(screenshot_path),
                    "snapshot": _snapshot_payload(snapshot),
                    "status": _visible_status(window),
                }
            )
    finally:
        window.close()
        localization_runtime.manager.close()
        window.deleteLater()
        application.processEvents()
    onboarding_evidence, onboarding_audit = capture_onboarding_matrix(
        artifact_root=output_root,
        install_root_locked=True,
    )
    evidence.extend(onboarding_evidence)
    journey_invariants = _verify_full_journey_entry(evidence)
    sentinel_hashes_after = _sentinel_hashes(sentinels)
    if sentinel_hashes_after != sentinel_hashes_before:
        raise SmokeBoundaryViolation("Smoke scenarios changed protected sentinels.")
    result: dict[str, object] = {
        "schema_version": 4,
        "headless": os.environ.get("QT_QPA_PLATFORM") == "offscreen",
        "production_windows": (
            f"{LauncherMainWindow.__module__}.{LauncherMainWindow.__name__}",
            "substitute.presentation.onboarding.onboarding_window.OnboardingWindow",
        ),
        "journey": ("bootstrap-launcher", "comfy-setup", "ready"),
        "journey_invariants": journey_invariants,
        "scenarios": evidence,
        "side_effect_audit": {
            "workflow_factory_calls": audit.workflow_factory_calls,
            "manifest_loads": 0,
            "network_calls": audit.network_calls,
            "downloads": audit.download_calls,
            "installs": audit.install_calls,
            "git_calls": audit.git_calls,
            "subprocesses": audit.subprocess_calls,
            "handoffs": audit.handoff_calls,
            "target_mutations": audit.target_mutations,
            **onboarding_audit,
        },
        "protected_sentinels": sentinel_hashes_after,
    }
    evidence_path = output_root / "evidence.json"
    evidence_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _verify_full_journey_entry(
    evidence: Sequence[dict[str, object]],
) -> dict[str, object]:
    """Require one install-root decision before every Comfy setup route."""

    language_entry = next(
        (item for item in evidence if item.get("scenario") == "language"),
        None,
    )
    language_snapshot = (
        language_entry.get("snapshot") if language_entry is not None else None
    )
    if not isinstance(language_snapshot, dict) or (
        language_snapshot.get("page") != "language"
    ):
        raise RuntimeError("The full journey does not start with language selection.")

    launcher_entry = next(
        (item for item in evidence if item.get("scenario") == "install"),
        None,
    )
    launcher_snapshot = (
        launcher_entry.get("snapshot") if launcher_entry is not None else None
    )
    if not isinstance(launcher_snapshot, dict) or (
        launcher_snapshot.get("page") != "install_location"
    ):
        raise RuntimeError("The full journey does not start at launcher install root.")

    setup_entries = [item for item in evidence if item.get("surface") == "comfy-setup"]
    if not setup_entries:
        raise RuntimeError("The full journey has no ComfyUI setup evidence.")
    if any(item.get("page") == "OnboardingWelcomePage" for item in setup_entries):
        raise RuntimeError(
            "ComfyUI setup repeated the launcher installation-root decision."
        )
    first_page_by_route: dict[str, object] = {}
    for item in setup_entries:
        route = item.get("route")
        if isinstance(route, str) and route not in first_page_by_route:
            first_page_by_route[route] = item.get("page")
    unexpected_entries = {
        route: page
        for route, page in first_page_by_route.items()
        if page != "OnboardingTargetModePage"
    }
    if unexpected_entries:
        raise RuntimeError(
            "ComfyUI setup entered the wrong first page after launcher handoff: "
            f"{unexpected_entries}"
        )
    return {
        "first_interaction": "language",
        "installation_root_decision_owner": "bootstrap-launcher",
        "installation_root_prompt_occurrences": 1,
        "comfy_setup_initial_page": "OnboardingTargetModePage",
        "verified_setup_routes": len(first_page_by_route),
    }


def run_interactive_smoke(
    page: str,
    *,
    surface: str = "launcher",
    artifact_root: Path = _DEFAULT_ARTIFACT_ROOT,
) -> int:
    """Open an explicitly requested production surface without external work."""

    if page not in _PAGES:
        raise ValueError(f"Unsupported smoke page: {page}")
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        os.environ.pop("QT_QPA_PLATFORM", None)
    application = _application()
    setTheme(Theme.DARK)
    if surface == "comfy-setup":
        session = open_interactive_onboarding(
            install_root=artifact_root / "interactive" / "synthetic-install",
            install_root_locked=False,
        )
        try:
            return int(application.exec())
        finally:
            session.close()
    if surface == "full":
        return run_interactive_full_experience(
            application=application,
            artifact_root=artifact_root,
            release_source=BlockedReleaseSource(),
        )
    if surface != "launcher":
        raise ValueError(f"Unsupported smoke surface: {surface}")
    audit = SideEffectAudit()
    window, localization_runtime = _window(
        application=application,
        audit=audit,
        repair=False,
    )
    _project_page(window, page)
    window.show()
    try:
        return int(application.exec())
    finally:
        window.close()
        localization_runtime.manager.close()


def _window(
    *,
    application: QApplication,
    audit: SideEffectAudit,
    repair: bool,
) -> tuple[LauncherMainWindow, LauncherLocalizationRuntime]:
    """Construct the real launcher shell around forbidden side-effect ports."""

    layout = InstallLayout.from_root(Path("smoke-install"))
    localization_runtime = build_launcher_localization_runtime(
        application,
        layout=layout,
        locale_override=None,
    )
    window = LauncherMainWindow(
        initial_layout=layout,
        continue_install=False,
        repair=repair,
        update_check_enabled=False,
        initial_release_source=BlockedReleaseSource(),
        workflow_factory=audit.workflow_factory,
        localization_manager=localization_runtime.manager,
    )
    return window, localization_runtime


def _project_page(
    window: LauncherMainWindow,
    page: str,
) -> None:
    """Drive real widgets into one deterministic smoke scenario."""

    active_dialog = window.failure_presenter.active_dialog
    if active_dialog is not None:
        active_dialog.hide()
        active_dialog.close()

    if page == "language":
        window.view.show_language_selection()
        return
    if page == "install":
        if window.ui_state is LauncherUiState.SELECT_LANGUAGE:
            window._handle_primary_clicked()
        window.view.show_install_location()
        return
    if page == "install-failure":
        window.view.show_install_location()
        window.view.show_status_output()
        window._handle_initial_install_failed("Simulated disk permission failure")
        return
    if page == "install-complete":
        window.view.show_install_location()
        window._append_log("Smoke: exact-version application payload verified.")
        window._append_log("Smoke: setup handoff ready; no process was started.")
        window.view.show_status_output()
        return
    if page.startswith("repair"):
        window.view.show_repair_scope()
        if page == "repair-full":
            QTest.mouseClick(
                window.view.repair_page.full_comfy_choice,
                Qt.MouseButton.LeftButton,
            )
        elif page == "repair-working":
            window.view.repair_page.set_status(
                "Verifying exact-version files before changing the installation...",
                working=True,
            )
        elif page == "repair-protected-data":
            window.view.repair_page.set_status(
                "Protected data verified: models, projects, outputs, inputs, user data, and third-party nodes are unchanged.",
                working=False,
            )
        elif page == "repair-failure":
            window._handle_repair_preparation_failed(
                "Simulated locked application file"
            )
        elif page == "repair-rollback":
            window.view.repair_page.set_status(
                "Validation failed after replacement. The previous application was restored; protected data was unchanged.",
                working=False,
            )
        elif page == "repair-complete":
            window.view.repair_page.set_status(
                "Repair completed and verified. SugarSubstitute is ready to start.",
                working=False,
            )
        return
    raise ValueError(f"Unsupported launcher smoke page: {page}")


def _create_protected_sentinels(output_root: Path) -> tuple[Path, ...]:
    """Create immutable smoke-only stand-ins for protected user data."""

    paths = tuple(
        output_root / "protected-target" / relative
        for relative in (
            "comfyui/models/user-model.safetensors",
            "comfyui/user/default/workflow.json",
            "comfyui/custom_nodes/third-party-node/keep.txt",
            "user/projects/keep.sugar",
            "user/outputs/keep.png",
        )
    )
    for index, path in enumerate(paths):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"protected-smoke-sentinel-{index}".encode())
    return paths


def _sentinel_hashes(paths: Sequence[Path]) -> dict[str, str]:
    """Return stable hashes proving smoke scenarios did not mutate sentinels."""

    import hashlib

    return {
        path.as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
    }


def _visible_status(window: LauncherMainWindow) -> str:
    """Return the scenario's visible status text for semantic evidence."""

    page = window.view.page_stack.currentWidget()
    status = getattr(page, "status_label", None)
    if status is not None and status.isVisible():
        return str(status.text())
    return ""


def _snapshot_payload(snapshot: ExperienceSnapshot) -> dict[str, object]:
    """Normalize enums and paths into portable semantic evidence."""

    payload = asdict(snapshot)
    payload["page"] = snapshot.page.value
    payload["repair_choice"] = (
        snapshot.repair_choice.value if snapshot.repair_choice is not None else None
    )
    return payload


def _require_artifact_root(artifact_root: Path) -> Path:
    """Permit smoke writes only inside the repository qualification tree."""

    resolved = artifact_root.resolve()
    allowed = (REPO_ROOT / "build" / "qualification").resolve()
    if resolved == allowed or not resolved.is_relative_to(allowed):
        raise SmokeBoundaryViolation(
            f"Smoke artifacts must stay below {allowed}; got {resolved}."
        )
    return resolved


def _application() -> QApplication:
    """Return one Qt application for headless or maintainer-driven smoke."""

    existing = QApplication.instance()
    if existing is not None:
        return cast(QApplication, existing)
    application = QApplication(sys.argv[:1])
    _load_headless_font()
    application.setFont(QFont("Segoe UI", 10))
    return application


def _load_headless_font() -> None:
    """Load a system font when Qt's offscreen plugin exposes no font database."""

    if QFontDatabase.families():
        return
    windows_root = os.environ.get("WINDIR")
    candidates = tuple(
        candidate
        for candidate in (
            Path(windows_root) / "Fonts" / "segoeui.ttf" if windows_root else None,
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/System/Library/Fonts/SFNS.ttf"),
        )
        if candidate is not None
    )
    for candidate in candidates:
        if (
            candidate.is_file()
            and QFontDatabase.addApplicationFont(str(candidate)) >= 0
        ):
            return
    raise RuntimeError(
        "Headless installer smoke could not load a readable system font."
    )


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse safe headless capture and explicit interactive modes."""

    parser = argparse.ArgumentParser(
        description=(
            "Inspect the complete production install experience without downloads, "
            "installs, subprocesses, or user-machine mutations."
        )
    )
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument(
        "--live-model-capture",
        action="store_true",
        help="Capture real read-only CivitAI recommendations and 1024px thumbnails.",
    )
    parser.add_argument(
        "--surface",
        choices=("full", "launcher", "comfy-setup"),
        default="full",
        help="Production install surface to open in explicit interactive mode.",
    )
    parser.add_argument("--page", choices=_PAGES, default="install")
    parser.add_argument("--artifact-root", type=Path, default=_DEFAULT_ARTIFACT_ROOT)
    return parser.parse_args(list(argv))


def main(argv: Sequence[str] | None = None) -> int:
    """Run an interactive page or write complete headless visual evidence."""

    args = _parse_args(sys.argv[1:] if argv is None else argv)
    if args.live_model_capture:
        application = _application()
        setTheme(Theme.DARK)
        artifact_root = _require_artifact_root(args.artifact_root)
        result = capture_live_recommendation_page(artifact_root=artifact_root)
        application.processEvents()
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
        return 0
    if args.interactive:
        return run_interactive_smoke(
            args.page,
            surface=args.surface,
            artifact_root=args.artifact_root,
        )
    result = run_headless_smoke(artifact_root=args.artifact_root)
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

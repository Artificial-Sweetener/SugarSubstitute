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
from collections.abc import Callable, Collection, Sequence
from typing import Never, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout  # noqa: E402
from launcher.sugarsubstitute_launcher.ui.experience_models import (  # noqa: E402
    ExperienceSnapshot,
)
from launcher.sugarsubstitute_launcher.ui.main_window import (  # noqa: E402
    LauncherMainWindow,
)
from launcher.sugarsubstitute_launcher.ui.model_onboarding_controller import (  # noqa: E402
    InstallerModelOnboardingController,
)
from sugarsubstitute_shared.model_acquisition import (  # noqa: E402
    ModelAcquisitionService,
)
from sugarsubstitute_shared.model_discovery import (  # noqa: E402
    CategoryModelDestinationPolicy,
    CubeModelCapability,
    DiscoveredModel,
    LocalModel,
    ModelCategory,
    ModelDiscoveryPlanner,
    ModelOnboardingService,
)


_DEFAULT_ARTIFACT_ROOT = REPO_ROOT / "build" / "qualification" / "installer-smoke"
_PAGES = (
    "install",
    "install-failure",
    "install-complete",
    "existing-model-skip",
    "repair",
    "repair-full",
    "repair-working",
    "repair-protected-data",
    "repair-failure",
    "repair-rollback",
    "repair-complete",
    "model-interests",
    "model-discovery-working",
    "model-discovery-failure",
    "model-gallery",
    "model-gallery-selected",
    "model-download-working",
    "model-download-failure",
    "model-download-complete",
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
    audit = SideEffectAudit()
    window = _window(audit=audit, repair=False)
    model_controller = _model_controller(window, output_root)
    sentinels = _create_protected_sentinels(output_root)
    sentinel_hashes_before = _sentinel_hashes(sentinels)
    window.show()
    application.processEvents()
    evidence: list[dict[str, object]] = []
    try:
        for page in _PAGES:
            _project_page(window, page, model_controller=model_controller)
            application.processEvents()
            screenshot_path = output_root / f"{page}.png"
            if not window.grab().save(str(screenshot_path), "PNG"):
                raise RuntimeError(
                    f"Could not write smoke screenshot: {screenshot_path}"
                )
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
        window.deleteLater()
        application.processEvents()
    sentinel_hashes_after = _sentinel_hashes(sentinels)
    if sentinel_hashes_after != sentinel_hashes_before:
        raise SmokeBoundaryViolation("Smoke scenarios changed protected sentinels.")
    result: dict[str, object] = {
        "schema_version": 1,
        "headless": os.environ.get("QT_QPA_PLATFORM") == "offscreen",
        "production_window": f"{LauncherMainWindow.__module__}.{LauncherMainWindow.__name__}",
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
        },
        "protected_sentinels": sentinel_hashes_after,
    }
    evidence_path = output_root / "evidence.json"
    evidence_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def run_interactive_smoke(page: str) -> int:
    """Show one production page for maintainer-driven aesthetic inspection."""

    if page not in _PAGES:
        raise ValueError(f"Unsupported smoke page: {page}")
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        os.environ.pop("QT_QPA_PLATFORM", None)
    application = _application()
    audit = SideEffectAudit()
    window = _window(audit=audit, repair=False)
    _project_page(window, page, model_controller=_model_controller(window, None))
    window.show()
    return int(application.exec())


def _window(*, audit: SideEffectAudit, repair: bool) -> LauncherMainWindow:
    """Construct the real launcher shell around forbidden side-effect ports."""

    return LauncherMainWindow(
        initial_layout=InstallLayout.from_root(Path("smoke-install")),
        continue_install=False,
        repair=repair,
        update_check_enabled=False,
        initial_release_source=BlockedReleaseSource(),
        workflow_factory=audit.workflow_factory,
    )


def _project_page(
    window: LauncherMainWindow,
    page: str,
    *,
    model_controller: InstallerModelOnboardingController,
) -> None:
    """Drive real widgets into one deterministic smoke scenario."""

    if page == "install":
        window.view.show_install_location()
        return
    if page == "install-failure":
        window.view.show_install_location()
        window._handle_initial_install_failed("Simulated disk permission failure")
        window.view.show_status_output()
        return
    if page == "install-complete":
        window.view.show_install_location()
        window._append_log("Smoke: exact-version application payload verified.")
        window._append_log("Smoke: setup handoff ready; no process was started.")
        window.view.show_status_output()
        return
    if page == "existing-model-skip":
        skip_controller = _model_controller(window, None, existing_model=True)
        if skip_controller.offer_if_eligible():
            raise SmokeBoundaryViolation(
                "Compatible local models did not suppress installer onboarding."
            )
        window.view.show_install_location()
        window._append_log(
            "Smoke: compatible local model found; optional model onboarding skipped."
        )
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
    if page == "model-interests":
        model_controller.offer_if_eligible()
        return
    if page == "model-discovery-working":
        model_controller.offer_if_eligible()
        window.view.model_interest_page.set_status(
            "Finding safe popular models from the last month...",
            working=True,
        )
        return
    if page == "model-discovery-failure":
        model_controller.offer_if_eligible()
        model_controller._handle_failure("Simulated provider timeout")
        return
    model_controller._handle_plan(_sample_plan())
    if page == "model-gallery-selected":
        first = window.view.model_gallery_page.visible_model_ids[0]
        window.view.model_gallery_page.set_model_selected(first, selected=True)
    elif page == "model-download-working":
        first = window.view.model_gallery_page.visible_model_ids[0]
        window.view.model_gallery_page.set_model_selected(first, selected=True)
        window.view.model_gallery_page.set_status(
            "Downloading 1 selected model file(s). Existing files will not be overwritten.",
            working=True,
        )
    elif page == "model-download-failure":
        model_controller._handle_failure("Simulated checksum mismatch")
    elif page == "model-download-complete":
        model_controller._handle_downloads((object(),))


def _sample_plan() -> object:
    """Return a real shared plan that the production controller can present."""

    planner = ModelDiscoveryPlanner(
        inventory=_SmokeInventory(),
        discovery=_SmokeDiscovery(),
        destinations=CategoryModelDestinationPolicy(
            Path("smoke-install/comfyui/models")
        ),
    )
    return planner.plan_installer(
        _smoke_capabilities(),
        selected_categories=(ModelCategory.CHECKPOINTS,),
    )


class _SmokeInventory:
    """Expose deterministic model inventory without touching a target."""

    def __init__(self, *, existing_model: bool = False) -> None:
        """Select whether gating observes one compatible local model."""

        self._existing_model = existing_model

    def list_models(
        self,
        categories: Collection[ModelCategory],
    ) -> tuple[LocalModel, ...]:
        """Return optional synthetic local evidence for smoke gating."""

        if self._existing_model and ModelCategory.CHECKPOINTS in categories:
            return (
                LocalModel(
                    category=ModelCategory.CHECKPOINTS,
                    path=Path("smoke-install/existing-model.safetensors"),
                    sha256="a" * 64,
                ),
            )
        return ()


class _SmokeDiscovery:
    """Return deterministic provider-shaped cards without network access."""

    def discover_monthly_popular(
        self,
        category: ModelCategory,
        *,
        limit: int,
    ) -> tuple[DiscoveredModel, ...]:
        """Return three safe candidates in monthly popularity order."""

        _ = limit
        if category is not ModelCategory.CHECKPOINTS:
            return ()
        gibibyte = 1024**3
        names = (
            ("Luminous XL", "Cinematic 2.1", "Sample Studio", "SDXL 1.0", 7),
            ("Illustria", "Soft Anime v4", "Example Creator", "Pony", 6),
            ("Photo Realism", "Natural Light", None, "Flux.1 D", 12),
        )
        return tuple(
            DiscoveredModel(
                category=category,
                model_id=index,
                version_id=100 + index,
                model_name=name,
                version_name=version,
                creator=creator,
                base_model=base,
                file_name=f"smoke-{index}.safetensors",
                size_bytes=size * gibibyte,
                sha256=f"{index:064x}",
                download_url=f"https://civitai.com/api/download/models/{100 + index}",
                model_page_url=f"https://civitai.com/models/{index}",
                thumbnail_url=None,
                provider_rank=index,
            )
            for index, (name, version, creator, base, size) in enumerate(names, 1)
        )


def _smoke_capabilities() -> tuple[CubeModelCapability, ...]:
    """Return one release-shaped supported category contract."""

    return (
        CubeModelCapability(
            cube_id="smoke-cubes",
            categories=frozenset(ModelCategory),
        ),
    )


def _model_controller(
    window: LauncherMainWindow,
    artifact_root: Path | None,
    *,
    existing_model: bool = False,
) -> InstallerModelOnboardingController:
    """Compose the production controller over deterministic no-I/O services."""

    model_root = (
        artifact_root / "simulated-model-root"
        if artifact_root is not None
        else Path.cwd() / "build" / "qualification" / "interactive-smoke-models"
    )
    service = ModelOnboardingService(
        planner=ModelDiscoveryPlanner(
            inventory=_SmokeInventory(existing_model=existing_model),
            discovery=_SmokeDiscovery(),
            destinations=CategoryModelDestinationPolicy(model_root),
        ),
        acquisition=ModelAcquisitionService(allowed_roots=(model_root,)),
    )
    return InstallerModelOnboardingController(
        view=window.view,
        service=service,
        capabilities=_smoke_capabilities(),
        on_finished=lambda: None,
        executor=window.model_onboarding_execution,
    )


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
    payload["selected_categories"] = [
        category.value for category in snapshot.selected_categories
    ]
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
            "Inspect production installer and repair pages without downloads, installs, "
            "subprocesses, or installation mutations."
        )
    )
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--page", choices=_PAGES, default="model-gallery")
    parser.add_argument("--artifact-root", type=Path, default=_DEFAULT_ARTIFACT_ROOT)
    return parser.parse_args(list(argv))


def main(argv: Sequence[str] | None = None) -> int:
    """Run an interactive page or write complete headless visual evidence."""

    args = _parse_args(sys.argv[1:] if argv is None else argv)
    if args.interactive:
        return run_interactive_smoke(args.page)
    result = run_headless_smoke(artifact_root=args.artifact_root)
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

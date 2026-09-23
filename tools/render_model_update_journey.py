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

"""Render real-model update decisions in the production node-card and modal UI."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from qfluentwidgets import Theme, setTheme  # type: ignore[import-untyped] # noqa: E402

from substitute.domain.model_metadata import CivitaiThumbnailPolicy  # noqa: E402
from substitute.infrastructure.model_recommendations.civitai_payload_parser import (  # noqa: E402
    safe_version_thumbnail,
)
from substitute.infrastructure.model_recommendations.thumbnail_fetcher import (  # noqa: E402
    CivitaiThumbnailFetcher,
)
from substitute.presentation.localization import LocalizedSwitchButton  # noqa: E402
from substitute.presentation.model_discovery.discovery_overlay import (  # noqa: E402
    ModelDiscoveryOverlay,
)
from substitute.presentation.model_updates.version_family_modal import (  # noqa: E402
    ModelVersionFamilyModal,
)
from substitute.presentation.shell.window_frame import SubstituteWindowFrame  # noqa: E402
from sugarsubstitute_shared.model_discovery import (  # noqa: E402
    CivitaiDiscoveryClient,
    ModelArtifactKind,
)
from sugarsubstitute_shared.model_updates import (  # noqa: E402
    CivitaiCompatibleUpdateGateway,
    ModelUpdateProposal,
    ModelUsageRecord,
)
from tools.install_experience_capture import (  # noqa: E402
    save_opaque_dark_widget_capture,
)
from tools.model_update_render_surfaces import (  # noqa: E402
    RealUpdateScenario,
    UpdatePreferenceService,
    mount_shell,
    settle,
)
from tools.model_update_lora_render import render_lora_prompt_node_card  # noqa: E402
from tools.model_update_node_card_render import render_node_card  # noqa: E402
from tools.render_openmodeldb_upscaler_picker import (  # noqa: E402
    register_qualification_font,
)


def _scenario(
    client: CivitaiDiscoveryClient,
    gateway: CivitaiCompatibleUpdateGateway,
    *,
    model_id: int,
    installed_version_id: int,
    kind: ModelArtifactKind,
) -> RealUpdateScenario:
    """Verify a real installed version's same-kind, same-base chronology."""

    available = client.discover_model_versions(model_id=model_id, artifact_kind=kind)
    installed = next(
        version for version in available if version.version_id == installed_version_id
    )
    versions = gateway.compatible_family(
        model_id=model_id,
        current_version_id=installed_version_id,
        artifact_kind=kind,
        base_model=installed.base_model,
    )
    if len(versions) < 2 or installed not in versions:
        raise AssertionError(f"Real model {model_id} has no usable update family.")
    return RealUpdateScenario(
        proposal=ModelUpdateProposal(
            current=ModelUsageRecord(
                sha256=installed.sha256,
                path=Path("models") / kind.value / installed.file_name,
                artifact_kind=kind,
                model_id=model_id,
                version_id=installed_version_id,
                base_model=installed.base_model,
                usage_count=1,
                last_used_at=datetime.now(UTC),
            ),
            candidate=versions[-1],
        ),
        versions=versions,
    )


def _render_family(
    app: QApplication,
    frame: SubstituteWindowFrame,
    scenario: RealUpdateScenario,
    fetcher: CivitaiThumbnailFetcher,
    output: Path,
    prefix: str,
    *,
    decisions: bool,
) -> int:
    """Capture chronological real-version cards inside the full-window wash."""

    overlay = ModelDiscoveryOverlay(owner=frame)
    modal = ModelVersionFamilyModal(
        proposal=scenario.proposal,
        open_url=lambda _url: True,
        parent=overlay,
    )
    overlay.attach(modal)
    overlay.present()
    modal.show_loading()
    settle(app)
    save_opaque_dark_widget_capture(frame, output / f"{prefix}-loading.png")
    current_index = next(
        index
        for index, version in enumerate(scenario.versions)
        if version.version_id == scenario.proposal.current.version_id
    )
    installed_hashes = {scenario.versions[current_index].sha256.casefold()}
    if current_index > 0:
        installed_hashes.add(scenario.versions[current_index - 1].sha256.casefold())
    modal.show_family(scenario.versions, installed_hashes=frozenset(installed_hashes))
    image_count = 0
    for version in scenario.versions:
        if version.thumbnail_url is None:
            modal.set_thumbnail_unavailable(version.version_id)
            continue
        try:
            image = QImage.fromData(fetcher.fetch(version.thumbnail_url))
        except (OSError, TimeoutError, ValueError, RuntimeError):
            image = QImage()
        if image.isNull():
            modal.set_thumbnail_unavailable(version.version_id)
        else:
            modal.set_thumbnail(version.version_id, image)
            image_count += 1
    settle(app)
    save_opaque_dark_widget_capture(frame, output / f"{prefix}-versions.png")
    if decisions:
        newest = scenario.versions[-1]
        modal._cards[newest.version_id].portrait.checkbox.setChecked(True)
        settle(app)
        save_opaque_dark_widget_capture(frame, output / f"{prefix}-selected.png")
        modal.set_downloading()
        settle(app)
        save_opaque_dark_widget_capture(frame, output / f"{prefix}-downloading.png")
        modal.finish_download()
        settle(app)
        save_opaque_dark_widget_capture(frame, output / f"{prefix}-downloaded.png")
    modal.reject()
    overlay.close()
    return image_count


def main() -> int:
    """Capture opt-in, a real node card, and exact model-family decisions."""

    app = cast(QApplication, QApplication.instance() or QApplication([]))
    register_qualification_font(app)
    setTheme(Theme.DARK)
    output = Path("build/qualification/model-update-journey").resolve()
    output.mkdir(parents=True, exist_ok=True)
    service = UpdatePreferenceService()
    settings, _ = mount_shell(settings=True, service=service)
    settle(app)
    save_opaque_dark_widget_capture(settings, output / "01-opt-in-off.png")
    switch = settings.findChild(LocalizedSwitchButton)
    if switch is None:
        raise AssertionError("The real settings switch was not mounted.")
    switch.setChecked(True)
    settle(app)
    assert service.model_update_notifications_enabled
    save_opaque_dark_widget_capture(settings, output / "02-opt-in-on.png")
    settings.close()

    fetcher = CivitaiThumbnailFetcher()
    client = CivitaiDiscoveryClient(
        thumbnail_selector=lambda images: safe_version_thumbnail(
            images, thumbnail_policy=CivitaiThumbnailPolicy()
        )
    )
    gateway = CivitaiCompatibleUpdateGateway(client)
    checkpoint = _scenario(
        client,
        gateway,
        model_id=934764,
        installed_version_id=2673989,
        kind=ModelArtifactKind.CHECKPOINTS,
    )
    second_checkpoint = _scenario(
        client,
        gateway,
        model_id=1318945,
        installed_version_id=2823418,
        kind=ModelArtifactKind.CHECKPOINTS,
    )
    lora = _scenario(
        client,
        gateway,
        model_id=1145743,
        installed_version_id=2196453,
        kind=ModelArtifactKind.LORAS,
    )
    diffusion = _scenario(
        client,
        gateway,
        model_id=934764,
        installed_version_id=3153747,
        kind=ModelArtifactKind.DIFFUSION_MODELS,
    )
    frame = render_node_card(
        app,
        service,
        (checkpoint, second_checkpoint),
        fetcher,
        output,
        "03-checkpoint",
        workflow_fixture="workflow_sdxl_baseline.json",
        cube_alias="Cube 1: SDXL/Text to Image",
        node_name="checkpoint",
        input_name="ckpt_name",
    )
    counts = {
        "checkpoint": _render_family(
            app, frame, checkpoint, fetcher, output, "04-checkpoint", decisions=True
        )
    }
    frame.close()
    frame = render_lora_prompt_node_card(app, service, lora, fetcher, output, "05-lora")
    counts["lora"] = _render_family(
        app, frame, lora, fetcher, output, "06-lora", decisions=False
    )
    frame.close()
    frame = render_node_card(
        app,
        service,
        (diffusion,),
        fetcher,
        output,
        "07-diffusion",
        workflow_fixture="workflow_anima_baseline.json",
        cube_alias="Cube 1: Anima/Text to Image",
        node_name="models",
        input_name="diffusion_model",
    )
    counts["diffusion"] = _render_family(
        app, frame, diffusion, fetcher, output, "08-diffusion", decisions=False
    )
    frame.close()
    evidence = {
        "source": "live public CivitAI API, safe real-version preview images",
        "checkpoint_capture": "production SDXL checkpoint node card and model picker",
        "diffusion_capture": "production Anima diffusion-model node card and model picker",
        "download_states": "visual states; atomic side-by-side transfer verified by lifecycle test",
        "scenarios": [
            {
                "kind": scenario.proposal.current.artifact_kind.value,
                "model_id": scenario.proposal.current.model_id,
                "model_name": scenario.proposal.candidate.model_name,
                "installed_version_id": scenario.proposal.current.version_id,
                "newest_version_id": scenario.proposal.candidate.version_id,
                "family_version_ids": [
                    version.version_id for version in scenario.versions
                ],
                "real_images_rendered": counts[name],
            }
            for name, scenario in (
                ("checkpoint", checkpoint),
                ("lora", lora),
                ("diffusion", diffusion),
            )
        ],
    }
    (output / "evidence.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

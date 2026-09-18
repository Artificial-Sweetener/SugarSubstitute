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

"""Verify Settings refreshes invalidate and publish the same metadata update."""

from substitute.app.bootstrap.settings_model_metadata_progress import (
    SettingsModelMetadataProgressSink,
)
from substitute.application.model_metadata import ModelMetadataRefreshEvent


def test_settings_refresh_preserves_update_event() -> None:
    """Let an open picker observe thumbnails produced by a Settings refresh."""
    events: list[ModelMetadataRefreshEvent] = []
    invalidations: list[bool] = []

    def publish(event: ModelMetadataRefreshEvent) -> None:
        """Observe catalog freshness at the surface notification boundary."""
        assert invalidations == [True]
        events.append(event)

    sink = SettingsModelMetadataProgressSink(
        invalidate_catalog=lambda: invalidations.append(True),
        publish_update=publish,
    )
    event = ModelMetadataRefreshEvent(
        kind="diffusion_models",
        value="Anima/model.safetensors",
        relative_path="Anima/model.safetensors",
        sha256="A" * 64,
        provider_status="found",
        thumbnail_updated=True,
    )

    sink.emit_model_updated(event)

    assert events == [event]

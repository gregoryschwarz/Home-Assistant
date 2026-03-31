"""Tests for manifest.json required fields (HA-01)."""
from __future__ import annotations

import json
from pathlib import Path


def test_manifest_has_required_fields() -> None:
    """Manifest must have all required HA fields for HA-01."""
    manifest_path = Path("custom_components/ha_ai_agent/manifest.json")
    assert manifest_path.exists(), "manifest.json must exist"
    manifest = json.loads(manifest_path.read_text())

    assert manifest["domain"] == "ha_ai_agent"
    assert manifest["config_flow"] is True, "config_flow must be True (HA-01)"
    assert "version" in manifest and manifest["version"], "version required (Pitfall 3)"
    assert "conversation" in manifest["dependencies"], "conversation dependency required (HA-04 prep)"
    assert manifest["iot_class"] == "cloud_polling"
    assert "name" in manifest


def test_manifest_no_deprecated_fields() -> None:
    """Manifest must not use patterns that break HA 2025.x."""
    manifest_path = Path("custom_components/ha_ai_agent/manifest.json")
    manifest = json.loads(manifest_path.read_text())
    # "quality_scale" is valid but not required — ensure it does not have
    # iot_class values that suggest local-only operation for a cloud agent
    assert manifest["iot_class"] != "local_polling"
    assert manifest["iot_class"] != "local_push"

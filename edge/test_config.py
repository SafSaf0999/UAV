"""Tests for edge/config.py — configuration loader."""

import os
import textwrap

import pytest
import yaml

from config import Config, _get_nested, _validate, load_config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_YAML = textwrap.dedent("""\
    device_id: edge-01
    mqtt:
      host: broker.example.com
      port: 8883
    camera:
      source: /dev/video0
      fps: 15
    model_profiles:
      - name: daylight-v1
        file_path: /models/yolo26_daylight.pt
        camera_mode: daylight
    active_model: daylight-v1
""")


def write_yaml(tmp_path, content: str) -> str:
    p = tmp_path / "config.yaml"
    p.write_text(content)
    return str(p)


# ---------------------------------------------------------------------------
# _get_nested
# ---------------------------------------------------------------------------


def test_get_nested_top_level():
    data = {"device_id": "edge-01"}
    found, val = _get_nested(data, "device_id")
    assert found is True
    assert val == "edge-01"


def test_get_nested_two_levels():
    data = {"mqtt": {"host": "broker", "port": 8883}}
    found, val = _get_nested(data, "mqtt.host")
    assert found is True
    assert val == "broker"


def test_get_nested_missing_key():
    data = {"mqtt": {"port": 8883}}
    found, _ = _get_nested(data, "mqtt.host")
    assert found is False


def test_get_nested_missing_parent():
    data = {}
    found, _ = _get_nested(data, "mqtt.host")
    assert found is False


# ---------------------------------------------------------------------------
# _validate — required fields
# ---------------------------------------------------------------------------


def test_validate_passes_with_all_required_fields():
    data = yaml.safe_load(VALID_YAML)
    _validate(data)  # should not raise or exit


def test_validate_exits_on_missing_device_id():
    data = yaml.safe_load(VALID_YAML)
    del data["device_id"]
    with pytest.raises(SystemExit) as exc_info:
        _validate(data)
    assert exc_info.value.code == 1


def test_validate_exits_on_missing_mqtt_host():
    data = yaml.safe_load(VALID_YAML)
    del data["mqtt"]["host"]
    with pytest.raises(SystemExit) as exc_info:
        _validate(data)
    assert exc_info.value.code == 1


def test_validate_exits_on_missing_mqtt_port():
    data = yaml.safe_load(VALID_YAML)
    del data["mqtt"]["port"]
    with pytest.raises(SystemExit) as exc_info:
        _validate(data)
    assert exc_info.value.code == 1


def test_validate_exits_on_missing_camera_source():
    data = yaml.safe_load(VALID_YAML)
    del data["camera"]["source"]
    with pytest.raises(SystemExit) as exc_info:
        _validate(data)
    assert exc_info.value.code == 1


def test_validate_exits_on_missing_active_model():
    data = yaml.safe_load(VALID_YAML)
    del data["active_model"]
    with pytest.raises(SystemExit) as exc_info:
        _validate(data)
    assert exc_info.value.code == 1


def test_validate_exits_when_active_model_not_in_profiles():
    data = yaml.safe_load(VALID_YAML)
    data["active_model"] = "nonexistent-model"
    with pytest.raises(SystemExit) as exc_info:
        _validate(data)
    assert exc_info.value.code == 1


def test_validate_passes_when_no_model_profiles_key():
    """active_model validation is skipped when model_profiles is absent."""
    data = yaml.safe_load(VALID_YAML)
    del data["model_profiles"]
    _validate(data)  # should not exit


# ---------------------------------------------------------------------------
# load_config — file loading
# ---------------------------------------------------------------------------


def test_load_config_returns_config_object(tmp_path):
    path = write_yaml(tmp_path, VALID_YAML)
    cfg = load_config(path)
    assert isinstance(cfg, Config)
    assert cfg.device_id == "edge-01"
    assert cfg.active_model == "daylight-v1"


def test_load_config_uses_edge_config_env_var(tmp_path, monkeypatch):
    path = write_yaml(tmp_path, VALID_YAML)
    monkeypatch.setenv("EDGE_CONFIG", path)
    cfg = load_config()
    assert cfg.device_id == "edge-01"


def test_load_config_exits_on_missing_file():
    with pytest.raises(SystemExit) as exc_info:
        load_config("/nonexistent/path/config.yaml")
    assert exc_info.value.code == 1


def test_load_config_exits_on_invalid_yaml(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("key: [unclosed bracket")
    with pytest.raises(SystemExit) as exc_info:
        load_config(str(p))
    assert exc_info.value.code == 1


def test_load_config_exits_on_non_mapping_yaml(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("- just\n- a\n- list\n")
    with pytest.raises(SystemExit) as exc_info:
        load_config(str(p))
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Config.get — dot-notation accessor
# ---------------------------------------------------------------------------


def test_config_get_nested_value(tmp_path):
    path = write_yaml(tmp_path, VALID_YAML)
    cfg = load_config(path)
    assert cfg.get("mqtt.host") == "broker.example.com"
    assert cfg.get("mqtt.port") == 8883


def test_config_get_returns_default_for_missing_key(tmp_path):
    path = write_yaml(tmp_path, VALID_YAML)
    cfg = load_config(path)
    assert cfg.get("nonexistent.key", "fallback") == "fallback"


# ---------------------------------------------------------------------------
# config.example.yaml is valid
# ---------------------------------------------------------------------------


def test_example_yaml_is_valid():
    example_path = os.path.join(os.path.dirname(__file__), "config.example.yaml")
    cfg = load_config(example_path)
    assert cfg.device_id == "edge-01"
    assert cfg.active_model == "daylight-v1"
    assert cfg.get("mqtt.host") == "main-device.example.com"
    assert cfg.get("mqtt.port") == 8883
    assert cfg.get("camera.source") == "/dev/video0"

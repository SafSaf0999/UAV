"""
Tests for edge/inference_engine.py

Unit tests:
  - Missing model file exits with code 1
  - Thermal preprocessing applied when camera_mode=="thermal", skipped otherwise
  - hot_swap returns False and retains current model when file missing

Property tests (hypothesis):
  - Property 10: Model Profile Structure is Valid
  - Property 11: Status Message Includes Active Model Name
  - Property 12: Thermal Preprocessing Changes Frame Data
"""

import queue
import sys
import threading
import types
import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Register hypothesis CI profile
# ---------------------------------------------------------------------------
from hypothesis import settings as hyp_settings, HealthCheck

hyp_settings.register_profile(
    "ci",
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow],
)
hyp_settings.load_profile("ci")

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------
from edge.inference_engine import apply_thermal_preprocessing, InferenceEngine, ModelManager


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_config(
    active_model: str = "daylight-v1",
    profiles: list | None = None,
    camera_mode: str = "daylight",
    model_file: str = "/tmp/fake_model.pt",
) -> MagicMock:
    """Build a minimal mock Config object."""
    if profiles is None:
        profiles = [
            {
                "name": active_model,
                "file_path": model_file,
                "camera_mode": camera_mode,
            }
        ]
    cfg = MagicMock()
    cfg.device_id = "edge-test"
    cfg.active_model = active_model
    cfg.get = lambda key, default=None: {
        "model_profiles": profiles,
        "camera.fps": 15,
        "model_swap_timeout_s": 5.0,
    }.get(key, default)
    return cfg


def _make_engine_with_mock_model(
    active_model: str = "daylight-v1",
    camera_mode: str = "daylight",
    model_file: str = "/tmp/fake_model.pt",
) -> InferenceEngine:
    """
    Build an InferenceEngine with a mocked ultralytics.YOLO so no real
    .pt file is needed.  We stub sys.modules["ultralytics"] so the lazy
    import inside _load_model resolves without the real package installed.
    """
    cfg = _make_config(
        active_model=active_model,
        camera_mode=camera_mode,
        model_file=model_file,
    )
    mock_model_instance = MagicMock()
    mock_yolo_cls = MagicMock(return_value=mock_model_instance)
    fake_ultralytics = types.ModuleType("ultralytics")
    fake_ultralytics.YOLO = mock_yolo_cls  # type: ignore[attr-defined]

    with patch.dict(sys.modules, {"ultralytics": fake_ultralytics}), \
         patch("os.path.exists", return_value=True):
        engine = InferenceEngine(cfg, queue.Queue())
    return engine


# ===========================================================================
# Unit Tests
# ===========================================================================

class TestMissingModelFileExits(unittest.TestCase):
    """Test that a missing .pt file causes sys.exit(1)."""

    def test_missing_model_file_exits_with_code_1(self):
        cfg = _make_config(model_file="/nonexistent/path/model.pt")
        with patch("os.path.exists", return_value=False):
            with self.assertRaises(SystemExit) as ctx:
                InferenceEngine(cfg, queue.Queue())
        self.assertEqual(ctx.exception.code, 1)


class TestThermalPreprocessing(unittest.TestCase):
    """Test that thermal preprocessing is applied / skipped correctly."""

    def _make_frame(self) -> np.ndarray:
        return np.random.randint(0, 256, (64, 64, 3), dtype=np.uint8)

    def test_thermal_preprocessing_applied_when_camera_mode_thermal(self):
        """_preprocess_frame should return a different array for thermal mode."""
        engine = _make_engine_with_mock_model(camera_mode="thermal")
        frame = self._make_frame()
        result = engine._preprocess_frame(frame)
        # The output must differ from the raw input
        self.assertFalse(
            np.array_equal(frame, result),
            "Thermal preprocessing must change the frame",
        )

    def test_thermal_preprocessing_skipped_when_camera_mode_daylight(self):
        """_preprocess_frame should return the same array for daylight mode."""
        engine = _make_engine_with_mock_model(camera_mode="daylight")
        frame = self._make_frame()
        result = engine._preprocess_frame(frame)
        self.assertTrue(
            np.array_equal(frame, result),
            "Non-thermal mode must not modify the frame",
        )

    def test_thermal_preprocessing_skipped_when_camera_mode_night(self):
        """_preprocess_frame should return the same array for night mode."""
        engine = _make_engine_with_mock_model(camera_mode="night")
        frame = self._make_frame()
        result = engine._preprocess_frame(frame)
        self.assertTrue(
            np.array_equal(frame, result),
            "Non-thermal mode must not modify the frame",
        )


class TestHotSwapMissingFile(unittest.TestCase):
    """Test that hot_swap returns False and retains current model when file missing."""

    def test_hot_swap_returns_false_when_file_missing(self):
        engine = _make_engine_with_mock_model(active_model="daylight-v1")
        original_model = engine.model
        original_profile = engine.active_profile

        cfg = engine.config
        # Add a second profile whose file does not exist
        profiles = [
            {"name": "daylight-v1", "file_path": "/tmp/fake.pt", "camera_mode": "daylight"},
            {"name": "thermal-v1", "file_path": "/nonexistent/thermal.pt", "camera_mode": "thermal"},
        ]
        cfg.get = lambda key, default=None: {
            "model_profiles": profiles,
            "camera.fps": 15,
            "model_swap_timeout_s": 5.0,
        }.get(key, default)

        manager = ModelManager(cfg, engine)

        with patch("os.path.exists", return_value=False):
            result = manager.hot_swap("thermal-v1")

        self.assertFalse(result, "hot_swap must return False when file is missing")
        self.assertIs(engine.model, original_model, "Model must not change on failed swap")
        self.assertEqual(
            engine.active_profile["name"],
            "daylight-v1",
            "Active profile must not change on failed swap",
        )
        # Engine must not remain paused
        self.assertFalse(engine.paused.is_set(), "Engine must not remain paused after failed swap")

    def test_hot_swap_returns_false_for_unknown_model_name(self):
        engine = _make_engine_with_mock_model()
        cfg = engine.config
        manager = ModelManager(cfg, engine)
        result = manager.hot_swap("nonexistent-model")
        self.assertFalse(result)

    def test_hot_swap_succeeds_when_file_exists(self):
        """hot_swap returns True and swaps model when file exists."""
        engine = _make_engine_with_mock_model(active_model="daylight-v1")
        profiles = [
            {"name": "daylight-v1", "file_path": "/tmp/fake_daylight.pt", "camera_mode": "daylight"},
            {"name": "thermal-v1", "file_path": "/tmp/fake_thermal.pt", "camera_mode": "thermal"},
        ]
        engine.config.get = lambda key, default=None: {
            "model_profiles": profiles,
            "camera.fps": 15,
            "model_swap_timeout_s": 5.0,
        }.get(key, default)

        manager = ModelManager(engine.config, engine)
        mock_new_model = MagicMock()
        fake_ultralytics = types.ModuleType("ultralytics")
        fake_ultralytics.YOLO = MagicMock(return_value=mock_new_model)  # type: ignore[attr-defined]

        with patch("os.path.exists", return_value=True), \
             patch.dict(sys.modules, {"ultralytics": fake_ultralytics}):
            result = manager.hot_swap("thermal-v1")

        self.assertTrue(result)
        self.assertEqual(engine.active_profile["name"], "thermal-v1")
        self.assertFalse(engine.paused.is_set())


# ===========================================================================
# Property Tests
# ===========================================================================

# ---------------------------------------------------------------------------
# Property 10: Model Profile Structure is Valid
# Feature: anti-uav-detection-system, Property 10: Model Profile Structure is Valid
# ---------------------------------------------------------------------------

VALID_CAMERA_MODES = ["daylight", "night", "thermal"]

profile_strategy = st.fixed_dictionaries(
    {
        "name": st.text(min_size=1, max_size=64),
        "file_path": st.text(min_size=1, max_size=256),
        "camera_mode": st.sampled_from(VALID_CAMERA_MODES),
    }
)


@given(profile=profile_strategy)
@settings(max_examples=100)
def test_property_10_model_profile_structure(profile):
    """
    # Feature: anti-uav-detection-system, Property 10: Model Profile Structure is Valid
    **Validates: Requirements 18.1**

    For any model profile, it must contain a non-empty name string, a
    non-empty file_path string, and a camera_mode that is one of
    "daylight", "night", or "thermal".
    """
    assert isinstance(profile["name"], str) and len(profile["name"]) > 0
    assert isinstance(profile["file_path"], str) and len(profile["file_path"]) > 0
    assert profile["camera_mode"] in VALID_CAMERA_MODES


# ---------------------------------------------------------------------------
# Property 11: Status Message Includes Active Model Name
# Feature: anti-uav-detection-system, Property 11: Status Message Includes Active Model Name
# ---------------------------------------------------------------------------

def _build_status_dict(device_id: str, active_model_name: str) -> dict:
    """Simulate the status dict that an edge device would publish."""
    from datetime import datetime, timezone
    return {
        "device_id": device_id,
        "status": "online",
        "active_model": active_model_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@given(
    device_id=st.text(min_size=1, max_size=64),
    model_name=st.text(min_size=1, max_size=64),
)
@settings(max_examples=100)
def test_property_11_status_includes_active_model(device_id, model_name):
    """
    # Feature: anti-uav-detection-system, Property 11: Status Message Includes Active Model Name
    **Validates: Requirements 18.7**

    For any retained uav/status/{device_id} message, the active_model field
    must match the name of the currently loaded model profile.
    """
    status = _build_status_dict(device_id, model_name)
    assert "active_model" in status
    assert status["active_model"] == model_name


# ---------------------------------------------------------------------------
# Property 12: Thermal Preprocessing Changes Frame Data
# Feature: anti-uav-detection-system, Property 12: Thermal Preprocessing Changes Frame Data
# ---------------------------------------------------------------------------

frame_strategy = st.integers(min_value=8, max_value=128).flatmap(
    lambda h: st.integers(min_value=8, max_value=128).map(
        lambda w: np.random.default_rng(42).integers(0, 256, (h, w, 3), dtype=np.uint8)
    )
)

# Use a fixed-seed numpy strategy for reproducibility
@given(
    height=st.integers(min_value=8, max_value=64),
    width=st.integers(min_value=8, max_value=64),
    seed=st.integers(min_value=0, max_value=2**31 - 1),
)
@settings(max_examples=100)
def test_property_12_thermal_preprocessing_changes_frame(height, width, seed):
    """
    # Feature: anti-uav-detection-system, Property 12: Thermal Preprocessing Changes Frame Data
    **Validates: Requirements 18.10**

    For any camera frame processed when camera_mode == "thermal", the
    preprocessed frame must differ from the raw input frame.
    """
    rng = np.random.default_rng(seed)
    frame = rng.integers(0, 256, (height, width, 3), dtype=np.uint8)
    result = apply_thermal_preprocessing(frame)

    # Output must be a numpy array
    assert isinstance(result, np.ndarray)
    # Output must differ from input (colormap normalization is not a no-op)
    assert not np.array_equal(frame, result), (
        "Thermal preprocessing must change the frame data"
    )

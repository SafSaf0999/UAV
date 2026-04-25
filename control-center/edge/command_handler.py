"""
Edge device — command handler.

Parses incoming MQTT command messages and dispatches to the appropriate
component:
  - "start_stream"    → webrtc_streamer.start()   (within 3 seconds)
  - "stop_stream"     → webrtc_streamer.stop()    (within 2 seconds)
  - "switch_model"    → model_manager.hot_swap()  (returns False → publish error status)
  - "update_config"   → update camera source/fps and/or active model
  - "ipwebcam_control"→ proxy control command to IP Webcam HTTP API
  - "ipwebcam_sensors"→ fetch sensors from IP Webcam and publish
  - unknown action    → log warning, ignore

Requirements: 7.3, 7.4, 18.3, 18.4, 18.6
"""

import base64
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CommandHandler:
    """
    Dispatches MQTT command messages to the correct edge device component.

    Args:
        mqtt_client:       MQTTClient instance used to publish error status.
        webrtc_streamer:   Optional WebRTC streamer; required for stream commands.
        model_manager:     ModelManager instance for hot-swap commands.
        camera_source:     Optional camera source string (for update_config).
        camera:            Optional CameraSource instance (for update_config).
        ipwebcam_handler:  Optional IPWebcamHandler instance.
    """

    def __init__(
        self,
        mqtt_client,
        webrtc_streamer=None,
        model_manager=None,
        camera_source=None,
        camera=None,
        ipwebcam_handler=None,
    ) -> None:
        self._mqtt_client = mqtt_client
        self._webrtc_streamer = webrtc_streamer
        self._model_manager = model_manager
        self._camera_source = camera_source
        self._camera = camera
        self._ipwebcam_handler = ipwebcam_handler

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle(self, topic: str, payload: bytes) -> None:
        """
        Parse a JSON command payload and dispatch based on the action field.

        Args:
            topic:   MQTT topic the message arrived on.
            payload: Raw bytes of the MQTT message payload.
        """
        try:
            data = json.loads(payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning("CommandHandler: failed to parse payload on %s: %s", topic, exc)
            return

        action = data.get("action")

        if action == "start_stream":
            self._handle_start_stream()
        elif action == "stop_stream":
            self._handle_stop_stream()
        elif action == "switch_model":
            model_name = data.get("model_name", "")
            self._handle_switch_model(model_name)
        elif action == "update_config":
            self._handle_update_config(data)
        elif action == "ipwebcam_control":
            setting = data.get("setting", "")
            value = data.get("value")
            self._handle_ipwebcam_control(setting, value)
        elif action == "ipwebcam_sensors":
            self._handle_ipwebcam_sensors()
        else:
            logger.warning(
                "CommandHandler: unknown action '%s' on topic %s — ignoring", action, topic
            )

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _handle_start_stream(self) -> None:
        """Start the WebRTC stream (must complete within 3 seconds per Req 7.4)."""
        if self._webrtc_streamer is None:
            logger.warning("CommandHandler: start_stream received but no WebRTC streamer configured")
            return
        logger.info("CommandHandler: starting WebRTC stream")
        self._webrtc_streamer.start()

    def _handle_stop_stream(self) -> None:
        """Stop the WebRTC stream (must complete within 2 seconds per Req 7.3)."""
        if self._webrtc_streamer is None:
            logger.warning("CommandHandler: stop_stream received but no WebRTC streamer configured")
            return
        logger.info("CommandHandler: stopping WebRTC stream")
        self._webrtc_streamer.stop()

    def _handle_switch_model(self, model_name: str) -> None:
        """
        Hot-swap the active model.

        If hot_swap returns False (file missing or unknown model), log the
        error and publish an error status via mqtt_client.publish_status().
        Requirements: 18.3, 18.4, 18.6
        """
        if self._model_manager is None:
            logger.warning("CommandHandler: switch_model received but no ModelManager configured")
            return

        logger.info("CommandHandler: switching model to '%s'", model_name)
        success = self._model_manager.hot_swap(model_name)

        if not success:
            logger.error(
                "CommandHandler: switch_model failed for '%s' — retaining current model",
                model_name,
            )
            # Publish error status so the control center is notified (Req 18.6)
            try:
                device_id = self._mqtt_client._device_id
            except AttributeError:
                device_id = "unknown"

            self._mqtt_client.publish_status(
                {
                    "device_id": device_id,
                    "status": "error",
                    "error": f"switch_model failed: model '{model_name}' not found or file missing",
                }
            )

    def _handle_update_config(self, data: dict) -> None:
        """
        Apply runtime config updates from an update_config command payload.

        Supported fields: camera_source, fps, active_model.
        Unrecognized fields are silently ignored.
        """
        camera_source = data.get("camera_source")
        fps = data.get("fps")
        active_model = data.get("active_model")

        if camera_source is not None or fps is not None:
            if self._camera is None:
                logger.warning("CommandHandler: update_config camera fields received but no camera configured")
            else:
                logger.info("CommandHandler: update_config — restarting camera")
                self._camera.stop()
                if camera_source is not None:
                    self._camera.source = camera_source
                    logger.info("CommandHandler: camera source updated to '%s'", camera_source)
                if fps is not None:
                    self._camera.fps = max(int(fps), 1)
                    logger.info("CommandHandler: camera fps updated to %d", self._camera.fps)
                self._camera.start()

        if active_model is not None:
            if self._model_manager is None:
                logger.warning("CommandHandler: update_config active_model received but no ModelManager configured")
            else:
                logger.info("CommandHandler: update_config — hot-swapping model to '%s'", active_model)
                self._model_manager.hot_swap(active_model)

    def _handle_ipwebcam_control(self, setting: str, value=None) -> None:
        """Proxy a control command to the IP Webcam HTTP API."""
        if self._ipwebcam_handler is None:
            logger.warning("CommandHandler: ipwebcam_control received but no IPWebcamHandler configured")
            return

        if setting in ("snapshot", "snapshot_af"):
            af = setting == "snapshot_af"
            try:
                image_bytes = self._ipwebcam_handler.fetch_snapshot(af=af)
                encoded = base64.b64encode(image_bytes).decode("ascii")
                try:
                    device_id = self._mqtt_client._device_id
                except AttributeError:
                    device_id = "unknown"
                topic = f"uav/snapshot/{device_id}"
                self._mqtt_client.publish_raw(topic, encoded.encode("ascii"))
                logger.info("CommandHandler: snapshot published to %s", topic)
            except Exception as exc:
                logger.warning("CommandHandler: snapshot fetch failed: %s", exc)
        else:
            success = self._ipwebcam_handler.handle_control(setting, value)
            if success:
                logger.info("CommandHandler: ipwebcam_control '%s'=%s applied", setting, value)
            else:
                logger.warning("CommandHandler: ipwebcam_control '%s'=%s failed", setting, value)

    def _handle_ipwebcam_sensors(self) -> None:
        """Fetch IP Webcam sensor data and publish to MQTT."""
        if self._ipwebcam_handler is None:
            logger.warning("CommandHandler: ipwebcam_sensors received but no IPWebcamHandler configured")
            return

        try:
            sensors = self._ipwebcam_handler.fetch_sensors()
            try:
                device_id = self._mqtt_client._device_id
            except AttributeError:
                device_id = "unknown"
            topic = f"uav/ipwebcam/sensors/{device_id}"
            self._mqtt_client.publish_raw(topic, json.dumps(sensors).encode("utf-8"))
            logger.info("CommandHandler: ipwebcam sensors published to %s", topic)
        except Exception as exc:
            logger.warning("CommandHandler: ipwebcam_sensors fetch failed: %s", exc)

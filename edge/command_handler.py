"""
Edge device — command handler.

Parses incoming MQTT command messages and dispatches to the appropriate
component:
  - "start_stream"  → webrtc_streamer.start()   (within 3 seconds)
  - "stop_stream"   → webrtc_streamer.stop()    (within 2 seconds)
  - "switch_model"  → model_manager.hot_swap()  (returns False → publish error status)
  - unknown action  → log warning, ignore

Requirements: 7.3, 7.4, 18.3, 18.4, 18.6
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CommandHandler:
    """
    Dispatches MQTT command messages to the correct edge device component.

    Args:
        mqtt_client:      MQTTClient instance used to publish error status.
        webrtc_streamer:  Optional WebRTC streamer; required for stream commands.
        model_manager:    ModelManager instance for hot-swap commands.
    """

    def __init__(
        self,
        mqtt_client,
        webrtc_streamer=None,
        model_manager=None,
    ) -> None:
        self._mqtt_client = mqtt_client
        self._webrtc_streamer = webrtc_streamer
        self._model_manager = model_manager

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

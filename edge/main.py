"""
Edge device — main entry point.

Loads config, wires all components, and handles graceful shutdown.

Components started:
  - CameraSource       (camera thread)
  - InferenceEngine    (inference thread)
  - MQTTClient         (network loop thread)
  - CommandHandler     (dispatches MQTT commands)
  - PTZController      (optional, if ptz.enabled)
  - SensorReader       (optional, if sensor.enabled)
  - Estimator          (optional, if estimator.enabled)
  - WebRTCStreamer      (optional, started on command)

Requirements: 1.1, 1.2, 2.3, 10.1, 10.3
"""

import logging
import queue
import signal
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    from edge.config import load_config
    from edge.camera import CameraSource
    from edge.inference_engine import InferenceEngine, ModelManager
    from edge.mqtt_client import MQTTClient
    from edge.command_handler import CommandHandler
    from edge.ptz_controller import PTZController
    from edge.payload import serialize, build_tracking_payload
    from edge.webrtc_streamer import WebRTCStreamer

    # ------------------------------------------------------------------
    # Load config
    # ------------------------------------------------------------------
    config = load_config()
    logger.info("Edge device '%s' starting", config.device_id)

    # ------------------------------------------------------------------
    # Shared frame queue
    # ------------------------------------------------------------------
    frame_queue: queue.Queue = queue.Queue(maxsize=10)

    # ------------------------------------------------------------------
    # Camera
    # ------------------------------------------------------------------
    camera = CameraSource(
        source=config.get("camera.source"),
        fps=int(config.get("camera.fps", 15)),
        frame_queue=frame_queue,
    )

    # ------------------------------------------------------------------
    # Inference engine + model manager
    # ------------------------------------------------------------------
    engine = InferenceEngine(config, frame_queue)
    model_manager = ModelManager(config, engine)

    # ------------------------------------------------------------------
    # Optional: estimator
    # ------------------------------------------------------------------
    estimator = None
    if config.get("estimator.enabled", False):
        from edge.estimator import Estimator
        estimator = Estimator(config)
        logger.info("Estimator enabled")

    # ------------------------------------------------------------------
    # Optional: sensor reader
    # ------------------------------------------------------------------
    sensor_reader = None
    if config.get("sensor.enabled", False):
        from edge.sensor_reader import SensorReader
        sensor_reader = SensorReader(config, None)  # mqtt_client set below
        logger.info("SensorReader enabled")

    # ------------------------------------------------------------------
    # WebRTC streamer (started on command)
    # ------------------------------------------------------------------
    webrtc_streamer = WebRTCStreamer(config, frame_queue)

    # ------------------------------------------------------------------
    # MQTT client
    # ------------------------------------------------------------------
    def on_message(topic: str, payload: bytes) -> None:
        device_id = config.device_id
        if topic == f"uav/command/{device_id}":
            command_handler.handle(topic, payload)
        elif topic == f"uav/ptz/{device_id}":
            ptz_controller.handle(topic, payload)

    mqtt_client = MQTTClient(config, message_callback=on_message)

    # Wire sensor reader's mqtt_client now that it's created
    if sensor_reader is not None:
        sensor_reader._mqtt_client = mqtt_client

    # ------------------------------------------------------------------
    # PTZ controller
    # ------------------------------------------------------------------
    ptz_controller = PTZController(config, mqtt_client)

    # ------------------------------------------------------------------
    # Command handler
    # ------------------------------------------------------------------
    command_handler = CommandHandler(
        mqtt_client=mqtt_client,
        webrtc_streamer=webrtc_streamer,
        model_manager=model_manager,
    )

    # ------------------------------------------------------------------
    # Wire inference engine payload callback
    # ------------------------------------------------------------------
    frame_width_px = int(config.get("camera.width_px", 640))

    def on_payload(payload: dict) -> None:
        if estimator is not None:
            payload = estimator.annotate_payload(payload, frame_width_px)
        payload_bytes = serialize(payload)
        mqtt_client.publish_tracking(payload_bytes)

    engine._on_payload = on_payload

    # ------------------------------------------------------------------
    # Start all components
    # ------------------------------------------------------------------
    camera.start()
    engine.start()
    mqtt_client.start()
    if sensor_reader is not None:
        sensor_reader.start()

    logger.info("All components started")

    # ------------------------------------------------------------------
    # Graceful shutdown
    # ------------------------------------------------------------------
    shutdown_requested = [False]

    def _shutdown(signum, frame):
        logger.info("Shutdown signal received (%s)", signum)
        shutdown_requested[0] = True

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        while not shutdown_requested[0]:
            time.sleep(0.5)
    finally:
        logger.info("Shutting down edge device '%s'", config.device_id)
        webrtc_streamer.stop()
        if sensor_reader is not None:
            sensor_reader.stop()
        engine.stop()
        camera.stop()
        mqtt_client.stop()
        logger.info("Edge device stopped")


if __name__ == "__main__":
    main()

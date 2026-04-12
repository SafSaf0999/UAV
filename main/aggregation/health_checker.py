"""
Aggregation service — edge device health timeout checker.

Background asyncio task that monitors device health timestamps and
transitions devices to "health_timeout" when they stop sending health
messages. Restores to "online" when health messages resume.

Requirements: 9.1, 9.2, 9.7
"""

import asyncio
import logging
import time

logger = logging.getLogger(__name__)


async def run_health_checker(
    registry,
    webhook_dispatcher,
    interval: int = 10,
    timeout: int = 60,
) -> None:
    """
    Periodically check device health timestamps and update status.

    Args:
        registry:           DeviceRegistry instance.
        webhook_dispatcher: WebhookDispatcher instance (may be None).
        interval:           How often to check, in seconds. Default 10.
        timeout:            Seconds without a health message before marking
                            a device as "health_timeout". Default 60.
    """
    logger.info("health_checker: started (interval=%ds, timeout=%ds)", interval, timeout)
    while True:
        await asyncio.sleep(interval)
        try:
            await _check_devices(registry, webhook_dispatcher, timeout)
        except Exception as exc:
            logger.warning("health_checker: error during check: %s", exc)


async def _check_devices(registry, webhook_dispatcher, timeout: int) -> None:
    """Iterate all devices and apply health timeout logic."""
    now = time.monotonic()
    async with registry._lock:
        devices = list(registry._devices.values())

    for state in devices:
        device_id = state.device_id
        status = state.status
        last_ts = state.last_health_ts

        if status == "online" and last_ts is not None:
            elapsed = now - last_ts
            if elapsed > timeout:
                logger.info(
                    "health_checker: device %s timed out (%.0fs since last health)",
                    device_id, elapsed,
                )
                async with registry._lock:
                    state.status = "health_timeout"
                # Dispatch device_offline webhook
                if webhook_dispatcher is not None:
                    try:
                        webhook_dispatcher.dispatch(
                            "device_offline",
                            device_id,
                            {"reason": "health_timeout", "elapsed_seconds": elapsed},
                        )
                    except Exception as exc:
                        logger.warning("health_checker: webhook dispatch failed: %s", exc)
                await registry._notify(device_id)

        elif status == "health_timeout":
            if last_ts is not None and (now - last_ts) <= timeout:
                logger.info(
                    "health_checker: device %s recovered (health resumed)", device_id
                )
                async with registry._lock:
                    state.status = "online"
                await registry._notify(device_id)

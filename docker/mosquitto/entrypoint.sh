#!/bin/sh
# entrypoint.sh — Substitute environment variables into mosquitto.conf template
# and start the Mosquitto broker.
#
# Environment variables:
#   MQTT_PORT          Listener port (default: 8883)
#   MQTT_TLS_CA        Path to CA certificate file (required)
#   MQTT_TLS_CERT      Path to server certificate file (required)
#   MQTT_TLS_KEY       Path to server private key file (required)
#   MQTT_AUTH_MODE     Authentication mode: cert | password | both (default: cert)
#   MQTT_PASSWORD_FILE Path to password file (required when MQTT_AUTH_MODE is password or both)

set -eu

# ── Defaults ──────────────────────────────────────────────────────────────────
MQTT_PORT="${MQTT_PORT:-8883}"
MQTT_AUTH_MODE="${MQTT_AUTH_MODE:-cert}"

# ── Validate required TLS paths ───────────────────────────────────────────────
if [ -z "${MQTT_TLS_CA:-}" ]; then
    echo "[ERROR] MQTT_TLS_CA is required" >&2
    exit 1
fi
if [ -z "${MQTT_TLS_CERT:-}" ]; then
    echo "[ERROR] MQTT_TLS_CERT is required" >&2
    exit 1
fi
if [ -z "${MQTT_TLS_KEY:-}" ]; then
    echo "[ERROR] MQTT_TLS_KEY is required" >&2
    exit 1
fi

# ── Resolve auth-mode-specific settings ───────────────────────────────────────
case "$MQTT_AUTH_MODE" in
    cert)
        REQUIRE_CERTIFICATE="true"
        USE_IDENTITY_AS_USERNAME="true"
        PASSWORD_FILE_LINE="# password_file not used in cert-only mode"
        ;;
    password)
        REQUIRE_CERTIFICATE="false"
        USE_IDENTITY_AS_USERNAME="false"
        if [ -z "${MQTT_PASSWORD_FILE:-}" ]; then
            echo "[ERROR] MQTT_PASSWORD_FILE is required when MQTT_AUTH_MODE=password" >&2
            exit 1
        fi
        PASSWORD_FILE_LINE="password_file ${MQTT_PASSWORD_FILE}"
        ;;
    both)
        REQUIRE_CERTIFICATE="true"
        USE_IDENTITY_AS_USERNAME="true"
        if [ -z "${MQTT_PASSWORD_FILE:-}" ]; then
            echo "[ERROR] MQTT_PASSWORD_FILE is required when MQTT_AUTH_MODE=both" >&2
            exit 1
        fi
        PASSWORD_FILE_LINE="password_file ${MQTT_PASSWORD_FILE}"
        ;;
    *)
        echo "[ERROR] MQTT_AUTH_MODE must be one of: cert, password, both (got: ${MQTT_AUTH_MODE})" >&2
        exit 1
        ;;
esac

export MQTT_PORT MQTT_TLS_CA MQTT_TLS_CERT MQTT_TLS_KEY
export REQUIRE_CERTIFICATE USE_IDENTITY_AS_USERNAME PASSWORD_FILE_LINE

# ── Generate config from template ─────────────────────────────────────────────
TEMPLATE="/mosquitto/config/mosquitto.conf.template"
CONFIG="/mosquitto/config/mosquitto.conf"

echo "[INFO] Generating ${CONFIG} from template (MQTT_AUTH_MODE=${MQTT_AUTH_MODE}, port=${MQTT_PORT})"
envsubst < "$TEMPLATE" > "$CONFIG"

# ── Start Mosquitto ───────────────────────────────────────────────────────────
echo "[INFO] Starting Mosquitto MQTT broker on port ${MQTT_PORT}"
exec mosquitto -c "$CONFIG"

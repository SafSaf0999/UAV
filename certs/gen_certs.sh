#!/usr/bin/env bash
# gen_certs.sh — Generate TLS certificates for the anti-UAV MQTT broker and edge devices.
#
# Usage:
#   DEVICE_IDS="edge-01 edge-02 edge-03" ./gen_certs.sh
#
# Environment variables:
#   DEVICE_IDS   Space-separated list of device IDs to generate client certs for (required)
#   SERVER_CN    Common Name for the broker server cert (default: localhost)
#   FORCE        Set to 1 to regenerate all certs even if they already exist (default: 0)
#
# Output:
#   secrets/ca.key, secrets/ca.crt
#   secrets/server.key, secrets/server.crt
#   secrets/{device_id}.key, secrets/{device_id}.crt  (for each device in DEVICE_IDS)

set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
SECRETS_DIR="$(cd "$(dirname "$0")/.." && pwd)/secrets"
DAYS=3650
SERVER_CN="${SERVER_CN:-localhost}"
FORCE="${FORCE:-0}"

# ── Helpers ──────────────────────────────────────────────────────────────────
info()  { echo "[INFO]  $*"; }
warn()  { echo "[WARN]  $*"; }
error() { echo "[ERROR] $*" >&2; exit 1; }

should_generate() {
    local file="$1"
    if [[ -f "$file" && "$FORCE" != "1" ]]; then
        warn "Skipping — $file already exists (set FORCE=1 to overwrite)"
        return 1
    fi
    return 0
}

# ── Validate inputs ──────────────────────────────────────────────────────────
if [[ -z "${DEVICE_IDS:-}" ]]; then
    error "DEVICE_IDS environment variable is required (space-separated list of device IDs)"
fi

command -v openssl >/dev/null 2>&1 || error "openssl is not installed or not in PATH"

mkdir -p "$SECRETS_DIR"
info "Output directory: $SECRETS_DIR"

# ── 1. Certificate Authority ─────────────────────────────────────────────────
if should_generate "$SECRETS_DIR/ca.key"; then
    info "Generating CA private key..."
    openssl genrsa -out "$SECRETS_DIR/ca.key" 4096
fi

if should_generate "$SECRETS_DIR/ca.crt"; then
    info "Generating CA self-signed certificate (CN=anti-uav-ca, ${DAYS} days)..."
    openssl req -new -x509 \
        -days "$DAYS" \
        -key "$SECRETS_DIR/ca.key" \
        -out "$SECRETS_DIR/ca.crt" \
        -subj "/CN=anti-uav-ca/O=AntiUAV/OU=CA"
fi

# ── 2. Broker / Server Certificate ───────────────────────────────────────────
if should_generate "$SECRETS_DIR/server.key"; then
    info "Generating server private key..."
    openssl genrsa -out "$SECRETS_DIR/server.key" 2048
fi

if should_generate "$SECRETS_DIR/server.crt"; then
    info "Generating server certificate (CN=${SERVER_CN}, ${DAYS} days)..."
    openssl req -new \
        -key "$SECRETS_DIR/server.key" \
        -out "$SECRETS_DIR/server.csr" \
        -subj "/CN=${SERVER_CN}/O=AntiUAV/OU=Broker"

    openssl x509 -req \
        -days "$DAYS" \
        -in "$SECRETS_DIR/server.csr" \
        -CA "$SECRETS_DIR/ca.crt" \
        -CAkey "$SECRETS_DIR/ca.key" \
        -CAcreateserial \
        -out "$SECRETS_DIR/server.crt"

    rm -f "$SECRETS_DIR/server.csr"
fi

# ── 3. Per-Device Client Certificates ────────────────────────────────────────
for device_id in $DEVICE_IDS; do
    KEY_FILE="$SECRETS_DIR/${device_id}.key"
    CRT_FILE="$SECRETS_DIR/${device_id}.crt"
    CSR_FILE="$SECRETS_DIR/${device_id}.csr"

    if should_generate "$KEY_FILE"; then
        info "Generating client key for device: ${device_id}..."
        openssl genrsa -out "$KEY_FILE" 2048
    fi

    if should_generate "$CRT_FILE"; then
        info "Generating client certificate for device: ${device_id} (${DAYS} days)..."
        openssl req -new \
            -key "$KEY_FILE" \
            -out "$CSR_FILE" \
            -subj "/CN=${device_id}/O=AntiUAV/OU=EdgeDevice"

        openssl x509 -req \
            -days "$DAYS" \
            -in "$CSR_FILE" \
            -CA "$SECRETS_DIR/ca.crt" \
            -CAkey "$SECRETS_DIR/ca.key" \
            -CAcreateserial \
            -out "$CRT_FILE"

        rm -f "$CSR_FILE"
    fi
done

# ── Done ─────────────────────────────────────────────────────────────────────
info "Certificate generation complete."
info ""
info "Files in $SECRETS_DIR:"
ls -1 "$SECRETS_DIR"

# TLS Certificate Generation

`gen_certs.sh` generates a self-signed CA, a broker server certificate, and per-device client certificates for the anti-UAV MQTT system. All output is written to `secrets/` which is excluded from version control.

## Prerequisites

- `openssl` must be installed and available in `PATH`

## Usage

```bash
DEVICE_IDS="edge-01 edge-02 edge-03" ./certs/gen_certs.sh
```

### Environment Variables

| Variable     | Required | Default       | Description                                                  |
|--------------|----------|---------------|--------------------------------------------------------------|
| `DEVICE_IDS` | Yes      | —             | Space-separated list of device IDs to generate client certs for |
| `SERVER_CN`  | No       | `localhost`   | Common Name for the broker server certificate (use the broker's hostname or IP) |
| `FORCE`      | No       | `0`           | Set to `1` to regenerate all certificates even if they already exist |

### Examples

Generate certs for three devices with a custom broker hostname:

```bash
SERVER_CN=broker.example.com \
DEVICE_IDS="edge-01 edge-02 edge-03" \
./certs/gen_certs.sh
```

Force-regenerate all certs (e.g., after a CA rotation):

```bash
FORCE=1 DEVICE_IDS="edge-01 edge-02" ./certs/gen_certs.sh
```

## Output Files

All files are written to `secrets/`:

| File                  | Description                                      |
|-----------------------|--------------------------------------------------|
| `ca.key`              | CA private key — keep secret, never distribute   |
| `ca.crt`              | CA certificate — distribute to all clients and the broker |
| `server.key`          | Broker private key                               |
| `server.crt`          | Broker certificate signed by the CA             |
| `{device_id}.key`     | Client private key for each edge device          |
| `{device_id}.crt`     | Client certificate signed by the CA for each edge device |

Certificates are valid for **3650 days** (10 years).

## Idempotency

The script is idempotent by default — it skips generating a file if it already exists. Set `FORCE=1` to overwrite existing files.

## Mosquitto Broker Configuration

Reference the generated files in `mosquitto.conf`:

```
listener 8883
cafile /secrets/ca.crt
certfile /secrets/server.crt
keyfile /secrets/server.key
require_certificate true
```

## Edge Device Configuration

Each edge device uses its own client cert pair and the shared CA cert:

```yaml
mqtt:
  host: broker.example.com
  port: 8883
  tls:
    ca_cert: /certs/ca.crt
    client_cert: /certs/edge-01.crt
    client_key: /certs/edge-01.key
```

Mount the relevant files into the edge device container (or copy them to the device):

- `secrets/ca.crt` → `/certs/ca.crt`
- `secrets/edge-01.crt` → `/certs/edge-01.crt`
- `secrets/edge-01.key` → `/certs/edge-01.key`

## Security Notes

- `secrets/` is listed in `.gitignore` — never commit private keys or certificates
- The CA private key (`ca.key`) should be stored securely and only used to sign new certs
- Rotate certificates by running the script with `FORCE=1` and redeploying all affected services

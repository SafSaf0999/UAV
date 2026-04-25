# WireGuard VPN Setup

This directory contains a WireGuard configuration template for securing remote
access to the UAV Control Center.

## Prerequisites

- WireGuard installed on the main device host (`apt install wireguard` on Debian/Ubuntu)
- `wg` and `wg-quick` CLI tools available

## Quick Start

### 1. Generate server key pair

```bash
wg genkey | tee secrets/server_wg.key | wg pubkey > secrets/server_wg.pub
```

### 2. Generate operator key pair (repeat per operator)

```bash
wg genkey | tee secrets/operator1_wg.key | wg pubkey > secrets/operator1_wg.pub
```

### 3. Generate edge device key pair (repeat per device)

```bash
wg genkey | tee secrets/edge1_wg.key | wg pubkey > secrets/edge1_wg.pub
```

### 4. Create the server config

```bash
cp docker/wireguard/wg0.conf.example /etc/wireguard/wg0.conf
# Edit /etc/wireguard/wg0.conf and fill in the generated keys
```

### 5. Start WireGuard

```bash
wg-quick up wg0
# Enable on boot:
systemctl enable wg-quick@wg0
```

### 6. Operator client config

Create `/etc/wireguard/wg0.conf` on the operator's machine:

```ini
[Interface]
PrivateKey = <OPERATOR_PRIVATE_KEY>
Address = 10.8.0.2/24
DNS = 1.1.1.1

[Peer]
PublicKey = <SERVER_PUBLIC_KEY>
Endpoint = <SERVER_PUBLIC_IP>:51820
AllowedIPs = 10.8.0.0/24
PersistentKeepalive = 25
```

### 7. Edge device client config

Same as operator config but with the edge device's key pair and IP (e.g. 10.8.0.10).

## Docker Integration (optional)

To run WireGuard inside Docker, add this service to `docker-compose.yml`:

```yaml
wireguard:
  image: linuxserver/wireguard
  cap_add:
    - NET_ADMIN
    - SYS_MODULE
  environment:
    - PUID=1000
    - PGID=1000
    - TZ=UTC
    - SERVERURL=<YOUR_PUBLIC_IP>
    - SERVERPORT=51820
    - PEERS=operator1,edge1
    - PEERDNS=auto
    - INTERNAL_SUBNET=10.8.0.0
  volumes:
    - ./wireguard:/config
    - /lib/modules:/lib/modules
  ports:
    - 51820:51820/udp
  sysctls:
    - net.ipv4.conf.all.src_valid_mark=1
  restart: unless-stopped
```

## Security Notes

- Never commit private keys to version control (`secrets/` is in `.gitignore`)
- Use `PresharedKey` for additional post-quantum resistance
- Rotate keys periodically
- The control center is only accessible via VPN when `REMOTE_ACCESS_MODE=vpn`

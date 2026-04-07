# Android Remote Access via WireGuard

This guide sets up a WireGuard VPN peer on your Android phone so you can access the Anti-UAV Control Center from anywhere securely.

---

## Prerequisites

- WireGuard installed on the main laptop (host service or Docker container)
- WireGuard app installed on Android (Play Store: "WireGuard")
- Main laptop has a public IP or domain name (or you're on the same network)

---

## 1. Generate Android peer keys (on main laptop)

```bash
# Generate a key pair for the Android peer
wg genkey | tee android-private.key | wg pubkey > android-public.key
cat android-private.key   # keep this secret
cat android-public.key    # add to server config
```

---

## 2. Add Android peer to server config

Edit `/etc/wireguard/wg0.conf` (or your WireGuard config file):

```ini
[Peer]
# Android phone
PublicKey = <android-public.key contents>
AllowedIPs = 10.0.0.2/32
```

Reload WireGuard:
```bash
sudo wg syncconf wg0 <(wg-quick strip wg0)
# or
sudo systemctl reload wg-quick@wg0
```

---

## 3. Create Android peer config

Create a file `android-peer.conf`:

```ini
[Interface]
PrivateKey = <android-private.key contents>
Address = 10.0.0.2/32
DNS = 1.1.1.1

[Peer]
PublicKey = <server-public.key contents>
Endpoint = <your-main-laptop-public-ip>:51820
AllowedIPs = 10.0.0.1/32
PersistentKeepalive = 25
```

Replace:
- `<android-private.key contents>` — from step 1
- `<server-public.key contents>` — run `wg show wg0 public-key` on main laptop
- `<your-main-laptop-public-ip>` — your public IP or domain

---

## 4. Import config to Android via QR code

On the main laptop, generate a QR code:

```bash
# Install qrencode if needed
sudo pacman -S qrencode   # Arch/CachyOS

# Generate QR code from the config file
qrencode -t ansiutf8 < android-peer.conf
```

On Android:
1. Open the WireGuard app
2. Tap **+** → **Scan from QR code**
3. Scan the QR code displayed in your terminal
4. Name the tunnel (e.g. "UAV Control")
5. Tap the toggle to connect

---

## 5. Access the control center from Android

Once connected to WireGuard:

- Anti-UAV Control Center: `http://10.0.0.1:8080`
- Install as PWA: open in Chrome → tap ⋮ menu → **Add to Home Screen**

The PWA installs as a standalone app with the UAV radar icon. It works like a native app — no browser chrome, full screen.

---

## 6. Verify connection

```bash
# On main laptop — check if Android peer is connected
sudo wg show wg0
```

You should see the Android peer with a recent handshake timestamp.

---

## Troubleshooting

**Can't connect to WireGuard**
- Check that UDP port 51820 is open: `sudo ufw allow 51820/udp`
- Verify the server public IP is correct in the peer config

**Control center not loading**
- Confirm WireGuard is connected (green indicator in the app)
- Try `http://10.0.0.1:8080` directly in Chrome
- Check that the control center Docker service is running

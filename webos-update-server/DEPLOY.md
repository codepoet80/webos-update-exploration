# Deploying the webOS Community Update Server

Target host: **`swupdate.webosarchive.org`** — matches Palm's original OTA update
subdomain (`omadm.swupdate.palm.com`). Devices are pointed at this host by the
OTA Ready (Beta) app; it does not replace Palm's DNS, it stands in for a server
that no longer exists.

## 1. Runtime

FastAPI + uvicorn, Python 3.9+. No system packages needed beyond Python.

```bash
cd webos-update-server
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

If the host's Python lacks `ensurepip`/`venv` (minimal images), bootstrap pip:

```bash
python3 -m venv --without-pip .venv
curl -sS https://bootstrap.pypa.io/get-pip.py | .venv/bin/python
.venv/bin/pip install -r requirements.txt
```

## 2. Configuration (environment variables)

| Var | Purpose | Example |
|-----|---------|---------|
| `PUBLIC_HOST` | Public hostname → `SERVER_URL` becomes `https://<host>` (used in download URLs) | `swupdate.webosarchive.org` |
| `SERVER_URL` | Override the full base URL verbatim (wins over `PUBLIC_HOST`) | `https://swupdate.webosarchive.org` |
| `LOG_FILE` | Persistent rotating access log (else stdout/journald only) | `/var/log/webos-update-server.log` |

With none set, `SERVER_URL` auto-detects the LAN IP (local dev). In production set
`PUBLIC_HOST` so the package `url`s handed to devices resolve publicly.

## 3. systemd unit

`/etc/systemd/system/webos-update.service`:

```ini
[Unit]
Description=webOS Community Update Server
After=network.target

[Service]
WorkingDirectory=/opt/webos-update-server
Environment=PUBLIC_HOST=swupdate.webosarchive.org
Environment=LOG_FILE=/var/log/webos-update-server.log
ExecStart=/opt/webos-update-server/.venv/bin/uvicorn server:app --host 127.0.0.1 --port 8080
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now webos-update
```

Bind uvicorn to `127.0.0.1` and let the reverse proxy terminate TLS on the public
interface.

## 4. Reverse proxy + TLS

The point of this whole project is modern TLS on old TouchPads, so serve HTTPS.
Target devices are `READY` (they already have the TLS 1.3 suite), so a modern
Let's Encrypt cert is reachable by them.

**Caddy** (automatic certs) — `/etc/caddy/Caddyfile`:

```
swupdate.webosarchive.org {
    reverse_proxy 127.0.0.1:8080
}
```

**nginx** equivalent: `proxy_pass http://127.0.0.1:8080;` in a TLS `server {}` for
`swupdate.webosarchive.org`, with certs from certbot. Forward `X-Forwarded-For`
(the server already reads it via `get_client_ip`) so per-device stats show the real IP.

DNS: an `A` record for `swupdate.webosarchive.org` → the host's public IP.

## 5. Health & logging

- **`GET /health`** — liveness for uptime monitors: status, uptime, version,
  `public_url`, package count, `requests_total`, `unique_clients`, `errors`.
- **`GET /api/stats`** — beta health: traffic by endpoint, status-code counts,
  per-device rows (ip, build, baseline, checks, downloads, last-seen), recent requests.
- **`LOG_FILE`** — rotating access log; each request logs `ACCESS <ip> <method> <path> -> <status> [build/baseline]`.

Quick check once live:

```bash
curl -s https://swupdate.webosarchive.org/health | python3 -m json.tool
curl -s https://swupdate.webosarchive.org/api/stats | python3 -m json.tool
```

> `/api/stats` and `/health` are unauthenticated and expose client IPs — fine
> behind a trusted proxy, but put them behind basic-auth or an allowlist if the
> host is public and you consider that sensitive.

## 6. Point a device at it

On the TouchPad (OTA Ready daemon reads this):

```bash
echo "https://swupdate.webosarchive.org" > /media/internal/.otaready/server-url
```

Absent that file, the daemon falls back to its compiled-in default. For the LAN
demo we used `http://<dev-ip>:8080`.

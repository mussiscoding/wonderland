---
title: "feat: Go live — multi-project VPS deploy (wonderland + leagues)"
type: feat
status: active
date: 2026-04-19
---

# Go Live — Multi-Project VPS Deploy

Deploy wonderland and leagues to a single Hetzner VPS with Caddy, systemd, and SQLite. Two subdomains, two services, one server.

## Overview

Based on [go-live brainstorm](../brainstorms/2026-04-09-go-live-brainstorm.md). The key constraint is that much of this work happens outside a Claude session (buying domains, provisioning servers, configuring Spotify dashboard). This plan separates steps into what the user does manually vs what Claude can prepare as files.

## Three repos

Shared server config lives in its own repo so neither project is the implicit "base". Each project repo holds only its own concerns.

```
/srv/server/         ← shared infra: Caddyfile, backup script, deploy script, systemd templates, hub page
/srv/wonderland/     ← wonderland app + its own systemd service/timer files
/srv/leagues/        ← leagues app + its own systemd service file
```

---

## Step 1 — Claude prepares config files locally

> **Who:** Claude
> **When:** Before the server exists — all files can be written now

### 1a. Create the `server` repo

New repo at `/Users/johnmusson/myCode/server/` with:

```
server/
  Caddyfile
  backup.sh
  deploy.sh
  systemd/
    project-backup@.service
    project-backup@wonderland.timer
    project-backup@leagues.timer
  hub/
    index.html              # simple landing page linking to subdomains (can be placeholder for now)
```

**`Caddyfile`:**
```
wonderland.johng.me {
    reverse_proxy 127.0.0.1:8000
}

leagues.johng.me {
    reverse_proxy 127.0.0.1:8001
}

johng.me {
    root * /srv/server/hub
    file_server
}
```

Note: `johng.me` gets replaced once the domain is chosen.

**`backup.sh`:**
```bash
#!/usr/bin/env bash
set -euo pipefail
BACKUP_DIR="/var/backups/$1"
mkdir -p "$BACKUP_DIR"
for db in /srv/"$1"/data/*.db; do
    name=$(basename "$db")
    sqlite3 "$db" ".backup '$BACKUP_DIR/${name%.db}-$(date +%Y%m%d).db'"
done
find "$BACKUP_DIR" -name "*.db" -mtime +7 -delete
```

**`deploy.sh`:**
```bash
#!/usr/bin/env bash
set -euo pipefail
cd /srv/"$1"
git pull
.venv/bin/pip install -r requirements.txt
sudo systemctl restart "$1"
```

Usage: `deploy.sh wonderland` or `deploy.sh leagues`.

**`systemd/project-backup@.service`:**
```ini
[Unit]
Description=Backup %i SQLite databases

[Service]
Type=oneshot
ExecStart=/usr/local/bin/project-backup %i
```

**`systemd/project-backup@wonderland.timer`** and **`systemd/project-backup@leagues.timer`:**
- `OnCalendar=daily`, `Persistent=true`

### 1b. Wonderland systemd files

In the wonderland repo, create `deploy/`:

**`deploy/wonderland.service`:**
```ini
[Unit]
Description=Wonderland gig finder
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/srv/wonderland
EnvironmentFile=/etc/wonderland.env
ExecStart=/srv/wonderland/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**`deploy/wonderland-fetch.service`** + **`deploy/wonderland-fetch.timer`:**
- Service: runs `python -m app.fetch_cli --cities london,berlin` (CLI entrypoint, bypasses HTTP auth)
- Timer: `OnCalendar=weekly`, `Persistent=true`

### 1c. Leagues systemd file

In the leagues repo, create `deploy/`:

**`deploy/leagues.service`:**
```ini
[Unit]
Description=League planner
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/srv/leagues
ExecStart=/srv/leagues/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 1d. CLI fetch entrypoint (wonderland only)

Create `app/fetch_cli.py` — a small script that imports the scraper logic and runs it directly, so the systemd timer doesn't need HTTP auth. Resolves the open question from the brainstorm.

### 1e. Environment template

The wonderland repo already has `.env.example` with all required variables. Step 3e references it directly — no separate deploy template needed. Just update `.env.example` to include a comment noting the production redirect URI format (`https://wonderland.johng.me/callback`).

### 1f. Deploy documentation

Add `docs/deploy.md` to each project repo: server hostname, systemd unit names, port, secret locations, rollback steps, backup restore steps. The server repo gets a short README covering the Caddyfile and shared scripts.

### Acceptance criteria — Step 1

- [ ] `server` repo created with: `Caddyfile`, `backup.sh`, `deploy.sh`, `systemd/` (template service + timers), `hub/index.html`
- [ ] `deploy/` in wonderland repo with: `wonderland.service`, `wonderland-fetch.service`, `wonderland-fetch.timer`
- [ ] `deploy/` in leagues repo with: `leagues.service`
- [ ] `app/fetch_cli.py` exists in wonderland and can be invoked as `python -m app.fetch_cli`
- [ ] `.env.example` updated with production redirect URI comment
- [ ] `docs/deploy.md` in each repo

---

## Step 2 — User: domain + DNS + VPS

> **Who:** User (manual, outside Claude)
> **When:** Whenever ready

### 2a. Register a domain

- Pick a registrar (Porkbun, Cloudflare, Namecheap — all fine)
- Transfer DNS to Cloudflare (free tier) regardless of registrar

### 2b. Provision the VPS

- Hetzner CX22 (~€4/mo), Ubuntu 24.04, EU region
- SSH key only (no password login)
- Note the server IP

### 2c. DNS records

In Cloudflare, create:
- `A` record: `wonderland.johng.me` → server IP
- `A` record: `leagues.johng.me` → server IP
- `A` record: `johng.me` → server IP (for hub page)
- (Or `*.johng.me` wildcard + apex — covers everything)

### 2d. Update Spotify developer dashboard

- Add `https://wonderland.johng.me/callback` as a redirect URI
- Keep `http://127.0.0.1:8000/callback` for local dev
- Add friends' Spotify emails to the app allowlist (≤25 users, stays in dev mode)

### Acceptance criteria — Step 2

- [ ] Domain registered, DNS on Cloudflare
- [ ] VPS provisioned, SSH access working
- [ ] DNS A records pointing to server IP
- [ ] Spotify redirect URI updated

---

## Step 3 — User: server bootstrap

> **Who:** User (SSH into server)
> **When:** After Step 2

### 3a. Basic server hardening

```bash
# Create non-root user
sudo adduser deploy --disabled-password
sudo usermod -aG sudo deploy

# Firewall
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```

### 3b. Install dependencies

```bash
sudo apt update && sudo apt install -y python3.12 python3.12-venv sqlite3 rclone
# Install Caddy (official apt repo)
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
```

### 3c. Clone all three repos + set up venvs

```bash
sudo mkdir -p /srv
sudo chown deploy:deploy /srv

# server (shared infra)
git clone <server-repo-url> /srv/server

# wonderland
git clone <wonderland-repo-url> /srv/wonderland
cd /srv/wonderland && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt

# leagues
git clone <leagues-repo-url> /srv/leagues
cd /srv/leagues && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

### 3d. Copy databases from local machine

From your laptop:
```bash
scp data/wonderland.db deploy@<server-ip>:/srv/wonderland/data/
scp /Users/johnmusson/myCode/leagues/data/planner.db deploy@<server-ip>:/srv/leagues/data/
```

Also copy Eventbrite venue cache files:
```bash
scp data/eventbrite_venues_*.json deploy@<server-ip>:/srv/wonderland/data/
```

### 3e. Write secrets file (wonderland only)

```bash
sudo cp /srv/wonderland/.env.example /etc/wonderland.env
sudo chmod 600 /etc/wonderland.env
sudo nano /etc/wonderland.env  # fill in real values from local .env
```

**Critical:** reuse the same `FERNET_KEY` from local `.env` so encrypted Spotify tokens keep working. Update `SPOTIFY_REDIRECT_URI` to `https://wonderland.johng.me/callback`.

### Acceptance criteria — Step 3

- [ ] `deploy` user exists, SSH works, UFW active
- [ ] Python 3.12, Caddy, sqlite3 installed
- [ ] All three repos cloned to `/srv/`
- [ ] Venvs created and deps installed for wonderland and leagues
- [ ] Databases copied to server
- [ ] `/etc/wonderland.env` populated with real secrets

---

## Step 4 — User: install config files + start services

> **Who:** User (SSH into server)
> **When:** After Step 3

### 4a. Install shared infra from server repo

```bash
# Backup script
sudo cp /srv/server/backup.sh /usr/local/bin/project-backup
sudo chmod +x /usr/local/bin/project-backup
sudo mkdir -p /var/backups/wonderland /var/backups/leagues

# Deploy script
sudo cp /srv/server/deploy.sh /usr/local/bin/project-deploy
sudo chmod +x /usr/local/bin/project-deploy

# Shared systemd units (backup template + timers)
sudo cp /srv/server/systemd/* /etc/systemd/system/

# Caddyfile
sudo cp /srv/server/Caddyfile /etc/caddy/Caddyfile
sudo nano /etc/caddy/Caddyfile  # replace johng.me with actual domain
```

### 4b. Install project systemd units

```bash
# Wonderland service + fetch timer
sudo cp /srv/wonderland/deploy/* /etc/systemd/system/

# Leagues service
sudo cp /srv/leagues/deploy/* /etc/systemd/system/

sudo systemctl daemon-reload
```

### 4c. Enable and start everything

```bash
sudo systemctl enable --now wonderland leagues wonderland-fetch.timer project-backup@wonderland.timer project-backup@leagues.timer
sudo systemctl reload caddy
```

### 4d. Verify everything works

```bash
# Check services are running
sudo systemctl status wonderland leagues

# Check Caddy got TLS certs
sudo systemctl status caddy

# Test from the server
curl -s http://127.0.0.1:8000 | head -5
curl -s http://127.0.0.1:8001 | head -5

# Test from your browser
# Visit https://wonderland.johng.me and https://leagues.johng.me
```

### Acceptance criteria — Step 4

- [ ] Both services running (`systemctl status` shows active)
- [ ] Caddy serving HTTPS on all subdomains + apex
- [ ] Timers enabled (fetch weekly, backups nightly)
- [ ] Sites accessible in browser over HTTPS
- [ ] Spotify OAuth flow works on wonderland (login → callback → dashboard)

---

## Summary: who does what

| Step | Who | What |
|------|-----|------|
| 1a | Claude | Create `server` repo with shared infra (Caddyfile, scripts, systemd templates, hub page) |
| 1b | Claude | Write wonderland systemd service + fetch timer |
| 1c | Claude | Write leagues systemd service |
| 1d | Claude | Write CLI fetch entrypoint for wonderland |
| 1e | Claude | Update `.env.example` with production comment |
| 1f | Claude | Write deploy docs for each repo |
| 2a | User | Register domain |
| 2b | User | Provision Hetzner VPS |
| 2c | User | Create DNS records in Cloudflare |
| 2d | User | Update Spotify dashboard redirect URI + allowlist |
| 3a–3e | User | SSH server setup: user, firewall, deps, clone all 3 repos, DBs, secrets |
| 4a–4d | User | Install config files, start services, verify |

## Open questions (carried from brainstorm)

- **Which domain?** To be chosen at registration time.

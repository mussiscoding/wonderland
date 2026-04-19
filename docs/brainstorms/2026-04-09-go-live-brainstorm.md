---
date: 2026-04-09
topic: go-live
---

# Going Live (Small Personal Deploy)

## What We're Building

Move hobby projects off localhost so a handful of friends (≤5) can use them from real URLs, without requiring the laptop to be on. The server will host multiple FastAPI apps as independent subdomains on a personal domain. Tiny VPS, SQLite per app, no enterprise-grade ops.

**Initial projects:**
- **wonderland** (`wonderland.johng.me`) — gig finder with Spotify OAuth, weekly scraper cron
- **leagues** (`leagues.johng.me`) — league task planner/tracker, no auth or secrets needed

## Why This Approach

For a ≤5-user hobby app, the "standard production checklist" (Docker, CI/CD, Postgres, Sentry, GDPR, staging, etc.) is pure overhead. This plan deliberately cuts all of it and commits to the simplest stack that runs 24/7, serves HTTPS, and survives a reboot. If any of the cut items later starts *actually* hurting, it can be added then.

Shape considered and rejected:
- **Tailscale / Cloudflare Tunnel (laptop-hosted)** — rejected because the laptop shouldn't have to be on, and sharing links with friends should work without enrolling them in a VPN.
- **Subpath (`myname.com/projects/wonderland`)** — rejected because it forces root-path refactoring of the FastAPI app (root_path config, template URL audits, OAuth redirect rewrites) for no meaningful gain.
- **Free-tier PaaS (Fly/Railway)** — rejected because SQLite on ephemeral disks is fragile, and a fixed-price €4 VPS is simpler and more predictable than tier limits.

## Key Decisions

- **Three repos**: a `server` repo for shared infra (Caddyfile, backup/deploy scripts, systemd templates, hub page), plus one repo per project. No project is the implicit "base" — shared config lives in `server`. Adding a project means: new service file in its repo, new Caddyfile block + backup timer in `server`.
- **Subdomain per project**: `wonderland.johng.me`, `leagues.johng.me`, etc. The hub page at `johng.me` is a static landing page served from the `server` repo. Projects stay fully independent — each has its own repo, venv, systemd unit, SQLite DB, and port.
- **Single small VPS** (Hetzner CX22, ~€4/mo, EU region). Ubuntu 24.04. No Docker — systemd is enough.
- **Caddy as reverse proxy + TLS**: auto HTTPS via Let's Encrypt, trivial config, no cron jobs to maintain certs.
- **SQLite stays**: the current DB is copied up on first deploy. Fernet key is copied up too so existing encrypted Spotify tokens keep working. Friends re-authing is an acceptable fallback if anything goes wrong.
- **Spotify dev mode, not extended quota**: stay under 25 allowlisted users to skip privacy policy / terms / demo video submission.
- **Scrapers on a weekly cron**: systemd timer (or plain cron) hits `/admin/fetch` once a week. Manual trigger still available via admin UI.
- **Backups as a cron script**: nightly `sqlite3 .backup` into `/backups/`, keep last 7 days. Optional weekly `rclone` push to a free B2/R2 bucket for off-server safety.
- **Deploy flow**: `git pull && systemctl restart wonderland`. No CI, no staging. Blast radius is 5 friends.
- **Explicitly not doing (yet)**: Docker, Postgres, Redis, Sentry, uptime monitoring, rate limiting, log aggregation, privacy policy, terms of service, cookie banner, GDPR DPA, CI/CD, staging env, secrets manager, WAF.

## Scope

### Infrastructure
- Buy a personal domain (registrar TBD — Porkbun / Cloudflare / Namecheap are all fine). Put DNS on Cloudflare regardless of registrar (free, fast, and gives us room for more projects).
- Provision a Hetzner CX22 (or equivalent), Ubuntu 24.04, SSH key only, no password login, UFW allowing 22/80/443.
- DNS: `A` records for `wonderland.johng.me` and `leagues.johng.me` → server IP. (Or a single `*.johng.me` wildcard — simple and future-proof for adding more projects.) Later, add a static landing page at the apex for the projects hub.

### Server setup (one-off)
- Create a non-root user to run the apps.
- Install: Python 3.12, `uv` or plain `venv`, `caddy`, `sqlite3`, `rclone`.
- Clone all three repos into `/srv/`:
  - `/srv/server` — shared infra (Caddyfile, scripts, systemd templates, hub page)
  - `/srv/wonderland` — create venv, install deps
  - `/srv/leagues` — create venv, install deps
- Copy SQLite DBs from local → server (scp):
  - `data/wonderland.db` → `/srv/wonderland/data/`
  - `data/*.db` → `/srv/leagues/data/`
- **wonderland secrets**: Write `/etc/wonderland.env` (chmod 600) with all secrets from the local `.env`, **reusing the same `fernet_key`** so encrypted tokens keep working. Update `spotify_redirect_uri` to `https://wonderland.johng.me/callback`.
- **leagues**: No `.env` needed — no secrets, no OAuth.

### Systemd
Each project gets its own service on a unique port. Pattern: `<project>.service` on port 800N.

**wonderland (port 8000):**
- `/etc/systemd/system/wonderland.service` — runs `uvicorn app.main:app --host 127.0.0.1 --port 8000`, `EnvironmentFile=/etc/wonderland.env`, `Restart=always`, `User=deploy`.
- `/etc/systemd/system/wonderland-fetch.service` + `wonderland-fetch.timer` — weekly timer that `curl`s `/admin/fetch` (or invokes a small CLI entrypoint directly, avoiding HTTP auth entirely — see open question).
- `/etc/systemd/system/wonderland-backup.service` + `.timer` — nightly `sqlite3 .backup` into `/var/backups/wonderland/`, keep last 7.

**leagues (port 8001):**
- `/etc/systemd/system/leagues.service` — runs `uvicorn app.main:app --host 127.0.0.1 --port 8001`, `WorkingDirectory=/srv/leagues`, `Restart=always`, `User=deploy`.
- `/etc/systemd/system/leagues-backup.service` + `.timer` — nightly `sqlite3 .backup` into `/var/backups/leagues/`, keep last 7.
- No fetch timer needed — scraping is manual via the UI.

### Caddy
- `/etc/caddy/Caddyfile`:
  ```
  wonderland.johng.me {
      reverse_proxy 127.0.0.1:8000
  }

  leagues.johng.me {
      reverse_proxy 127.0.0.1:8001
  }
  ```
- That's it. Caddy handles TLS automatically for all subdomains. Adding a new project is just another block + port.

### Spotify app config
- In the Spotify developer dashboard, add `https://wonderland.johng.me/callback` as an additional redirect URI (keep the localhost one for local dev).
- Add each friend's Spotify account email to the app's user allowlist.

### Deploy script
Single parameterized script in the `server` repo: `deploy.sh wonderland` or `deploy.sh leagues`.

### Documentation
- Add a short `docs/deploy.md` to each repo capturing: the server hostname, the systemd unit names, the port, where secrets live (if any), how to roll back (git checkout prev commit + restart), how to restore from backup.

## Open Questions

- ~~**How should the weekly scraper trigger auth itself?**~~ **Resolved:** CLI entrypoint (`app/fetch_cli.py`) invoked by systemd timer, bypassing HTTP auth entirely.
- **Which domain?** To be chosen at registration time. Needs to be short-ish, memorable, and acceptable as a long-term personal hub.
- ~~**Where does the hub page live?**~~ **Resolved:** In the `server` repo at `hub/index.html`, served by Caddy from `/srv/server/hub/`.
- ~~**Do we need a staging subdomain?**~~ **Resolved:** No. Test locally, deploy straight to prod.
- ~~**Shared user or per-project user?**~~ **Resolved:** A single `deploy` Linux user running all apps. Project-neutral name works better than naming it after one project.

## Next Steps
→ Plan written: [2026-04-19-feat-go-live-multi-project-deploy-plan.md](../plans/2026-04-19-feat-go-live-multi-project-deploy-plan.md)

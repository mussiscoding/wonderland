#!/usr/bin/env bash
# Deploy wonderland (dance-time) to the Hetzner box.
#
# Usage: bash deploy/deploy.sh
#
# Pushes the current branch to GitHub, pulls on the server as the deploy user,
# installs any new requirements into the venv, restarts the systemd service,
# and pings the site to confirm it's up.
#
# Gotcha: the repo is `mussiscoding/wonderland` and only that GitHub account
# has push access. If `git push` is rejected, run `gh auth switch --user
# mussiscoding` and retry.
set -euo pipefail

SSH_HOST="root@46.225.17.228"
SSH_KEY="$HOME/.ssh/id_ed25519_personal"
SERVER_PATH="/srv/wonderland"
SERVICE="wonderland"
HEALTH_URL="https://wonderland.johng.me/"

cyan() { printf '\033[36m%s\033[0m\n' "$*"; }
red()  { printf '\033[31m%s\033[0m\n' "$*"; }

cd "$(dirname "$0")/.."

if ! git diff --quiet || ! git diff --cached --quiet; then
  red "Working tree has uncommitted changes. Commit or stash before deploying."
  git status --short
  exit 1
fi

BRANCH=$(git rev-parse --abbrev-ref HEAD)
LOCAL_SHA=$(git rev-parse HEAD)

cyan "==> Pushing $BRANCH to origin"
git push origin "$BRANCH"

cyan "==> Deploying $LOCAL_SHA on $SSH_HOST"
ssh -i "$SSH_KEY" "$SSH_HOST" "
  set -e
  sudo -u deploy bash -lc '
    set -euo pipefail
    cd $SERVER_PATH
    git fetch --quiet origin
    git reset --hard origin/$BRANCH
    .venv/bin/pip install --quiet -r requirements.txt
  '
  systemctl restart $SERVICE
"

cyan "==> Verifying"
# Healthy = 307 (redirect to /login) on an unauthenticated request. Treat any
# 2xx/3xx as live. Retry briefly: Caddy can briefly 502 while reconnecting to
# the freshly-restarted upstream.
code=""
for attempt in 1 2 3 4 5 6 7 8 9 10; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$HEALTH_URL")
  case "$code" in
    2*|3*) break ;;
  esac
  sleep 1
done
printf '  %s  %s\n' "$code" "$HEALTH_URL"
case "$code" in
  2*|3*) ;;
  *) red "Health check returned $code after 10s of retries"; exit 1 ;;
esac

REMOTE_SHA=$(ssh -i "$SSH_KEY" "$SSH_HOST" "sudo -u deploy git -C $SERVER_PATH rev-parse HEAD")
if [ "$REMOTE_SHA" = "$LOCAL_SHA" ]; then
  cyan "==> Live SHA matches local: $LOCAL_SHA"
else
  red "Live SHA $REMOTE_SHA != local $LOCAL_SHA"
  exit 1
fi

cyan "==> Done"

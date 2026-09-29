#!/usr/bin/env bash
# Builds this fork from source and starts it with a preconfigured Keycloak.
set -euo pipefail
cd "$(dirname "$0")"

COMPOSE=(docker compose
  -f docker-compose.yml
  -f docker-compose.onyx-lite.yml
  -f docker-compose.local-fork.yml
  --env-file env.local-fork)

if [[ "${1:-}" == "down" ]]; then
  "${COMPOSE[@]}" down
  exit 0
fi

# Service env file (read by every Onyx container). Created once with fresh secrets.
if [[ ! -f .env ]]; then
  cp env.template .env
  secret="$(openssl rand -hex 32)"
  sed -i.bak "s/^USER_AUTH_SECRET=.*/USER_AUTH_SECRET=\"${secret}\"/" .env && rm -f .env.bak
  echo "Created .env with a generated USER_AUTH_SECRET"
fi

if [[ "${SKIP_BUILD:-}" != "1" ]]; then
  docker build -t onyx-fork-backend:local ../../backend
  docker build -t onyx-fork-web:local \
    --build-arg NODE_OPTIONS=--max-old-space-size=4096 ../../web
fi

"${COMPOSE[@]}" up -d --wait

cat <<'MSG'

Onyx fork is running:
  Onyx       http://localhost:3030   (first sign-up with email/password becomes admin)
  Keycloak   http://keycloak.localhost:8180   (console: admin / admin)

Keycloak test users (realm "onyx", password Password123!):
  admin@example.com, jan.kowalski@example.com, maria.nowak@example.com

Stop:  ./start-local-fork.sh down
MSG

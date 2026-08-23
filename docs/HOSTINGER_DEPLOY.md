# Hostinger deployment

The real deployment: `api.sgummallaworks.com/knowledge` (API, path-prefixed — that domain hosts
multiple APIs) and `knowledge.sgummallaworks.com` (webui, its own subdomain). Three containers —
Caddy (the only one reachable from outside the box: reverse proxy, automatic HTTPS, and static
webui serving), `knowledge-api` (the published Docker Hub image), `knowledge-db`
(Postgres/pgvector) — all defined in `deploy/docker-compose.prod.yml`.

Caddy was chosen over Traefik for this: a single, human-readable `Caddyfile` beats debugging
label-based routing spread across services, and automatic HTTPS needs zero extra configuration.
The one thing this trades away is Traefik's automatic Docker-service-discovery — adding a future
API to `api.sgummallaworks.com` means adding a `handle_path` block to `deploy/Caddyfile` and
reloading, not a fully hands-off addition. Worth it for a solo operator.

## Known limitation

`GET /.well-known/oauth-authorization-server` (RFC 8414 discovery) is required by spec to live at
the domain root, but `api.sgummallaworks.com` is shared across multiple APIs each wanting their own
issuer identity — genuinely incompatible with path-based sharing. It's left unrouted (404s
externally) rather than faked. Nothing currently depends on it: MCP clients authenticate with a
pasted personal access token, not OAuth auto-discovery. Revisit only if a future integration
actually needs live discovery.

## One-time setup

### 1. DNS

- `api.sgummallaworks.com` already resolves to this box (`31.220.50.148`) — nothing to do.
- Add an **A record**: `knowledge.sgummallaworks.com` → `31.220.50.148`. Give it a few minutes to
  propagate before starting the stack (Let's Encrypt's HTTP challenge needs it resolving correctly
  first, or certificate issuance will fail).

### 2. Install Docker on the box

```bash
curl -fsSL https://get.docker.com | sh
```

Confirm it worked:

```bash
docker --version
docker compose version
```

### 3. Get the deploy files onto the box

From your own machine, copy the `deploy/` folder (just the files this deployment needs, not the
whole repo) to the box. From this repo's root:

```bash
scp deploy/docker-compose.prod.yml deploy/Dockerfile.caddy deploy/Dockerfile.caddy.dockerignore deploy/Caddyfile deploy/.env.prod.example root@31.220.50.148:~/knowledge-deploy/
```

(Creates `~/knowledge-deploy/` on the box if it doesn't already exist — `scp` makes the directory
for you as part of the copy as long as the parent exists; if it errors, `ssh` in first and
`mkdir -p ~/knowledge-deploy`, then retry.)

The `Dockerfile.caddy` build also needs `webui/` itself (its build context is the repo root, not
just `deploy/`) — copy that over too:

```bash
scp -r webui root@31.220.50.148:~/knowledge-deploy/
```

On the box, `~/knowledge-deploy/` should now have: `docker-compose.prod.yml`, `Dockerfile.caddy`,
`Dockerfile.caddy.dockerignore`, `Caddyfile`, `.env.prod.example`, `webui/`. Since
`docker-compose.prod.yml`'s build context expects `deploy/Dockerfile.caddy` and `webui/` as
siblings one level up (mirroring this repo's real layout), adjust by placing `Dockerfile.caddy`,
`Dockerfile.caddy.dockerignore`, and `Caddyfile` in a `deploy/` subfolder instead:

```bash
ssh root@31.220.50.148
cd ~/knowledge-deploy
mkdir deploy
mv docker-compose.prod.yml Dockerfile.caddy Dockerfile.caddy.dockerignore Caddyfile .env.prod.example deploy/
# now: ~/knowledge-deploy/deploy/*.yml,Dockerfile.caddy,Caddyfile,.env.prod.example
#      ~/knowledge-deploy/webui/
```

### 4. Create the real secrets file

Still on the box:

```bash
cd ~/knowledge-deploy/deploy
cp .env.prod.example .env.prod
```

Edit `.env.prod` (`nano .env.prod`) and fill in the two blank values — generate real random ones,
don't make them up:

```bash
openssl rand -hex 16   # paste as POSTGRES_PASSWORD
openssl rand -hex 32   # paste as SECRET_KEY
```

Leave `KNOWLEDGE_VERSION` at whatever's current (check
[Docker Hub tags](https://hub.docker.com/r/sgummalla/knowledge/tags) or this repo's `VERSION`
file for the latest).

### 5. Start it

```bash
cd ~/knowledge-deploy
docker compose -p knowledge -f deploy/docker-compose.prod.yml --env-file deploy/.env.prod up -d --build
```

First run builds the Caddy+webui image (a minute or two) and pulls `knowledge-db`/`knowledge-api`
from their registries. Caddy requests real Let's Encrypt certificates for both domains on first
start — watch for errors in its logs if that fails (usually a DNS-not-propagated-yet issue, see
step 1).

### 6. Verify

```bash
docker compose -p knowledge -f deploy/docker-compose.prod.yml ps
curl -s https://api.sgummallaworks.com/knowledge/health
curl -sI https://knowledge.sgummallaworks.com/
```

The first `curl` should return `{"status":"ok","version":"..."}`; the second a `200` with
`content-type: text/html`. Then open `https://knowledge.sgummallaworks.com/sign-in` in a browser —
`admin@local` / `admin`, forced password change on first login (same as every fresh instance).

## Upgrading later

1. Bump `KNOWLEDGE_VERSION` in `deploy/.env.prod` to the new published tag.
2. ```bash
   docker compose -p knowledge -f deploy/docker-compose.prod.yml --env-file deploy/.env.prod pull knowledge-api
   docker compose -p knowledge -f deploy/docker-compose.prod.yml --env-file deploy/.env.prod up -d knowledge-api
   ```
   Only recreates the API container — `knowledge-db` and `caddy` are untouched, no downtime for
   the DB or a fresh TLS handshake.
3. If `webui/` itself changed (a new commit, not just a backend version bump), rebuild `caddy` too:
   ```bash
   docker compose -p knowledge -f deploy/docker-compose.prod.yml --env-file deploy/.env.prod up -d --build caddy
   ```
   (Requires re-copying the updated `webui/` source to the box first — step 3 above, minus the
   `deploy/` files that haven't changed.)

## Adding a second API to api.sgummallaworks.com later

Add a `handle_path /other-api/* { reverse_proxy other-api-container:PORT }` block to
`deploy/Caddyfile` (alongside the existing `/knowledge/*` one, inside the same
`api.sgummallaworks.com { ... }` block), put that new API's container on the same Docker network as
`caddy`, then:

```bash
docker compose -p knowledge -f deploy/docker-compose.prod.yml --env-file deploy/.env.prod up -d --build caddy
```

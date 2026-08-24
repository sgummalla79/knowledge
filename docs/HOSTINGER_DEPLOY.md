# Hostinger deployment (k3s)

Real domains: `api.sgummallaworks.com/knowledge` (API, path-prefixed — that domain hosts multiple
APIs) and `knowledge.sgummallaworks.com` (webui, its own subdomain, no prefix). Deployed to the
k3s cluster already running on the box (`31.220.50.148`) — Traefik (k3s's built-in Ingress
controller) and cert-manager are already installed there; nothing else was.

Manifests live in two directories in this repo — `api/deploy/k3s/` for the api+db release
artifacts (they move in lockstep with the api image's own release lifecycle), `deploy/k3s/` for
everything webui-only or cluster-shared — but land together in one flat `k3s/` directory on the
box (see step 2), and are applied in order (the number prefixes reflect real dependency order —
`01-postgres.yaml` before `02-api.yaml`, etc.) regardless of which directory each one came from:

| File | Repo source | What |
|---|---|---|
| `00-namespace.yaml` | `deploy/k3s/` | The `knowledge` namespace everything else lives in |
| `01-postgres.yaml` | `api/deploy/k3s/` | Postgres/pgvector — PVC (`local-path` StorageClass), Deployment, Service |
| `02-api.yaml` | `api/deploy/k3s/` | The API — Deployment (pulls the published `sgummalla/knowledge` image straight from Docker Hub, no build needed), Service |
| `03-webui.yaml` | `deploy/k3s/` | webui — Deployment (a locally-built image, see step 4 below), Service |
| `04-middleware.yaml` | `api/deploy/k3s/` | Traefik `Middleware` that strips `/knowledge` before forwarding to the API |
| `05-ingress.yaml` | `deploy/k3s/` | The two `Ingress` resources (one per domain) that actually route external traffic in — genuinely cross-cutting (api + webui in one file), which is why it stays outside `api/deploy/` |
| `06-cluster-issuer.yaml` | `deploy/k3s/` | cert-manager `ClusterIssuer` for Let's Encrypt — cluster-wide, not `knowledge`-namespaced, applied once regardless of how many apps this cluster ends up running |
| `07-ingestion-worker.yaml` | `api/deploy/k3s/` | Standalone ingestion-job worker — same published image as the API, different command, no Service/Ingress (not HTTP). Ships at `replicas: 0` — see this repo's ingestion-worker Release 1 plan for why it's not live yet |

## Known limitation

`GET /.well-known/oauth-authorization-server` (RFC 8414 discovery) is required by spec to live at
the domain root, but `api.sgummallaworks.com` is shared across multiple APIs each wanting their own
issuer identity — genuinely incompatible with path-based sharing. No `Ingress` route exists for it
(404s externally) rather than faking it. Nothing currently depends on it: MCP clients authenticate
with a pasted personal access token, not OAuth auto-discovery. Revisit only if a future integration
actually needs live discovery.

## One-time setup

### 1. DNS

- `api.sgummallaworks.com` already resolves to this box (`31.220.50.148`) — nothing to do.
- Add an **A record**: `knowledge.sgummallaworks.com` → `31.220.50.148`. Give it a few minutes to
  propagate before applying the Ingress in step 6 — cert-manager's HTTP01 challenge needs it
  resolving correctly first, or certificate issuance fails.

### 2. Get the manifests onto the box

From this repo's root, on your own machine — the two `k3s/` sources merge into one flat `k3s/`
directory on the box, since the split only matters on the repo side (see the table above):

```bash
ssh root@31.220.50.148 mkdir -p ~/knowledge-deploy/k3s
scp api/deploy/k3s/*.yaml deploy/k3s/*.yaml root@31.220.50.148:~/knowledge-deploy/k3s/
scp deploy/Dockerfile.webui deploy/Dockerfile.webui.dockerignore deploy/nginx.conf root@31.220.50.148:~/knowledge-deploy/
scp -r webui root@31.220.50.148:~/knowledge-deploy/
```

### 3. Create the namespace and secrets

SSH in, then:

```bash
cd ~/knowledge-deploy
kubectl apply -f k3s/00-namespace.yaml
```

Generate real random secrets and create them as a single Kubernetes `Secret` — don't type these
in by hand, generate them:

```bash
POSTGRES_PASSWORD=$(openssl rand -hex 16)
SECRET_KEY=$(openssl rand -hex 32)

kubectl create secret generic knowledge-secrets -n knowledge \
  --from-literal=postgres-password="$POSTGRES_PASSWORD" \
  --from-literal=secret-key="$SECRET_KEY" \
  --from-literal=database-url="postgresql://knowledge:${POSTGRES_PASSWORD}@knowledge-db:5432/knowledge"
```

(`knowledge-db` in that connection string is the Service name from `01-postgres.yaml` — Kubernetes
DNS resolves it automatically within the `knowledge` namespace, no IP to hardcode.)

### 4. Deploy Postgres and the API

```bash
kubectl apply -f k3s/01-postgres.yaml
kubectl apply -f k3s/02-api.yaml
kubectl -n knowledge get pods -w
```

Wait for both to show `Running`/`1/1` before continuing (Ctrl+C once they do — `-w` watches
forever otherwise). The API pod won't go ready until Postgres is up and migrations run
automatically on its own startup.

### 5. Build and load the webui image

No registry involved — built once, right here on the box, then loaded directly into containerd
(the runtime k3s actually uses, not Docker) since a webui image bakes in a deployment-specific API
URL and isn't a reusable published artifact the way the API image is.

Install Docker first if it isn't already there:

```bash
curl -fsSL https://get.docker.com | sh
```

Then build and load:

```bash
cd ~/knowledge-deploy
docker build -f Dockerfile.webui \
  --build-arg VITE_API_BASE_URL=https://api.sgummallaworks.com/knowledge \
  -t knowledge-webui:local .
docker save knowledge-webui:local -o knowledge-webui.tar
k3s ctr images import knowledge-webui.tar
rm knowledge-webui.tar
```

```bash
kubectl apply -f k3s/03-webui.yaml
kubectl -n knowledge get pods -w
```

### 6. Route real traffic in

```bash
kubectl apply -f k3s/04-middleware.yaml
kubectl apply -f k3s/06-cluster-issuer.yaml
kubectl apply -f k3s/05-ingress.yaml
```

Watch certificate issuance (can take a minute or two):

```bash
kubectl -n knowledge get certificate -w
```

Both should reach `READY: True`. If one hangs, check
`kubectl -n knowledge describe certificate <name>` and
`kubectl -n cert-manager logs -l app=cert-manager --tail=50` — the most common cause is DNS not
having propagated yet (step 1) or `ingressClassName: traefik` not matching this cluster's actual
IngressClass name (`kubectl get ingressclass` to check).

### 7. Verify

```bash
curl -s https://api.sgummallaworks.com/knowledge/health
curl -sI https://knowledge.sgummallaworks.com/
```

The first should return `{"status":"ok","version":"..."}`; the second a `200` with
`content-type: text/html`. Then open `https://knowledge.sgummallaworks.com/sign-in` in a browser —
`admin@local` / `admin`, forced password change on first login (same as every fresh instance).

## Upgrading later

**API version bump** (no webui change): edit the `image:` tag in `api/deploy/k3s/02-api.yaml` to
the new version, then:

```bash
kubectl apply -f k3s/02-api.yaml
```

Kubernetes handles the rollout — the old pod stays serving until the new one's ready.

**webui changed**: re-copy the updated `webui/` source to the box (step 2), rebuild and reload the
image (step 5's `docker build`/`save`/`k3s ctr images import` commands, then):

```bash
kubectl -n knowledge rollout restart deployment/knowledge-webui
```

(A plain `kubectl apply` won't pick up a reloaded image under the same tag — the Deployment spec
itself didn't change, so nothing tells Kubernetes to recreate the pod. `rollout restart` forces it.)

## Adding a second API to api.sgummallaworks.com later

Each new API is fully independent — its own `Middleware` (a different prefix), its own `Ingress`,
no shared file to edit. Copy the pattern from `api/deploy/k3s/04-middleware.yaml` and
`deploy/k3s/05-ingress.yaml`'s `knowledge-api` block: a new `Middleware` stripping that API's own
path prefix, and a new `Ingress` on the same `api.sgummallaworks.com` host with that prefix's
`path:`, annotated with that new `Middleware`'s `@kubernetescrd` reference. `06-cluster-issuer.yaml`
is already applied cluster-wide — reuse `cert-manager.io/cluster-issuer: letsencrypt-prod` as-is,
nothing new needed there.

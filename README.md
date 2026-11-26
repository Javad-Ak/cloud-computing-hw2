# Cloud Computing HW2 — Containers & CI/CD

- **Student:** Mohammad Javad Akbari (40231005)
- **Repository:** https://github.com/Javad-Ak/cloud-computing-hw2
- **GitHub Pages:** https://javad-ak.github.io/cloud-computing-hw2/
- **GHCR Packages:**
  - `ghcr.io/javad-ak/cc-hello:slim`
  - `ghcr.io/javad-ak/lab-queue:latest`

---

## Repository Structure

- `part1/` — Docker basics, `full` vs `slim` images, layer caching, and BuildKit secrets (`part1/secrets/`)
- `part2/` — Lab Queue HTTP service (file-backed with `fcntl.flock` + `os.replace`, plus Redis & Prometheus bonus stack), Nginx proxy, tests, and static Pages site
- `.github/workflows/ci.yml` — CI/CD pipeline (`lint`, `test`, `build`, `push`, `pages`, `tag`)
- `.github/workflows/deploy.yml` — Manual rollback of any Git tag to GitHub Pages

---

## Demo Day Verification Commands

### Part 1 — Docker

#### 1. Pre-built Image (`gosonic/sonic:latest`)
```bash
docker pull gosonic/sonic:latest
docker image history gosonic/sonic:latest
docker image inspect gosonic/sonic:latest --format "{{json .Config.ExposedPorts}}"
docker run -d --name cc-hello -p 8080:8080 gosonic/sonic:latest
docker logs cc-hello
docker stop cc-hello && docker rm cc-hello

```

#### 2. `full` vs `slim` Images & GHCR

```bash
cd part1
docker build -t full .
docker build -f Dockerfile.slim -t slim .
docker images
docker run --rm ghcr.io/javad-ak/cc-hello:slim

```

#### 3. Build Secrets (Leaky vs Safe)

```bash
cd part1/secrets
docker build -f Dockerfile.leaky -t secret-leaky .
docker run --rm secret-leaky

docker build --no-cache -f Dockerfile.secret --secret id=demo,src=secret.txt -t secret-safe .
docker run --rm secret-safe
docker image history --no-trunc secret-safe

```

---

### Part 2 — Lab Queue Service & Docker Compose

#### 1. Unit & Site Tests (No Docker Required)

```bash
cd part2
python -m pip install -r requirements-dev.txt
pytest

```

#### 2. 3 Replicas Behind Nginx + Race Condition Fix (`fcntl.flock` + `os.replace`)

Ensure `part2/.env` exists (copy from `part2/.env.example`).

```bash
cd part2
docker compose down -v
docker compose up -d --build --scale app=3
docker compose restart proxy
docker compose ps

# 200 concurrent joins + drain verification
python tools/concurrent_join.py --url http://localhost:8000 --drain

# Verify load balancing across all 3 app replicas
docker compose logs proxy --tail=20

```

#### 3. Volume Persistence Check

```bash
curl -X POST http://localhost:8000/join -H "Content-Type: application/json" -d '{"name":"Ali"}'
docker compose rm -sf app
docker compose up -d --scale app=3
docker compose restart proxy
curl -X POST http://localhost:8000/next
docker compose down

```

---

### Part 3 — GitHub Actions & GitHub Pages

1. **Automated Pipeline (`ci.yml`):**
* Runs `lint` (Hadolint + Ruff), `test` (`pytest`), and `build` (Docker image artifact) on all branches and PRs.
* Runs `push` (GHCR versioned tag + `latest`), `pages` (injects tag into `__VERSION__` and deploys), and `tag` (creates annotated Git tag) **only on pushes to `main**`.


2. **Manual Rollback (`deploy.yml`):**
* Go to **Actions → Manual Deploy Tag to Pages → Run workflow**.
* Enter an existing Git tag (e.g., the first release tag) and run.
* Refresh https://javad-ak.github.io/cloud-computing-hw2/ to verify both the version and sentence revert to that tag's commit.



---

### Bonus 1 & 2 — Redis Backend + Prometheus Monitoring

#### 1. Start the Bonus Stack (3 `app` Replicas + Redis AOF + `redis_exporter` + Prometheus)

```bash
cd part2
docker compose -f compose.bonus.yaml down -v
docker compose -f compose.bonus.yaml up -d --build --scale app=3
docker compose -f compose.bonus.yaml restart proxy
docker compose -f compose.bonus.yaml ps

```

#### 2. Verify Concurrency & Redis Persistence

```bash
python tools/concurrent_join.py --url http://localhost:8000 --drain

curl -X POST http://localhost:8000/join -H "Content-Type: application/json" -d '{"name":"Ali"}'
docker compose -f compose.bonus.yaml rm -sf db
docker compose -f compose.bonus.yaml up -d db
sleep 3
curl -X POST http://localhost:8000/next

```

#### 3. Verify Prometheus Monitoring

* **Targets:** http://localhost:9090/targets (3 `app` targets + 1 `db` exporter target, all `UP`)
* **Graphs:** http://localhost:9090/graph
* Request rate: `sum(rate(http_requests_total{job="app", route!="/metrics"}[1m]))`
* Errors (`4xx`/`5xx`): `sum by (status) (rate(http_requests_total{job="app", status=~"4..|5.."}[1m]))`
* Avg latency: `sum(rate(http_request_duration_seconds_sum{job="app", route!="/metrics"}[1m])) / sum(rate(http_request_duration_seconds_count{job="app", route!="/metrics"}[1m]))`
* p95 latency: `histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{job="app", route!="/metrics"}[1m])))`
* Redis health & metrics: `redis_up`, `redis_connected_clients`, `rate(redis_commands_processed_total[1m])`



#### 4. Cleanup

```bash
docker compose -f compose.bonus.yaml down

```

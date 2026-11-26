# Lab Queue Service (Part 2)

## Running Tests
```bash
cd part2
python -m pip install -r requirements-dev.txt
pytest
```

## Running with Docker Compose

Copy .env.example to .env, then run:

```bash
docker compose up -d --build
```

## Running Bonus (Redis + Prometheus)
```bash
cd part2
docker compose -f compose.bonus.yaml up -d --build --scale app=3
docker compose -f compose.bonus.yaml restart proxy
```
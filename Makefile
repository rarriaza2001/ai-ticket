COMPOSE := docker compose -f docker/docker-compose.yml
ENV_FILE := --env-file docker/.env.example
ENV_BASELINE := --env-file docker/.env.example --env-file docker/.env.baseline

.PHONY: compose-up compose-down lint seed-phase4 seed-phase4-small seed-phase4-medium seed-phase4-large clear-phase4
.PHONY: rebuild-api rebuild-api-baseline rebuild-api-cached benchmark-baseline benchmark-cold-cache benchmark-warm-cache benchmark-redis-down

compose-up:
	$(COMPOSE) $(ENV_FILE) up --build

compose-down:
	$(COMPOSE) down

# Rebuild running stack so Phase 4 cache env vars and code are picked up.
rebuild-api:
	$(COMPOSE) $(ENV_FILE) up --build -d --wait

rebuild-api-baseline:
	$(COMPOSE) $(ENV_BASELINE) up --build -d --wait api-service

rebuild-api-cached:
	$(COMPOSE) $(ENV_FILE) up --build -d --wait api-service redis

lint:
	python -m ruff check shared-contracts/shared_contracts api-service/app ai-worker/worker scripts/phase4_benchmark

seed-phase4: seed-phase4-medium

seed-phase4-small:
	cd api-service && python ../scripts/seed_phase4_benchmark_data.py --size small --reset

seed-phase4-medium:
	cd api-service && python ../scripts/seed_phase4_benchmark_data.py --size medium --reset

seed-phase4-large:
	cd api-service && python ../scripts/seed_phase4_benchmark_data.py --size large --reset

clear-phase4:
	cd api-service && python ../scripts/clear_phase4_benchmark_data.py

benchmark-baseline: rebuild-api-baseline seed-phase4-medium
	cd api-service && python ../scripts/benchmark_phase4_cache.py --mode baseline --iterations 100

benchmark-cold-cache: rebuild-api-cached seed-phase4-medium
	cd api-service && python ../scripts/benchmark_phase4_cache.py --mode cold-cache --iterations 100

benchmark-warm-cache: rebuild-api-cached seed-phase4-medium
	cd api-service && python ../scripts/benchmark_phase4_cache.py --mode warm-cache --warmup 20 --iterations 100

benchmark-redis-down: rebuild-api-cached seed-phase4-medium
	cd api-service && python ../scripts/benchmark_phase4_cache.py --mode redis-down --iterations 50

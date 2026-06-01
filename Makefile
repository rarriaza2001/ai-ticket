COMPOSE := docker compose -f docker/docker-compose.yml



.PHONY: compose-up compose-down lint seed-phase4 seed-phase4-small seed-phase4-medium seed-phase4-large clear-phase4



compose-up:

	$(COMPOSE) --env-file docker/.env.example up --build



compose-down:

	$(COMPOSE) down



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



# Benchmarks require running api-service. Example:

#   cd api-service && python ../scripts/benchmark_phase4_cache.py --mode warm-cache --warmup 20 --iterations 100

# See docs/BENCHMARKS.md for baseline, cold-cache, and redis-down modes.


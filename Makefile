COMPOSE := docker compose -f docker/docker-compose.yml

.PHONY: compose-up compose-down lint

compose-up:
	$(COMPOSE) --env-file docker/.env.example up --build

compose-down:
	$(COMPOSE) down

lint:
	python -m ruff check shared-contracts/shared_contracts api-service/app ai-worker/worker

COMPOSE := docker compose -f compose.yml
APP_SERVICE := credit-backend

.DEFAULT_GOAL := help


.env:
	cp .env.test .env


.PHONY: up up_build stop down down_v bash logs logs_all migrate

up: .env
	$(COMPOSE) up -d

up_build: .env
	$(COMPOSE) up -d --build

stop:
	$(COMPOSE) stop

down:
	$(COMPOSE) down

down_v:
	$(COMPOSE) down -v

bash:
	docker exec -it $(APP_SERVICE) bash

logs:
	docker logs $(APP_SERVICE) -f

logs_all:
	$(COMPOSE) logs -f

migrate:
	$(COMPOSE) run --rm credit-migrate


.PHONY: lint test test_contract test_e2e openapi

lint:
	cd backend && uv run ruff check src tests scripts && uv run ruff format --check src tests scripts && uv run mypy src
	cd mocks && ../backend/.venv/bin/ruff check src && ../backend/.venv/bin/ruff format --check src

test:
	cd backend && uv run pytest

test_contract:
	cd backend && ML_URL=http://localhost:8001 uv run pytest -m contract

test_e2e:
	cd backend && E2E_API_URL=http://localhost:8000 uv run pytest -m e2e

openapi:
	cd backend && PYTHONPATH=src uv run python scripts/export_openapi.py ../docs/openapi.json


.PHONY: help

help:
	@echo "Использование: make [команда]"
	@echo ""
	@echo "Основные команды:"
	@echo "  up               Запуск контейнеров приложения в фоне (без пересборки)"
	@echo "  up_build         Пересборка и запуск контейнеров приложения в фоне"
	@echo "  stop             Остановка контейнеров приложения"
	@echo "  down             Остановка и удаление контейнеров приложения (без volumes)"
	@echo "  down_v           Остановка и удаление контейнеров приложения с очисткой volumes"
	@echo "  bash             Запуск bash в основном контейнере (${APP_SERVICE})"
	@echo "  logs             Просмотр логов основного контейнера (${APP_SERVICE}) в реальном времени"
	@echo "  logs_all         Просмотр логов всех контейнеров в реальном времени"
	@echo "  migrate          Применение миграций БД"
	@echo ""
	@echo "Разработка:"
	@echo "  lint             ruff и mypy для backend и mocks"
	@echo "  test             Юнит- и интеграционные тесты backend (нужен Docker)"
	@echo "  test_contract    Контрактные тесты против запущенного ml"
	@echo "  test_e2e         Сквозные сценарии против поднятого compose"
	@echo "  openapi          Экспорт docs/openapi.json"

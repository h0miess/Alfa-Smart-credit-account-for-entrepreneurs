COMPOSE_FILE := docker-compose.yml
APP_SERVICE := credit-backend

.DEFAULT_GOAL := help


.PHONY: up up_build stop down down_v bash logs logs_all

up:
	docker compose -f $(COMPOSE_FILE) up -d

up_build:
	docker compose -f $(COMPOSE_FILE) up -d --build

stop:
	docker compose -f $(COMPOSE_FILE) stop

down:
	docker compose -f $(COMPOSE_FILE) down

down_v:
	docker compose -f $(COMPOSE_FILE) down -v

bash:
	docker exec -it $(APP_SERVICE) bash

logs:
	docker logs $(APP_SERVICE) -f

logs_all:
	docker compose -f $(COMPOSE_FILE) logs -f


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

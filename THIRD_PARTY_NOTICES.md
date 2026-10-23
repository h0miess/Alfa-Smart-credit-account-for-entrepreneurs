# Сторонние компоненты

Прототип использует только открытое ПО без платных лицензий. Точные версии библиотек
зафиксированы в `backend/uv.lock`, `mocks/uv.lock` и `ml/uv.lock`, версии образов — в
`compose.yml`.

## Моделированные интеграции

Внешние системы банка и государства заменены моками в `mocks/` с упрощёнными, но смысловыми
контрактами. Реальные системы прототип не вызывает. Все данные синтетические
(`seed/companies.json`); совпадение ИНН, ОГРН, счетов и имён с реальными лицами случайно.

| Система | Что моделирует мок | Эндпоинт мока |
|---|---|---|
| ЕГРЮЛ / ЕГРИП | статус, дата регистрации, ОКВЭД, смены руководителя, массовый адрес | `GET /egrul/{inn}` |
| ФНС | налоговая задолженность | `GET /fns/{inn}/arrears` |
| БКИ | кредитная история, просрочки, запросы, долговая нагрузка | `GET /bki/{inn}/report` |
| АБС банка | выписка по расчётному счёту, зачисление кредита | `GET /abs/{inn}/statement`, `POST /abs/disbursements` |

Подписание согласий и договора моделируется кодом, который показывается в интерфейсе, без SMS и
электронной подписи. Зачисление моделируется записью об операции в моке АБС.

## Инфраструктура (образы Docker)

| Компонент | Версия | Лицензия |
|---|---|---|
| PostgreSQL | 18.6 | PostgreSQL License |
| Keycloak | 26.8.1 | Apache-2.0 |
| Redis | 8.8.3 | RSALv2 / SSPLv1 / AGPLv3 (на выбор) |
| MinIO (сборка pgsty/minio) | RELEASE.2026-08-04 | AGPL-3.0 |
| Python | 3.12.13 (backend, mocks), 3.11 (ml) | PSF License |
| uv | 0.11.16 | Apache-2.0 / MIT |

Redis и MinIO используются как отдельные сервисы без изменений исходного кода.

## Библиотеки backend

| Библиотека | Версия | Лицензия |
|---|---|---|
| FastAPI | 0.160.0 | MIT |
| Starlette | 1.9.0 | BSD-3-Clause |
| Uvicorn | 0.54.0 | BSD-3-Clause |
| Pydantic, pydantic-settings | 2.14.1, 2.16.1 | MIT |
| SQLAlchemy | 2.1.6 | MIT |
| asyncpg | 0.32.0 | Apache-2.0 |
| Alembic | 1.20.1 | MIT |
| httpx | 0.28.1 | BSD-3-Clause |
| tenacity | 9.2.1 | Apache-2.0 |
| PyJWT | 2.15.1 | MIT |
| cryptography | 50.0.2 | Apache-2.0 / BSD-3-Clause |
| Taskiq, taskiq-redis, taskiq-fastapi | 0.13.0, 1.2.4, 0.5.0 | MIT |
| redis-py | 8.1.0 | MIT |
| aioboto3, aiobotocore, botocore | 15.5.0, 2.25.1, 1.40.61 | Apache-2.0 |
| Jinja2 | 3.1.6 | BSD-3-Clause |
| python-multipart | 0.0.32 | Apache-2.0 |

Для разработки и тестов: pytest 9.1.1 (MIT), pytest-asyncio 1.4.0 (Apache-2.0), testcontainers
4.15.0 (Apache-2.0), respx 0.23.1 (BSD-3-Clause), ruff 0.17.2 (MIT), mypy 2.4.0 (MIT).

## Библиотеки mocks

FastAPI 0.161.0 (MIT), Starlette 1.9.0 (BSD-3-Clause), Uvicorn 0.54.0 (BSD-3-Clause),
pydantic-settings 2.16.1 (MIT).

## Библиотеки ml

| Библиотека | Версия | Лицензия |
|---|---|---|
| LightGBM | 4.7.0 | MIT |
| scikit-learn | 1.7.2 | BSD-3-Clause |
| pandas | 2.3.3 | BSD-3-Clause |
| NumPy | 2.5.4 | BSD-3-Clause |
| SciPy | 1.18.1 | BSD-3-Clause |
| FastAPI, Uvicorn, Pydantic | 0.159.1, 0.54.0, 2.14.1 | MIT, BSD-3-Clause, MIT |

## Инструменты

Коллекция запросов в `collection/` открывается в [Bruno](https://www.usebruno.com/) (MIT).

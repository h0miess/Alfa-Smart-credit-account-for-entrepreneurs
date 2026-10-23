# API кредитного кабинета

Базовый адрес: `http://localhost:8000`. Все бизнес-методы лежат под `/api/v1`. Полная схема —
[openapi.json](openapi.json) (`make openapi` выгружает её заново), интерактивная документация —
Swagger UI на `/docs`. Готовые запросы — коллекция Bruno в [`collection/`](../collection).

## 1. Авторизация

SSO через Keycloak, realm `alfa-credit`, клиент `credit-cabinet-web`.

- **Swagger:** кнопка Authorize → вход на странице Keycloak (Authorization Code + PKCE).
- **curl / Bruno:** для тестовых учёток включён password grant:

```bash
TOKEN=$(curl -s http://localhost:8080/realms/alfa-credit/protocol/openid-connect/token \
  -d client_id=credit-cabinet-web -d grant_type=password -d scope=openid \
  -d username=ip.ivanov -d password=alfa2026 | jq -r .access_token)
```

Токен передаётся в заголовке `Authorization: Bearer <token>`. Роли: `client` — методы клиента,
`underwriter` — методы `/underwriter`. Справочники и каталог доступны обеим ролям.

## 2. Ошибки

Тело ошибки одинаковое для всех методов:

```json
{"details": "Подписать договор может только руководитель компании: передайте заявку ему", "code": "signer_required"}
```

| HTTP | Когда | Примеры `code` |
|---|---|---|
| 401 | нет токена или он не прошёл проверку | `unauthorized` |
| 403 | нет роли; пользователь не привязан к компании; подписывает не руководитель | `forbidden`, `signer_required` |
| 404 | заявки нет **или она принадлежит другой компании** | `not_found` |
| 409 | действие недопустимо в текущем статусе; дубль активной заявки; истёкший оффер; договор не совпал с оффером | `invalid_transition`, `conflict`, `offer_expired`, `contract_mismatch` |
| 422 | нарушено правило: лимиты продукта, нет согласий, не хватает документов, неверный код; ошибка схемы запроса | `business_rule_violation` |
| 503 | внешний сервис недоступен (ml, хранилище) | `service_unavailable` |

Команды идемпотентны по состоянию: повтор той же команды сразу после успешной (двойной клик,
ретрай сети) возвращает текущую карточку без побочных эффектов. Это `submit` в SUBMITTED или
CHECKING, `offer/accept` в ACCEPTED, `contract/sign` в SIGNED или ISSUED и `documents/complete` в
CHECKING.

## 3. Клиент (роль `client`)

| Метод | Путь | Что делает |
|---|---|---|
| GET | `/me` | пользователь, роли, представитель (`can_sign`) и профиль компании |
| GET | `/statuses` | справочник статусов: `title`, `next_action`, `eta_text` |
| GET | `/purposes` | цели кредита |
| GET | `/products` | продукты: лимиты и диапазон ставки от грейда A до D |
| POST | `/products/recommend` | `{purpose, amount?, term_months?}` → подходящие продукты и примерный платёж |
| POST | `/calculator` | `{product, amount, term_months, collateral_value?}` → платёж и переплата при лучшем и худшем грейде |
| POST | `/applications` | черновик: только `product, requested_amount, term_months, purpose, collateral_value, collateral_description`; любые другие поля → 422 |
| GET | `/applications` | заявки компании |
| GET | `/applications/{id}` | карточка: статус со сроком, решение, оффер, договор, документы, журнал |
| PATCH | `/applications/{id}` | изменить черновик |
| DELETE | `/applications/{id}` | удалить черновик (→ CANCELLED) |
| POST | `/applications/{id}/submit` | `{consent_bki, consent_pd}` → SUBMITTED, обработка начинается автоматически |
| GET | `/applications/{id}/events` | журнал переходов: кто, когда, из какого статуса в какой и почему |
| GET | `/applications/{id}/stream` | SSE-поток статуса (раздел 5) |
| POST | `/applications/{id}/copy` | новая заявка с теми же параметрами после отказа или отмены |
| POST | `/applications/{id}/offer/accept` | принять предложение → ACCEPTED, формируется договор |
| POST | `/applications/{id}/offer/reject` | отказаться → CANCELLED |
| GET | `/applications/{id}/contract` | договор и признак `matches_offer` |
| GET | `/applications/{id}/contract/document` | договор в HTML |
| POST | `/applications/{id}/contract/sign-code` | код подписи; показывается в интерфейсе, действует 5 минут |
| POST | `/applications/{id}/contract/sign` | `{code}` → SIGNED, затем выдача |
| GET | `/applications/{id}/documents` | что запрошено и что уже загружено |
| POST | `/applications/{id}/documents` | multipart: `file`, `reason_code` и поля для конкретного дозапроса (раздел 4) |
| GET | `/applications/{id}/documents/{doc_id}/file` | скачать файл |
| POST | `/applications/{id}/documents/complete` | все документы загружены → CHECKING, повторная проверка |

Клиент видит причины решения и факторы риска простым языком. PD, балл и грейд в ответах для
клиента отсутствуют. Карточка оффера всегда содержит `note: "Подключение других продуктов банка не
требуется"`, а при встречном предложении — `is_counter_offer: true` и запрошенные клиентом сумму и
срок.

## 4. Документы по дозапросу

| `reason_code` | Документ | Обязательные поля формы | Что меняется во входе скоринга |
|---|---|---|---|
| `INFO_TAX_ARREARS` | справка ФНС или подтверждение погашения | — | `tax_arrears = false` |
| `INFO_LOW_TURNOVER` | выписки из других банков | `external_monthly_turnover` | `avg_monthly_turnover += external_monthly_turnover` |
| `INFO_NO_COLLATERAL` | сведения о залоге | `collateral_value`, `collateral_description` | `collateral_value` заявки |

Документ принимается автоматически (допущение MVP, см. process.md §7). Извлечённые значения
хранятся в `DOCUMENT.extracted` и попадают в `DECISION.request_payload` следующего решения.

## 5. Поток статуса (SSE)

```bash
curl -N -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/applications/$ID/stream
```

```
event: status
data: {"application_id": "…", "status": {"code": "DRAFT", "title": "Черновик", …}, "from_status": null, "changed_at": null}

event: status
id: 2026-10-23T00:16:31.029346+00:00
data: {"application_id": "…", "status": {"code": "SUBMITTED", …, "eta_deadline": "…"}, "from_status": "DRAFT", "changed_at": "…"}

: ping
```

Первое событие — текущее состояние, дальше каждое изменение, в том числе сделанное worker'ом или
андеррайтером. Браузерный `EventSource` не умеет передавать `Authorization`, поэтому фронту нужен
клиент SSE на fetch, например `@microsoft/fetch-event-source`.

## 6. Андеррайтер (роль `underwriter`)

| Метод | Путь | Что делает |
|---|---|---|
| GET | `/underwriter/queue` | заявки в MANUAL_REVIEW по сроку: компания, сумма, грейд, PD, причины передачи `MR_*` |
| GET | `/underwriter/applications/{id}` | карточка: компания с отчётностью, снимки ЕГРЮЛ/ФНС/БКИ/выписки, системное решение (PD, грейд, балл, факторы риска и плюсы, причины), предварительный оффер, документы, журнал |
| POST | `/underwriter/applications/{id}/decision` | решение, `comment` обязателен |
| GET | `/underwriter/applications/{id}/documents/{doc_id}/file` | скачать документ клиента |

Варианты решения:

```json
{"action": "approve", "comment": "Адрес проверен"}
{"action": "change_terms", "amount": 1500000, "term_months": 18, "comment": "Снижаем сумму"}
{"action": "request_info", "documents": ["collateral_info"], "comment": "Нужен залог"}
{"action": "decline", "reason": "Текст причины для клиента", "comment": "Внутренний комментарий"}
```

Решение андеррайтера — отдельная запись DECISION с `decided_by = underwriter`. PD, грейд и
версии модели и политики копируются из системного решения. `approve` берёт условия
предварительного оффера системы; если его нет, нужен `change_terms`. Сумма и срок в
`change_terms` ограничены лимитами продукта, а ставка берётся из предварительного оффера или
считается по политике ml.

## 7. Служебные методы

| Метод | Путь | Ответ |
|---|---|---|
| GET | `/health` | `{"status": "ok"}` — процесс жив |
| GET | `/ready` | `{"status": "ready", "checks": {"postgres": "ok", "redis": "ok", "keycloak": "ok", "scoring": "ok"}}`; 503, если что-то недоступно |
| PUT | `http://localhost:8002/admin/failures/{source}` | режим отказов моков: `{"mode": "error" | "timeout" | "off"}` |

## 8. Пример: основной путь через curl

```bash
API=http://localhost:8000/api/v1
H="Authorization: Bearer $TOKEN"

ID=$(curl -s -H "$H" -H 'Content-Type: application/json' -X POST $API/applications \
  -d '{"product":"express","requested_amount":1500000,"term_months":12,"purpose":"working_capital"}' | jq -r .id)
curl -s -H "$H" -H 'Content-Type: application/json' -X POST $API/applications/$ID/submit \
  -d '{"consent_bki":true,"consent_pd":true}' | jq .status
sleep 3; curl -s -H "$H" $API/applications/$ID | jq '{status: .status.code, offer: .offer}'
curl -s -H "$H" -X POST $API/applications/$ID/offer/accept | jq .status.code
CODE=$(curl -s -H "$H" -X POST $API/applications/$ID/contract/sign-code | jq -r .code)
curl -s -H "$H" -H 'Content-Type: application/json' -X POST $API/applications/$ID/contract/sign \
  -d "{\"code\":\"$CODE\"}" | jq .status.code
sleep 3; curl -s -H "$H" $API/applications/$ID | jq '[.events[].to_status]'
```

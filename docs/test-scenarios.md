# Тест-сценарии

Сценарии проверяют путь клиента и банка на реальных Keycloak, ml, моках, worker и MinIO. Каждый
сценарий опирается на синтетическую компанию из [`seed/companies.json`](../seed/companies.json):
её данные подобраны так, чтобы настоящая модель давала заявленный исход. Это проверяет
контрактный тест `test_seed_profile_gives_declared_outcome`.

Пароль всех учёток — `alfa2026`.

## Как запустить

| Что | Команда | Что нужно |
|---|---|---|
| Юнит- и интеграционные тесты | `make test` | Docker (testcontainers поднимает Postgres и MinIO) |
| Контрактные тесты с ml | `make test_contract` | запущенный `credit-ml` |
| Сценарии 1–5 автоматически | `make test_e2e` | поднятый `make up` |
| Основной путь в Bruno | папка `00 Основной путь`, окружение `local` | поднятый `make up` |

E2E-тесты закрывают активные заявки компании перед прогоном, поэтому их можно запускать
повторно на одном стенде.

## 1. Одобрение и выдача — `ip.ivanov`

ИП Иванов: обороты по счёту покрывают запрос, чистая кредитная история.

| Шаг | Действие | Ожидаемый результат |
|---|---|---|
| 1 | `GET /me` | представитель с `can_sign: true`, профиль ИП Иванова |
| 2 | `POST /products/recommend {purpose: working_capital, amount: 1500000}` | экспресс-кредит и овердрафт с диапазоном ставки и платежом |
| 3 | `POST /applications` с экспресс-кредитом 1 500 000 ₽ на 12 мес. | DRAFT; данных компании в запросе нет |
| 4 | `POST /submit` с согласиями | SUBMITTED со сроком `eta_deadline`; поток статуса показывает SUBMITTED → CHECKING → OFFERED |
| 5 | `GET /applications/{id}` через несколько секунд | OFFERED, исход APPROVED, оффер 1 500 000 ₽ под 19 %, «подключение других продуктов не требуется» |
| 6 | `POST /offer/accept`, `GET /contract` | ACCEPTED; сумма, срок, ставка и платёж договора равны офферу, `matches_offer: true` |
| 7 | `POST /contract/sign-code`, `POST /contract/sign` | код показан в ответе; SIGNED |
| 8 | `GET /applications/{id}` | ISSUED «Деньги на счёте»; журнал: DRAFT, SUBMITTED, CHECKING, OFFERED, ACCEPTED, SIGNED, ISSUED |
| 9 | `GET /underwriter/applications/{id}` под `underwriter` | у решения есть `model_version`, `policy_version`, 4 снимка источников |

Автотест: `test_ip_ivanov_approved_to_issued`.

## 2. Встречное предложение, подпись руководителем — `ooo.romashka.accountant`, `ooo.romashka.director`

ООО «Ромашка»: оборотов меньше, чем нужно для 9 000 000 ₽.

| Шаг | Действие | Ожидаемый результат |
|---|---|---|
| 1 | бухгалтер подаёт экспресс-кредит 9 000 000 ₽ на 12 мес. | OFFERED, исход COUNTER_OFFER, `is_counter_offer: true`, сумма оффера меньше запрошенной, видны запрошенные сумма и срок |
| 2 | бухгалтер принимает предложение | ACCEPTED |
| 3 | бухгалтер запрашивает код подписи | 403 `signer_required` «передайте заявку руководителю» |
| 4 | директор запрашивает код и подписывает | SIGNED → ISSUED |

Автотест: `test_romashka_counter_offer_signed_by_director`.

## 3. Дозапрос документа — `ooo.vector.director`

ООО «Вектор»: по данным ФНС есть налоговая задолженность.

| Шаг | Действие | Ожидаемый результат |
|---|---|---|
| 1 | подать экспресс-кредит 3 000 000 ₽ на 12 мес. | INFO_REQUESTED «Нужны документы», в `requested_documents` — справка ФНС (`INFO_TAX_ARREARS`) |
| 2 | `POST /documents/complete` до загрузки | 422 со списком недостающих документов |
| 3 | загрузить PDF с `reason_code=INFO_TAX_ARREARS` | 201; файл лежит в MinIO и скачивается обратно |
| 4 | `POST /documents/complete` | CHECKING; повторная проверка в той же заявке |
| 5 | через несколько секунд | OFFERED, исход APPROVED; в `request_payload` нового решения `tax_arrears: false`, в первом — `true` |

Автотест: `test_vector_documents_then_offer`.

## 4. Ручная проверка — `ip.petrov`, `underwriter`

ИП Петров: адрес массовой регистрации.

| Шаг | Действие | Ожидаемый результат |
|---|---|---|
| 1 | подать экспресс-кредит 2 000 000 ₽ на 24 мес. | MANUAL_REVIEW «Заявку проверяет специалист, ориентир — 1 рабочий день»; оффера клиент не видит |
| 2 | андеррайтер: `GET /underwriter/queue` | заявка в очереди с причиной `MR_MASS_ADDRESS` и сроком |
| 3 | андеррайтер: карточка | PD, грейд, балл, факторы риска и плюсы, снимки четырёх источников, предварительный оффер |
| 4 | андеррайтер: `approve` с комментарием | OFFERED; клиент видит оффер с условиями предварительного; в журнале переход от андеррайтера |

Другие решения андеррайтера (`change_terms`, `request_info`, `decline`) проверяют интеграционные
тесты в `tests/integration/test_underwriter.py`.

Автотест: `test_petrov_manual_review_by_underwriter`.

## 5. Отказ и новая заявка — `ooo.delta.director`

ООО «Дельта»: просрочка больше 90 дней.

| Шаг | Действие | Ожидаемый результат |
|---|---|---|
| 1 | подать экспресс-кредит 2 500 000 ₽ на 12 мес. | DECLINED с причиной `STOP_OVERDUE_90` простым языком |
| 2 | `POST /applications/{id}/copy` | новый DRAFT с теми же параметрами кредита; старая заявка остаётся в истории с причиной отказа |

Автотест: `test_delta_declined_then_new_application`.

## 6. Надёжность и граничные случаи

| Сценарий | Ожидаемый результат | Где проверяется |
|---|---|---|
| БКИ недоступно (`PUT :8002/admin/failures/bki {"mode":"error"}`) | клиент видит «на рассмотрении», 5 попыток с паузами, затем MANUAL_REVIEW с `SYSTEM_UNAVAILABLE`; андеррайтер может назначить условия | `test_failures_hand_application_to_underwriter`, проверено вручную на стенде |
| Чужая заявка | 404 | `test_other_company_application_is_not_found` |
| Токен с неверной подписью | 401 на всех защищённых методах | `test_invalid_token_is_rejected_everywhere` |
| Повторный `submit` | второй вызов ничего не делает, задача ставится один раз | `test_submit_is_idempotent_and_enqueues_once` |
| Вторая активная заявка на тот же продукт | 409 | `test_second_active_application_for_product_is_conflict` |
| Данные компании в черновике | 422 | `test_company_data_is_not_accepted_in_draft` |
| Договор изменён после принятия | подпись отклоняется, 409 `contract_mismatch` | `test_contract_differing_from_offer_is_not_signed` |
| Оффер истёк | 409 `offer_expired`, заявка CANCELLED | `test_expired_offer_cannot_be_accepted`, `test_expired_offer_is_cancelled_by_scheduler` |
| Клиент принимает оффер, пока планировщик его истекает | ровно один переход в CANCELLED | `test_accept_racing_expiry_has_single_winner` |
| Нет ответа на дозапрос 30 дней | CANCELLED от системы | `test_info_request_without_answer_is_cancelled_after_30_days` |
| Заявка зависла в SUBMITTED | планировщик ставит задачу заново | `test_stuck_applications_are_requeued` |
| Повторная выдача | АБС вызывается один раз, `Idempotency-Key = contract_id` | `test_happy_path_to_issued` |
| Статус меняется у открытого потока | событие приходит в SSE без перезагрузки | `test_stream_sends_current_status_then_changes` |

## 7. Сверка кода с документацией

| Что сверяется | Тест |
|---|---|
| Переходы статусов = mermaid-диаграмма process.md §4 | `test_transitions_match_state_diagram` |
| Тексты статусов = таблица «Что видит клиент» | `test_status_view_matches_client_table` |
| Исход скоринга → статус = таблица process.md §5 | `test_outcome_mapping_matches_decision_table` |
| Источник каждого поля запроса к ml = таблица process.md §6 | `test_field_sources_match_process_table`, `test_each_field_is_taken_from_its_source` |
| Зеркало запроса = схема `ApplicationIn` живого ml | `test_request_mirror_matches_ml_schema` |
| Ставка и платёж бэкенда = офферы ml | `test_seed_profile_gives_declared_outcome` |

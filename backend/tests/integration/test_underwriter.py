from typing import Any

import httpx

from application.use_cases.processing.process_application import ProcessApplication
from domain.entities.user import UserRole
from tests.integration.pipeline import Login, ml_response, scored
from tests.users import IP_IVANOV, IP_PETROV, UNDERWRITER

PETROV_INN = "663205817446"
MASS_ADDRESS = {
    "code": "MR_MASS_ADDRESS",
    "text": "Адрес массовой регистрации — нужна проверка андеррайтером",
}


def manual_review(with_offer: bool = True) -> dict[str, Any]:
    offer = {
        "product": "express",
        "product_name": "Экспресс-кредит на оборотные средства",
        "amount": 2000000.0,
        "term_months": 24,
        "rate": 19.0,
        "monthly_payment": 100813.01,
    }
    return ml_response(
        "MANUAL_REVIEW",
        grade="A",
        pd=0.0118,
        max_amount=4350000.0,
        offer=offer if with_offer else None,
        reasons=[MASS_ADDRESS],
    )


async def in_review(
    client: httpx.AsyncClient,
    login: Login,
    process: ProcessApplication,
    response: dict[str, Any] | None = None,
) -> str:
    login(IP_PETROV, UserRole.CLIENT)
    application_id = await scored(
        client,
        process,
        PETROV_INN,
        response or manual_review(),
        requested_amount=2000000,
        term_months=24,
    )
    login(UNDERWRITER, UserRole.UNDERWRITER)
    return application_id


def decision_url(application_id: str) -> str:
    return f"/api/v1/underwriter/applications/{application_id}/decision"


async def test_queue_and_card_show_risk_and_reasons(
    client: httpx.AsyncClient, login: Login, process: ProcessApplication
) -> None:
    application_id = await in_review(client, login, process)

    queue = (await client.get("/api/v1/underwriter/queue")).json()
    card = (
        await client.get(f"/api/v1/underwriter/applications/{application_id}")
    ).json()

    assert [item["id"] for item in queue] == [application_id]
    assert queue[0]["manual_review_reasons"] == [MASS_ADDRESS]
    assert queue[0]["eta_deadline"] is not None
    decision = card["system_decision"]
    assert (decision["pd"], decision["grade"], decision["score"]) == (0.0118, "A", 742)
    assert decision["risk_factors"][0]["label"] == "Высокая доля наличных"
    assert decision["positive_factors"]
    assert decision["manual_review_reasons"] == [MASS_ADDRESS]
    assert card["preliminary_offer"]["amount"] == 2000000
    assert {s["source"] for s in card["snapshots"]} == {
        "egrul",
        "fns",
        "bki",
        "statement",
    }
    assert card["company"]["annual_revenue"] == 18000000


async def test_client_does_not_see_preliminary_offer(
    client: httpx.AsyncClient, login: Login, process: ProcessApplication
) -> None:
    application_id = await in_review(client, login, process)

    login(IP_PETROV, UserRole.CLIENT)
    card = (await client.get(f"/api/v1/applications/{application_id}")).json()

    assert card["status"]["code"] == "MANUAL_REVIEW"
    assert card["status"]["next_action"] == "ждать, ориентир — 1 рабочий день"
    assert card["offer"] is None


async def test_approve_gives_client_preliminary_offer(
    client: httpx.AsyncClient, login: Login, process: ProcessApplication
) -> None:
    application_id = await in_review(client, login, process)

    response = await client.post(
        decision_url(application_id),
        json={
            "action": "approve",
            "comment": "Адрес проверен, офис по договору аренды",
        },
    )

    assert response.status_code == 200
    latest = response.json()["latest_decision"]
    assert latest["decided_by"] == "underwriter"
    assert (latest["pd"], latest["grade"]) == (0.0118, "A")
    assert latest["model_version"] == "pd-smb-lgbm-test"
    login(IP_PETROV, UserRole.CLIENT)
    card = (await client.get(f"/api/v1/applications/{application_id}")).json()
    assert card["status"]["code"] == "OFFERED"
    assert (card["offer"]["amount"], card["offer"]["monthly_payment"]) == (
        2000000,
        100813.01,
    )
    assert card["events"][-1]["actor"] == "underwriter"


async def test_change_terms_within_product_limits(
    client: httpx.AsyncClient, login: Login, process: ProcessApplication
) -> None:
    application_id = await in_review(client, login, process)

    too_much = await client.post(
        decision_url(application_id),
        json={
            "action": "change_terms",
            "amount": 50000000,
            "term_months": 24,
            "comment": "Проверка",
        },
    )
    changed = await client.post(
        decision_url(application_id),
        json={
            "action": "change_terms",
            "amount": 1500000,
            "term_months": 18,
            "comment": "Снижаем сумму из-за сезонности",
        },
    )

    assert too_much.status_code == 422
    assert changed.json()["latest_decision"]["outcome"] == "COUNTER_OFFER"
    login(IP_PETROV, UserRole.CLIENT)
    card = (await client.get(f"/api/v1/applications/{application_id}")).json()
    assert card["offer"]["is_counter_offer"] is True
    assert (card["offer"]["amount"], card["offer"]["term_months"]) == (1500000, 18)
    assert card["offer"]["rate"] == 19.0


async def test_request_info_and_decline(
    client: httpx.AsyncClient, login: Login, process: ProcessApplication
) -> None:
    first = await in_review(client, login, process)
    requested = await client.post(
        decision_url(first),
        json={
            "action": "request_info",
            "documents": ["collateral_info"],
            "comment": "Нужен залог",
        },
    )
    login(IP_PETROV, UserRole.CLIENT)
    card = (await client.get(f"/api/v1/applications/{first}")).json()

    assert requested.json()["status"]["code"] == "INFO_REQUESTED"
    assert [d["reason_code"] for d in card["requested_documents"]] == [
        "INFO_NO_COLLATERAL"
    ]

    login(IP_IVANOV, UserRole.CLIENT)
    second = await scored(client, process, "772814539067", manual_review(False))
    login(UNDERWRITER, UserRole.UNDERWRITER)
    approve_without_offer = await client.post(
        decision_url(second), json={"action": "approve", "comment": "Одобряю"}
    )
    declined = await client.post(
        decision_url(second),
        json={
            "action": "decline",
            "reason": "Не подтверждён фактический адрес ведения бизнеса",
            "comment": "Выезд не подтвердил",
        },
    )
    again = await client.post(
        decision_url(second), json={"action": "approve", "comment": "Одобряю"}
    )

    assert approve_without_offer.status_code == 422
    assert declined.json()["status"]["code"] == "DECLINED"
    assert again.status_code == 409
    login(IP_IVANOV, UserRole.CLIENT)
    card = (await client.get(f"/api/v1/applications/{second}")).json()
    assert card["decision"]["reasons"][0]["text"] == (
        "Не подтверждён фактический адрес ведения бизнеса"
    )


async def test_client_cannot_use_underwriter_api(
    client: httpx.AsyncClient, login: Login
) -> None:
    login(IP_PETROV, UserRole.CLIENT)

    assert (await client.get("/api/v1/underwriter/queue")).status_code == 403

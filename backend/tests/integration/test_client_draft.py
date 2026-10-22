from collections.abc import Callable
from typing import Any
from uuid import UUID

import httpx
import pytest

from domain.entities.user import UserRole
from tests.fakes import FakeTaskQueue
from tests.users import IP_IVANOV, ROMASHKA_DIRECTOR, UNDERWRITER

Login = Callable[[UUID, UserRole], None]

DRAFT = {
    "product": "express",
    "requested_amount": 1500000,
    "term_months": 12,
    "purpose": "working_capital",
}
CONSENTS = {"consent_bki": True, "consent_pd": True}


@pytest.fixture(autouse=True)
def as_ivanov(login: Login) -> None:
    login(IP_IVANOV, UserRole.CLIENT)


async def create(client: httpx.AsyncClient, **overrides: Any) -> dict[str, Any]:
    response = await client.post("/api/v1/applications", json=DRAFT | overrides)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_draft_needs_only_loan_parameters(client: httpx.AsyncClient) -> None:
    card = await create(client)

    assert card["status"]["code"] == "DRAFT"
    assert card["status"]["title"] == "Черновик"
    assert card["requested_amount"] == 1500000
    assert [e["to_status"] for e in card["events"]] == ["DRAFT"]


async def test_company_data_is_not_accepted_in_draft(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/applications", json=DRAFT | {"inn": "772814539067"}
    )

    assert response.status_code == 422


async def test_product_limits_are_checked_immediately(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/applications", json=DRAFT | {"requested_amount": 20_000_000}
    )

    assert response.status_code == 422
    assert "10 000 000" in response.json()["details"]


async def test_second_active_application_for_product_is_conflict(
    client: httpx.AsyncClient,
) -> None:
    await create(client)

    response = await client.post("/api/v1/applications", json=DRAFT)

    assert response.status_code == 409


async def test_submit_requires_consents(client: httpx.AsyncClient) -> None:
    card = await create(client)

    response = await client.post(
        f"/api/v1/applications/{card['id']}/submit",
        json={"consent_bki": True, "consent_pd": False},
    )

    assert response.status_code == 422


async def test_submit_is_idempotent_and_enqueues_once(
    client: httpx.AsyncClient, task_queue: FakeTaskQueue
) -> None:
    card = await create(client)
    url = f"/api/v1/applications/{card['id']}/submit"

    first = await client.post(url, json=CONSENTS)
    second = await client.post(url, json=CONSENTS)

    assert first.status_code == second.status_code == 200
    assert first.json()["status"]["code"] == "SUBMITTED"
    assert first.json()["consent_at"] is not None
    assert first.json()["status"]["eta_deadline"] is not None
    assert second.json()["status"]["code"] == "SUBMITTED"
    assert task_queue.processing == [UUID(card["id"])]
    events = (await client.get(f"/api/v1/applications/{card['id']}/events")).json()
    assert [e["to_status"] for e in events] == ["DRAFT", "SUBMITTED"]


async def test_other_company_application_is_not_found(
    client: httpx.AsyncClient, login: Login
) -> None:
    card = await create(client)

    login(ROMASHKA_DIRECTOR, UserRole.CLIENT)
    response = await client.get(f"/api/v1/applications/{card['id']}")

    assert response.status_code == 404


async def test_underwriter_has_no_access_to_client_api(
    client: httpx.AsyncClient, login: Login
) -> None:
    login(UNDERWRITER, UserRole.UNDERWRITER)

    response = await client.get("/api/v1/applications")

    assert response.status_code == 403


async def test_update_only_draft(client: httpx.AsyncClient) -> None:
    card = await create(client)
    url = f"/api/v1/applications/{card['id']}"

    updated = await client.patch(url, json={"term_months": 24})
    assert updated.status_code == 200
    assert updated.json()["term_months"] == 24

    await client.post(f"{url}/submit", json=CONSENTS)
    assert (await client.patch(url, json={"term_months": 6})).status_code == 409


async def test_delete_draft_then_copy(client: httpx.AsyncClient) -> None:
    card = await create(client)
    url = f"/api/v1/applications/{card['id']}"

    deleted = await client.delete(url)
    copy = await client.post(f"{url}/copy")

    assert deleted.json()["status"]["code"] == "CANCELLED"
    assert copy.status_code == 201
    assert copy.json()["id"] != card["id"]
    assert copy.json()["status"]["code"] == "DRAFT"
    listed = (await client.get("/api/v1/applications")).json()
    assert {a["status"]["code"] for a in listed} == {"DRAFT", "CANCELLED"}


async def test_catalog(client: httpx.AsyncClient) -> None:
    statuses = (await client.get("/api/v1/statuses")).json()
    products = (await client.get("/api/v1/products")).json()
    recommended = (
        await client.post(
            "/api/v1/products/recommend",
            json={"purpose": "working_capital", "amount": 2_000_000},
        )
    ).json()
    calculation = await client.post(
        "/api/v1/calculator",
        json={"product": "express", "amount": 1_500_000, "term_months": 12},
    )

    assert len(statuses) == 11
    assert {p["code"] for p in products} == {"express", "overdraft", "investment"}
    assert [r["product"]["code"] for r in recommended] == ["express", "overdraft"]
    assert recommended[0]["calculation"]["best"]["rate"] == 19.0
    assert calculation.json()["best"]["monthly_payment"] == 138234.87
    assert calculation.json()["worst"]["rate"] == 26.0

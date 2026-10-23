import asyncio
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest

from tests.seed_data import seed_companies

API_URL = os.environ.get("E2E_API_URL")
KEYCLOAK_URL = os.environ.get("E2E_KEYCLOAK_URL", "http://localhost:8080")
PASSWORD = os.environ.get("E2E_PASSWORD", "alfa2026")
CONSENTS = {"consent_bki": True, "consent_pd": True}
IN_PROGRESS = {"SUBMITTED", "CHECKING"}
DECISION_TIMEOUT_IN_SECONDS = 90

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not API_URL, reason="нужен поднятый compose: E2E_API_URL"),
]


class User:
    def __init__(self, client: httpx.AsyncClient, token: str) -> None:
        self._client = client
        self._headers = {"Authorization": f"Bearer {token}"}

    async def get(self, path: str) -> httpx.Response:
        return await self._client.get(f"/api/v1{path}", headers=self._headers)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self._client.post(
            f"/api/v1{path}", headers=self._headers, **kwargs
        )

    async def delete(self, path: str) -> httpx.Response:
        return await self._client.delete(f"/api/v1{path}", headers=self._headers)


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(base_url=API_URL or "", timeout=30) as client:
        yield client


async def login(http: httpx.AsyncClient, username: str) -> User:
    async with httpx.AsyncClient(timeout=10) as keycloak:
        response = await keycloak.post(
            f"{KEYCLOAK_URL}/realms/alfa-credit/protocol/openid-connect/token",
            data={
                "client_id": "credit-cabinet-web",
                "grant_type": "password",
                "username": username,
                "password": PASSWORD,
                "scope": "openid",
            },
        )
    response.raise_for_status()
    return User(http, response.json()["access_token"])


async def clean_slate(http: httpx.AsyncClient, client: User, product: str) -> None:
    underwriter = await login(http, "underwriter")
    for application in (await client.get("/applications")).json():
        if application["product"] != product:
            continue
        code, app_id = application["status"]["code"], application["id"]
        if code == "DRAFT":
            await client.delete(f"/applications/{app_id}")
        elif code == "OFFERED":
            await client.post(f"/applications/{app_id}/offer/reject")
        elif code == "MANUAL_REVIEW":
            await underwriter.post(
                f"/underwriter/applications/{app_id}/decision",
                json={
                    "action": "decline",
                    "reason": "Закрыто перед e2e-прогоном",
                    "comment": "e2e",
                },
            )


async def wait_decision(client: User, app_id: str) -> dict[str, Any]:
    async with asyncio.timeout(DECISION_TIMEOUT_IN_SECONDS):
        while True:
            card: dict[str, Any] = (await client.get(f"/applications/{app_id}")).json()
            if card["status"]["code"] not in IN_PROGRESS:
                return card
            await asyncio.sleep(1)


async def wait_status(client: User, app_id: str, status: str) -> dict[str, Any]:
    async with asyncio.timeout(60):
        while True:
            card: dict[str, Any] = (await client.get(f"/applications/{app_id}")).json()
            if card["status"]["code"] == status:
                return card
            await asyncio.sleep(1)


async def apply(http: httpx.AsyncClient, client: User, inn: str) -> dict[str, Any]:
    company = next(c for c in seed_companies() if c["inn"] == inn)
    request = company["demo_request"]
    await clean_slate(http, client, request["product"])
    draft = await client.post("/applications", json=request)
    assert draft.status_code == 201, draft.text
    app_id = draft.json()["id"]
    submitted = await client.post(f"/applications/{app_id}/submit", json=CONSENTS)
    assert submitted.json()["status"]["code"] == "SUBMITTED"
    return await wait_decision(client, app_id)


async def sign_and_wait_issue(signer: User, app_id: str) -> dict[str, Any]:
    code = (await signer.post(f"/applications/{app_id}/contract/sign-code")).json()[
        "code"
    ]
    signed = await signer.post(
        f"/applications/{app_id}/contract/sign", json={"code": code}
    )
    assert signed.json()["status"]["code"] == "SIGNED"
    return await wait_status(signer, app_id, "ISSUED")


async def test_ip_ivanov_approved_to_issued(http: httpx.AsyncClient) -> None:
    client = await login(http, "ip.ivanov")

    card = await apply(http, client, "772814539067")
    app_id = card["id"]
    assert card["status"]["code"] == "OFFERED"
    assert card["decision"]["outcome"] == "APPROVED"
    assert card["offer"]["is_counter_offer"] is False

    accepted = (await client.post(f"/applications/{app_id}/offer/accept")).json()
    contract = (await client.get(f"/applications/{app_id}/contract")).json()
    assert contract["matches_offer"] is True
    for field in ("amount", "term_months", "rate", "monthly_payment"):
        assert contract[field] == accepted["offer"][field]

    issued = await sign_and_wait_issue(client, app_id)
    assert [e["to_status"] for e in issued["events"]] == [
        "DRAFT",
        "SUBMITTED",
        "CHECKING",
        "OFFERED",
        "ACCEPTED",
        "SIGNED",
        "ISSUED",
    ]
    underwriter = await login(http, "underwriter")
    review = (await underwriter.get(f"/underwriter/applications/{app_id}")).json()
    assert review["system_decision"]["model_version"]
    assert review["system_decision"]["policy_version"]
    assert len(review["snapshots"]) == 4


async def test_romashka_counter_offer_signed_by_director(
    http: httpx.AsyncClient,
) -> None:
    accountant = await login(http, "ooo.romashka.accountant")

    card = await apply(http, accountant, "7701846322")
    app_id = card["id"]
    assert card["decision"]["outcome"] == "COUNTER_OFFER"
    assert card["offer"]["is_counter_offer"] is True
    assert card["offer"]["amount"] < card["offer"]["requested_amount"]

    await accountant.post(f"/applications/{app_id}/offer/accept")
    forbidden = await accountant.post(f"/applications/{app_id}/contract/sign-code")
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "signer_required"

    director = await login(http, "ooo.romashka.director")
    issued = await sign_and_wait_issue(director, app_id)
    assert issued["status"]["code"] == "ISSUED"


async def test_vector_documents_then_offer(http: httpx.AsyncClient) -> None:
    client = await login(http, "ooo.vector.director")

    card = await apply(http, client, "5406723981")
    app_id = card["id"]
    assert card["status"]["code"] == "INFO_REQUESTED"
    assert [d["reason_code"] for d in card["requested_documents"]] == [
        "INFO_TAX_ARREARS"
    ]

    uploaded = await client.post(
        f"/applications/{app_id}/documents",
        data={"reason_code": "INFO_TAX_ARREARS"},
        files={"file": ("spravka.pdf", b"%PDF-1.4 e2e", "application/pdf")},
    )
    assert uploaded.status_code == 201
    await client.post(f"/applications/{app_id}/documents/complete")

    card = await wait_decision(client, app_id)
    assert card["status"]["code"] == "OFFERED"
    assert card["decision"]["outcome"] == "APPROVED"


async def test_petrov_manual_review_by_underwriter(http: httpx.AsyncClient) -> None:
    client = await login(http, "ip.petrov")

    card = await apply(http, client, "663205817446")
    app_id = card["id"]
    assert card["status"]["code"] == "MANUAL_REVIEW"
    assert card["offer"] is None

    underwriter = await login(http, "underwriter")
    queue = (await underwriter.get("/underwriter/queue")).json()
    item = next(i for i in queue if i["id"] == app_id)
    assert "MR_MASS_ADDRESS" in {r["code"] for r in item["manual_review_reasons"]}
    review = (await underwriter.get(f"/underwriter/applications/{app_id}")).json()
    assert review["system_decision"]["pd"] is not None
    assert review["system_decision"]["grade"]
    assert review["system_decision"]["risk_factors"]
    assert review["preliminary_offer"] is not None

    decided = await underwriter.post(
        f"/underwriter/applications/{app_id}/decision",
        json={"action": "approve", "comment": "Адрес проверен, e2e"},
    )
    assert decided.json()["status"]["code"] == "OFFERED"
    card = (await client.get(f"/applications/{app_id}")).json()
    assert card["offer"]["amount"] == review["preliminary_offer"]["amount"]


async def test_delta_declined_then_new_application(http: httpx.AsyncClient) -> None:
    client = await login(http, "ooo.delta.director")

    card = await apply(http, client, "7810492265")
    assert card["status"]["code"] == "DECLINED"
    assert card["decision"]["reasons"][0]["code"] == "STOP_OVERDUE_90"

    copy = await client.post(f"/applications/{card['id']}/copy")
    assert copy.status_code == 201
    assert copy.json()["status"]["code"] == "DRAFT"
    assert copy.json()["requested_amount"] == card["requested_amount"]
    await client.delete(f"/applications/{copy.json()['id']}")

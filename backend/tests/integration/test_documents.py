import json
from typing import Any
from uuid import UUID

import httpx
import respx

from application.use_cases.processing.process_application import ProcessApplication
from domain.entities.user import UserRole
from tests.fakes import FakeDocumentStorage, FakeTaskQueue
from tests.integration.pipeline import ML, Login, ml_response, route_mocks, scored
from tests.integration.test_underwriter import in_review
from tests.users import IP_PETROV, UNDERWRITER, VECTOR_DIRECTOR

VECTOR_INN = "5406723981"
PDF = ("spravka.pdf", b"%PDF-1.4 tax certificate", "application/pdf")


def request_info() -> dict[str, Any]:
    return ml_response(
        "REQUEST_INFO",
        pd=None,
        score=None,
        grade=None,
        max_amount=None,
        offer=None,
        reasons=[
            {
                "code": "INFO_TAX_ARREARS",
                "text": "По данным ФНС есть задолженность по налогам",
            }
        ],
        requested_documents=["Справка ФНС"],
    )


def docs_url(application_id: str, path: str = "") -> str:
    return f"/api/v1/applications/{application_id}/documents{path}"


async def test_tax_certificate_closes_request_and_rescoring_approves(
    client: httpx.AsyncClient,
    login: Login,
    process: ProcessApplication,
    task_queue: FakeTaskQueue,
    storage: FakeDocumentStorage,
) -> None:
    login(VECTOR_DIRECTOR, UserRole.CLIENT)
    app_id = await scored(
        client, process, VECTOR_INN, request_info(), requested_amount=3000000
    )

    early = await client.post(docs_url(app_id, "/complete"))
    wrong_reason = await client.post(
        docs_url(app_id),
        data={"reason_code": "INFO_NO_COLLATERAL"},
        files={"file": PDF},
    )
    wrong_type = await client.post(
        docs_url(app_id),
        data={"reason_code": "INFO_TAX_ARREARS"},
        files={"file": ("a.exe", b"MZ", "application/octet-stream")},
    )
    uploaded = await client.post(
        docs_url(app_id), data={"reason_code": "INFO_TAX_ARREARS"}, files={"file": PDF}
    )
    listing = (await client.get(docs_url(app_id))).json()
    download = await client.get(docs_url(app_id, f"/{uploaded.json()['id']}/file"))
    completed = await client.post(docs_url(app_id, "/complete"))

    assert early.status_code == 422
    assert "Справка ФНС" in early.json()["details"]
    assert wrong_reason.status_code == 422
    assert wrong_type.status_code == 422
    assert uploaded.status_code == 201
    assert listing["requested"][0]["uploaded"] is True
    assert download.content == PDF[1]
    assert download.headers["content-type"] == "application/pdf"
    assert f"applications/{app_id}/{uploaded.json()['id']}" in storage.files
    assert completed.json()["status"]["code"] == "CHECKING"
    assert task_queue.processing.count(UUID(app_id)) == 2

    with respx.mock() as router:
        route_mocks(router, VECTOR_INN)
        call = router.post(f"{ML}/v1/decision").respond(json=ml_response("APPROVED"))
        await process(UUID(app_id))

    assert json.loads(call.calls[0].request.content)["tax_arrears"] is False
    card = (await client.get(f"/api/v1/applications/{app_id}")).json()
    assert card["status"]["code"] == "OFFERED"
    assert [e["to_status"] for e in card["events"]][-3:] == [
        "INFO_REQUESTED",
        "CHECKING",
        "OFFERED",
    ]


async def test_collateral_requested_by_underwriter_updates_application(
    client: httpx.AsyncClient,
    login: Login,
    process: ProcessApplication,
) -> None:
    app_id = await in_review(client, login, process)
    await client.post(
        f"/api/v1/underwriter/applications/{app_id}/decision",
        json={
            "action": "request_info",
            "documents": ["collateral_info"],
            "comment": "Нужен залог",
        },
    )
    login(IP_PETROV, UserRole.CLIENT)

    without_value = await client.post(
        docs_url(app_id),
        data={"reason_code": "INFO_NO_COLLATERAL"},
        files={"file": PDF},
    )
    with_value = await client.post(
        docs_url(app_id),
        data={
            "reason_code": "INFO_NO_COLLATERAL",
            "collateral_value": "3500000",
            "collateral_description": "Грузовой фургон 2022 года",
        },
        files={"file": PDF},
    )
    card = (await client.get(f"/api/v1/applications/{app_id}")).json()

    assert without_value.status_code == 422
    assert with_value.status_code == 201
    assert card["collateral_value"] == 3500000
    assert card["collateral_description"] == "Грузовой фургон 2022 года"

    login(UNDERWRITER, UserRole.UNDERWRITER)
    review_file = await client.get(
        f"/api/v1/underwriter/applications/{app_id}/documents/"
        f"{with_value.json()['id']}/file"
    )
    assert review_file.content == PDF[1]


async def test_upload_only_when_documents_requested(
    client: httpx.AsyncClient, login: Login, process: ProcessApplication
) -> None:
    login(VECTOR_DIRECTOR, UserRole.CLIENT)
    app_id = await scored(
        client, process, VECTOR_INN, ml_response("APPROVED"), requested_amount=3000000
    )

    response = await client.post(
        docs_url(app_id), data={"reason_code": "INFO_TAX_ARREARS"}, files={"file": PDF}
    )

    assert response.status_code == 409

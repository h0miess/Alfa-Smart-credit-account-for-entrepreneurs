from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from failures import Source, simulate
from registry import find_company, months_since

router = APIRouter()

_disbursements: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(UTC).isoformat()


@router.get("/egrul/{inn}", tags=["ЕГРЮЛ/ЕГРИП"])
async def egrul_extract(inn: str) -> dict[str, Any]:
    await simulate(Source.EGRUL)
    company = find_company(inn)
    return {
        "inn": company.inn,
        "ogrn": company.ogrn,
        "name": company.name,
        "legal_form": company.legal_form,
        **company.sources["egrul"],
        "fetched_at": _now(),
    }


@router.get("/fns/{inn}/arrears", tags=["ФНС"])
async def fns_arrears(inn: str) -> dict[str, Any]:
    await simulate(Source.FNS)
    company = find_company(inn)
    return {"inn": company.inn, **company.sources["fns"], "checked_at": _now()}


@router.get("/bki/{inn}/report", tags=["БКИ"])
async def bki_report(inn: str) -> dict[str, Any]:
    await simulate(Source.BKI)
    company = find_company(inn)
    return {"inn": company.inn, **company.sources["bki"], "report_date": _now()}


@router.get("/abs/{inn}/statement", tags=["АБС"])
async def abs_statement(inn: str) -> dict[str, Any]:
    await simulate(Source.ABS)
    company = find_company(inn)
    return {
        "inn": company.inn,
        "account": company.settlement_account,
        "period_months": 12,
        **company.sources["statement"],
        "bank_client_months": months_since(company.bank_client_since, date.today()),
        "fetched_at": _now(),
    }


class DisbursementIn(BaseModel):
    contract_id: UUID
    account: str = Field(min_length=20, max_length=20)
    amount: Decimal = Field(gt=0)


@router.post("/abs/disbursements", tags=["АБС"], status_code=status.HTTP_201_CREATED)
async def abs_disburse(
    body: DisbursementIn,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> dict[str, Any]:
    await simulate(Source.ABS)
    known = _disbursements.get(idempotency_key)
    if known is not None:
        if known["contract_id"] != str(body.contract_id):
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Ключ идемпотентности уже использован"
            )
        return known

    operation = {
        "operation_id": f"ABS-{uuid4().hex[:12].upper()}",
        "contract_id": str(body.contract_id),
        "account": body.account,
        "amount": float(body.amount),
        "status": "COMPLETED",
        "executed_at": _now(),
    }
    _disbursements[idempotency_key] = operation
    return operation

import json
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status

from settings import settings


@dataclass(frozen=True, slots=True)
class CompanyRecord:
    inn: str
    ogrn: str
    name: str
    legal_form: str
    bank_client_since: date
    settlement_account: str
    sources: dict[str, dict[str, Any]]


@cache
def _registry(path: Path) -> dict[str, CompanyRecord]:
    companies = json.loads(path.read_text(encoding="utf-8"))["companies"]
    return {
        c["inn"]: CompanyRecord(
            inn=c["inn"],
            ogrn=c["ogrn"],
            name=c["name"],
            legal_form=c["legal_form"],
            bank_client_since=date.fromisoformat(c["bank_client_since"]),
            settlement_account=c["settlement_account"],
            sources=c["sources"],
        )
        for c in companies
    }


def find_company(inn: str) -> CompanyRecord:
    company = _registry(settings.SEED_FILE).get(inn)
    if company is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Сведения по ИНН {inn} не найдены"
        )
    return company


def months_since(start: date, today: date) -> int:
    months = (today.year - start.year) * 12 + today.month - start.month
    if today.day < start.day:
        months -= 1
    return max(months, 0)

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.company import Company, Industry, LegalForm
from domain.entities.representative import Representative, RepresentativeRole


def read_seed(path: Path) -> list[dict[str, Any]]:
    companies: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))[
        "companies"
    ]
    return companies


def build_company(data: dict[str, Any]) -> Company:
    return Company(
        id=UUID(data["id"]),
        legal_form=LegalForm(data["legal_form"]),
        inn=data["inn"],
        ogrn=data["ogrn"],
        name=data["name"],
        industry=Industry(data["industry"]),
        region_tier=data["region_tier"],
        registered_at=date.fromisoformat(data["registered_at"]),
        employees=data["employees"],
        bank_client_since=date.fromisoformat(data["bank_client_since"]),
        annual_revenue=Decimal(str(data["annual_revenue"])),
        net_margin=Decimal(str(data["net_margin"])),
        settlement_account=data["settlement_account"],
    )


def build_representatives(data: dict[str, Any]) -> list[Representative]:
    return [
        Representative(
            id=UUID(item["id"]),
            company_id=UUID(data["id"]),
            keycloak_user_id=UUID(item["keycloak_user_id"]),
            full_name=item["full_name"],
            role=RepresentativeRole(item["role"]),
            can_sign=item["can_sign"],
        )
        for item in data["representatives"]
    ]


async def load_seed(session: AsyncSession, path: Path) -> int:
    companies = read_seed(path)
    for data in companies:
        await session.merge(build_company(data))
    await session.flush()
    for data in companies:
        for representative in build_representatives(data):
            await session.merge(representative)
    await session.commit()
    return len(companies)

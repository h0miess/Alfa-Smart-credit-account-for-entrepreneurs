from collections.abc import Mapping, Sequence
from datetime import date
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final

from domain.entities.company import Company
from domain.entities.document import Document
from domain.entities.enrichment_snapshot import EnrichmentSource
from domain.entities.loan_application import LoanApplication


class FieldSource(StrEnum):
    COMPANY = "company"
    EGRUL = EnrichmentSource.EGRUL.value
    FNS = EnrichmentSource.FNS.value
    BKI = EnrichmentSource.BKI.value
    STATEMENT = EnrichmentSource.STATEMENT.value
    APPLICATION = "application"


FIELD_SOURCES: Final[Mapping[str, FieldSource]] = MappingProxyType(
    {
        "legal_form": FieldSource.COMPANY,
        "industry": FieldSource.COMPANY,
        "region_tier": FieldSource.COMPANY,
        "employees": FieldSource.COMPANY,
        "annual_revenue": FieldSource.COMPANY,
        "net_margin": FieldSource.COMPANY,
        "business_age_months": FieldSource.EGRUL,
        "director_changes_12m": FieldSource.EGRUL,
        "mass_address": FieldSource.EGRUL,
        "tax_arrears": FieldSource.FNS,
        "bki_history_months": FieldSource.BKI,
        "max_overdue_days_12m": FieldSource.BKI,
        "overdue_count_24m": FieldSource.BKI,
        "credit_inquiries_3m": FieldSource.BKI,
        "existing_debt": FieldSource.BKI,
        "monthly_debt_payments": FieldSource.BKI,
        "avg_monthly_turnover": FieldSource.STATEMENT,
        "turnover_volatility": FieldSource.STATEMENT,
        "turnover_trend_12m": FieldSource.STATEMENT,
        "cash_withdrawal_share": FieldSource.STATEMENT,
        "top_counterparty_share": FieldSource.STATEMENT,
        "bank_client_months": FieldSource.STATEMENT,
        "product": FieldSource.APPLICATION,
        "requested_amount": FieldSource.APPLICATION,
        "term_months": FieldSource.APPLICATION,
        "collateral_value": FieldSource.APPLICATION,
    }
)


def build_decision_request(
    application: LoanApplication,
    company: Company,
    sources: Mapping[EnrichmentSource, Mapping[str, Any]],
    documents: Sequence[Document],
    today: date,
) -> dict[str, Any]:
    egrul = sources[EnrichmentSource.EGRUL]
    fns = sources[EnrichmentSource.FNS]
    bki = sources[EnrichmentSource.BKI]
    statement = sources[EnrichmentSource.STATEMENT]

    values: dict[FieldSource, dict[str, Any]] = {
        FieldSource.COMPANY: {
            "legal_form": company.legal_form.value,
            "industry": company.industry.value,
            "region_tier": company.region_tier,
            "employees": company.employees,
            "annual_revenue": float(company.annual_revenue),
            "net_margin": float(company.net_margin),
        },
        FieldSource.EGRUL: {
            "business_age_months": months_between(
                date.fromisoformat(egrul["registration_date"]), today
            ),
            "director_changes_12m": egrul["director_changes_12m"],
            "mass_address": egrul["mass_address"],
        },
        FieldSource.FNS: {"tax_arrears": fns["tax_arrears"]},
        FieldSource.BKI: {
            field: bki[field]
            for field, source in FIELD_SOURCES.items()
            if source is FieldSource.BKI
        },
        FieldSource.STATEMENT: {
            field: statement[field]
            for field, source in FIELD_SOURCES.items()
            if source is FieldSource.STATEMENT
        },
        FieldSource.APPLICATION: {
            "product": application.product.value,
            "requested_amount": float(application.requested_amount),
            "term_months": application.term_months,
            "collateral_value": float(application.collateral_value),
        },
    }

    request = {field: values[source][field] for field, source in FIELD_SOURCES.items()}
    request["application_id"] = str(application.id)
    return apply_document_adjustments(request, documents)


def apply_document_adjustments(
    request: dict[str, Any], documents: Sequence[Document]
) -> dict[str, Any]:
    adjusted = dict(request)
    for document in documents:
        extracted = document.extracted
        if "tax_arrears" in extracted:
            adjusted["tax_arrears"] = extracted["tax_arrears"]
        if "external_monthly_turnover" in extracted:
            adjusted["avg_monthly_turnover"] += extracted["external_monthly_turnover"]
        if "collateral_value" in extracted:
            adjusted["collateral_value"] = extracted["collateral_value"]
    return adjusted


def months_between(start: date, end: date) -> int:
    months = (end.year - start.year) * 12 + end.month - start.month
    if end.day < start.day:
        months -= 1
    return max(months, 0)

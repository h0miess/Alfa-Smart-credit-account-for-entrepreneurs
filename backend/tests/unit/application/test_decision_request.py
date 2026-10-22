from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from application.decision_request import (
    FIELD_SOURCES,
    FieldSource,
    build_decision_request,
    months_between,
)
from domain.entities.document import Document, DocumentKind, DocumentStatus
from domain.entities.enrichment_snapshot import EnrichmentSource
from seed.loader import build_company
from tests.process_doc import backticked, read_process_md, section, table_rows
from tests.seed_data import demo_application, mock_payloads, seed_company

DOC_SOURCE_LABELS = {
    "профиль компании": FieldSource.COMPANY,
    "отчётность компании": FieldSource.COMPANY,
    "мок ЕГРЮЛ/ЕГРИП": FieldSource.EGRUL,
    "мок ФНС": FieldSource.FNS,
    "мок БКИ": FieldSource.BKI,
    "выписка по счёту из АБС": FieldSource.STATEMENT,
    "заявка": FieldSource.APPLICATION,
}
TODAY = date(2026, 10, 23)
IVANOV_INN = "772814539067"


def _documented_sources() -> dict[str, FieldSource]:
    model_section = section(read_process_md(), "6.")
    table = model_section[model_section.index("Откуда берутся признаки скоринга") :]
    documented = {}
    for fields, source in table_rows(table)[1:]:
        [kind] = [
            v for label, v in DOC_SOURCE_LABELS.items() if source.startswith(label)
        ]
        for field in backticked(fields):
            documented[field] = kind
    return documented


def test_field_sources_match_process_table() -> None:
    assert dict(FIELD_SOURCES) == _documented_sources()


def test_each_field_is_taken_from_its_source() -> None:
    company_data = seed_company(IVANOV_INN)
    company = build_company(company_data)
    application = demo_application(company_data)
    payloads = mock_payloads(company_data, TODAY)

    request = build_decision_request(application, company, payloads, [], TODAY)

    assert request.keys() == {*FIELD_SOURCES, "application_id"}
    for field, source in FIELD_SOURCES.items():
        match source:
            case FieldSource.APPLICATION:
                expected = getattr(application, field)
            case FieldSource.COMPANY:
                expected = getattr(company, field)
            case FieldSource.EGRUL if field == "business_age_months":
                registered = payloads[EnrichmentSource.EGRUL]["registration_date"]
                expected = months_between(date.fromisoformat(registered), TODAY)
            case _:
                expected = payloads[EnrichmentSource(source.value)][field]
        if hasattr(expected, "value"):
            expected = expected.value
        if isinstance(expected, Decimal):
            expected = float(expected)
        assert request[field] == expected, field


def test_documents_adjust_request() -> None:
    company_data = seed_company("5406723981")
    application = demo_application(company_data)
    request = build_decision_request(
        application,
        build_company(company_data),
        mock_payloads(company_data, TODAY),
        [
            _document("INFO_TAX_ARREARS", {"tax_arrears": False}),
            _document("INFO_LOW_TURNOVER", {"external_monthly_turnover": 500000.0}),
        ],
        TODAY,
    )

    assert request["tax_arrears"] is False
    assert request["avg_monthly_turnover"] == 5800000 + 500000.0


def test_months_between() -> None:
    assert months_between(date(2019, 4, 15), date(2026, 10, 14)) == 89
    assert months_between(date(2019, 4, 15), date(2026, 10, 15)) == 90


def _document(reason_code: str, extracted: dict[str, object]) -> Document:
    return Document(
        id=uuid4(),
        application_id=uuid4(),
        kind=DocumentKind.TAX_CERTIFICATE,
        reason_code=reason_code,
        file_ref="ref",
        file_name="file.pdf",
        content_type="application/pdf",
        size_bytes=1,
        status=DocumentStatus.ACCEPTED,
        extracted=extracted,
        uploaded_at=datetime.now(UTC),
    )

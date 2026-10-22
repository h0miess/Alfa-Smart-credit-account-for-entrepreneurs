from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import registry

from domain.entities.application_event import ApplicationEvent
from domain.entities.company import Company
from domain.entities.contract import Contract
from domain.entities.decision import Decision
from domain.entities.disbursement import Disbursement
from domain.entities.document import Document
from domain.entities.enrichment_snapshot import EnrichmentSnapshot
from domain.entities.loan_application import LoanApplication
from domain.entities.offer import Offer
from domain.entities.representative import Representative
from infra.postgres.models import (
    application_event_table,
    application_table,
    company_table,
    contract_table,
    decision_table,
    disbursement_table,
    document_table,
    enrichment_snapshot_table,
    metadata,
    offer_table,
    representative_table,
)

mapper_registry = registry(metadata=metadata)

_MAPPINGS = (
    (Company, company_table),
    (Representative, representative_table),
    (LoanApplication, application_table),
    (ApplicationEvent, application_event_table),
    (Decision, decision_table),
    (EnrichmentSnapshot, enrichment_snapshot_table),
    (Offer, offer_table),
    (Document, document_table),
    (Contract, contract_table),
    (Disbursement, disbursement_table),
)


def start_mappers() -> None:
    if mapper_registry.mappers:
        return

    for entity, table in _MAPPINGS:
        mapper_registry.map_imperatively(entity, table, exclude_properties=["seq"])

    event.listen(LoanApplication, "load", _init_pending_events)


def _init_pending_events(application: LoanApplication, _: Any) -> None:
    application._events = []

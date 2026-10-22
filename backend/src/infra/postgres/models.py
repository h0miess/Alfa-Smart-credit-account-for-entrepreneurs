from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Table,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB

from domain.entities.application_event import ActorType
from domain.entities.company import Industry, LegalForm
from domain.entities.decision import DecidedBy
from domain.entities.document import DocumentKind, DocumentStatus
from domain.entities.enrichment_snapshot import EnrichmentSource
from domain.entities.offer import OfferStatus
from domain.entities.representative import RepresentativeRole
from domain.outcomes import Grade, ScoringOutcome
from domain.products import LoanPurpose, ProductCode
from domain.statuses import TERMINAL_STATUSES, ApplicationStatus

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


def _enum(enum_cls: type[StrEnum]) -> Enum:
    return Enum(
        enum_cls,
        native_enum=False,
        length=32,
        values_callable=lambda members: [m.value for m in members],
        validate_strings=True,
    )


def _money() -> Numeric:
    return Numeric(16, 2)


def _timestamp() -> DateTime:
    return DateTime(timezone=True)


company_table = Table(
    "company",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("legal_form", _enum(LegalForm), nullable=False),
    Column("inn", String(12), nullable=False, unique=True),
    Column("ogrn", String(15), nullable=False, unique=True),
    Column("name", String(255), nullable=False),
    Column("industry", _enum(Industry), nullable=False),
    Column("region_tier", SmallInteger, nullable=False),
    Column("registered_at", Date, nullable=False),
    Column("employees", Integer, nullable=False),
    Column("bank_client_since", Date, nullable=False),
    Column("annual_revenue", _money(), nullable=False),
    Column("net_margin", Numeric(6, 4), nullable=False),
    Column("settlement_account", String(20), nullable=False),
)

representative_table = Table(
    "representative",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("company_id", ForeignKey("company.id"), nullable=False, index=True),
    Column("keycloak_user_id", Uuid, nullable=False, unique=True),
    Column("full_name", String(255), nullable=False),
    Column("role", _enum(RepresentativeRole), nullable=False),
    Column("can_sign", Boolean, nullable=False),
)

application_table = Table(
    "application",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("company_id", ForeignKey("company.id"), nullable=False, index=True),
    Column("created_by", ForeignKey("representative.id"), nullable=False),
    Column("product", _enum(ProductCode), nullable=False),
    Column("requested_amount", _money(), nullable=False),
    Column("term_months", SmallInteger, nullable=False),
    Column("purpose", _enum(LoanPurpose), nullable=False),
    Column("collateral_value", _money(), nullable=False),
    Column("collateral_description", Text),
    Column("status", _enum(ApplicationStatus), nullable=False, index=True),
    Column("consent_at", _timestamp()),
    Column("created_at", _timestamp(), nullable=False),
    Column("updated_at", _timestamp(), nullable=False),
    Column("status_changed_at", _timestamp(), nullable=False),
)

Index(
    "uq_application_active_company_product",
    application_table.c.company_id,
    application_table.c.product,
    unique=True,
    postgresql_where=application_table.c.status.not_in(
        [s.value for s in sorted(TERMINAL_STATUSES)]
    ),
)

application_event_table = Table(
    "application_event",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("application_id", ForeignKey("application.id"), nullable=False),
    Column("from_status", _enum(ApplicationStatus)),
    Column("to_status", _enum(ApplicationStatus), nullable=False),
    Column("actor", _enum(ActorType), nullable=False),
    Column("actor_id", Uuid),
    Column("comment", Text),
    Column("at", _timestamp(), nullable=False),
    Column("seq", BigInteger, Identity(), nullable=False),
    Index("ix_application_event_application_id_seq", "application_id", "seq"),
)

decision_table = Table(
    "decision",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("application_id", ForeignKey("application.id"), nullable=False),
    Column("outcome", _enum(ScoringOutcome), nullable=False),
    Column("pd", Numeric(6, 4)),
    Column("grade", _enum(Grade)),
    Column("score", Integer),
    Column("max_amount", _money()),
    Column("reasons", JSONB, nullable=False),
    Column("risk_factors", JSONB, nullable=False),
    Column("positive_factors", JSONB, nullable=False),
    Column("requested_documents", JSONB, nullable=False),
    Column("decided_by", _enum(DecidedBy), nullable=False),
    Column("decided_by_user_id", Uuid),
    Column("model_version", String(64)),
    Column("policy_version", String(64)),
    Column("request_payload", JSONB),
    Column("raw_response", JSONB),
    Column("comment", Text),
    Column("at", _timestamp(), nullable=False),
    Index("ix_decision_application_id_at", "application_id", "at"),
)

enrichment_snapshot_table = Table(
    "enrichment_snapshot",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("application_id", ForeignKey("application.id"), nullable=False, index=True),
    Column("source", _enum(EnrichmentSource), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("fetched_at", _timestamp(), nullable=False),
    Column("decision_id", ForeignKey("decision.id"), index=True),
)

offer_table = Table(
    "offer",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("decision_id", ForeignKey("decision.id"), nullable=False, unique=True),
    Column("product", _enum(ProductCode), nullable=False),
    Column("amount", _money(), nullable=False),
    Column("term_months", SmallInteger, nullable=False),
    Column("rate", Numeric(5, 2), nullable=False),
    Column("monthly_payment", _money(), nullable=False),
    Column("valid_until", Date, nullable=False),
    Column("status", _enum(OfferStatus), nullable=False, index=True),
)

document_table = Table(
    "document",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("application_id", ForeignKey("application.id"), nullable=False, index=True),
    Column("kind", _enum(DocumentKind), nullable=False),
    Column("reason_code", String(64), nullable=False),
    Column("file_ref", String(255), nullable=False),
    Column("file_name", String(255), nullable=False),
    Column("content_type", String(128), nullable=False),
    Column("size_bytes", Integer, nullable=False),
    Column("status", _enum(DocumentStatus), nullable=False),
    Column("extracted", JSONB, nullable=False),
    Column("uploaded_at", _timestamp(), nullable=False),
)

contract_table = Table(
    "contract",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("offer_id", ForeignKey("offer.id"), nullable=False, unique=True),
    Column("amount", _money(), nullable=False),
    Column("term_months", SmallInteger, nullable=False),
    Column("rate", Numeric(5, 2), nullable=False),
    Column("monthly_payment", _money(), nullable=False),
    Column("created_at", _timestamp(), nullable=False),
    Column("signed_by", ForeignKey("representative.id")),
    Column("signed_at", _timestamp()),
    Column("sign_code_hash", String(64)),
    Column("sign_code_expires_at", _timestamp()),
)

disbursement_table = Table(
    "disbursement",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("contract_id", ForeignKey("contract.id"), nullable=False, unique=True),
    Column("amount", _money(), nullable=False),
    Column("account", String(20), nullable=False),
    Column("external_id", String(64), nullable=False),
    Column("at", _timestamp(), nullable=False),
)

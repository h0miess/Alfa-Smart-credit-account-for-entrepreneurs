from dataclasses import dataclass
from uuid import UUID

from application.interfaces.clock import Clock
from application.interfaces.storage import DocumentStorage
from application.interfaces.tasks import TaskQueue
from application.interfaces.uow import UnitOfWork
from application.use_cases.client.access import (
    get_own_application,
    get_representative,
)
from application.use_cases.client.card import ApplicationCard, load_card
from domain.entities.application_event import ActorType
from domain.entities.decision import Decision
from domain.entities.document import (
    DOCUMENT_REQUESTS,
    Document,
    DocumentDetails,
    DocumentRequest,
)
from domain.entities.loan_application import LoanApplication
from domain.exceptions.base import (
    BusinessRuleViolationError,
    ConflictError,
    NotFoundError,
)
from domain.statuses import ApplicationStatus


@dataclass(frozen=True, slots=True)
class UploadedFile:
    file_name: str
    content_type: str
    data: bytes


@dataclass(frozen=True, slots=True)
class DocumentContent:
    document: Document
    data: bytes


async def _requested(
    uow: UnitOfWork, application: LoanApplication
) -> tuple[Decision, list[DocumentRequest]]:
    if application.status is not ApplicationStatus.INFO_REQUESTED:
        raise ConflictError("Документы по заявке сейчас не запрошены")
    decision = await uow.decisions.latest_for_application(application.id)
    assert decision is not None
    return decision, [
        DOCUMENT_REQUESTS[item["reason_code"]]
        for item in decision.requested_documents
        if item["reason_code"] in DOCUMENT_REQUESTS
    ]


class UploadDocument:
    def __init__(self, uow: UnitOfWork, storage: DocumentStorage, clock: Clock) -> None:
        self._uow = uow
        self._storage = storage
        self._clock = clock

    async def __call__(
        self,
        user_id: UUID,
        application_id: UUID,
        reason_code: str,
        file: UploadedFile,
        details: DocumentDetails,
    ) -> Document:
        async with self._uow as uow:
            representative = await get_representative(uow, user_id)
            application = await get_own_application(
                uow, representative, application_id, for_update=True
            )
            _, requests = await _requested(uow, application)
            request = next((r for r in requests if r.reason_code == reason_code), None)
            if request is None:
                raise BusinessRuleViolationError(
                    "Этот документ по заявке не запрашивали"
                )

            now = self._clock.now()
            document = Document.accept(
                application_id=application.id,
                request=request,
                file_name=file.file_name,
                content_type=file.content_type,
                size_bytes=len(file.data),
                details=details,
                at=now,
            )
            if details.collateral_value and details.collateral_description:
                application.provide_collateral(
                    value=details.collateral_value,
                    description=details.collateral_description,
                    at=now,
                )
            await self._storage.put(document.file_ref, file.data, file.content_type)
            await uow.documents.add(document)
            await uow.commit()
            return document


class CompleteDocuments:
    def __init__(self, uow: UnitOfWork, clock: Clock, tasks: TaskQueue) -> None:
        self._uow = uow
        self._clock = clock
        self._tasks = tasks

    async def __call__(self, user_id: UUID, application_id: UUID) -> ApplicationCard:
        async with self._uow as uow:
            representative = await get_representative(uow, user_id)
            application = await get_own_application(
                uow, representative, application_id, for_update=True
            )
            if application.status is ApplicationStatus.CHECKING:
                return await load_card(uow, application)
            decision, requests = await _requested(uow, application)
            uploaded = {
                document.reason_code
                for document in await uow.documents.list_for_application(application.id)
                if document.uploaded_at >= decision.at
            }
            missing = [r.title for r in requests if r.reason_code not in uploaded]
            if missing:
                raise BusinessRuleViolationError(
                    "Не хватает документов: " + "; ".join(missing)
                )

            application.transition_to(
                ApplicationStatus.CHECKING,
                actor=ActorType.CLIENT,
                actor_id=user_id,
                at=self._clock.now(),
                comment="Клиент загрузил запрошенные документы",
            )
            await uow.commit()
            card = await load_card(uow, application)

        await self._tasks.enqueue_processing(application.id)
        return card


class ListDocuments:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def __call__(self, user_id: UUID, application_id: UUID) -> ApplicationCard:
        async with self._uow as uow:
            representative = await get_representative(uow, user_id)
            application = await get_own_application(uow, representative, application_id)
            return await load_card(uow, application)


class DownloadDocument:
    def __init__(self, uow: UnitOfWork, storage: DocumentStorage) -> None:
        self._uow = uow
        self._storage = storage

    async def for_client(
        self, user_id: UUID, application_id: UUID, document_id: UUID
    ) -> DocumentContent:
        async with self._uow as uow:
            representative = await get_representative(uow, user_id)
            application = await get_own_application(uow, representative, application_id)
            document = await self._document(uow, application.id, document_id)
        return DocumentContent(document, await self._storage.get(document.file_ref))

    async def for_underwriter(
        self, application_id: UUID, document_id: UUID
    ) -> DocumentContent:
        async with self._uow as uow:
            document = await self._document(uow, application_id, document_id)
        return DocumentContent(document, await self._storage.get(document.file_ref))

    async def _document(
        self, uow: UnitOfWork, application_id: UUID, document_id: UUID
    ) -> Document:
        document = await uow.documents.get(document_id)
        if document is None or document.application_id != application_id:
            raise NotFoundError("Документ не найден")
        return document

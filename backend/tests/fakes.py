from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from application.interfaces.auth import AuthService, UserInfo
from application.interfaces.scoring import ModelInfo, ScoringGateway
from application.interfaces.tasks import TaskQueue
from domain.entities.user import UserRole
from domain.products import Product, ProductCode

ML_PRODUCTS = (
    Product(
        code=ProductCode.EXPRESS,
        name="Экспресс-кредит на оборотные средства",
        min_amount=Decimal("100000"),
        max_amount=Decimal("10000000"),
        min_term=3,
        max_term=36,
        rate_adj=Decimal("0.0"),
        secured_from=None,
    ),
    Product(
        code=ProductCode.OVERDRAFT,
        name="Овердрафт к расчётному счёту",
        min_amount=Decimal("50000"),
        max_amount=Decimal("15000000"),
        min_term=12,
        max_term=12,
        rate_adj=Decimal("1.0"),
        secured_from=None,
    ),
    Product(
        code=ProductCode.INVESTMENT,
        name="Инвестиционный кредит",
        min_amount=Decimal("1000000"),
        max_amount=Decimal("100000000"),
        min_term=12,
        max_term=84,
        rate_adj=Decimal("-1.5"),
        secured_from=Decimal("5000000"),
    ),
)


class FakeScoringGateway(ScoringGateway):
    async def get_products(self) -> Sequence[Product]:
        return ML_PRODUCTS

    async def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            model_version="pd-smb-lgbm-test",
            policy_version="policy-test",
            key_rate=Decimal("16.0"),
        )


class FakeTaskQueue(TaskQueue):
    def __init__(self) -> None:
        self.processing: list[UUID] = []
        self.disbursements: list[UUID] = []

    async def enqueue_processing(self, application_id: UUID) -> None:
        self.processing.append(application_id)

    async def enqueue_disbursement(self, application_id: UUID) -> None:
        self.disbursements.append(application_id)


class FakeAuthService(AuthService):
    def __init__(self, user_id: UUID, role: UserRole) -> None:
        self._user_id = user_id
        self._role = role

    async def get_current_user_uuid(self) -> UUID:
        return self._user_id

    async def get_current_user_roles(self) -> frozenset[UserRole]:
        return frozenset({self._role})

    async def get_user_info(self) -> UserInfo:
        return UserInfo(
            uuid=self._user_id,
            username="test",
            first_name=None,
            last_name=None,
            email="test@example.com",
        )

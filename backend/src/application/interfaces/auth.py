from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from domain.entities.user import UserRole


@dataclass(frozen=True, slots=True)
class UserInfo:
    uuid: UUID
    username: str
    first_name: str | None
    last_name: str | None
    email: str


class AuthService(Protocol):
    async def get_current_user_uuid(self) -> UUID: ...

    async def get_current_user_roles(self) -> frozenset[UserRole]: ...

    async def get_user_info(self) -> UserInfo: ...

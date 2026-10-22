from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TokenContext:
    token: str
    payload: dict[str, Any]
    user_uuid: UUID
    roles: frozenset[str]


class TokenContextProcessor(Protocol):
    def get_user_uuid(self) -> UUID: ...

    def get_token_context(self) -> TokenContext: ...

    def verify(self, token: str) -> dict[str, Any]: ...

    def parse_user_uuid(self, uuid_: str | None) -> UUID: ...

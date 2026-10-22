import logging
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette import status

from application.exceptions.authorization import AuthorizationError
from domain.exceptions.base import (
    AccessDeniedError,
    BusinessRuleViolationError,
    ConflictError,
    NotFoundError,
)

logger = logging.getLogger(__name__)

_ERROR_STATUS_MAPPING: Final[Mapping[type[Exception], int]] = MappingProxyType(
    {
        # 401
        AuthorizationError: status.HTTP_401_UNAUTHORIZED,
        # 403
        AccessDeniedError: status.HTTP_403_FORBIDDEN,
        # 404
        NotFoundError: status.HTTP_404_NOT_FOUND,
        # 409
        ConflictError: status.HTTP_409_CONFLICT,
        # 422
        BusinessRuleViolationError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    }
)
_MSG_INTERNAL_SERVER_ERROR: Final[str] = "Internal server error"


@dataclass(frozen=True, slots=True)
class ExceptionSchema:
    details: str
    code: str | None = None


def setup_handlers(app: FastAPI) -> None:
    async def handle_exception(_: Request, exc: Exception) -> JSONResponse:
        status_code = resolve_status_code(exc)
        response = build_exception_response(exc, status_code)
        logger.error(str(exc))

        return JSONResponse(
            status_code=status_code,
            content=jsonable_encoder(response),
        )

    for exc_class in _ERROR_STATUS_MAPPING:
        app.add_exception_handler(exc_class, handle_exception)


def resolve_status_code(exc: Exception) -> int:
    for exc_type, status_code in _ERROR_STATUS_MAPPING.items():
        if isinstance(exc, exc_type):
            return status_code

    return _ERROR_STATUS_MAPPING.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


def build_exception_response(
    exc: Exception,
    status_code: int,
) -> ExceptionSchema:
    description = (
        str(exc)
        if status_code < status.HTTP_500_INTERNAL_SERVER_ERROR
        else _MSG_INTERNAL_SERVER_ERROR
    )
    code = getattr(exc, "code", None)
    return ExceptionSchema(details=description, code=code)

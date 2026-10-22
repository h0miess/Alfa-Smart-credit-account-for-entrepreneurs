from collections.abc import AsyncGenerator
from typing import Any

from fastapi import Request
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Mapper, Session

from core.configs.database import PostgresSettings, SQLEngineSettings


def create_engine(
    postgres_settings: PostgresSettings,
    sql_settings: SQLEngineSettings,
) -> AsyncEngine:
    return create_async_engine(
        url=postgres_settings.url,
        echo=sql_settings.ECHO,
        echo_pool=sql_settings.ECHO_POOL,
        pool_size=sql_settings.POOL_SIZE,
        max_overflow=sql_settings.MAX_OVERFLOW,
    )


def create_sessionmaker(
    async_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=async_engine,
        autoflush=False,
        expire_on_commit=False,
    )


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI-зависимость: сессия на один запрос из sessionmaker, созданного в lifespan."""
    sessionmaker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with sessionmaker() as session:
        try:
            yield session
        except SQLAlchemyError:
            await session.rollback()
            raise


# Сессия держит сильные ссылки на загруженные и добавленные объекты,
# чтобы они не пропадали из identity map, пока сессия жива
def _index_object(session: Session, instance: Any) -> None:
    set_ = session.info.get("strong_set", None)
    if not set_:
        session.info["strong_set"] = set_ = set()

    set_.add(instance)


@event.listens_for(Mapper, "load")
def object_loaded(instance: Any, ctx: Any) -> None:
    if getattr(ctx, "session", None) is not None:
        _index_object(ctx.session, instance)


@event.listens_for(Session, "after_attach")
def index_object(session: Session, instance: Any) -> None:
    _index_object(session, instance)

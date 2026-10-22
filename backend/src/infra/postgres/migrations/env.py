import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from core.configs import settings
from infra.postgres.models import metadata

config = context.config

if config.config_file_name and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    context.configure(
        url=settings.postgres.url.render_as_string(hide_password=False),
        target_metadata=metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(settings.postgres.url)

    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())

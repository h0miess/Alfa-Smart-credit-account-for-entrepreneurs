import asyncio
import logging

from core.configs import settings
from infra.postgres.database import create_engine, create_sessionmaker
from infra.postgres.mappings import start_mappers
from seed.loader import load_seed

logger = logging.getLogger("credit_cabinet.seed")


async def main() -> None:
    start_mappers()
    engine = create_engine(settings.postgres, settings.sql_engine)
    try:
        async with create_sessionmaker(engine)() as session:
            count = await load_seed(session, settings.seed.PATH)
    finally:
        await engine.dispose()
    logger.info("Seed загружен: компаний %s из %s", count, settings.seed.PATH)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    asyncio.run(main())

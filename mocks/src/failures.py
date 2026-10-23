import asyncio
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, status

from settings import settings


class Source(StrEnum):
    EGRUL = "egrul"
    FNS = "fns"
    BKI = "bki"
    ABS = "abs"
    ALL = "all"


class Mode(StrEnum):
    OFF = "off"
    ERROR = "error"
    TIMEOUT = "timeout"


_modes: dict[Source, Mode] = {}

router = APIRouter(prefix="/admin/failures", tags=["Режим отказов"])


async def simulate(source: Source) -> None:
    mode = _modes.get(source) or _modes.get(Source.ALL) or Mode.OFF
    if mode is Mode.ERROR:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"{source} временно недоступен (включён режим отказов)",
        )
    if mode is Mode.TIMEOUT:
        await asyncio.sleep(settings.TIMEOUT_DELAY_IN_SECONDS)


@router.get("")
async def get_modes() -> dict[Source, Mode]:
    return {source: _modes.get(source, Mode.OFF) for source in Source}


@router.put("/{source}")
async def set_mode(
    source: Source, mode: Annotated[Mode, Body(embed=True)]
) -> dict[Source, Mode]:
    if mode is Mode.OFF:
        _modes.pop(source, None)
    else:
        _modes[source] = mode
    return await get_modes()

from fastapi import APIRouter

from presentation.api.v1.routers.me import me_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(me_router, tags=["me"])

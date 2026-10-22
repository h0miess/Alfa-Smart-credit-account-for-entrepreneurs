from fastapi import APIRouter

from presentation.api.v1.routers.applications import applications_router
from presentation.api.v1.routers.catalog import catalog_router
from presentation.api.v1.routers.me import me_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(me_router, tags=["me"])
api_v1_router.include_router(catalog_router, tags=["catalog"])
api_v1_router.include_router(applications_router, tags=["applications"])

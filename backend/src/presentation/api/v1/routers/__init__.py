from fastapi import APIRouter

from presentation.api.v1.routers.applications import applications_router
from presentation.api.v1.routers.catalog import catalog_router
from presentation.api.v1.routers.documents import documents_router
from presentation.api.v1.routers.me import me_router
from presentation.api.v1.routers.offer import offer_router
from presentation.api.v1.routers.stream import stream_router
from presentation.api.v1.routers.underwriter import underwriter_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(me_router, tags=["me"])
api_v1_router.include_router(catalog_router, tags=["catalog"])
api_v1_router.include_router(applications_router, tags=["applications"])
api_v1_router.include_router(offer_router, tags=["offer"])
api_v1_router.include_router(stream_router, tags=["stream"])
api_v1_router.include_router(underwriter_router, tags=["underwriter"])
api_v1_router.include_router(documents_router, tags=["documents"])

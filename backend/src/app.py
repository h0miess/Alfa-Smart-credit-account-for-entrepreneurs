
from fastapi import FastAPI

VERSION = "0.1.0"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Умный кредитный кабинет предпринимателя",
        version=VERSION,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    return app

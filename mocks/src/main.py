from fastapi import FastAPI

import failures
from routes import router

app = FastAPI(
    title="Моки внешних систем кредитного конвейера",
    version="0.1.0",
    description="ЕГРЮЛ/ЕГРИП, ФНС, БКИ и АБС банка. Данные синтетические, по ИНН из seed.",
)

app.include_router(router)
app.include_router(failures.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

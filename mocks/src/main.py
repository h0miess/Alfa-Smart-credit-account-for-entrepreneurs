from fastapi import FastAPI

app = FastAPI(
    title="Моки внешних систем кредитного конвейера",
    version="0.1.0",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

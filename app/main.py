from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.settings import settings


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "status": "running",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }

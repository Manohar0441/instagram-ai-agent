from fastapi import APIRouter

from app.api.v1.endpoints import analytics, auth, instagram, users

api_router = APIRouter()
api_router.include_router(analytics.router)
api_router.include_router(auth.router)
api_router.include_router(instagram.router)
api_router.include_router(users.router)

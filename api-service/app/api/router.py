from fastapi import APIRouter

from app.api.routes import health, ready, tickets

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(ready.router)
api_router.include_router(tickets.router)

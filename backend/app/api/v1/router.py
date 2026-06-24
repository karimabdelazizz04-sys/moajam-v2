from fastapi import APIRouter

from app.api.v1 import accounting, auth, clients, invoices, portal, translations

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(clients.router)
api_router.include_router(invoices.router)
api_router.include_router(translations.router)
api_router.include_router(accounting.router)
api_router.include_router(portal.router)

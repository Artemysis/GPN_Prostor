from fastapi import APIRouter

from app.api.v1 import (
    admin,
    analytics,
    auth,
    calculations,
    chat,
    companies,
    contracts,
    documents,
    jobs,
    products,
    requests,
    search,
    tz,
    tz_templates,
)

api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(companies.router, tags=["companies"])
api_router.include_router(contracts.router, tags=["contracts"])
api_router.include_router(products.router, tags=["products"])
api_router.include_router(calculations.router, tags=["cost-calculations"])
api_router.include_router(tz_templates.router, tags=["tz-templates"])
api_router.include_router(requests.router, tags=["requests"])
api_router.include_router(tz.router, tags=["tz"])
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(documents.router, tags=["documents"])
api_router.include_router(search.router, tags=["search"])
api_router.include_router(analytics.router, tags=["analytics"])
api_router.include_router(admin.router, tags=["admin"])
api_router.include_router(jobs.router, tags=["jobs"])

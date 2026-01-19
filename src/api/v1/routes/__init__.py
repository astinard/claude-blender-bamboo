"""API v1 route modules."""

from src.api.v1.routes.auth import router as auth_router
from src.api.v1.routes.users import router as users_router
from src.api.v1.routes.organizations import router as organizations_router
from src.api.v1.routes.printers import router as printers_router
from src.api.v1.routes.jobs import router as jobs_router
from src.api.v1.routes.materials import router as materials_router
from src.api.v1.routes.models import router as models_router
from src.api.v1.routes.analytics import router as analytics_router

__all__ = [
    "auth_router",
    "users_router",
    "organizations_router",
    "printers_router",
    "jobs_router",
    "materials_router",
    "models_router",
    "analytics_router",
]

"""FastAPI application entry point."""

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from newton.core.config import get_settings
from newton.core.db import get_db
from newton.domains.audit.router import router as audit_router
from newton.domains.auth.router import router as auth_router
from newton.domains.company.router import router as company_router
from newton.domains.users.router import router as users_router

CSRF_HEADER = "x-newton-csrf"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

settings = get_settings()
is_prod = settings.newton_env == "production"

app = FastAPI(
    title="NEWTON API",
    version="0.1.0",
    docs_url=None if is_prod else "/api/docs",
    redoc_url=None,
    openapi_url=None if is_prod else "/api/openapi.json",
)


@app.middleware("http")
async def csrf_and_security_headers(request: Request, call_next):
    # Auth cookies are SameSite=Strict. As a second layer, every state-changing request
    # must carry a custom header, which a cross-site HTML form cannot set.
    if (
        request.method in UNSAFE_METHODS
        and request.url.path.startswith("/api/")
        and request.headers.get(CSRF_HEADER) != "1"
    ):
        return JSONResponse(
            status_code=403,
            content={"detail": {"code": "csrf", "message": "Requête refusée (CSRF)."}},
        )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health", tags=["health"])
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "env": settings.newton_env}


app.include_router(auth_router)
app.include_router(company_router)
app.include_router(users_router)
app.include_router(audit_router)

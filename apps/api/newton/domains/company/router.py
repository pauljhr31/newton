"""Current company (tenant) profile."""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from newton.core import audit
from newton.core.context import RequestContext, get_context, require_role
from newton.core.db import get_db
from newton.core.errors import api_error
from newton.core.models import Company

router = APIRouter(prefix="/api/company", tags=["company"])


class CompanyOut(BaseModel):
    id: UUID
    name: str
    siret: str | None
    is_demo: bool


class CompanyUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    siret: str | None = Field(default=None, pattern=r"^[0-9]{14}$")


def _load(db: Session, company_id: UUID) -> Company:
    company = db.execute(select(Company).where(Company.id == company_id)).scalar_one_or_none()
    if company is None:
        raise api_error(404, "not_found", "Entreprise introuvable.")
    return company


def _out(c: Company) -> CompanyOut:
    return CompanyOut(id=c.id, name=c.name, siret=c.siret, is_demo=c.is_demo)


@router.get("", response_model=CompanyOut)
def get_company(ctx: RequestContext = Depends(get_context), db: Session = Depends(get_db)):
    return _out(_load(db, ctx.company_id))


@router.patch("", response_model=CompanyOut)
def update_company(
    body: CompanyUpdateIn,
    ctx: RequestContext = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    before = _out(_load(db, ctx.company_id))
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is not None:
        changes["name"] = changes["name"].strip()
        if not changes["name"]:
            raise api_error(400, "invalid_name", "Le nom ne peut pas être vide.")
    if not changes:
        return before
    db.execute(update(Company).where(Company.id == ctx.company_id).values(**changes))
    db.expire_all()
    after = _out(_load(db, ctx.company_id))
    audit.record(
        db,
        company_id=ctx.company_id,
        action="company.updated",
        entity_type="company",
        entity_id=ctx.company_id,
        actor_user_id=ctx.user_id,
        before=before.model_dump(mode="json"),
        after=after.model_dump(mode="json"),
        ip=ctx.ip,
    )
    return after

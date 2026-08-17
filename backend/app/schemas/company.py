from pydantic import BaseModel, ConfigDict

from app.schemas.contract import ContractOut


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    company_id: str
    name: str
    info: str | None = None
    services: str | None = None
    rating: int | None = None


class CompanyDetailOut(CompanyOut):
    contracts: list[ContractOut] = []

from pydantic import BaseModel, ConfigDict


class ContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    contract_id: str
    contract_number: str
    company_id: str

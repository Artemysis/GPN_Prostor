from datetime import date

from pydantic import BaseModel, ConfigDict


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: str
    product_name: str


class ProductRateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    price_id: str
    price_name: str
    measurement_name: str | None = None
    measurement_type: str | None = None


class ProductOperationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    operation_id: str
    operation_name: str
    operation_order: int | None = None


class CostCalculationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    calc_id: str
    calc_name: str
    calc_start_date: date | None = None
    calc_end_date: date | None = None
    product_id: str | None = None


class CalculationStageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stage_id: str
    stage_name: str
    parent_stage_id: str | None = None
    stage_order_num: int | None = None
    stage_start_date: date | None = None
    stage_end_date: date | None = None
    stage_documentation_list: str | None = None

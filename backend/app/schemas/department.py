from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DepartmentBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    code: str = Field(..., min_length=2, max_length=50)
    description: str | None = Field(default=None, max_length=1000)


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(DepartmentBase):
    is_active: bool = True


class DepartmentOut(DepartmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

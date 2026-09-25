import uuid
from pydantic import BaseModel


class DepartmentRequest(BaseModel):
    name: str


class DepartmentResponse(BaseModel):
    id: uuid.UUID
    name: str

    class Config:
        from_attributes = True


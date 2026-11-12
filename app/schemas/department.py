
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

OrganisationType = Literal[
    "red_ant",
    "bella_organics",
    "juakali",
]


class DepartmentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    organisation: OrganisationType


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    organisation: OrganisationType

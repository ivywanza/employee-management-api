import uuid

from sqlalchemy import Column, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Department(Base):
    __tablename__ = "departments"

    __table_args__ = (
        UniqueConstraint(
            "name",
            "organisation",
            name="uq_department_name_organisation",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    organisation = Column(
        String(50),
        nullable=False,
        default="red_ant",
        server_default="red_ant",
    )

    employees = relationship("User", back_populates="department")
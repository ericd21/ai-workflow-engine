from enum import Enum

from pydantic import BaseModel, EmailStr, Field, model_validator


class Department(str, Enum):
    support = "support"
    billing = "billing"
    sales = "sales"
    other = "other"


class IntakeRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(
        None,
        min_length=7,
        max_length=20,
        description="Digits or E.164 format",
    )
    department: Department
    message: str = Field(..., min_length=10, max_length=5000)

    @model_validator(mode="after")
    def validate_contact_method(self) -> "IntakeRequest":
        if not self.email and not self.phone:
            raise ValueError("Either email or phone must be provided.")
        return self

from pydantic import BaseModel, EmailStr, Field, root_validator
from typing import Optional
from enum import Enum


class Department(str, Enum):
    support = "support"
    billing = "billing"
    sales = "sales"
    other = "other"

class IntakeRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(
        None,
        min_length=7,
        max_length=20,
        description="Digits or E.164 format"
    )
    department: Department
    message: str = Field(..., min_length=10, max_length=5000)
    
    @root_validator
    def validate_contact_method(cls, values):
        email = values.get("email")
        phone = values.get("phone")

        if not email and not phone:
            raise ValueError("Either email or phone must be provided.")

        return values

"""Pydantic DTOs for /account endpoints (request/response boundary models)."""

from pydantic import BaseModel, EmailStr, Field

from app.domains import models as dm


class SignUpRequestDTO(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, examples=["StrongPass123"])

    def to_entity(self) -> dm.SignUpData:
        return dm.SignUpData(email=str(self.email), password=self.password)


class SignInRequestDTO(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, examples=["StrongPass123"])

    def to_entity(self) -> dm.SignInRequest:
        return dm.SignInRequest(email=str(self.email), password=self.password)

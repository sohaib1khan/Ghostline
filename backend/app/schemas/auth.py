"""Request and response models for setup and auth."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _clean_name(value: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValueError("Name is required")
    return cleaned


class SetupStatusOut(BaseModel):
    setup_required: bool


class SetupIn(BaseModel):
    setup_token: str = Field(min_length=20, max_length=200)
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(min_length=12, max_length=200)

    @field_validator("first_name", "last_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _clean_name(value)

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return value.strip().lower()


class LoginIn(BaseModel):
    # A plain string, not EmailStr. A malformed address gets the same response
    # as a wrong password, so the body does not reveal whether an account exists.
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class SignupIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(min_length=12, max_length=200)

    @field_validator("first_name", "last_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _clean_name(value)

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return value.strip().lower()


class SignupOut(BaseModel):
    message: str


class ProfileIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    public_alias: str = Field(min_length=2, max_length=40)

    @field_validator("first_name", "last_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _clean_name(value)

    @field_validator("public_alias")
    @classmethod
    def clean_alias(cls, value: str) -> str:
        from app.services.aliases import clean_alias

        return clean_alias(value)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=12, max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    first_name: str
    last_name: str
    public_alias: str
    role: str
    status: str

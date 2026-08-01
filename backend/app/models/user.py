"""
Pydantic schemas for User entity, registration, authentication, tokens, and OTP flows.
"""

from typing import Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserCreate(BaseModel):
    """Schema for registering a new primary user."""

    full_name: str = Field(..., min_length=1, max_length=100, description="Full legal name")
    date_of_birth: str = Field(..., description="Date of birth in YYYY-MM-DD format")
    email: EmailStr | None = Field(default=None, description="User email address")
    phone_number: str | None = Field(default=None, description="User phone number")
    password: str = Field(..., min_length=8, description="Plaintext password (min 8 chars)")
    preferred_language: str = Field(default="en", description="ISO language code, e.g. 'en', 'es'")
    large_text_mode: bool = Field(default=False, description="Accessibility preference")

    @model_validator(mode="after")
    def validate_contact_info(self) -> Self:
        """Ensure either email or phone_number is provided."""
        if not self.email and not self.phone_number:
            raise ValueError("Either email or phone_number must be provided for registration")
        return self


class UserRead(BaseModel):
    """Public User representation (never exposes password_hash)."""

    user_id: str
    full_name: str
    date_of_birth: str
    email: str | None = None
    phone_number: str | None = None
    preferred_language: str = "en"
    large_text_mode: bool = False
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    """Schema for password-based login."""

    email_or_phone: str = Field(..., description="User email address or phone number")
    password: str = Field(..., description="Plaintext password")


class TokenPair(BaseModel):
    """JWT Access and Refresh Token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Schema for refreshing an access token using a refresh token."""

    refresh_token: str = Field(..., description="Valid JWT refresh token")


class OTPRequest(BaseModel):
    """Schema for requesting a 6-digit OTP code."""

    email_or_phone: str = Field(..., description="Registered email or phone number")


class OTPVerify(BaseModel):
    """Schema for verifying a 6-digit OTP code."""

    email_or_phone: str = Field(..., description="Registered email or phone number")
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit numeric OTP code")


class OTPResponse(BaseModel):
    """Response returned when an OTP is requested."""

    message: str
    otp_dev: str | None = Field(default=None, description="Raw OTP returned ONLY when ENV=dev for testing")

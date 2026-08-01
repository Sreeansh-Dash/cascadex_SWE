"""
Pydantic schemas and enums for Caregiver entities and RBAC permission linkage.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class PermissionLevel(str, Enum):
    """Server-enforced permission levels for linked caregivers."""

    VIEW_ONLY = "view_only"
    MANAGE = "manage"


class CaregiverLinkRequest(BaseModel):
    """Schema for linking a caregiver to a primary user account."""

    caregiver_email_or_phone: str = Field(..., description="Caregiver's email or phone number")
    permission_level: PermissionLevel = Field(..., description="Access level granted to caregiver ('view_only' or 'manage')")
    relationship_to_user: str | None = Field(default=None, description="e.g. 'Daughter', 'Nurse', 'Son'")


class CaregiverRead(BaseModel):
    """Schema representing a linked caregiver."""

    caregiver_id: str
    full_name: str
    email: str | None = None
    phone_number: str | None = None
    permission_level: PermissionLevel
    relationship_to_user: str | None = None
    linked_at: str

    model_config = ConfigDict(from_attributes=True)

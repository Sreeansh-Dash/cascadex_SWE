"""
Authentication & User Management API Router.
"""

from fastapi import APIRouter, Depends, Request, status
from neo4j import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.neo4j_session import get_session
from app.models.caregiver import CaregiverLinkRequest, CaregiverRead
from app.models.user import (
    LoginRequest,
    OTPRequest,
    OTPResponse,
    OTPVerify,
    RefreshTokenRequest,
    TokenPair,
    UserCreate,
    UserRead,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a primary user",
)
@limiter.limit(lambda: settings.rate_limit_register)
async def register(
    request: Request,
    user_data: UserCreate,
    session: AsyncSession = Depends(get_session),
) -> UserRead:
    """Register a new primary user.

    Requires full name, date of birth, password, and at least one contact method (email or phone).
    """
    return await auth_service.register_user(user_data, session)


@router.post(
    "/login",
    response_model=TokenPair,
    status_code=status.HTTP_200_OK,
    summary="Authenticate with email/phone and password",
)
@limiter.limit(lambda: settings.rate_limit_login)
async def login(
    request: Request,
    credentials: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenPair:
    """Log in with password and receive an access/refresh JWT pair."""
    account_node, role = await auth_service.authenticate_user(credentials, session)
    account_id = account_node["user_id"] if role == "user" else account_node["caregiver_id"]
    token_version = account_node.get("token_version", 1)
    return await auth_service.issue_tokens_for_account(
        account_id=account_id,
        role=role,
        token_version=token_version,
    )


@router.post(
    "/refresh",
    response_model=TokenPair,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token with refresh token rotation",
)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenPair:
    """Exchange a valid refresh token for a new access and refresh token pair."""
    return await auth_service.refresh_tokens(refresh_data.refresh_token, session)


@router.post(
    "/otp/request",
    response_model=OTPResponse,
    status_code=status.HTTP_200_OK,
    summary="Request a 6-digit OTP code",
)
@limiter.limit(lambda: settings.rate_limit_login)
async def request_otp_code(
    request: Request,
    otp_req: OTPRequest,
    session: AsyncSession = Depends(get_session),
) -> OTPResponse:
    """Generate a 6-digit OTP code for a user."""
    return await auth_service.request_otp(otp_req.email_or_phone, session)


@router.post(
    "/otp/verify",
    response_model=TokenPair,
    status_code=status.HTTP_200_OK,
    summary="Verify OTP and obtain JWT pair",
)
async def verify_otp_code(
    verify_data: OTPVerify,
    session: AsyncSession = Depends(get_session),
) -> TokenPair:
    """Verify a 6-digit OTP code and obtain authentication tokens."""
    return await auth_service.verify_otp(verify_data.email_or_phone, verify_data.otp, session)


@router.post(
    "/caregivers/link",
    response_model=CaregiverRead,
    status_code=status.HTTP_201_CREATED,
    summary="Link a caregiver to the authenticated user",
)
async def link_caregiver_account(
    request: CaregiverLinkRequest,
    current_auth: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CaregiverRead:
    """Link a caregiver account to the authenticated primary user with a specified permission level."""
    user_id = current_auth["account_id"]
    return await auth_service.link_caregiver(user_id, request, session)


@router.get(
    "/caregivers",
    response_model=list[CaregiverRead],
    status_code=status.HTTP_200_OK,
    summary="List all linked caregivers for the authenticated user",
)
async def list_caregivers(
    current_auth: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CaregiverRead]:
    """List all caregivers currently linked to the authenticated primary user."""
    user_id = current_auth["account_id"]
    return await auth_service.get_user_caregivers(user_id, session)

"""
Authentication, user registration, token management, and caregiver linking service.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from neo4j import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_otp,
    hash_otp,
    hash_password,
    verify_password,
)
from app.core.security import (
    verify_otp as check_otp,
)
from app.models.caregiver import CaregiverLinkRequest, CaregiverRead, PermissionLevel
from app.models.user import (
    LoginRequest,
    OTPResponse,
    TokenPair,
    UserCreate,
    UserRead,
)

logger = logging.getLogger(__name__)


async def register_user(data: UserCreate, session: AsyncSession) -> UserRead:
    """Register a new primary user.

    Raises:
        HTTPException(400): If email or phone is already registered.
    """
    check_query = """
    MATCH (u:User)
    WHERE ($email IS NOT NULL AND u.email = $email)
       OR ($phone IS NOT NULL AND u.phone_number = $phone)
    RETURN u.email AS email, u.phone_number AS phone_number
    """
    res = await session.run(
        check_query,
        {"email": data.email, "phone": data.phone_number},
    )
    existing = await res.single()
    if existing:
        if data.email and existing.get("email") == data.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "email_already_registered", "message": "Email is already registered"},
            )
        if data.phone_number and existing.get("phone_number") == data.phone_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "phone_already_registered", "message": "Phone number is already registered"},
            )

    user_id = f"usr_{uuid.uuid4().hex[:12]}"
    pw_hash = hash_password(data.password)
    now_iso = datetime.now(UTC).isoformat()

    create_query = """
    CREATE (u:User {
        user_id: $user_id,
        full_name: $full_name,
        date_of_birth: $date_of_birth,
        email: $email,
        phone_number: $phone_number,
        password_hash: $password_hash,
        preferred_language: $preferred_language,
        large_text_mode: $large_text_mode,
        token_version: 1,
        created_at: $created_at
    })
    RETURN u
    """
    res = await session.run(
        create_query,
        {
            "user_id": user_id,
            "full_name": data.full_name,
            "date_of_birth": data.date_of_birth,
            "email": data.email,
            "phone_number": data.phone_number,
            "password_hash": pw_hash,
            "preferred_language": data.preferred_language,
            "large_text_mode": data.large_text_mode,
            "created_at": now_iso,
        },
    )
    record = await res.single()
    u_node = record["u"]

    return UserRead(
        user_id=u_node["user_id"],
        full_name=u_node["full_name"],
        date_of_birth=u_node["date_of_birth"],
        email=u_node.get("email"),
        phone_number=u_node.get("phone_number"),
        preferred_language=u_node.get("preferred_language", "en"),
        large_text_mode=u_node.get("large_text_mode", False),
        created_at=u_node["created_at"],
    )


async def authenticate_user(login_data: LoginRequest, session: AsyncSession) -> tuple[dict, str]:
    """Authenticate a user by email/phone and password."""
    query_user = """
    MATCH (u:User)
    WHERE u.email = $identifier OR u.phone_number = $identifier
    RETURN u, "user" AS role
    """
    res = await session.run(query_user, {"identifier": login_data.email_or_phone})
    record = await res.single()

    if not record:
        query_cg = """
        MATCH (c:Caregiver)
        WHERE c.email = $identifier OR c.phone_number = $identifier
        RETURN c AS u, "caregiver" AS role
        """
        res = await session.run(query_cg, {"identifier": login_data.email_or_phone})
        record = await res.single()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": "Invalid email/phone or password"},
        )

    node = dict(record["u"])
    role = record["role"]
    pw_hash = node.get("password_hash")

    if not pw_hash or not verify_password(login_data.password, pw_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": "Invalid email/phone or password"},
        )

    return node, role


async def issue_tokens_for_account(
    account_id: str,
    role: str = "user",
    token_version: int = 1,
) -> TokenPair:
    """Issue JWT access and refresh token pair."""
    token_payload = {
        "sub": account_id,
        "role": role,
        "token_version": token_version,
    }
    access_token = create_access_token(token_payload)
    refresh_token = create_refresh_token(token_payload)
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


async def refresh_tokens(refresh_token_str: str, session: AsyncSession) -> TokenPair:
    """Rotate refresh token and issue new token pair."""
    payload = decode_token(refresh_token_str)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "Token is not a refresh token"},
        )

    account_id = payload.get("sub")
    role = payload.get("role", "user")
    token_version = payload.get("token_version", 1)

    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "Token payload missing subject"},
        )

    label = "User" if role == "user" else "Caregiver"
    id_field = "user_id" if role == "user" else "caregiver_id"

    query = f"""
    MATCH (n:{label} {{{id_field}: $account_id}})
    RETURN n.token_version AS current_version
    """
    res = await session.run(query, {"account_id": account_id})
    record = await res.single()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "user_not_found", "message": "Account associated with token no longer exists"},
        )

    current_version = record.get("current_version", 1)
    if token_version != current_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "token_revoked", "message": "Refresh token has been revoked or already used"},
        )

    new_version = current_version + 1
    update_query = f"""
    MATCH (n:{label} {{{id_field}: $account_id}})
    SET n.token_version = $new_version
    """
    await session.run(update_query, {"account_id": account_id, "new_version": new_version})

    return await issue_tokens_for_account(account_id=account_id, role=role, token_version=new_version)


async def request_otp(email_or_phone: str, session: AsyncSession) -> OTPResponse:
    """Generate and store OTP for user."""
    query = """
    MATCH (u:User)
    WHERE u.email = $identifier OR u.phone_number = $identifier
    RETURN u.user_id AS user_id
    """
    res = await session.run(query, {"identifier": email_or_phone})
    record = await res.single()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "user_not_found", "message": "No account found with provided email or phone"},
        )

    user_id = record["user_id"]
    raw_otp = generate_otp()
    hashed = hash_otp(raw_otp)
    expires_at = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()

    update_query = """
    MATCH (u:User {user_id: $user_id})
    SET u.otp_hash = $otp_hash, u.otp_expires_at = $expires_at
    """
    await session.run(update_query, {"user_id": user_id, "otp_hash": hashed, "expires_at": expires_at})

    otp_dev = raw_otp if settings.is_dev else None
    return OTPResponse(
        message="OTP sent successfully",
        otp_dev=otp_dev,
    )


async def verify_otp(email_or_phone: str, otp: str, session: AsyncSession) -> TokenPair:
    """Verify OTP and return authentication tokens."""
    query = """
    MATCH (u:User)
    WHERE u.email = $identifier OR u.phone_number = $identifier
    RETURN u
    """
    res = await session.run(query, {"identifier": email_or_phone})
    record = await res.single()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "user_not_found", "message": "No account found with provided email or phone"},
        )

    u_node = record["u"]
    stored_hash = u_node.get("otp_hash")
    expires_at_str = u_node.get("otp_expires_at")

    if not stored_hash or not expires_at_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "otp_not_requested", "message": "No OTP request pending for this account"},
        )

    expires_at = datetime.fromisoformat(expires_at_str)
    if datetime.now(UTC) > expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "otp_expired", "message": "OTP has expired. Please request a new code"},
        )

    if not check_otp(otp, stored_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_otp", "message": "Invalid OTP code"},
        )

    clear_query = """
    MATCH (u:User {user_id: $user_id})
    SET u.otp_hash = null, u.otp_expires_at = null
    """
    await session.run(clear_query, {"user_id": u_node["user_id"]})

    return await issue_tokens_for_account(
        account_id=u_node["user_id"],
        role="user",
        token_version=u_node.get("token_version", 1),
    )


async def link_caregiver(
    primary_user_id: str,
    request: CaregiverLinkRequest,
    session: AsyncSession,
) -> CaregiverRead:
    """Link a caregiver account to a primary user."""
    user_res = await session.run("MATCH (u:User {user_id: $uid}) RETURN u", {"uid": primary_user_id})
    if not await user_res.single():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "user_not_found", "message": "Primary user not found"},
        )

    identifier = request.caregiver_email_or_phone
    is_email = "@" in identifier

    find_cg_query = """
    MATCH (c:Caregiver)
    WHERE c.email = $id OR c.phone_number = $id
    RETURN c
    """
    cg_res = await session.run(find_cg_query, {"id": identifier})
    cg_record = await cg_res.single()

    now_iso = datetime.now(UTC).isoformat()

    if cg_record:
        cg_node = cg_record["c"]
        caregiver_id = cg_node["caregiver_id"]
    else:
        caregiver_id = f"cg_{uuid.uuid4().hex[:12]}"
        email_val = identifier if is_email else None
        phone_val = identifier if not is_email else None
        full_name_val = identifier

        create_cg_query = """
        CREATE (c:Caregiver {
            caregiver_id: $caregiver_id,
            full_name: $full_name,
            email: $email,
            phone_number: $phone_number,
            token_version: 1,
            created_at: $created_at
        })
        RETURN c
        """
        cg_res = await session.run(
            create_cg_query,
            {
                "caregiver_id": caregiver_id,
                "full_name": full_name_val,
                "email": email_val,
                "phone_number": phone_val,
                "created_at": now_iso,
            },
        )
        cg_node = (await cg_res.single())["c"]

    link_id = f"link_{uuid.uuid4().hex[:12]}"
    link_query = """
    MATCH (u:User {user_id: $user_id})
    MATCH (c:Caregiver {caregiver_id: $caregiver_id})
    MERGE (c)-[r:CARE_GIVER_FOR]->(u)
    SET r.link_id = $link_id,
        r.permission_level = $permission_level,
        r.relationship_to_user = $relationship_to_user,
        r.linked_at = $linked_at
    RETURN c, r
    """
    res = await session.run(
        link_query,
        {
            "user_id": primary_user_id,
            "caregiver_id": caregiver_id,
            "link_id": link_id,
            "permission_level": request.permission_level.value,
            "relationship_to_user": request.relationship_to_user,
            "linked_at": now_iso,
        },
    )
    rec = await res.single()
    c_out = rec["c"]
    r_out = rec["r"]

    return CaregiverRead(
        caregiver_id=c_out["caregiver_id"],
        full_name=c_out.get("full_name", identifier),
        email=c_out.get("email"),
        phone_number=c_out.get("phone_number"),
        permission_level=PermissionLevel(r_out["permission_level"]),
        relationship_to_user=r_out.get("relationship_to_user"),
        linked_at=r_out["linked_at"],
    )


async def get_user_caregivers(primary_user_id: str, session: AsyncSession) -> list[CaregiverRead]:
    """List all caregivers linked to a primary user."""
    query = """
    MATCH (c:Caregiver)-[r:CARE_GIVER_FOR]->(u:User {user_id: $user_id})
    RETURN c, r
    """
    res = await session.run(query, {"user_id": primary_user_id})
    records = await res.data()

    caregivers = []
    for row in records:
        c_node = row["c"]
        r_rel = row["r"]
        caregivers.append(
            CaregiverRead(
                caregiver_id=c_node["caregiver_id"],
                full_name=c_node.get("full_name", "Caregiver"),
                email=c_node.get("email"),
                phone_number=c_node.get("phone_number"),
                permission_level=PermissionLevel(r_rel["permission_level"]),
                relationship_to_user=r_rel.get("relationship_to_user"),
                linked_at=r_rel["linked_at"],
            )
        )
    return caregivers

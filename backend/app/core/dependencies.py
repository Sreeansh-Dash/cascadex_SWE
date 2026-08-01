"""
CascadeX FastAPI dependency injection — Authentication & RBAC enforcement.
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from neo4j import AsyncSession

from app.core.security import decode_token
from app.db.neo4j_session import get_session
from app.models.caregiver import PermissionLevel

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    x_caregiver_target_user: Annotated[str | None, Header(alias="X-Caregiver-Target-User")] = None,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Extract and validate the current authenticated user/caregiver from JWT.

    Returns:
        dict: Auth context `{"account_id": str, "role": str, "permission_level": PermissionLevel | None, "target_user_id": str}`.

    Raises:
        HTTPException(401): If token is missing, invalid, or revoked.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "authentication_required", "message": "Bearer authorization token missing"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(token)
    account_id = payload.get("sub")
    role = payload.get("role", "user")
    token_version = payload.get("token_version", 1)

    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "Token payload missing subject"},
        )

    # Check database to ensure account exists and token_version matches
    label = "User" if role == "user" else "Caregiver"
    id_field = "user_id" if role == "user" else "caregiver_id"

    query = f"""
    MATCH (n:{label} {{{id_field}: $account_id}})
    RETURN n.token_version AS version
    """
    res = await session.run(query, {"account_id": account_id})
    record = await res.single()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "user_not_found", "message": "Account associated with token no longer exists"},
        )

    db_version = record.get("version", 1)
    if token_version != db_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "token_revoked", "message": "Token has been revoked"},
        )

    auth_context = {
        "account_id": account_id,
        "user_id": account_id if role == "user" else x_caregiver_target_user,
        "role": role,
        "permission_level": None,
    }

    # If caregiver acting on behalf of a primary user, check link permission level
    if role == "caregiver" and x_caregiver_target_user:
        perm_query = """
        MATCH (c:Caregiver {caregiver_id: $cg_id})-[r:CARE_GIVER_FOR]->(u:User {user_id: $target_id})
        RETURN r.permission_level AS perm
        """
        perm_res = await session.run(perm_query, {"cg_id": account_id, "target_id": x_caregiver_target_user})
        perm_rec = await perm_res.single()
        if not perm_rec:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "permission_denied", "message": "Caregiver is not linked to the specified target user"},
            )
        auth_context["permission_level"] = PermissionLevel(perm_rec["perm"])

    return auth_context


def require_permission(required_level: PermissionLevel):
    """Factory dependency enforcing server-side authorization (RBAC).

    Primary users automatically pass. Caregivers are validated against their
    linked permission level (`view_only` vs `manage`).
    """

    async def _dependency(auth_context: dict = Depends(get_current_user)) -> dict:
        role = auth_context.get("role")
        if role == "user":
            return auth_context

        if role == "caregiver":
            perm = auth_context.get("permission_level")
            # If required level is MANAGE and caregiver is VIEW_ONLY, reject 403
            if required_level == PermissionLevel.MANAGE and perm == PermissionLevel.VIEW_ONLY:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "permission_denied",
                        "message": "Caregiver with view_only permission cannot perform write or manage operations",
                    },
                )
            return auth_context

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "permission_denied", "message": "Invalid auth role"},
        )

    return _dependency

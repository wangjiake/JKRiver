"""FastAPI auth dependencies — admin gate for system / family management endpoints."""

from fastapi import HTTPException, Request

from agent.core.identity import DEFAULT_OWNER_ID, is_admin


def require_admin(request: Request) -> int:
    """Block non-admin owners from system config / family management endpoints.

    Returns the admin owner_id on success; raises 403 otherwise.
    """
    owner_id = getattr(request.state, "owner_id", DEFAULT_OWNER_ID)
    if not is_admin(owner_id):
        raise HTTPException(
            status_code=403,
            detail="Admin only. This endpoint is restricted to the primary family account.",
        )
    return owner_id

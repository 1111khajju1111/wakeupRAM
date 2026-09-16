import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import TokenPayloadError, create_access_token, decode_token
from app.database.session import get_db
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPair
from app.schemas.user import UserCreate, UserRead
from app.services import audit_service, auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, request: Request, db: Session = Depends(get_db)) -> UserRead:
    try:
        user = auth_service.register_user(db, payload.email, payload.password)
    except auth_service.AuthError as exc:
        audit_service.record_event(
            db, "register", status="failure", ip_address=request.client.host if request.client else None
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    audit_service.record_event(
        db, "register", user_id=user.id, ip_address=request.client.host if request.client else None
    )
    return user


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenPair:
    client_ip = request.client.host if request.client else None
    try:
        user = auth_service.authenticate_user(db, payload.email, payload.password)
    except auth_service.AuthError as exc:
        # Never record which part failed (unknown email vs. wrong password) —
        # that distinction is exactly the kind of detail that helps an
        # attacker enumerate valid accounts.
        audit_service.record_event(db, "login", status="failure", ip_address=client_ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    access_token, refresh_token = auth_service.issue_token_pair(user)
    audit_service.record_event(db, "login", user_id=user.id, ip_address=client_ip)
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)) -> TokenPair:
    client_ip = request.client.host if request.client else None
    try:
        token_payload = decode_token(payload.refresh_token, expected_type="refresh")
    except TokenPayloadError as exc:
        audit_service.record_event(db, "token_refresh", status="failure", ip_address=client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token"
        ) from exc

    # Note: full production hardening should also add refresh-token rotation
    # and a revocation list so a stolen refresh token can be invalidated
    # server-side before its natural expiry — tracked as a follow-up, not
    # done in this pass (see README).
    new_access_token = create_access_token(subject=token_payload["sub"])
    audit_service.record_event(
        db, "token_refresh", user_id=uuid.UUID(token_payload["sub"]), ip_address=client_ip
    )
    return TokenPair(access_token=new_access_token, refresh_token=payload.refresh_token)

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.auth.dependencies import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.auth.security import verify_password, create_access_token
from app.auth.dependencies import require_roles


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Authenticate a user and return a JWT access token."""

    user = db.query(User).filter(
        User.email == form_data.username
    ).first()

    if (
        user is None
        or not verify_password(
            form_data.password,
            user.password_hash
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive."
        )

    access_token = create_access_token(
        user_id=user.user_id,
        role=user.role
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }
@router.get("/me")
def get_my_account(
    current_user: User = Depends(get_current_user)
):
    """Return the currently authenticated user's information."""

    return {
        "user_id": current_user.user_id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active
    }

@router.get("/admin-test")
def admin_test(
    current_user: User = Depends(require_roles("ADMIN"))
):
    return {
        "message": "Admin access verified successfully.",
        "user": current_user.name,
        "role": current_user.role
    }


@router.get("/manager-test")
def manager_test(
    current_user: User = Depends(require_roles("MANAGER"))
):
    return {
        "message": "Manager access verified successfully.",
        "user": current_user.name,
        "role": current_user.role
    }
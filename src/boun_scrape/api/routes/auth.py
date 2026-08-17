"""Authentication endpoints: login and current-session identity."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from boun_scrape.api.auth import create_jwt_token, get_current_user, verify_password
from boun_scrape.api.deps import get_settings_dep
from boun_scrape.api.rate_limit import login_rate_limit_dep
from boun_scrape.config import Settings

router = APIRouter(prefix="/auth", tags=["Auth"])


class Token(BaseModel):
    access_token: str
    token_type: str


class UserInfo(BaseModel):
    username: str


@router.post("/login", response_model=Token, dependencies=[Depends(login_rate_limit_dep)])
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    settings: Settings = Depends(get_settings_dep),
):
    input_user = (form_data.username or "").strip()
    input_pwd = (form_data.password or "").strip()

    if input_user.lower() != settings.admin_user.lower() or not verify_password(input_pwd, settings.admin_password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_jwt_token({"sub": settings.admin_user}, settings.jwt_secret_key)
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserInfo)
async def get_me(current_user: str = Depends(get_current_user)):
    return {"username": current_user}

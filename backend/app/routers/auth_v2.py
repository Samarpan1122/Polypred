from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from app.services.cognito_service import cognito_service

router = APIRouter(prefix="/api/auth", tags=["auth"])

class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    name: str = "Researcher"
    affiliation: str = "TBA"

class SignInRequest(BaseModel):
    email: EmailStr
    password: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str

class ConfirmSignUpRequest(BaseModel):
    email: EmailStr
    code: str

@router.post("/signup")
def signup(request: SignUpRequest):
    return cognito_service.sign_up(
        email=request.email,
        password=request.password,
        name=request.name,
        affiliation=request.affiliation
    )

@router.post("/login")
def login(request: SignInRequest):
    return cognito_service.sign_in(email=request.email, password=request.password)

@router.post("/confirm-signup")
def confirm_signup(request: ConfirmSignUpRequest):
    return cognito_service.confirm_signup(email=request.email, code=request.code)

@router.post("/forgot-password")
def forgot_password(request: ForgotPasswordRequest):
    return cognito_service.forgot_password(email=request.email)

@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest):
    return cognito_service.confirm_forgot_password(
        email=request.email,
        code=request.code,
        new_password=request.new_password
    )

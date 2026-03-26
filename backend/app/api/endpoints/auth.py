from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from app.db.database import get_db
from app.db.models import User
from app.services.auth_service import (
    get_password_hash, 
    verify_password, 
    create_access_token,
    verify_institutional_email
)
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/api/auth_legacy", tags=["auth"])

class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    affiliation: str

class Token(BaseModel):
    access_token: str
    token_type: str

@router.post("/signup", response_model=Token)
async def signup(user_in: UserCreate, db: Session = Depends(get_db)):
    # 1. Institutional Verification (Cybersecurity enforced)
    if not await verify_institutional_email(user_in.email):
        raise HTTPException(
            status_code=400,
            detail="Registration restricted to valid academic or business email addresses."
        )
    
    # 2. Check existence
    existing_user = db.query(User).filter(User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists.")
    
    # 3. Create user with Argon2 hash
    user = User(
        full_name=user_in.full_name,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        affiliation=user_in.affiliation
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # 4. Return JWT
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
from app.config import settings

# Security configuration
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
ALGORITHM = "HS256"

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def verify_institutional_email(email: str) -> bool:
    """
    Validates if email belongs to an academic or business institution.
    Placeholder for ApyHub/Hunter API integration.
    """
    # Defensive check against public/temp providers
    disallowed = ["gmail.com", "outlook.com", "hotmail.com", "yahoo.com", "mailinator.com", "temp-mail.org"]
    domain = email.split("@")[-1].lower()
    if domain in disallowed:
        return False
    
    # In production, call ApyHub here
    return True

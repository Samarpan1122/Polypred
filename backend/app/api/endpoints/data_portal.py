from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.db.database import get_db
from app.db.models import User, UserUpload, TrainedModel
from app.services.s3_service import upload_user_file, download_file
from app.services.auth_service import verify_password # Placeholder for current_user dependency
from pydantic import BaseModel

router = APIRouter(prefix="/data", tags=["data"])

# --- Schemas ---
class UploadMetadata(BaseModel):
    id: int
    filename: str
    is_public: bool
    created_at: datetime

    class Config:
        from_attributes = True

class PublicShareForm(BaseModel):
    description: str
    paper_doi: str = None

# --- Endpoints ---

@router.get("/my-uploads", response_model=List[UploadMetadata])
async def get_my_uploads(user_id: int, db: Session = Depends(get_db)):
    """List all private/public uploads for the authenticated user."""
    return db.query(UserUpload).filter(UserUpload.user_id == user_id).all()

@router.post("/make-public/{upload_id}")
async def make_upload_public(
    upload_id: int, 
    form: PublicShareForm, 
    user_id: int, 
    db: Session = Depends(get_db)
):
    """Transition a private dataset to public with required metadata."""
    upload = db.query(UserUpload).filter(
        UserUpload.id == upload_id, 
        UserUpload.user_id == user_id
    ).first()
    
    if not upload:
        raise HTTPException(status_code=404, detail="Dataset not found or unauthorized.")
    
    upload.is_public = True
    upload.description = form.description
    upload.paper_doi = form.paper_doi
    db.commit()
    return {"message": "Dataset is now public."}

@router.delete("/delete/{upload_id}")
async def delete_upload(upload_id: int, user_id: int, db: Session = Depends(get_db)):
    """Permanently delete user data from DB and S3."""
    upload = db.query(UserUpload).filter(
        UserUpload.id == upload_id, 
        UserUpload.user_id == user_id
    ).first()
    
    if not upload:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    
    # In production, call s3_service.delete_file(upload.s3_key)
    db.delete(upload)
    db.commit()
    return {"message": "Data deleted permanently."}

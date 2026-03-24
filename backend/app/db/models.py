from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    affiliation = Column(String(255), nullable=False)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    uploads = relationship("UserUpload", back_populates="owner")
    models = relationship("TrainedModel", back_populates="owner")

class UserUpload(Base):
    __tablename__ = "user_uploads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    filename = Column(String(255), nullable=False)
    s3_key = Column(String(512), unique=True, nullable=False)  # Encrypted at rest in S3
    is_public = Column(Boolean, default=False)
    
    # Metadata for public sharing
    description = Column(Text, nullable=True)
    paper_doi = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="uploads")

class TrainedModel(Base):
    __tablename__ = "trained_models"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    model_name = Column(String(255), nullable=False)
    s3_key = Column(String(512), unique=True, nullable=False) # weights encrypted in S3
    metrics_json = Column(Text, nullable=True) # JSON dump of training results
    is_public = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="models")
